"""
Exporta resumo para Notion.
Requer: NOTION_TOKEN, NOTION_DATABASE_ID
"""
import os
import requests

def export_to_notion(summary):
    token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_DATABASE_ID")
    if not token or not db_id:
        raise Exception("NOTION_TOKEN e NOTION_DATABASE_ID obrigatórios")
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    data = {
        "parent": {"database_id": db_id},
        "properties": summary["properties"],
        "children": summary["children"]
    }
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()

if __name__ == "__main__":
    # Exemplo de uso
    print(export_to_notion({"properties": {}, "children": []}))
