"""
Script: fetch_sindico_leads
Função: Executa busca de leads de síndicos via mcp-leads e imprime resumo sem PII.
Usar quando: cron lead_fetch_and_enrich (exec direto, sem depender de tool bundling MCP)

ENV_VARS:
  - (nenhuma — importa direto do mcp-leads container)
"""
import sys
import os

sys.path.insert(0, "/app/mcps/crm_mcp")

try:
    from mcps.crm_mcp.contatos import run_sindico_leads  # type: ignore
except ImportError:
    try:
        sys.path.insert(0, "/app")
        from mcps.crm_mcp.contatos import run_sindico_leads  # type: ignore
    except ImportError:
        # fallback: chama via docker exec no container mcp-leads
        import subprocess
        import json

        cmd = [
            "docker", "exec", "mcp-leads", "python3", "-c",
            "from main import run_sindico_leads; import json; "
            "r = run_sindico_leads({'max_results': 20}); "
            "print(json.dumps(r, ensure_ascii=False))"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        lines = [l for l in result.stdout.splitlines() if not l.startswith("WARNING")]
        if lines:
            r = json.loads(lines[-1])
            print(f"Leads descobertos: {r.get('leads_discovered', 0)} | "
                  f"Novos: {r.get('new', 0)} | Atualizados: {r.get('updated', 0)} | "
                  f"Cidade: {r.get('city', 'SP')}")
        else:
            print(f"Erro: {result.stderr[:200]}")
        sys.exit(0)


def main():
    tenant_id = os.environ.get("LEADS_TENANT_ID", "default")
    city = os.environ.get("LEADS_CITY", "São Paulo")
    r = run_sindico_leads({"max_results": 20, "tenant_id": tenant_id, "city": city})
    print(f"Leads descobertos: {r.get('leads_discovered', 0)} | "
          f"Novos: {r.get('new', 0)} | Atualizados: {r.get('updated', 0)} | "
          f"Cidade: {r.get('city', 'SP')} | Tenant: {r.get('tenant_id', tenant_id)}")


if __name__ == "__main__":
    main()
