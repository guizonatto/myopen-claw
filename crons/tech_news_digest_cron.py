"""
Cronjob: Gera digest de notícias de tecnologia usando a skill tech-news-digest.
"""
from apscheduler.schedulers.blocking import BlockingScheduler
import subprocess
import sys
import os

# Caminho para o script principal do pipeline
dir_skill = os.path.abspath(os.path.join(os.path.dirname(__file__), '../skills/tech-news-digest/scripts'))
script_pipeline = os.path.join(dir_skill, 'run-pipeline.py')


def job():
    print("[tech_news_digest_cron] Executando pipeline de digest de tech news...")
    result = subprocess.run([sys.executable, script_pipeline], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("[ERRO]", result.stderr)

if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(job, 'cron', hour=7, minute=0)
    print("[tech_news_digest_cron] Agendado para rodar diariamente às 07h00.")
    scheduler.start()
