"""
Agente para busca inteligente de leads em SP, com memória semântica (MemClaw/Cortex Memory)
e foco em leads com WhatsApp.
"""
from datetime import datetime
from typing import List, Dict, Any

# Dependências do domínio
from mcps.crm_mcp.models import Contato

from openclaw.cortex_mem import CortexMemClient, sanitize_session_id

class LeadFetcherAgent:
    """
    Agente que busca, enriquece e registra leads no CRM, priorizando leads com WhatsApp e
    registrando aprendizados como memória semântica no MemClaw.
    """
    def __init__(
        self,
        crm_session,
        *,
        memclaw_client: CortexMemClient | None = None,
        memclaw_session_id: str | None = None,
    ):
        self.crm_session = crm_session
        self.memclaw = memclaw_client or CortexMemClient()
        self.memclaw_session_id = sanitize_session_id(memclaw_session_id or "agent-lead_fetcher")

    def buscar_memorias(self) -> list[dict[str, Any]]:
        """Busca memórias relevantes para estratégias e leads já processados (MemClaw)."""
        scope = f"cortex://session/{self.memclaw_session_id}"
        try:
            return self.memclaw.search(
                "lead estrategia whatsapp sao paulo",
                scope=scope,
                limit=20,
                min_score=0.1,
                return_layers=["L0"],
            )
        except Exception:
            return []

    def salvar_memoria(self, conteudo: str, categoria: str | None = None, origem: str | None = None) -> bool:
        content_lines = [
            "Entidade: lead",
            "Tipo: estrategia",
            f"Categoria: {categoria or '-'}",
            f"Origem: {origem or '-'}",
            "",
            conteudo,
        ]
        try:
            self.memclaw.add_message(
                self.memclaw_session_id,
                role="assistant",
                content="\n".join(content_lines),
                metadata={
                    "entidade": "lead",
                    "tipo": "estrategia",
                    "categoria": categoria,
                    "origem": origem,
                },
            )
            return True
        except Exception:
            return False

    def commit_memorias(self) -> None:
        """Dispara extração/consolidação do MemClaw para a sessão do agente."""
        try:
            self.memclaw.commit_session(self.memclaw_session_id)
        except Exception:
            return

    def buscar_leads(self) -> List[Dict[str, Any]]:
        """
        Estratégia dinâmica: consulta memórias, seleciona fontes, busca e enriquece leads.
        Foco em leads com WhatsApp.
        """
        # Exemplo: alternar entre estratégias salvas na memória
        memorias = self.buscar_memorias()
        # TODO: lógica para selecionar estratégia vencedora
        # TODO: implementar busca real (Google, Instagram, LinkedIn, CNAE, etc.)
        # Aqui retorna mock
        return [
            {
                'nome': 'Empresa Exemplo',
                'telefone': '+5511999999999',
                'whatsapp': '+5511999999999',
                'email': 'contato@exemplo.com',
                'cidade': 'São Paulo',
                'cnae': '6201-5/01',
                'origem': 'mock_google',
            }
        ]

    def processar_leads(self):
        """
        Busca, enriquece e registra/atualiza leads no CRM, evitando duplicidade e salvando aprendizados.
        """
        leads = self.buscar_leads()
        commit_needed = False
        for lead in leads:
            # Verifica duplicidade
            query = self.crm_session.query(Contato).filter(
                Contato.nome == lead['nome'],
                Contato.email == lead.get('email'),
                Contato.telefone == lead.get('telefone'),
            )
            existente = query.first()
            if existente:
                # Atualiza se houver informação nova
                atualizado = False
                for campo in ['whatsapp', 'cnae', 'origem']:
                    if lead.get(campo) and getattr(existente, campo, None) != lead.get(campo):
                        setattr(existente, campo, lead.get(campo))
                        atualizado = True
                if atualizado:
                    existente.updated_at = datetime.utcnow()
                    self.crm_session.commit()
                    commit_needed |= self.salvar_memoria(
                        f"Lead atualizado: {lead['nome']} ({lead.get('email')})",
                        categoria="atualizacao",
                        origem=lead.get("origem"),
                    )
            else:
                # Cria novo lead
                novo = Contato(
                    nome=lead['nome'],
                    telefone=lead.get('telefone'),
                    whatsapp=lead.get('whatsapp'),
                    email=lead.get('email'),
                    empresa=lead.get('empresa'),
                    setor=lead.get('setor'),
                    tipo='lead',
                    notas=f"Origem: {lead.get('origem')} | CNAE: {lead.get('cnae')}",
                )
                self.crm_session.add(novo)
                self.crm_session.commit()
                commit_needed |= self.salvar_memoria(
                    f"Lead criado: {lead['nome']} ({lead.get('email')})",
                    categoria="novo",
                    origem=lead.get("origem"),
                )

        if commit_needed:
            self.commit_memorias()

# Exemplo de uso (no cronjob):
# from agents.lead_fetcher.agent import LeadFetcherAgent
# agent = LeadFetcherAgent(crm_session, memclaw_session_id="agent-lead_fetcher")
# agent.processar_leads()
