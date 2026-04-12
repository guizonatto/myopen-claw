"""
Função: Cronjob para buscar trends do Twitter Brasil e salvar no MCP trends_mcp
Usar quando: Atualização periódica dos trending topics do Twitter Brasil
ENV_VARS: Nenhuma obrigatória
"""
from apscheduler.schedulers.blocking import BlockingScheduler
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../skills/trends')))
from fetch_and_summarize import run

def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(run, 'interval', hours=1, id='fetch_trends_brazil')
    print("Cronjob de trends do Twitter Brasil agendado para rodar a cada 1 hora.")
    scheduler.start()

if __name__ == "__main__":
    main()
