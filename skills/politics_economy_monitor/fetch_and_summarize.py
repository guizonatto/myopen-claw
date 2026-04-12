"""
Função: Monitorar fontes de política e economia e gerar resumos
Usar quando: É necessário obter e resumir notícias de política e economia
ENV_VARS: Nenhuma obrigatória
DB_TABLES: politics_economy_news (no MCP de negócios, se existir)
"""

from typing import List, Dict
import requests
from bs4 import BeautifulSoup

FONTES = [
    # Política Nacional
    {"nome": "JOTA", "url": "https://www.jota.info/"},
    {"nome": "Nexo Jornal", "url": "https://www.nexojornal.com.br/"},
    # Política Internacional
    {"nome": "NYT World", "url": "https://www.nytimes.com/section/world"},
    {"nome": "BBC News Mundo", "url": "https://www.bbc.com/portuguese/internacional"},
    # Economia Nacional
    {"nome": "Brazil Journal", "url": "https://braziljournal.com/"},
    {"nome": "Valor Econômico", "url": "https://valor.globo.com/"},
    # Economia Internacional
    {"nome": "Bloomberg", "url": "https://www.bloomberg.com/"},
    {"nome": "Financial Times", "url": "https://www.ft.com/"},
]

def fetch_news() -> List[Dict[str, str]]:
    """
    Busca as principais manchetes das fontes de política e economia e gera um resumo para cada notícia.
    Returns:
        List[Dict[str, str]]: Lista de dicts com 'fonte', 'titulo', 'url', 'summary'.
    """
    noticias = []
    for fonte in FONTES:
        try:
            resp = requests.get(fonte["url"], timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            titulos = [a.text.strip() for a in soup.find_all("a") if a.text and len(a.text) > 30][:5]
            for titulo in titulos:
                summary = summarize_news(titulo, fonte["nome"])
                noticias.append({
                    "fonte": fonte["nome"],
                    "titulo": titulo,
                    "url": fonte["url"],
                    "summary": summary
                })
        except Exception as e:
            noticias.append({
                "fonte": fonte["nome"],
                "titulo": "[ERRO AO BUSCAR]",
                "url": fonte["url"],
                "summary": str(e)
            })
    return noticias

def summarize_news(titulo: str, fonte: str) -> str:
    """
    Gera um resumo explicativo para a notícia.
    Args:
        titulo (str): Título da notícia
        fonte (str): Nome da fonte
    Returns:
        str: Resumo explicativo
    """
    return f"Resumo automático: '{titulo}' é destaque em {fonte}."

def run():
    """
    Função principal para execução standalone ou via cron/pipe.
    """
    noticias = fetch_news()
    # Aqui faria o POST para o MCP de negócios, se existir
    print(noticias)

if __name__ == "__main__":
    run()
