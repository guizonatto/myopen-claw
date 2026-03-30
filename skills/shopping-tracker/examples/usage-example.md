# Exemplo de uso da skill Shopping Tracker

## Input do usuário
"2x leite, 1 pão, 1kg arroz, 1 pacote de café"

## Output esperado
- itens_normalizados:
    - nome: leite
      quantidade: 2
    - nome: pão
      quantidade: 1
    - nome: arroz
      quantidade: 1
      unidade: kg
    - nome: café
      quantidade: 1
      unidade: pacote
- tracking_periodicidade:
    - nome: leite
      media_dias: 7
    - nome: arroz
      media_dias: 30
    - nome: café
      media_dias: 20
- notificacao_compra: "Você deve comprar leite em 5 dias."
