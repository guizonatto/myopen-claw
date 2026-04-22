"""
Cronjob: Busca e enriquece leads em SP a cada 30 minutos, priorizando leads com WhatsApp.
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from agents.lead_fetcher.agent import LeadFetcherAgent
import os

# Configuração do banco (ajustar conforme ambiente)
CRM_DB_URL = os.getenv('CRM_DB_URL', 'postgresql://user:pass@localhost:5432/crm')

crm_engine = create_engine(CRM_DB_URL)
CRM_Session = sessionmaker(bind=crm_engine)


def job():
    crm_session = CRM_Session()
    agent = LeadFetcherAgent(
        crm_session,
        memclaw_session_id=os.getenv("MEMCLAW_SESSION_ID") or "agent-lead_fetcher",
    )
    agent.processar_leads()
    crm_session.close()


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(job, 'cron', minute='*/30')
    print("[lead_fetch_and_enrich_cron] Agendado para rodar a cada 30 minutos.")
    scheduler.start()
