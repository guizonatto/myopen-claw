"""
Função: Cronjob para buscar e organizar o digest diário do Reddit
Usar quando: Digest diário dos principais posts dos subreddits de IA
ENV_VARS: Nenhuma obrigatória
"""
from apscheduler.schedulers.blocking import BlockingScheduler
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../skills/reddit_digest')))
from fetch_and_curate import run

def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(run, 'cron', hour=17, minute=0, id='fetch_reddit_digest')
    print("Cronjob do Reddit Digest agendado para rodar diariamente às 17h.")
    scheduler.start()

if __name__ == "__main__":
    main()
