# Configuração do Canal WhatsApp (Baileys)

- type: whatsapp
- provider: baileys
- enabled: true
- session_path: .data/baileys_session.json
- webhook_url: ""
- phone_number: "{{WHATSAPP_PHONE}}"
- admin_numbers:
    - "{{WHATSAPP_ADMIN}}"
- description: |
    Canal WhatsApp integrado via Baileys. Configure variáveis de ambiente no .env:
    - WHATSAPP_PHONE
    - WHATSAPP_ADMIN
    - WHATSAPP_BAILEYS_SESSION_PATH
