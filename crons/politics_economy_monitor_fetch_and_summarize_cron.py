"""
Função: Cronjob para buscar notícias de política e economia
Usar quando: Atualização diária das principais notícias de política e economia
ENV_VARS: Nenhuma obrigatória
"""
from apscheduler.schedulers.blocking import BlockingScheduler
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../skills/politics_economy_monitor')))
from fetch_and_summarize import run

def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(run, 'cron', hour=7, minute=45, id='fetch_politics_economy_news')
    print("Cronjob de política e economia agendado para rodar diariamente às 07h45.")
    scheduler.start()

if __name__ == "__main__":
    main()
