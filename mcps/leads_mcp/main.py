from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape as html_unescape
from typing import Any, AsyncGenerator
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request as UrlRequest, urlopen

import json
import logging
import os
import re
import sys

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from .auth import verify_api_key
except ImportError:  # pragma: no cover
    from auth import verify_api_key

app = FastAPI()

# Configuração de log para stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-leads")


@app.get("/health")
def health():
    return {"status": "ok"}


class SkillRequest(BaseModel):
    operation: str
    params: dict[str, Any]


@dataclass(frozen=True)
class DiscoveredLead:
    name: str
    email: str | None = None
    telefone: str | None = None
    whatsapp: str | None = None
    linkedin: str | None = None
    instagram: str | None = None
    empresa: str | None = None
    cargo: str | None = None
    setor: str | None = None
    source_url: str | None = None


_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}")
_WHATSAPP_LINK_RE = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\d{10,15})", re.I)
_PHONE_RE = re.compile(r"(?:\+?55\s*)?\(?\d{2}\)?\s*9?\d{4}[-\s]?\d{4}")


def _norm_digits(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\D+", "", value)


def _normalize_br_phone(raw: str | None) -> str | None:
    digits = _norm_digits(raw)
    if not digits:
        return None
    digits = digits.lstrip("0")
    if digits.startswith("55") and 12 <= len(digits) <= 13:
        return f"+{digits}"
    if len(digits) in {10, 11}:
        return f"+55{digits}"
    return f"+{digits}" if digits.startswith("+") else digits


def _http_get_text(url: str, *, timeout_s: int = 20, max_bytes: int = 250_000) -> str:
    req = UrlRequest(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout_s) as resp:
        data = resp.read(max_bytes)
        return data.decode("utf-8", errors="replace")


def _resolve_duckduckgo_href(href: str) -> str:
    if href.startswith("//"):
        href = f"https:{href}"
    if href.startswith("/"):
        href = f"https://duckduckgo.com{href}"
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        uddg = qs.get("uddg", [None])[0]
        if uddg:
            return unquote(uddg)
    return href


def _ddg_lite_search(query: str, *, max_results: int) -> list[dict[str, str]]:
    url = f"https://lite.duckduckgo.com/lite/?q={quote(query)}"
    html = _http_get_text(url, timeout_s=20, max_bytes=400_000)
    href_pattern = re.compile(
        r"<a rel=\"nofollow\" href=\"(?P<href>[^\"]+)\" class='result-link'>(?P<title>.*?)</a>",
        re.I,
    )

    results: list[dict[str, str]] = []
    for match in href_pattern.finditer(html):
        href = _resolve_duckduckgo_href(match.group("href"))
        title = re.sub(r"<.*?>", "", match.group("title"))
        title = html_unescape(title).strip()
        if not href.startswith("http"):
            continue
        results.append({"url": href, "title": title})
        if len(results) >= max_results:
            break
    return results


def _extract_from_html(html: str) -> dict[str, list[str]]:
    emails = sorted({m.group(0) for m in _EMAIL_RE.finditer(html)})
    whatsapp_numbers = sorted({m.group(1) for m in _WHATSAPP_LINK_RE.finditer(html)})
    phones = sorted({m.group(0) for m in _PHONE_RE.finditer(html)})
    return {"emails": emails, "whatsapp": whatsapp_numbers, "phones": phones}


def _extract_title(html: str) -> str | None:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if not m:
        return None
    title = re.sub(r"\s+", " ", re.sub(r"<.*?>", "", m.group(1))).strip()
    title = html_unescape(title)
    return title[:160] if title else None


def _crm_execute(payload: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ.get("MCP_API_KEY", "")
    if not api_key:
        raise RuntimeError("MCP_API_KEY não configurada no mcp-leads")

    crm_url = os.environ.get("CRM_EXECUTE_URL", "http://mcp-crm:8001/execute")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = UrlRequest(
        crm_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
        method="POST",
    )
    with urlopen(req, timeout=20) as resp:
        raw = resp.read(2_000_000)
    return json.loads(raw.decode("utf-8", errors="replace"))


def _find_exact_match(contacts: list[dict[str, Any]], lead: DiscoveredLead) -> dict[str, Any] | None:
    email = (lead.email or "").strip().lower()
    whatsapp = _norm_digits(lead.whatsapp)
    telefone = _norm_digits(lead.telefone)

    for c in contacts:
        if email and (c.get("email") or "").strip().lower() == email:
            return c
        if whatsapp and _norm_digits(c.get("whatsapp")) == whatsapp:
            return c
        if telefone and _norm_digits(c.get("telefone")) == telefone:
            return c
    return contacts[0] if contacts else None


def _upsert_lead_into_crm(lead: DiscoveredLead) -> tuple[str, bool, bool]:
    """Return (contact_id, created, divergence)."""
    candidates: list[str] = []
    if lead.email:
        candidates.append(lead.email)
    if lead.whatsapp:
        candidates.append(lead.whatsapp)
    if lead.telefone:
        candidates.append(lead.telefone)
    if not candidates:
        candidates.append(lead.name)

    found: dict[str, Any] | None = None
    for q in candidates:
        resp = _crm_execute({"operation": "search_contact", "query": q})
        contacts = resp.get("result") or []
        if isinstance(contacts, list) and contacts:
            found = _find_exact_match(contacts, lead)
            break

    note = f"Lead enrichment (sindico_leads) — fonte: {lead.source_url or '-'}"

    if not found:
        add_payload: dict[str, Any] = {
            "operation": "add_contact",
            "nome": lead.name,
            "tipo": "lead",
            "email": lead.email,
            "telefone": lead.telefone,
            "whatsapp": lead.whatsapp,
            "linkedin": lead.linkedin,
            "instagram": lead.instagram,
            "empresa": lead.empresa,
            "cargo": lead.cargo,
            "setor": lead.setor,
            "nota": note,
        }
        created = _crm_execute(add_payload)
        contact_id = created.get("id") or ""
        return contact_id, True, False

    contact_id = str(found.get("id") or "")
    divergence = False
    if lead.email and found.get("email") and found.get("email") != lead.email:
        divergence = True
    if lead.whatsapp and found.get("whatsapp") and _norm_digits(found.get("whatsapp")) != _norm_digits(lead.whatsapp):
        divergence = True
    if lead.telefone and found.get("telefone") and _norm_digits(found.get("telefone")) != _norm_digits(lead.telefone):
        divergence = True
    if lead.empresa and found.get("empresa") and found.get("empresa") != lead.empresa:
        divergence = True

    update_payload: dict[str, Any] = {
        "operation": "update_contact",
        "contact_id": contact_id,
        "nota": note,
    }
    if lead.email and not found.get("email"):
        update_payload["email"] = lead.email
    if lead.telefone and not found.get("telefone"):
        update_payload["telefone"] = lead.telefone
    if lead.whatsapp and not found.get("whatsapp"):
        update_payload["whatsapp"] = lead.whatsapp
    if lead.empresa and not found.get("empresa"):
        update_payload["empresa"] = lead.empresa
    if lead.cargo and not found.get("cargo"):
        update_payload["cargo"] = lead.cargo
    if lead.setor and not found.get("setor"):
        update_payload["setor"] = lead.setor
    if lead.linkedin and not found.get("linkedin"):
        update_payload["linkedin"] = lead.linkedin
    if lead.instagram and not found.get("instagram"):
        update_payload["instagram"] = lead.instagram
    if found.get("tipo") != "lead":
        update_payload["tipo"] = found.get("tipo") or "lead"

    _crm_execute(update_payload)
    return contact_id, False, divergence


def run_sindico_leads(params: dict[str, Any]) -> dict[str, Any]:
    max_results = int(params.get("max_results") or 20)
    city = (params.get("city") or "São Paulo").strip()
    query = (params.get("query") or f"síndico profissional {city} contato whatsapp email").strip()

    search_hits = _ddg_lite_search(query, max_results=min(max_results * 3, 40))
    seen: set[str] = set()
    discovered: list[DiscoveredLead] = []

    for hit in search_hits:
        url = hit.get("url") or ""
        if not url:
            continue
        try:
            page = _http_get_text(url, timeout_s=20, max_bytes=350_000)
        except Exception:
            continue

        extracted = _extract_from_html(page)
        email = extracted["emails"][0] if extracted["emails"] else None
        whatsapp = _normalize_br_phone(extracted["whatsapp"][0]) if extracted["whatsapp"] else None
        telefone = _normalize_br_phone(extracted["phones"][0]) if extracted["phones"] else None

        if not (email or whatsapp or telefone):
            continue

        identifier = (email or whatsapp or telefone or "").lower()
        if identifier and identifier in seen:
            continue
        if identifier:
            seen.add(identifier)

        title = _extract_title(page) or hit.get("title") or ""
        name = title.strip() or urlparse(url).netloc

        discovered.append(
            DiscoveredLead(
                name=name[:120],
                email=email,
                telefone=telefone,
                whatsapp=whatsapp,
                source_url=url,
            )
        )
        if len(discovered) >= max_results:
            break

    new_count = 0
    updated_count = 0
    divergence_count = 0

    for lead in discovered:
        try:
            _, created, divergence = _upsert_lead_into_crm(lead)
        except Exception as exc:
            logger.warning("Falha ao upsert lead (sem PII): %s", exc)
            continue

        if created:
            new_count += 1
        else:
            updated_count += 1
        if divergence:
            divergence_count += 1

    return {
        "operation": "sindico_leads",
        "query": query,
        "city": city,
        "leads_discovered": len(discovered),
        "new": new_count,
        "updated": updated_count,
        "divergences": divergence_count,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


def run_operation(operation: str, params: dict[str, Any]) -> dict[str, Any]:
    if operation == "sindico_leads":
        return run_sindico_leads(params)
    return {"operation": operation, "result": f"Operação {operation} executada com params {params}"}


@app.post("/execute", dependencies=[Depends(verify_api_key)])
def execute_skill(req: SkillRequest):
    return {"result": run_operation(req.operation, req.params)}


async def sse_event_generator(operation: str, params: dict) -> AsyncGenerator[str, None]:
    try:
        yield f"data: {json.dumps({'status': 'started', 'operation': operation})}\n\n"
        import asyncio

        for i in range(3):
            await asyncio.sleep(1)
            yield f"data: {json.dumps({'progress': (i+1)*33, 'msg': f'Etapa {i+1}/3', 'operation': operation})}\n\n"
        result = f"Operação {operation} executada com params {params}"
        yield f"data: {json.dumps({'status': 'done', 'result': result})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"


@app.post("/sse", dependencies=[Depends(verify_api_key)])
async def sse_skill(req: SkillRequest, request: Request):
    async def event_stream():
        async for event in sse_event_generator(req.operation, req.params):
            if await request.is_disconnected():
                break
            yield event

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# MCP STDIO Support (import-safe fora do container)
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError:  # pragma: no cover
    async def main_mcp():
        raise RuntimeError("Dependência 'mcp' não encontrada. Instale mcp[stdio] para usar via STDIO.")
else:
    mcp_server = Server("mcp-leads")

    @mcp_server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="execute_lead_skill",
                description="Executa uma operação de prospecção de leads (ex: sindico_leads) e retorna um resumo.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string"},
                        "params": {"type": "object"},
                    },
                    "required": ["operation", "params"],
                },
            ),
            Tool(
                name="sindico_leads",
                description="Atalho: executa operation='sindico_leads' (busca e upsert de leads de síndicos) e retorna um resumo sem PII.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "max_results": {"type": "integer", "description": "Máximo de leads a processar (default: 20)."},
                        "city": {"type": "string", "description": "Cidade alvo (default: São Paulo)."},
                        "query": {"type": "string", "description": "Query de busca opcional."},
                    },
                    "required": [],
                },
            ),
        ]

    @mcp_server.call_tool()
    async def call_tool(name: str, arguments: dict):
        try:
            if name not in {"execute_lead_skill", "sindico_leads"}:
                raise ValueError(f"Tool not found: {name}")

            if name == "sindico_leads":
                params = arguments or {}
                if not isinstance(params, dict):
                    raise ValueError("arguments must be an object")
                result = run_sindico_leads(params)
                summary = f"Leads: {result['new']} novos, {result['updated']} atualizados, {result['divergences']} divergências."
                return [TextContent(type="text", text=summary)]

            operation = arguments.get("operation")
            params = arguments.get("params") or {}
            if not isinstance(params, dict):
                raise ValueError("params must be an object")

            result = run_operation(operation, params)
            if operation == "sindico_leads":
                summary = f"Leads: {result['new']} novos, {result['updated']} atualizados, {result['divergences']} divergências."
                return [TextContent(type="text", text=summary)]

            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
        except Exception as e:
            logger.error("Erro ao executar ferramenta %s: %s", name, e)
            return [TextContent(type="text", text=f"Erro interno: {str(e)}")]

    async def main_mcp():
        try:
            async with stdio_server() as (read_stream, write_stream):
                await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())
        except Exception as e:
            logger.error("Falha fatal no servidor MCP leads: %s", e, exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main_mcp())
