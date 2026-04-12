"""
Função: Cronjob para buscar notícias de negócios e salvar no MCP de negócios
Usar quando: Atualização diária das principais notícias de negócios
ENV_VARS: Nenhuma obrigatória
"""
from apscheduler.schedulers.blocking import BlockingScheduler
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../skills/business_monitor')))
from fetch_and_summarize import run

def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(run, 'cron', hour=6, minute=0, id='fetch_business_news')
    print("Cronjob de notícias de negócios agendado para rodar diariamente às 06h.")
    scheduler.start()

if __name__ == "__main__":
    main()
