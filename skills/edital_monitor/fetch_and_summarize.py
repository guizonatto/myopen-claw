"""
Função: Monitorar editais e subvenções de inovação e gerar resumos
Usar quando: É necessário obter e resumir editais de subvenção econômica para SaaS/startups
ENV_VARS: Nenhuma obrigatória
DB_TABLES: editais_news (no MCP de negócios, se existir)
"""

from typing import List, Dict
import requests
from bs4 import BeautifulSoup

FONTES = [
    {"nome": "FINEP", "url": "https://finep.gov.br/chamadas-publicas"},
    {"nome": "Inovativos", "url": "https://inovativos.com.br/"},
    {"nome": "Fundação Araucária", "url": "https://www.fappr.pr.gov.br/"},
    {"nome": "Sebrae Editais", "url": "https://sebrae.com.br/editais"},
    {"nome": "BNDES Garagem", "url": "https://www.bndes.gov.br/wps/portal/site/home/onde-atuamos/garagem"},
]

def fetch_editais() -> List[Dict[str, str]]:
    """
    Busca os principais editais/subvenções das fontes e gera um resumo para cada edital.
    Returns:
        List[Dict[str, str]]: Lista de dicts com 'fonte', 'titulo', 'url', 'summary'.
    """
    editais = []
    for fonte in FONTES:
        try:
            resp = requests.get(fonte["url"], timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # Heurística simples para títulos de editais
            titulos = [a.text.strip() for a in soup.find_all("a") if a.text and len(a.text) > 30][:5]
            for titulo in titulos:
                summary = summarize_edital(titulo, fonte["nome"])
                editais.append({
                    "fonte": fonte["nome"],
                    "titulo": titulo,
                    "url": fonte["url"],
                    "summary": summary
                })
        except Exception as e:
            editais.append({
                "fonte": fonte["nome"],
                "titulo": "[ERRO AO BUSCAR]",
                "url": fonte["url"],
                "summary": str(e)
            })
    return editais

def summarize_edital(titulo: str, fonte: str) -> str:
    """
    Gera um resumo explicativo para o edital.
    Args:
        titulo (str): Título do edital
        fonte (str): Nome da fonte
    Returns:
        str: Resumo explicativo
    """
    return f"Resumo automático: '{titulo}' é destaque em {fonte}."

def run():
    """
    Função principal para execução standalone ou via cron/pipe.
    """
    editais = fetch_editais()
    # Aqui faria o POST para o MCP de negócios, se existir
    print(editais)

if __name__ == "__main__":
    run()
