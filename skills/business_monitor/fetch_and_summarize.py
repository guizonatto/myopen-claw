"""
Função: Monitorar fontes de notícias de negócios nacionais e internacionais e gerar resumos
Usar quando: É necessário obter e resumir notícias de negócios para acompanhamento ágil
ENV_VARS: Nenhuma obrigatória
DB_TABLES: business_news (no MCP de negócios, se existir)
"""

from typing import List, Dict
import requests
from bs4 import BeautifulSoup

FONTES = [
    # Nacional
    {"nome": "Exame PME", "url": "https://exame.com/pme/"},
    {"nome": "Startups.com.br", "url": "https://startups.com.br/"},
    {"nome": "Endeavor Brasil", "url": "https://endeavor.org.br/"},
    # Internacional
    {"nome": "TechCrunch", "url": "https://techcrunch.com/"},
    {"nome": "Reuters Business", "url": "https://www.reuters.com/business/"},
    {"nome": "Morning Brew", "url": "https://www.morningbrew.com/daily"},
    {"nome": "HackerNews", "url": "https://thehackernews.com/"},
    {"nome": "Product Hunt", "url": "https://www.producthunt.com/"},
]

def fetch_news() -> List[Dict[str, str]]:
    """
    Busca as principais manchetes das fontes de negócios e gera um resumo para cada notícia.
    Returns:
        List[Dict[str, str]]: Lista de dicts com 'fonte', 'titulo', 'url', 'summary'.
    """
    noticias = []
    for fonte in FONTES:
        try:
            resp = requests.get(fonte["url"], timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # Heurística simples para manchetes/notícias
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
