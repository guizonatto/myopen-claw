---
name: sindico-leads
description: "Use esta skill quando o usuário pedir para buscar informações sobre síndicos profissionais. Ela detalha como usar a ferramenta 'browser' interna do OpenClaw para extrair dados de forma autônoma."
metadata:
  openclaw:
    model: anthropic/haiku
---


# SKILL: sindico-leads

## Objetivo
Buscar na web a maior quantidade possível de informações sobre síndicos profissionais e mapear para o modelo de dados do CRM (nome, apelido, tipo, aniversário, telefone, whatsapp, email, linkedin, instagram, empresa, cargo, setor, notas, publicações, etc.), gerando uma lista de leads para cadastro e atualização no CRM como tipo "lead".

## Descrição
Esta skill automatiza a busca de síndicos profissionais em fontes públicas na web, extraindo e mapeando para os campos do modelo Contato do CRM:
- nome
- tipo
- telefone
- whatsapp
- email
- linkedin
- instagram
- empresa
- setor
- notas
- publicações, notícias ou menções públicas (armazenadas em notas ou campo dedicado)
- CNPJ: se disponível, para identificação única e enriquecimento do lead
- CNAE: lista de todos os cnaes dos síndicos encontrados, se possível

O sistema utiliza o mecanismo de busca mais eficiente disponível (ex: browser, scraping, APIs públicas) para maximizar a quantidade de leads e minimizar o custo de tokens.

Após a coleta, os leads são enviados para a base de dados do CRM, marcados como tipo "lead". Se o síndico já existir, as informações são atualizadas. Caso haja divergências relevantes (ex: telefones diferentes, e-mails divergentes), é criado um "acontecimento" (evento) vinculado ao contato, informando a diferença encontrada para posterior análise.

## Fluxo
1. Buscar páginas, listas e menções de síndicos profissionais usando web search otimizado (em searchs e apis públicas usando a memória como uma fonte para saber quais sites tem trazido resultados relevantes e rankeando estes sites em memória).
2. Extrair e mapear todos os campos possíveis para o modelo Contato do CRM.
3. Normalizar, deduplicar e enriquecer os leads.
4. Para cada lead:
  - Se não existir no CRM, cadastrar como novo lead.
  - Se já existir, se pertinente atualizar informações novas e criar "acontecimento" caso haja divergência relevante (ex: telefone, e-mail, empresa, etc.).

## Exemplo de output
```json
[
  {
    "nome": "João da Silva",
    "apelido": "João Síndico",
    "tipo": "sindico_profissional",
    "aniversario": "1980-05-10",
    "telefone": "+55 11 91234-5678",
    "whatsapp": "+55 11 91234-5678",
    "email": "joao@xyz.com",
    "linkedin": "https://linkedin.com/in/joaosilva",
    "instagram": "https://instagram.com/joaosilva",
    "empresa": "Condomínios XYZ",
    "cargo": "Síndico Profissional",
    "setor": "Condomínios",
    "notas": "Publicações: https://portalcondominio.com/artigo-joao, https://jornalcondominio.com/entrevista-joao",
    "CNPJ": "12.345.678/0001-90",
    "CNAE": ["68.20-6-00 - Atividades de administração de imóveis e condomínios", "68.10-2-01 - Atividades de corretagem imobiliária", "68.10-2-02 - Atividades de administração de imóveis próprios"],
    "ativo": true
  },
  {
    "nome": "Maria Souza",
    "apelido": null,
    "tipo": "sindico_profissional",
    "aniversario": null,
    "telefone": "+55 21 99876-5432",
    "whatsapp": null,
    "email": null,
    "linkedin": null,
    "instagram": null,
    "empresa": null,
    "cargo": null,
    "setor": null,
    "notas": null,
    "ativo": true
  }
]
```

## Observações
- Priorize fontes confiáveis e listas públicas.
- Use scraping apenas quando permitido.
- O cadastro/atualização no CRM deve ser feito via tool/pipe já existente (ex: `add_lead_crm`), respeitando a modelagem de dados do CRM.
- Não reinserir síndicos já existentes, mas atualizar informações novas se existirem.
- Se houver divergência relevante (ex: telefones, e-mails, empresa), criar um "acontecimento" para o síndico informando a diferença.
- Documente eventuais limitações ou bloqueios de fontes.
- Se achar APIs que podemos trazer estas infos, salva como uma memória para lembrarmos de usar isso no futuro. Rankeie as fontes para podermos reusar.
- Aprenda e memorize quais fontes tem trazido mais leads relevantes para otimizar buscas futuras.
- Evite usar muitos tokens enviando apenas os campos mais relevantes e resumindo notas quando necessário.
- Se não for possível encontrar leads, informe isso de forma sucinta.
- Foque em quantidade e qualidade dos leads, mas seja eficiente no uso de tokens e recursos.
- Sempre que possível, normalize e deduplicate os dados para evitar registros duplicados ou inconsistentes no CRM.
- Mantenha um registro das fontes utilizadas e dos resultados obtidos para futuras otimizações e análises de eficácia.
- Se a busca por síndicos profissionais for muito ampla, considere segmentar por região. Foco: Cidade de São Paulo, Cidade do Rio de Janeiro, Belo Horizonte, Salvador, Recife, Curitiba, Porto Alegre, Brasília, Fortaleza e outras capitais brasileiras. Santos, Campinas, São José dos Campos, Sorocaba, Ribeirão Preto, podem ser consideradas também.
- Se possível, in

# User response
- Only inform the user how many leads were found and updated, and if there were divergences relevantes (ex: telefones, e-mails, empresa) que geraram acontecimentos. Não mostre os dados dos leads para o usuário, apenas um resumo da operação realizada.
- Exemplo: "Foram encontrados 50 leads de síndicos profissionais. 30 foram cadastrados como novos leads, 15 tiveram informações atualizadas e 5 apresentaram divergências relevantes que geraram acontecimentos para análise."
- Se não for possível encontrar leads, informe: "Não foram encontrados leads de síndicos profissionais nas fontes pesquisadas."
- Evite usar termos técnicos ou detalhes do processo na resposta para o usuário, foque apenas no resultado final da operação.
- Não seja verboso. Quanto mais sucinto melhor. Reduzir quantidade de tokens usados no output é um plus.

## Referências
- tools/browser
- tools/add_lead_crm
- tools/memory_db
- skills/crm