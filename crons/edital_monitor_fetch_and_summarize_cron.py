"""
Função: Cronjob para buscar editais de inovação e salvar no MCP de negócios
Usar quando: Atualização diária dos principais editais de subvenção
ENV_VARS: Nenhuma obrigatória
"""
from apscheduler.schedulers.blocking import BlockingScheduler
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../skills/edital_monitor')))
from fetch_and_summarize import run

def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(run, 'cron', hour=6, minute=30, id='fetch_editais')
    print("Cronjob de editais de inovação agendado para rodar diariamente às 06h30.")
    scheduler.start()

if __name__ == "__main__":
    main()
