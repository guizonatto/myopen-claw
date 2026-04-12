# Sobre o OpenClaw (Node.js)

Este projeto utiliza e integra o [OpenClaw](https://docs.openclaw.ai/), um gateway multi-canal open source feito em Node.js, que conecta WhatsApp, Telegram, Discord, iMessage e outros canais a agentes de IA (ex: Pi, agentes Python customizados). O OpenClaw Gateway é responsável por:
- Roteamento multiagente e isolamento de sessões
- Plugins para canais e extensões
- UI web de controle e chat
- Deploy self-hosted, seguro e extensível

Neste repositório, customizamos e estendemos o comportamento dos agentes Python que se conectam ao Gateway, focando em automação, integração e deploy distribuído, mantendo compatibilidade com o ecossistema OpenClaw.

Para detalhes completos do Gateway, consulte: https://docs.openclaw.ai/

## Configuração do Telegram

Para ativar o canal Telegram no OpenClaw:

1. Copie o arquivo de exemplo:
	```sh
	cp configs/openclaw.telegram.example.json ~/.openclaw/openclaw.telegram.json
	```
2. Preencha os campos necessários no arquivo copiado.
3. **Antes de rodar o OpenClaw, preencha as variáveis no seu `.env` ou ambiente:**
	- `TELEGRAM_BOT_TOKEN` — token do seu bot Telegram
	- `TELEGRAM_USER_ID` — seu user ID autorizado

	Exemplo no `.env.example`:
	```env
	TELEGRAM_BOT_TOKEN=seu_token_aqui
	TELEGRAM_USER_ID=seu_user_id
	```
4. O OpenClaw irá ler essas variáveis automaticamente ao inicializar.

No config, use referência de variável:
```json
{
  "botToken": "${TELEGRAM_BOT_TOKEN}",
  "allowFrom": ["tg:${TELEGRAM_USER_ID}"]
}
```

Consulte o exemplo e a documentação oficial para mais opções: https://docs.openclaw.ai/gateway/configuration-reference
## Configuração do OpenClaw

O OpenClaw lê um arquivo opcional de configuração JSON5 em `~/.openclaw/openclaw.json`.
Se o arquivo não existir, o sistema usa defaults seguros.

Principais motivos para configurar:
- Conectar canais e controlar quem pode interagir com o bot
- Definir modelos, ferramentas, sandbox, automações (cron, hooks)
- Ajustar sessões, mídia, rede ou UI

Consulte a referência completa de todos os campos disponíveis:
https://docs.openclaw.ai/gateway/configuration
## O que é este projeto
Este projeto é uma customização pessoal do OpenClaw — um assistente digital multifuncional rodando em Python + Docker.

O que é:
- Fork/customização pessoal do https://docs.openclaw.ai/, adaptado para uso diário do dono do repositório.
- O agente se chama Clawlito e atua como assistente profissional/pessoal.

O que faz:
- Monitora redes sociais (Twitter, LinkedIn) e analisa tendências de mercado.
- Gerencia um CRM pessoal de contatos (clientes, familiares, amigos).
- Envia alertas e notificações via Telegram.
- Sugere e gera conteúdo para LinkedIn e negócios.
- Lembra datas importantes (aniversários, follow-ups).

Stack técnica:
- Python com estrutura em camadas: skills/ → tools/ → pipes/ → crons/ + triggers/
- PostgreSQL + pgvector como banco de dados (memória, contatos, trends)
- Docker + Watchtower para deploy e atualização automática em servidor
- APScheduler para tarefas agendadas

Objetivo principal: permitir replicar todo o ambiente em qualquer servidor clonando o repo e rodando o deploy, sem reconfigurar nada manualmente.


## Manutenção do repositório

Use a skill `repo_maintenance` para registrar e lembrar das regras e decisões do projeto. Consulte o arquivo `docs/decisions.md` para histórico de decisões importantes.
## MEMORY no banco de dados

O OpenClaw já está preparado para usar o PostgreSQL como backend do MEMORY. O módulo `openclaw/memory_db.py` cria e gerencia a tabela `memory` automaticamente. Basta usar as funções `add_memory` e `get_memory` para registrar e consultar aprendizados e histórico.
## Atualização automática do OpenClaw

Para que o servidor OpenClaw seja atualizado automaticamente após push de nova imagem Docker:

1. Configure o workflow CI/CD para publicar a imagem no Docker Hub ou outro registry.
2. No servidor, use o arquivo `watchtower-compose.yml` e rode:

```sh
docker compose -f watchtower-compose.yml up -d
```

O Watchtower monitora e atualiza o container OpenClaw sempre que uma nova imagem for publicada.


# Customização Pessoal do OpenClaw

Este repositório NÃO é o projeto OpenClaw original ([open source, veja aqui](https://docs.openclaw.ai/)).

Aqui está a minha customização pessoal do assistente OpenClaw, adaptada para minhas necessidades diárias, integrações e automações específicas.

O objetivo é facilitar o redeploy em qualquer servidor ou ambiente, sem precisar reconfigurar ou reescrever tudo do zero: basta clonar este repositório e rodar o deploy, e todas as minhas skills, pipes, triggers, crons e integrações já estarão prontas para uso.

**Resumo:**
- Baseado no OpenClaw open source, mas com automações, integrações e habilidades customizadas para meu uso pessoal
- Permite replicar rapidamente o ambiente em novos servidores, mantendo todas as configurações e fluxos prontos
- Evita retrabalho manual a cada troca de máquina ou ambiente

Se você procura o OpenClaw original, acesse: https://docs.openclaw.ai/

---

## Importante sobre automação de dependências

Sempre que instalar dependências, plugins ou comandos que precisem rodar no deploy, registre a entrada correspondente no arquivo `entrypoint.sh`. Isso garante que tudo será automatizado e reprodutível em qualquer ambiente, sem necessidade de setup manual após o deploy.

## Instalação e deploy

Depois de configurar o `.env` e subir o stack com Docker, o `entrypoint.sh` executa automaticamente o bootstrap do ambiente.

No start do container, o fluxo de instalação/deploy faz:
- onboarding inicial do OpenClaw quando necessário
- sincronização das skills a partir de `SKILLS_GIT_REPO`
- subida do gateway OpenClaw
- espera ativa até o gateway ficar disponível
- registro automático de todos os cronjobs versionados em `crons/*.cron.md`

Isso evita cadastro manual de jobs e garante que um novo deploy recrie os cronjobs declarados no repositório.

## OpenProse: instalação e uso

O OpenProse é um plugin oficial do OpenClaw para workflows markdown-first, pesquisa multi-agente e automação paralela.

### Como instalar e habilitar o OpenProse
1. Habilite o plugin:
	```sh
	openclaw plugins enable open-prose
	```
2. Reinicie o gateway:
	```sh
	openclaw gateway restart
	```
3. Verifique se o comando `/prose` está disponível.

### Comandos principais
- `/prose help` — mostra ajuda
- `/prose run <arquivo.prose>` — executa um programa .prose local
- `/prose run <handle/slug>` — executa um programa remoto
- `/prose compile <arquivo.prose>` — compila um programa
- `/prose examples` — exemplos de uso
- `/prose update` — atualiza o plugin

### Estrutura de arquivos
O OpenProse mantém estado em `.prose/` no workspace:
```
.prose/
  ├── .env
  ├── runs/
  └── agents/
```
Agentes persistentes ficam em `~/.prose/agents/`.

### Observações de segurança
- `.prose` são programas: revise antes de rodar.
- Use allowlists e approval gates para controlar efeitos colaterais.

Mais detalhes: https://docs.openclaw.ai/prose

---


## Como usar


1. Edite `requirements.txt` para adicionar dependências extras, se necessário.
2. Coloque suas skills, ferramentas e fluxos customizados nas pastas apropriadas (`skills/`, `tools/`, `pipes/`, etc).
3. Para buildar a imagem Docker:

```sh
docker build -t openclaw .
```


4. Para rodar o container:

```sh
docker run --rm openclaw
```


## Estrutura inicial
- openclaw/main.py: ponto de entrada do projeto
- requirements.txt: dependências Python
- Dockerfile: empacotamento para distribuição
- skills/: coloque aqui suas skills customizadas
- tools/: coloque aqui suas ferramentas customizadas
- pipes/: fluxos de processamento de dados
- crons/: tarefas agendadas
- triggers/: disparadores baseados em eventos
- workflows/: scripts de agentes e orquestração


## Como rodar um agente de skills

```sh
python -m workflows.agent_example
```


## Como rodar agendador de crons

```sh
python -m workflows.cron_example
```

---

## Sincronização automática de skills via GitHub

A partir de 2026-03, este repositório suporta sincronização automática das skills customizadas diretamente de um repositório GitHub, durante o start do container.

**Como funciona:**
- O script `entrypoint.sh` verifica se existe um repositório Git configurado em `/root/.openclaw/workspace/skills`.
- Se existir, executa `git pull` para atualizar as skills.
- Se não existir, executa `git clone` usando a URL definida na variável de ambiente `SKILLS_GIT_REPO`.
- Isso garante que as skills estejam sempre atualizadas com o repositório remoto, sem sobrescrever skills já existentes.

**Como configurar:**
1. Defina a variável de ambiente `SKILLS_GIT_REPO` no seu `docker-compose.yml`:
   ```yaml
   environment:
     - SKILLS_GIT_REPO=https://github.com/SEU_USUARIO/SEU_REPO_DE_SKILLS.git
   ```
2. O entrypoint irá sincronizar as skills automaticamente a cada start do container.

**Vantagens:**
- Permite atualizar/adicionar/remover skills apenas com um push no GitHub.
- Facilita o deploy em múltiplos servidores sem rebuild manual da imagem.
- Garante que o ambiente de skills esteja sempre consistente com o repositório remoto.

Veja o script em `entrypoint.sh` para detalhes e customização.

## ATUALIZAÇÃO IMPORTANTE (2026-04-10)
As tools do MCP de memórias de longo prazo foram renomeadas para evitar conflito com o memory builtin do OpenClaw:
- save_memory → save_memory_long
- get_memory → get_memory_long
Atualize suas skills, pipes e integrações para usar os novos nomes ao persistir ou buscar memórias longas.
