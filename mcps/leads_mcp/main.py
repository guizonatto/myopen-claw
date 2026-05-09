from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape as html_unescape
from typing import Any, AsyncGenerator
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import HTTPError, URLError

import json
import logging
import os
import re
import sys
import threading
import time
from pathlib import Path

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
_STATE_LOCK = threading.Lock()
_SEARCH_PLAN_VERSION = "v1"


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
    source: str | None = None
    query: str | None = None


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


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path() -> Path:
    return Path(os.environ.get("LEADS_STATE_PATH", "/tmp/leads_hybrid_state.json"))


def _load_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {"plans": {}, "history": {}, "optimizer_failures": {}, "short_memory": {}, "long_memory": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Falha ao ler estado de leads; reiniciando estado vazio.")
        return {"plans": {}, "history": {}, "optimizer_failures": {}, "short_memory": {}, "long_memory": {}}


def _save_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _baseline_queries(city: str, max_results: int) -> list[dict[str, Any]]:
    base = [
        f"síndico profissional {city} contato whatsapp email",
        f"administradora de condomínios {city} síndico telefone",
        f"consultoria condominial {city} contato",
    ]
    queries: list[dict[str, Any]] = []
    for i, text in enumerate(base, start=1):
        queries.append(
            {
                "id": f"baseline_{i}",
                "text": text,
                "priority": float(len(base) - i + 1),
                "source": "tavily",
                "city": city,
                "segment": "sindico",
                "max_results": int(max_results),
                "enabled": True,
            }
        )
    return queries


def _build_baseline_plan(*, tenant_id: str, city: str, max_results: int) -> dict[str, Any]:
    return {
        "version": _SEARCH_PLAN_VERSION,
        "tenant_id": tenant_id,
        "generated_at": _utcnow_iso(),
        "valid_until": None,
        "queries": _baseline_queries(city, max_results),
        "dedupe_policy": {"prefer": ["email", "whatsapp", "telefone"], "global_unique": True},
        "limits": {"max_results": int(max_results), "max_queries": 6},
        "meta": {"origin": "baseline", "fallback_reason": None},
    }


def _latest_plan_for_tenant(state: dict[str, Any], tenant_id: str) -> dict[str, Any] | None:
    plan = (state.get("plans") or {}).get(tenant_id)
    if not isinstance(plan, dict):
        return None
    return plan


def _record_history(
    state: dict[str, Any],
    *,
    tenant_id: str,
    outcome: dict[str, Any],
    plan_meta: dict[str, Any],
) -> None:
    history = state.setdefault("history", {})
    tenant_hist = history.setdefault(tenant_id, [])
    tenant_hist.append(
        {
            "recorded_at": _utcnow_iso(),
            "outcome": outcome,
            "plan_meta": plan_meta,
        }
    )
    # guarda apenas últimas 100 execuções por tenant
    if len(tenant_hist) > 100:
        del tenant_hist[:-100]


def _update_short_memory(state: dict[str, Any], *, tenant_id: str, outcome: dict[str, Any]) -> None:
    short_mem = state.setdefault("short_memory", {})
    tenant_short = short_mem.setdefault(tenant_id, [])
    tenant_short.append(
        {
            "recorded_at": _utcnow_iso(),
            "new": int(outcome.get("new", 0) or 0),
            "updated": int(outcome.get("updated", 0) or 0),
            "divergences": int(outcome.get("divergences", 0) or 0),
            "upsert_failed": int(outcome.get("upsert_failed", 0) or 0),
            "leads_discovered": int(outcome.get("leads_discovered", 0) or 0),
            "query_metrics": outcome.get("query_metrics", []),
        }
    )
    if len(tenant_short) > 30:
        del tenant_short[:-30]


def _derive_long_term_lessons(*, outcome: dict[str, Any]) -> list[dict[str, Any]]:
    lessons: list[dict[str, Any]] = []
    metrics = [m for m in (outcome.get("query_metrics") or []) if isinstance(m, dict)]

    for m in metrics:
        qid = str(m.get("query_id") or "unknown")
        discovered = int(m.get("discovered", 0) or 0)
        updated = int(m.get("updated", 0) or 0)
        new = int(m.get("new", 0) or 0)
        dup_rate = float(m.get("dup_rate", 0.0) or 0.0)
        source = str(m.get("source") or "unknown")
        score = new + updated
        if score > 0:
            lessons.append(
                {
                    "kind": "effective_query",
                    "query_id": qid,
                    "source": source,
                    "score": score,
                    "dup_rate": dup_rate,
                    "summary": f"{qid} performou bem (new={new}, updated={updated}, dup_rate={dup_rate:.2f})",
                }
            )
        if discovered > 0 and dup_rate >= 0.5:
            lessons.append(
                {
                    "kind": "high_duplicate_query",
                    "query_id": qid,
                    "source": source,
                    "dup_rate": dup_rate,
                    "summary": f"{qid} gerou muitos duplicados (dup_rate={dup_rate:.2f})",
                }
            )

    if int(outcome.get("upsert_failed", 0) or 0) > 0:
        lessons.append(
            {
                "kind": "persistence_risk",
                "reasons": outcome.get("upsert_failure_reasons", {}),
                "summary": "Houve falhas de persistência no CRM; evitar repetir execução sem corrigir integração.",
            }
        )

    return lessons


def _update_long_memory(state: dict[str, Any], *, tenant_id: str, outcome: dict[str, Any]) -> list[dict[str, Any]]:
    long_mem = state.setdefault("long_memory", {})
    tenant_long = long_mem.setdefault(tenant_id, [])
    new_lessons = _derive_long_term_lessons(outcome=outcome)
    for lesson in new_lessons:
        tenant_long.append(
            {
                "recorded_at": _utcnow_iso(),
                "lesson": lesson,
            }
        )
    if len(tenant_long) > 200:
        del tenant_long[:-200]
    return new_lessons


def _sync_lessons_to_memclaw(*, tenant_id: str, lessons: list[dict[str, Any]], outcome: dict[str, Any]) -> None:
    if not lessons:
        return
    base = (os.environ.get("CORTEX_MEM_URL") or "").strip()
    if not base:
        return
    endpoint = os.environ.get("LEADS_MEMCLAW_SYNC_URL") or f"{base.rstrip('/')}/memory/ingest"
    token = (os.environ.get("LEADS_MEMCLAW_SYNC_TOKEN") or "").strip()
    payload = {
        "tenant_id": tenant_id,
        "source": "mcp-leads",
        "kind": "lead_engine_lessons",
        "lessons": lessons,
        "context": {
            "city": outcome.get("city"),
            "max_results": outcome.get("max_results"),
            "new": outcome.get("new"),
            "updated": outcome.get("updated"),
            "divergences": outcome.get("divergences"),
        },
        "recorded_at": _utcnow_iso(),
    }
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = UrlRequest(endpoint, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(req, timeout=8) as resp:
            _ = resp.read(200_000)
    except Exception as exc:
        logger.info("MemClaw sync best-effort falhou (não bloqueante): %s", exc.__class__.__name__)


def _increment_optimizer_failure(state: dict[str, Any], tenant_id: str, reason: str) -> int:
    failures = state.setdefault("optimizer_failures", {})
    tenant = failures.setdefault(tenant_id, {"count": 0, "last_reason": None, "updated_at": None})
    tenant["count"] = int(tenant.get("count", 0)) + 1
    tenant["last_reason"] = reason
    tenant["updated_at"] = _utcnow_iso()
    return int(tenant["count"])


def _reset_optimizer_failure(state: dict[str, Any], tenant_id: str) -> None:
    failures = state.setdefault("optimizer_failures", {})
    failures[tenant_id] = {"count": 0, "last_reason": None, "updated_at": _utcnow_iso()}


def _heuristic_optimize_plan(
    *,
    tenant_id: str,
    previous_plan: dict[str, Any],
    outcome: dict[str, Any],
) -> dict[str, Any]:
    queries = list(previous_plan.get("queries") or [])
    metrics = {m.get("query_id"): m for m in outcome.get("query_metrics", []) if isinstance(m, dict)}

    kept: list[dict[str, Any]] = []
    for q in queries:
        qid = q.get("id")
        metric = metrics.get(qid, {})
        dup = float(metric.get("dup_rate", 0.0) or 0.0)
        discovered = int(metric.get("discovered", 0) or 0)
        if discovered == 0 and dup > 0.8:
            continue
        kept.append(dict(q))

    # nunca remover 100% do baseline
    if not kept:
        kept = _baseline_queries(
            city=(outcome.get("city") or "São Paulo"),
            max_results=int(outcome.get("max_results") or 20),
        )

    # variação controlada (até 30%)
    max_new = max(1, int(len(kept) * 0.3))
    city = (outcome.get("city") or "São Paulo").strip()
    new_queries = [
        f"síndico autônomo {city} contato",
        f"síndico profissional {city} condomínio telefone",
        f"gestão condominial {city} contato whatsapp",
    ][:max_new]

    next_id = 1
    existing_ids = {str(item.get("id") or "") for item in kept}
    additions: list[dict[str, Any]] = []
    for text in new_queries:
        candidate_id = f"opt_{next_id}"
        while candidate_id in existing_ids:
            next_id += 1
            candidate_id = f"opt_{next_id}"
        existing_ids.add(candidate_id)
        additions.append(
            {
                "id": candidate_id,
                "text": text,
                "priority": 0.9,
                "source": "tavily",
                "city": city,
                "segment": "sindico",
                "max_results": int(outcome.get("max_results") or 20),
                "enabled": True,
            }
        )
        next_id += 1

    optimized = kept + additions
    return {
        "version": _SEARCH_PLAN_VERSION,
        "tenant_id": tenant_id,
        "generated_at": _utcnow_iso(),
        "valid_until": None,
        "queries": optimized,
        "dedupe_policy": previous_plan.get("dedupe_policy") or {"prefer": ["email", "whatsapp", "telefone"], "global_unique": True},
        "limits": previous_plan.get("limits") or {"max_results": int(outcome.get("max_results") or 20), "max_queries": 6},
        "meta": {"origin": "optimized", "fallback_reason": None},
    }


def _build_search_plan(
    *,
    tenant_id: str,
    city: str,
    max_results: int,
    previous_plan: dict[str, Any] | None,
    outcome: dict[str, Any],
) -> dict[str, Any]:
    timeout_s = float(os.environ.get("LEADS_OPTIMIZER_TIMEOUT_S", "3"))
    mode = (os.environ.get("LEADS_OPTIMIZER_MODE", "heuristic") or "heuristic").strip().lower()
    if mode not in {"heuristic"}:
        # placeholder explícito: fallback para heurística.
        logger.info("Optimizer mode '%s' não suportado no runtime atual, usando heurística.", mode)
    _ = timeout_s  # reservado para implementação de modo LLM com timeout curto.
    base_plan = previous_plan or _build_baseline_plan(tenant_id=tenant_id, city=city, max_results=max_results)
    return _heuristic_optimize_plan(tenant_id=tenant_id, previous_plan=base_plan, outcome=outcome)


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


def _tavily_search(query: str, *, max_results: int) -> list[dict[str, str]]:
    api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY não configurada")

    payload = {
        "query": query,
        "max_results": max(1, min(int(max_results), 20)),
        "search_depth": "basic",
        "include_raw_content": False,
    }
    req = UrlRequest(
        "https://api.tavily.com/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urlopen(req, timeout=25) as resp:
        body = resp.read(600_000).decode("utf-8", errors="replace")

    parsed = json.loads(body)
    rows = parsed.get("results") or []
    hits: list[dict[str, str]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        hits.append({"url": url, "title": str(item.get("title") or "").strip()})
        if len(hits) >= max_results:
            break
    return hits


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
    attempts = int(os.environ.get("LEADS_CRM_RETRIES", "3"))
    last_exc: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        req = UrlRequest(
            crm_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key,
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=20) as resp:
                raw = resp.read(2_000_000)
            return json.loads(raw.decode("utf-8", errors="replace"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_exc = exc
            if attempt < max(1, attempts):
                time.sleep(min(0.5 * attempt, 2.0))
                continue
            break
    raise RuntimeError(f"crm_execute_failed:{last_exc.__class__.__name__ if last_exc else 'unknown'}")


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


def _collect_query_leads(query_cfg: dict[str, Any], *, max_scan_results: int) -> list[DiscoveredLead]:
    query = str(query_cfg.get("text") or "").strip()
    source = str(query_cfg.get("source") or "tavily").strip()
    query_id = str(query_cfg.get("id") or query)
    if not query:
        return []
    if source == "tavily":
        try:
            search_hits = _tavily_search(query, max_results=max_scan_results)
        except Exception as exc:
            logger.warning("Tavily indisponível para query '%s'; fallback duckduckgo_lite (%s)", query_id, exc.__class__.__name__)
            source = "duckduckgo_lite"
            search_hits = _ddg_lite_search(query, max_results=max_scan_results)
    elif source == "duckduckgo_lite":
        search_hits = _ddg_lite_search(query, max_results=max_scan_results)
    else:
        logger.warning("Fonte de busca não suportada para leads: %s", source)
        return []
    seen_local: set[str] = set()
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
        if identifier and identifier in seen_local:
            continue
        if identifier:
            seen_local.add(identifier)
        title = _extract_title(page) or hit.get("title") or ""
        name = title.strip() or urlparse(url).netloc
        discovered.append(
            DiscoveredLead(
                name=name[:120],
                email=email,
                telefone=telefone,
                whatsapp=whatsapp,
                source_url=url,
                source=source,
                query=query_id,
            )
        )
    return discovered


def run_sindico_leads(params: dict[str, Any]) -> dict[str, Any]:
    max_results = int(params.get("max_results") or 20)
    city = (params.get("city") or "São Paulo").strip()
    tenant_id = (params.get("tenant_id") or os.environ.get("LEADS_TENANT_ID") or "default").strip()
    optimizer_alert_threshold = int(os.environ.get("LEADS_OPTIMIZER_ALERT_THRESHOLD", "3"))

    started_at = datetime.now(timezone.utc)

    with _STATE_LOCK:
        state = _load_state()
        previous_plan = _latest_plan_for_tenant(state, tenant_id)
        active_plan = previous_plan or _build_baseline_plan(tenant_id=tenant_id, city=city, max_results=max_results)
        active_plan_meta = dict(active_plan.get("meta") or {})
        active_plan_meta.setdefault("origin", "baseline")
        active_plan_meta.setdefault("fallback_reason", None)

    queries = [q for q in (active_plan.get("queries") or []) if isinstance(q, dict) and q.get("enabled", True)]
    max_queries = int((active_plan.get("limits") or {}).get("max_queries", 6))
    if max_queries > 0:
        queries = queries[:max_queries]

    global_seen: set[str] = set()
    collected: list[DiscoveredLead] = []
    query_metrics: list[dict[str, Any]] = []

    collector_started = datetime.now(timezone.utc)
    for query_cfg in queries:
        query_id = str(query_cfg.get("id") or "unknown")
        query_text = str(query_cfg.get("text") or "")
        max_scan_results = min(int(query_cfg.get("max_results") or max_results) * 3, 40)
        raw = _collect_query_leads(query_cfg, max_scan_results=max_scan_results)
        deduped_for_query: list[DiscoveredLead] = []
        dup_count = 0
        for lead in raw:
            identifier = (lead.email or lead.whatsapp or lead.telefone or "").lower()
            if identifier and identifier in global_seen:
                dup_count += 1
                continue
            if identifier:
                global_seen.add(identifier)
            deduped_for_query.append(lead)

        if deduped_for_query:
            collected.extend(deduped_for_query)
        query_metrics.append(
            {
                "query_id": query_id,
                "query": query_text,
                "source": query_cfg.get("source", "tavily"),
                "discovered": len(raw),
                "deduped_kept": len(deduped_for_query),
                "dup_count": dup_count,
                "dup_rate": round((dup_count / max(1, len(raw))), 4),
                "wpp_rate": round((sum(1 for item in deduped_for_query if item.whatsapp) / max(1, len(deduped_for_query))), 4),
                "new": 0,
                "updated": 0,
            }
        )
        if len(collected) >= max_results:
            collected = collected[:max_results]
            break

    collector_finished = datetime.now(timezone.utc)

    new_count = 0
    updated_count = 0
    divergence_count = 0
    upsert_failed_count = 0
    upsert_failure_reasons: dict[str, int] = {}
    query_metric_map = {m["query_id"]: m for m in query_metrics}

    for lead in collected:
        try:
            _, created, divergence = _upsert_lead_into_crm(lead)
        except Exception as exc:
            logger.warning("Falha ao upsert lead (sem PII): %s", exc)
            upsert_failed_count += 1
            reason = exc.__class__.__name__
            upsert_failure_reasons[reason] = int(upsert_failure_reasons.get(reason, 0)) + 1
            continue
        if created:
            new_count += 1
            if lead.query in query_metric_map:
                query_metric_map[lead.query]["new"] += 1
        else:
            updated_count += 1
            if lead.query in query_metric_map:
                query_metric_map[lead.query]["updated"] += 1
        if divergence:
            divergence_count += 1

    outcome: dict[str, Any] = {
        "operation": "sindico_leads",
        "tenant_id": tenant_id,
        "city": city,
        "max_results": max_results,
        "leads_discovered": len(collected),
        "new": new_count,
        "updated": updated_count,
        "divergences": divergence_count,
        "upsert_failed": upsert_failed_count,
        "upsert_failure_reasons": upsert_failure_reasons,
        "query_metrics": query_metrics,
        "ran_at": _utcnow_iso(),
    }

    optimizer_started = datetime.now(timezone.utc)
    optimizer_status = "ok"
    fallback_reason = None
    next_plan = None
    alert = None

    with _STATE_LOCK:
        state = _load_state()
        previous_plan = _latest_plan_for_tenant(state, tenant_id)
        try:
            next_plan = _build_search_plan(
                tenant_id=tenant_id,
                city=city,
                max_results=max_results,
                previous_plan=previous_plan,
                outcome=outcome,
            )
            (state.setdefault("plans", {}))[tenant_id] = next_plan
            _reset_optimizer_failure(state, tenant_id)
        except Exception as exc:
            optimizer_status = "fallback"
            fallback_reason = f"optimizer_failure:{exc.__class__.__name__}"
            fail_count = _increment_optimizer_failure(state, tenant_id, fallback_reason)
            next_plan = previous_plan or _build_baseline_plan(tenant_id=tenant_id, city=city, max_results=max_results)
            if isinstance(next_plan, dict):
                meta = dict(next_plan.get("meta") or {})
                meta["origin"] = meta.get("origin") or "baseline"
                meta["fallback_reason"] = fallback_reason
                next_plan["meta"] = meta
                (state.setdefault("plans", {}))[tenant_id] = next_plan
            if fail_count >= optimizer_alert_threshold:
                alert = {
                    "kind": "optimizer_consecutive_failures",
                    "tenant_id": tenant_id,
                    "count": fail_count,
                    "threshold": optimizer_alert_threshold,
                    "reason": fallback_reason,
                }

        plan_meta = dict((next_plan or {}).get("meta") or {})
        _record_history(
            state,
            tenant_id=tenant_id,
            outcome=outcome,
            plan_meta=plan_meta,
        )
        _update_short_memory(state, tenant_id=tenant_id, outcome=outcome)
        learned = _update_long_memory(state, tenant_id=tenant_id, outcome=outcome)
        _save_state(state)

    _sync_lessons_to_memclaw(tenant_id=tenant_id, lessons=learned, outcome=outcome)

    optimizer_finished = datetime.now(timezone.utc)

    timings = {
        "collector_ms": int((collector_finished - collector_started).total_seconds() * 1000),
        "optimizer_ms": int((optimizer_finished - optimizer_started).total_seconds() * 1000),
        "total_ms": int((optimizer_finished - started_at).total_seconds() * 1000),
    }

    persisted_count = new_count + updated_count
    persistence_failure = len(collected) > 0 and persisted_count == 0 and upsert_failed_count > 0
    success = not persistence_failure
    outcome.update(
        {
            "query": (queries[0].get("text") if queries else f"síndico profissional {city} contato whatsapp email"),
            "search_plan": {
                "version": _SEARCH_PLAN_VERSION,
                "tenant_id": tenant_id,
                "generated_at": (next_plan or {}).get("generated_at"),
                "valid_until": (next_plan or {}).get("valid_until"),
                "queries": (next_plan or {}).get("queries", []),
                "meta": {
                    "origin": ((next_plan or {}).get("meta") or {}).get("origin", active_plan_meta.get("origin", "baseline")),
                    "fallback_reason": ((next_plan or {}).get("meta") or {}).get("fallback_reason", fallback_reason),
                },
            },
            "optimizer_status": optimizer_status,
            "fallback_reason": fallback_reason,
            "observability": {
                "timings": timings,
                "execution_complete": bool(success),
                "execution_complete_rate": 1.0 if success else 0.0,
                "persisted_count": persisted_count,
            },
        }
    )
    if persistence_failure:
        outcome["alert"] = {
            "kind": "lead_persistence_failure",
            "tenant_id": tenant_id,
            "discovered": len(collected),
            "persisted": persisted_count,
            "upsert_failed": upsert_failed_count,
            "reasons": upsert_failure_reasons,
        }
    if alert:
        existing_alert = outcome.get("alert")
        if existing_alert:
            outcome["alerts"] = [existing_alert, alert]
            outcome.pop("alert", None)
        else:
            outcome["alert"] = alert
    return outcome


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
