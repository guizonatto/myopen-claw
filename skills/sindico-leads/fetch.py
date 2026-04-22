"""
Skill: sindico-leads/fetch
Função: Busca síndicos profissionais via web_search + crawl de páginas de resultado.
Usar quando: agente precisa buscar leads de síndicos profissionais.

Estratégia:
  1. Tavily web_search com queries definidas em sindico_leads.yaml
  2. Crawl das URLs retornadas para extrair contatos (nome, telefone, WhatsApp)

ENV_VARS:
  - TAVILY_API_KEY: chave da API Tavily (obrigatória)

DB_TABLES:
  (nenhuma)
"""
import os
import re
from typing import Any

FONTES = ["sindico_leads"]

_QUERIES = [
    "síndico profissional São Paulo telefone celular",
    "síndico profissional SP whatsapp contato",
    "administradora condomínios SP síndico contato celular",
]

_PHONE_RE = re.compile(r"(?:\+55\s?)?(?:\(?\d{2}\)?\s?)(?:9\s?)?\d{4}[-.\s]?\d{4}")
_WPP_RE = re.compile(r"(?:whatsapp|wpp|zap)[^\d]*(\(?\d{2}\)?\s?9?\s?\d{4}[-.\s]?\d{4})", re.I)


def run(
    fonte: str = "sindico_leads",
    cidade: str = "São Paulo",
    max_results: int = 20,
) -> list[dict[str, Any]]:
    if fonte not in FONTES:
        raise ValueError(f"Fonte desconhecida: {fonte!r}. Disponíveis: {FONTES}")

    leads = _sindico_leads(cidade, max_results)

    for lead in leads:
        lead["origem"] = fonte

    return leads


# ── implementação ─────────────────────────────────────────────────────────

def _sindico_leads(cidade: str, max_results: int) -> list[dict[str, Any]]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY não configurada.")

    resultados: list[dict] = []
    seen_urls: set[str] = set()

    for query in _QUERIES:
        if len(resultados) >= max_results:
            break
        q = query if cidade == "São Paulo" else query.replace("São Paulo", cidade).replace("SP", cidade)
        hits = _tavily_search(api_key, q, max_results=10)
        for hit in hits:
            url = hit.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            leads = _extrair_leads_de_hit(hit)
            resultados.extend(leads)

    return resultados[:max_results]


def _tavily_search(api_key: str, query: str, max_results: int = 10) -> list[dict]:
    import urllib.request, json
    payload = json.dumps({
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "include_raw_content": True,
    }).encode()
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return data.get("results", [])


def _extrair_leads_de_hit(hit: dict) -> list[dict]:
    """Extrai contatos do resultado Tavily (snippet + raw_content)."""
    texto = " ".join(filter(None, [
        hit.get("title", ""),
        hit.get("content", ""),
        hit.get("raw_content", ""),
    ]))

    telefones = list(dict.fromkeys(_PHONE_RE.findall(texto)))
    wpp_matches = list(dict.fromkeys(_WPP_RE.findall(texto)))

    if not telefones and not wpp_matches:
        return []

    nome = _extrair_nome(hit.get("title", ""), hit.get("url", ""))
    fone = _normalizar_fone(telefones[0]) if telefones else None
    wpp = _normalizar_fone(wpp_matches[0]) if wpp_matches else fone

    return [{
        "nome": nome,
        "telefone": fone,
        "whatsapp": wpp,
        "email": None,
        "empresa": None,
        "setor": "condomínios",
        "cnae": None,
        "fonte_url": hit.get("url"),
    }]


def _extrair_nome(title: str, url: str) -> str:
    for token in title.split("|"):
        token = token.strip()
        if len(token) > 4:
            return token
    return url.split("/")[2] if url else "Desconhecido"


def _normalizar_fone(fone: str) -> str:
    digits = re.sub(r"\D", "", fone)
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return fone


if __name__ == "__main__":
    leads = run()
    wpp = sum(1 for l in leads if l.get("whatsapp"))
    print(f"sindico_leads: {len(leads)} leads, {wpp} com WhatsApp")
    for l in leads[:3]:
        print(" ", l)
