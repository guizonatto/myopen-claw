"""
Tool: settings
Função: Centraliza a leitura das variáveis de ambiente da stack de telemetria.
Usar quando: Precisar inicializar o proxy, storage local ou dispatch do relatório.

ENV_VARS:
  - MODEL_USAGE_DB_PATH: caminho do SQLite
  - MODEL_USAGE_CAPTURE_PAYLOADS: `off|preview|full` para auditoria de request/response
  - MODEL_USAGE_PROXY_TIMEOUT_SECONDS: timeout do passthrough HTTP
  - MODEL_USAGE_ESTIMATE_CHAT_TOKENS: estima tokens de chat/responses sem usage explícito
  - MODEL_USAGE_REPORT_TIMEZONE: timezone do relatório
  - MODEL_USAGE_RETENTION_DAYS: retenção do SQLite
  - MODEL_USAGE_SYNC_OPENCLAW_MODELS: `true|false` para espelhar modelos do OpenClaw no SQLite
  - MODEL_USAGE_SYNC_OPENCLAW_MODELS_STRICT: `true|false` para desabilitar modelos fora do OpenClaw
  - OPENCLAW_CONFIG_PATH: caminho do openclaw.json (para sync de modelos)
  - MODEL_LIMITS_CATALOG_PATH: caminho do JSON com limites por model/provider (opcional)
  - OPENCLAW_GATEWAY_URL: URL do gateway para dispatch
  - OPENCLAW_GATEWAY_TOKEN: token opcional do gateway
  - OPENCLAW_GATEWAY_PASSWORD / ADMIN_PASSWORD: senha bearer do gateway
  - DISCORD_BOT_TOKEN: token do bot para envio direto de relatórios
  - MODEL_USAGE_REPORT_DISCORD_CHANNEL_ID: canal Discord do relatório

DB_TABLES:
  - (nenhuma)
"""
from dataclasses import dataclass
import os

from llm_usage_telemetry.model_limits_catalog import DEFAULT_MODEL_LIMITS_CATALOG_PATH

@dataclass(slots=True)
class TelemetrySettings:
    db_path: str
    capture_payloads: str
    proxy_timeout_seconds: float
    estimate_chat_tokens: bool
    report_timezone: str
    retention_days: int
    gateway_url: str
    gateway_token: str
    gateway_password: str
    discord_bot_token: str
    discord_channel_id: str
    openclaw_config_path: str = "/openclaw/openclaw.json"
    model_limits_catalog_path: str = DEFAULT_MODEL_LIMITS_CATALOG_PATH
    sync_openclaw_models: bool = True
    sync_openclaw_models_strict: bool = False


def load_settings(env: dict[str, str] | None = None) -> TelemetrySettings:
    env_map = os.environ if env is None else env
    return TelemetrySettings(
        db_path=env_map.get("MODEL_USAGE_DB_PATH", "/data/llm-usage.sqlite3"),
        capture_payloads=env_map.get("MODEL_USAGE_CAPTURE_PAYLOADS", "off").lower(),
        proxy_timeout_seconds=float(env_map.get("MODEL_USAGE_PROXY_TIMEOUT_SECONDS", "120")),
        estimate_chat_tokens=env_map.get("MODEL_USAGE_ESTIMATE_CHAT_TOKENS", "false").lower()
        in {"1", "true", "yes", "on"},
        report_timezone=env_map.get("MODEL_USAGE_REPORT_TIMEZONE", "America/Sao_Paulo"),
        retention_days=int(env_map.get("MODEL_USAGE_RETENTION_DAYS", "30")),
        openclaw_config_path=env_map.get("OPENCLAW_CONFIG_PATH", "/openclaw/openclaw.json"),
        model_limits_catalog_path=env_map.get("MODEL_LIMITS_CATALOG_PATH", DEFAULT_MODEL_LIMITS_CATALOG_PATH),
        sync_openclaw_models=env_map.get("MODEL_USAGE_SYNC_OPENCLAW_MODELS", "true").lower()
        in {"1", "true", "yes", "on"},
        sync_openclaw_models_strict=env_map.get("MODEL_USAGE_SYNC_OPENCLAW_MODELS_STRICT", "false").lower()
        in {"1", "true", "yes", "on"},
        gateway_url=env_map.get("OPENCLAW_GATEWAY_URL", "http://openclaw-gateway:18789"),
        gateway_token=env_map.get("OPENCLAW_GATEWAY_TOKEN", ""),
        gateway_password=env_map.get("OPENCLAW_GATEWAY_PASSWORD", env_map.get("ADMIN_PASSWORD", "")),
        discord_bot_token=env_map.get("DISCORD_BOT_TOKEN", ""),
        discord_channel_id=env_map.get("MODEL_USAGE_REPORT_DISCORD_CHANNEL_ID", ""),
    )
