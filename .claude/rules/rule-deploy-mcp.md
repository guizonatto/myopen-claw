
# ---
description: Regra para deploy de MCP (Model Context Protocol) — OpenClaw
alwaysApply: true
# ---

# Regra para Deploy de MCP (Model Context Protocol) — OpenClaw

> Consulte também: [docs/openclaw-mcp.md](../../docs/openclaw-mcp.md) e [docs/architecture.md](../../docs/architecture.md)

## Conceito
- MCP significa sempre Model Context Protocol.
- Cada MCP é um serviço/container independente, responsável por executar operações de IA via HTTP/SSE.

## Estrutura de Deploy
- O código-fonte de cada MCP reside em `mcp/{nome_mcp}/`.
- Cada MCP deve ter seu próprio `Dockerfile`.
- O deploy é feito via orquestração (ex: `docker-compose.yml`), nunca rodando múltiplos MCPs no mesmo container.
- O `docker-compose.yml` deve orquestrar:
	- openclaw-core (imagem oficial)
	- banco de dados (ex: Postgres + pgvector)
	- um ou mais MCPs (cada um em seu container)


## Boas práticas
- Documente endpoints e payloads esperados de cada MCP.
- Nunca misture múltiplos MCPs ou processos no mesmo container.
- Sempre referencie MCP como Model Context Protocol na documentação e código.
- Sempre que um novo MCP é criado, se não tiver um dockerfile associado, crie um dockerfile que exponha o endpoint HTTP/SSE para execução das operações definidas nas skills textuais.
- Garanta que o `docker-compose.yml` seja atualizado para incluir o novo MCP, definindo os serviços necessários para sua execução e comunicação com o core do OpenClaw.
- Plugue o MCP no fluxo de orquestração do OpenClaw, garantindo que os MCPs estejam disponíveis para serem usados pelo OpenClaw.
- Teste cada MCP isoladamente antes do deploy, garantindo que ele responda corretamente via HTTP/SSE e execute as operações definidas.
- Garanta que o código do MCP seja atômico e autossuficiente, seguindo as regras de atomicidade e autossuficiência definidas em `docs/atomic_rules.md`.
- **A porta exposta no Dockerfile do MCP deve ser igual à porta mapeada no docker-compose.yml para o serviço correspondente, garantindo consistência e funcionamento correto da comunicação.**

## Pós-deploy
- Valide que cada MCP responde corretamente via HTTP/SSE.
- Atualize a documentação e exemplos sempre que um novo MCP for criado ou alterado.