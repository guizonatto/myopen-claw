"""
Função: Buscar trends do Twitter Brasil e gerar resumo explicativo
Usar quando: É necessário obter os trending topics do Twitter Brasil e salvar no MCP de trends, com contexto/resumo de cada trend.
ENV_VARS: Nenhuma obrigatória (pode usar requests para scraping)
DB_TABLES: trends (no MCP trends_mcp)
"""

from typing import List, Dict
import requests
from bs4 import BeautifulSoup


def fetch_trends_and_summaries() -> List[Dict[str, str]]:
    """
    Busca os trending topics do Twitter Brasil em https://trends24.in/brazil/ e gera um resumo para cada trend.
    Returns:
        List[Dict[str, str]]: Lista de dicts com 'trend' e 'summary'.
    """
    url = "https://trends24.in/brazil/"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    trends = []
    for trend_tag in soup.select(".trend-card .trend-card__list li a"):
        trend = trend_tag.text.strip()
        if trend:
            trends.append(trend)
    # Remove duplicados e filtra trends vazios
    trends = list(dict.fromkeys([t for t in trends if t]))
    # Gera resumo para cada trend
    results = []
    for trend in trends:
        summary = summarize_trend(trend)
        results.append({"trend": trend, "summary": summary})
    return results


def summarize_trend(trend: str) -> str:
    """
    Gera um resumo explicativo para o trending topic.
    Args:
        trend (str): Nome do trending topic
    Returns:
        str: Resumo explicativo
    """
    # Aqui pode-se usar uma API de LLM ou heurística simples
    # Exemplo: placeholder
    return f"Resumo automático: '{trend}' é um dos assuntos mais comentados no Twitter Brasil no momento."


def run():
    """
    Função principal para execução standalone ou via cron/pipe.
    """
    trends = fetch_trends_and_summaries()
    # Aqui faria o POST para o MCP trends_mcp
    print(trends)

if __name__ == "__main__":
    run()
