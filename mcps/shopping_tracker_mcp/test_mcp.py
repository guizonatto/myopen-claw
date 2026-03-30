# Teste básico para o endpoint de compras do MCP
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_registrar_compra():
    payload = [
        {
            "nome": "leite",
            "quantidade": 2,
            "unidade": "unidade",
            "wishlist": False,
            "preco": 7.99,
            "supermercado": "Supermercado Central"
        }
    ]
    response = client.post("/compras", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
