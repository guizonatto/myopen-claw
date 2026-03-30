# OpenClaw — Browser (Gerenciado)

> **Resumo:** O OpenClaw pode controlar um navegador Chrome/Brave/Edge/Chromium isolado, dedicado ao agente, sem afetar seu browser pessoal. Ideal para automação, scraping, snapshots e testes seguros.

---

## Visão geral
- Perfil de navegador isolado: `openclaw` (laranja por padrão)
- Controle determinístico de abas (listar, abrir, focar, fechar)
- Ações: clicar, digitar, arrastar, selecionar, snapshots, screenshots, PDFs
- Suporte a múltiplos perfis (openclaw, work, remote, user, etc)
- Não interfere no seu browser do dia a dia

---

## Como usar (Quick start)
```sh
openclaw browser --browser-profile openclaw status
openclaw browser --browser-profile openclaw start
openclaw browser --browser-profile openclaw open https://example.com
openclaw browser --browser-profile openclaw snapshot
```
Se aparecer “Browser disabled”, habilite no config e reinicie o Gateway.

---

## Controle por plugin
- O browser tool padrão é um plugin embutido (pode ser desabilitado ou substituído)
- Exemplo para desabilitar:
```jsonc
{
  "plugins": {
    "entries": {
      "browser": { "enabled": false }
    }
  }
}
```
- Para funcionar: `plugins.entries.browser.enabled` não pode estar desabilitado **e** `browser.enabled=true`
- Mudanças de config exigem restart do Gateway

---

## Perfis: openclaw vs user
- `openclaw`: navegador isolado, gerenciado (default)
- `user`: conecta ao Chrome real logado via Chrome MCP
- Use `profile="user"` quando precisar do estado logado do usuário
- Defina `browser.defaultProfile: "openclaw"` para modo gerenciado por padrão

---

## Exemplo de configuração
```jsonc
{
  "browser": {
    "enabled": true,
    "ssrfPolicy": {
      "dangerouslyAllowPrivateNetwork": true
    },
    "defaultProfile": "openclaw",
    "color": "#FF4500",
    "headless": false,
    "noSandbox": false,
    "attachOnly": false,
    "executablePath": "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe",
    "profiles": {
      "openclaw": { "cdpPort": 18800, "color": "#FF4500" },
      "work": { "cdpPort": 18801, "color": "#0066CC" },
      "user": { "driver": "existing-session", "attachOnly": true, "color": "#00AA00" },
      "brave": { "driver": "existing-session", "attachOnly": true, "userDataDir": "~/Library/Application Support/BraveSoftware/Brave-Browser", "color": "#FB542B" },
      "remote": { "cdpUrl": "http://10.0.0.42:9222", "color": "#00AA00" }
    }
  }
}
```

---

## Modos de controle
- **Local:** Gateway inicia serviço de controle e pode lançar browser local
- **Remoto:** node host com browser, Gateway faz proxy das ações
- **Remote CDP:** use `cdpUrl` para browsers remotos (Chromium-based)
- **Browserless/Browserbase:** suporte a WebSocket direto para browsers hospedados

---

## Segurança
- Controle só via loopback (localhost) ou node pareado
- Gateway gera token de auth se não houver
- Prefira variáveis de ambiente para tokens de serviços remotos
- Mantenha Gateway/node hosts em rede privada

---

## Perfis e multi-browser
- Perfis podem ser: openclaw-managed, remote, existing-session
- openclaw é criado automaticamente se faltar
- user é built-in para Chrome MCP
- Portas locais: 18800–18899
- CLI usa `--browser-profile <nome>`

---

## Existing-session via Chrome MCP
- Permite conectar ao Chrome/Brave/Edge já aberto/logado
- Exemplo de uso:
```sh
openclaw browser --browser-profile user start
openclaw browser --browser-profile user status
openclaw browser --browser-profile user tabs
openclaw browser --browser-profile user snapshot --format ai
```
- Requer habilitar remote debugging no browser
- Use profile="user" para acessar estado logado

---

## Garantias de isolamento
- User data dir dedicado
- Portas dedicadas (evita 9222)
- Controle determinístico de abas

---

## Seleção de browser
- Ordem: Chrome → Brave → Edge → Chromium → Chrome Canary
- Override: `browser.executablePath`
- Plataformas: macOS, Linux, Windows

---

## Referências
- Chrome DevTools MCP
- Browserless, Browserbase
- Documentação oficial OpenClaw