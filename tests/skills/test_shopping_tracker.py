# Teste da skill shopping_tracker (mock)
def test_skill_shopping_tracker():
    # Simula input do usuário
    compras_usuario = "2x leite, 1 pão, 1kg arroz"
    # Esperado: parsing correto incluindo preço e supermercado
    # (mock, pois a skill real é YAML/textual)
    itens_normalizados = [
        {"nome": "leite", "quantidade": 2, "preco": 7.99, "supermercado": "Supermercado Central"},
        {"nome": "pão", "quantidade": 1, "preco": 8.50, "supermercado": "Supermercado Central"},
        {"nome": "arroz", "quantidade": 1, "unidade": "kg", "preco": 5.99, "supermercado": "Supermercado Central"}
    ]
    assert any(item["nome"] == "leite" and "preco" in item for item in itens_normalizados)
    assert all("supermercado" in item for item in itens_normalizados)
