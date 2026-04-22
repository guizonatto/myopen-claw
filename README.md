# Clawlito — assistente de negócios (self‑hosted)

Clawlito é um assistente que roda no seu servidor e ajuda a tocar o “operacional” do dia a dia: **captar e registrar leads**, **organizar informação**, **gerar resumos e relatórios** e **entregar tudo no Telegram/Discord/WhatsApp**.

O objetivo é simples: **menos tarefas repetitivas, mais consistência** — sem depender de SaaS e mantendo seus dados sob controle.

## O que ele faz (na prática)

- **Leads → CRM automaticamente**: coleta leads, enriquece e faz **cadastro/atualização direto no CRM** (sem “copiar/colar”).
- **Resumos e monitoramento**: notícias, tendências, editais e relatórios em horários programados (rotinas agendadas).
- **Conteúdo**: ideias e rascunhos de posts para redes sociais (ex.: IA e Mercado Condominial).
- **Conhecimento e busca**: suas **notas do Obsidian são a fonte de verdade** e o assistente mantém uma **busca inteligente** para encontrar e responder rápido (para devs: MemClaw).

## Para quem é

- Empreendedores solo e times pequenos
- Consultores, freelancers e prestadores de serviço
- Criadores de conteúdo B2B

## Como funciona (visão simples)

1. Você fala com o bot no **Telegram/Discord/WhatsApp**.
2. O **OpenClaw Gateway** escolhe qual rotina executar.
3. A rotina usa integrações (CRM, Obsidian, web search, etc.).
4. O resultado volta para o canal em texto curto e acionável.

## Começar (self‑host)

1. Copie e preencha as variáveis:
	```sh
	cp .env.example .env
	```
2. Suba o stack:
	```sh
	docker compose up -d --build
	```
3. Acompanhe o boot:
	```sh
	docker logs -f openclaw-gateway
	```

Os crons versionados em `crons/*.cron.md` são registrados automaticamente no start do container (via `entrypoint.sh`).

## Configuração rápida de canais (ex.: Telegram)

1. Copie o exemplo:
	```sh
	cp configs/openclaw.telegram.example.json ~/.openclaw/openclaw.telegram.json
	```
2. Preencha `TELEGRAM_BOT_TOKEN` e `TELEGRAM_USER_ID` no `.env`.
3. No JSON, use referências:
	```json
	{
	  "botToken": "${TELEGRAM_BOT_TOKEN}",
	  "allowFrom": ["tg:${TELEGRAM_USER_ID}"]
	}
	```

Mais opções: https://docs.openclaw.ai/gateway/configuration-reference

## Onde ver o que existe (sem “jargão”)

- Lista de tools disponíveis e como chamar: `configs/TOOLS.md`
- Documentação do projeto: `docs/INDEX.md`
- Fonte de automações: `crons/`
- Skills e comportamentos: `skills/`

## Sobre o OpenClaw (o “motor” por trás)

Este projeto utiliza e integra o [OpenClaw](https://docs.openclaw.ai/): um gateway multi‑canal open source (Node.js) que conecta canais (WhatsApp, Telegram, Discord…) a agentes/skills.

Consulte a referência de configuração do gateway: https://docs.openclaw.ai/gateway/configuration
