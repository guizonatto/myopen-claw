"""
Agent: lead_fetcher
Função: Busca leads em SP com WhatsApp, aprende quais fontes têm melhor taxa e prioriza nas próximas sessões.
Usar quando: busca periódica de leads novos no CRM.

ENV_VARS:
  - CORTEX_MEM_URL: URL do serviço MemClaw (default: http://cortex-mem:8085)

DB_TABLES:
  - contatos: leitura+escrita
"""
from collections import defaultdict
from datetime import datetime
from typing import Any

from mcps.crm_mcp.models import Contato
from agents.base_agent import BaseAgent
from skills.leads import fetch as leads_fetch


class LeadFetcherAgent(BaseAgent):
    """
    Busca leads em SP com WhatsApp.
    Aprende qual fonte tem melhor taxa_wpp e prioriza nas sessões seguintes.
    """

    name = "lead_fetcher"

    def __init__(self, crm_session):
        super().__init__()
        self.crm_session = crm_session

    # ── aprendizado de fontes ──────────────────────────────────────────────

    def _rankear_fontes(self) -> list[str]:
        """
        Lê histórico de resultados no MemClaw e retorna fontes ordenadas por
        taxa_wpp média (melhor primeiro). Fontes sem histórico entram no fim.
        """
        memorias = self.recall("resultado_fonte taxa whatsapp lead", limit=50, min_score=0.1)

        acumulado: dict[str, list[float]] = defaultdict(list)
        for m in memorias:
            meta = m.get("metadata") or {}
            fonte = meta.get("fonte")
            taxa = meta.get("taxa_wpp")
            if fonte and taxa is not None:
                acumulado[fonte].append(float(taxa))

        if not acumulado:
            print(f"[{self.name}] sem histórico — usando ordem padrão.")
            return list(leads_fetch.FONTES)

        ranking = sorted(acumulado, key=lambda f: sum(acumulado[f]) / len(acumulado[f]), reverse=True)

        # Fontes novas (sem histórico) entram no fim para exploração
        for f in leads_fetch.FONTES:
            if f not in ranking:
                ranking.append(f)

        medias = {f: f"{sum(acumulado[f])/len(acumulado[f]):.0%}" for f in acumulado}
        print(f"[{self.name}] ranking fontes (taxa_wpp média): {medias}")
        return ranking

    def _salvar_resultado_fonte(self, fonte: str, total: int, com_wpp: int, duplicatas: int) -> None:
        """Captura determinística — sempre salva métricas por fonte, sem julgamento."""
        taxa = com_wpp / total if total > 0 else 0.0
        self.remember(
            "resultado_fonte",
            f"fonte={fonte} total={total} whatsapp={com_wpp} duplicatas={duplicatas} taxa_wpp={taxa:.2f}",
            fonte=fonte,
            total=total,
            com_wpp=com_wpp,
            duplicatas=duplicatas,
            taxa_wpp=taxa,
        )

    # ── busca e processamento ──────────────────────────────────────────────

    def buscar_leads(self) -> list[dict[str, Any]]:
        """Busca em todas as fontes na ordem aprendida, registrando métricas por fonte."""
        todos: list[dict[str, Any]] = []

        for fonte in self._rankear_fontes():
            leads = leads_fetch.run(fonte)
            com_wpp = sum(1 for l in leads if l.get("whatsapp"))
            self._salvar_resultado_fonte(fonte, len(leads), com_wpp, duplicatas=0)
            todos.extend(leads)
            print(f"[{self.name}] {fonte}: {len(leads)} leads, {com_wpp} com WhatsApp")

        return todos

    def processar_leads(self) -> None:
        """Registra leads novos no CRM, atualiza existentes, corrige contagem de duplicatas."""
        leads = self.buscar_leads()
        duplicatas_por_fonte: dict[str, int] = defaultdict(int)

        for lead in leads:
            origem = lead.get("origem", "desconhecida")
            existente = self.crm_session.query(Contato).filter(
                Contato.nome == lead["nome"],
                Contato.email == lead.get("email"),
                Contato.telefone == lead.get("telefone"),
            ).first()

            if existente:
                duplicatas_por_fonte[origem] += 1
                atualizado = False
                for campo in ["whatsapp", "cnae", "origem"]:
                    if lead.get(campo) and getattr(existente, campo, None) != lead[campo]:
                        setattr(existente, campo, lead[campo])
                        atualizado = True
                if atualizado:
                    existente.updated_at = datetime.utcnow()
                    self.crm_session.commit()
                    self.remember("lead_atualizado", f"Lead atualizado: {lead['nome']} via {origem}", origem=origem)
            else:
                self.crm_session.add(Contato(
                    nome=lead["nome"],
                    telefone=lead.get("telefone"),
                    whatsapp=lead.get("whatsapp"),
                    email=lead.get("email"),
                    empresa=lead.get("empresa"),
                    setor=lead.get("setor"),
                    tipo="lead",
                    notas=f"Origem: {origem} | CNAE: {lead.get('cnae')}",
                ))
                self.crm_session.commit()
                self.remember("lead_criado", f"Lead criado: {lead['nome']} via {origem}", origem=origem)

        # Corrige métricas com contagem real de duplicatas
        if duplicatas_por_fonte:
            for fonte, n_dups in duplicatas_por_fonte.items():
                leads_fonte = [l for l in leads if l.get("origem") == fonte]
                com_wpp = sum(1 for l in leads_fonte if l.get("whatsapp"))
                self._salvar_resultado_fonte(fonte, len(leads_fonte), com_wpp, n_dups)
                print(f"[{self.name}] {fonte}: {n_dups} duplicata(s) detectada(s)")

    def decide_and_run(self):
        self.processar_leads()


if __name__ == "__main__":
    LeadFetcherAgent(crm_session=None).run()
