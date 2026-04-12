"""
Agente para busca inteligente de leads em SP, com memória persistente (MCP-Memories) e foco em leads com WhatsApp.
"""
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

# Dependências do domínio
from mcps.crm_mcp.models import Contato
from mcps.memories_mcp.models import Memory

class LeadFetcherAgent:
    """
    Agente que busca, enriquece e registra leads no CRM, priorizando leads com WhatsApp e utilizando memória persistente.
    """
    def __init__(self, crm_session, memories_session):
        self.crm_session = crm_session
        self.memories_session = memories_session

    def buscar_memorias(self) -> List[Memory]:
        """Busca memórias relevantes para estratégias e leads já processados."""
        return self.memories_session.query(Memory).filter(Memory.entidade == 'lead').all()

    def salvar_memoria(self, conteudo: str, categoria: str = None, origem: str = None):
        memoria = Memory(
            entidade='lead',
            tipo='estrategia',
            conteudo=conteudo,
            categoria=categoria,
            origem=origem,
            importancia=5,
            validade=None,
        )
        self.memories_session.add(memoria)
        self.memories_session.commit()

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
                    self.salvar_memoria(f"Lead atualizado: {lead['nome']} ({lead.get('email')})", categoria='atualizacao', origem=lead.get('origem'))
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
                self.salvar_memoria(f"Lead criado: {lead['nome']} ({lead.get('email')})", categoria='novo', origem=lead.get('origem'))

# Exemplo de uso (no cronjob):
# from agents.lead_fetcher.agent import LeadFetcherAgent
# agent = LeadFetcherAgent(crm_session, memories_session)
# agent.processar_leads()
