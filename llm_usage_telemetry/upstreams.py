"""
Tool: upstreams
Função: Resolve upstreams reais a partir de refs usage-router/provider/model.
Usar quando: Precisar encaminhar chamadas do proxy para o provider final correto.

ENV_VARS:
  - GROQ_API_KEY: chave do provider Groq
  - GOOGLE_API_KEY: chave do provider Google Gemini
  - GEMINI_API_KEY: fallback para Gemini
  - GOOGLE_AUTH_MODE: `gemini_api` (gratis via AI Studio) ou `vertex_oauth`
  - GOOGLE_OPENAI_BASE_URL: override do endpoint OpenAI-compatible do Google
  - GOOGLE_GEMINI_BASE_URL: override do endpoint nativo do Gemini Developer API
  - MISTRAL_API_KEY: chave do provider Mistral
  - CEREBRAS_API_KEY: chave do provider Cerebras
  - QWEN_API_KEY: chave do provider Qwen/DashScope
  - DEEPSEEK_API_KEY: chave do provider DeepSeek
  - OPENROUTER_API_KEY: chave do provider OpenRouter
  - OPENROUTER_BASE_URL: base URL do OpenRouter
  - OLLAMA_URL: base URL OpenAI-compatible/Ollama

DB_TABLES:
  - (nenhuma)
"""
from dataclasses import dataclass
import os


@dataclass(slots=True)
class TargetModel:
    provider: str
    model: str
    model_ref: str


@dataclass(slots=True)
class UpstreamConfig:
    provider: str
    base_url: str
    api_key: str
    upstream_model: str
    auth_mode: str  # "bearer" | "x-goog-api-key"


def parse_target_model(model_ref: str) -> TargetModel:
    if not isinstance(model_ref, str) or not model_ref.startswith("usage-router/"):
        raise ValueError(f"invalid usage-router model ref: {model_ref!r}")

    _, _, remainder = model_ref.partition("usage-router/")
    provider, sep, model = remainder.partition("/")
    if not sep or not provider or not model:
        raise ValueError(f"invalid usage-router model ref: {model_ref!r}")

    return TargetModel(
        provider=provider,
        model=model,
        model_ref=f"{provider}/{model}",
    )


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def resolve_upstream(target: TargetModel, env: dict[str, str] | None = None) -> UpstreamConfig:
    env_map = os.environ if env is None else env
    provider = target.provider
    google_auth_mode = env_map.get("GOOGLE_AUTH_MODE", "gemini_api").strip().lower() or "gemini_api"

    if google_auth_mode == "vertex_oauth":
        google_base_url = env_map.get("GOOGLE_OPENAI_BASE_URL", "")
        google_api_key = env_map.get("GOOGLE_OAUTH_TOKEN", "")
        google_header_mode = "bearer"
    else:
        google_base_url = env_map.get(
            "GOOGLE_GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta",
        )
        google_api_key = env_map.get("GOOGLE_API_KEY", "") or env_map.get("GEMINI_API_KEY", "")
        google_header_mode = "x-goog-api-key"

    provider_map = {
        "groq": (
            env_map.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            env_map.get("GROQ_API_KEY", ""),
            "bearer",
        ),
        "google": (
            google_base_url,
            google_api_key,
            google_header_mode,
        ),
        "mistral": (
            env_map.get("MISTRAL_BASE_URL", "https://api.mistral.ai/v1"),
            env_map.get("MISTRAL_API_KEY", ""),
            "bearer",
        ),
        "cerebras": (
            env_map.get("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1"),
            env_map.get("CEREBRAS_API_KEY", ""),
            "bearer",
        ),
        "qwen": (
            env_map.get(
                "QWEN_BASE_URL",
                "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            ),
            env_map.get("QWEN_API_KEY", ""),
            "bearer",
        ),
        "deepseek": (
            env_map.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            env_map.get("DEEPSEEK_API_KEY", ""),
            "bearer",
        ),
        "openrouter": (
            env_map.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            env_map.get("OPENROUTER_API_KEY", ""),
            "bearer",
        ),
        "ollama": (
            env_map.get("OLLAMA_URL", "http://host.docker.internal:11434/v1"),
            env_map.get("OLLAMA_API_KEY", "ollama-local"),
            "bearer",
        ),
    }

    if provider not in provider_map:
        raise ValueError(f"unsupported provider: {provider!r}")

    base_url, api_key, auth_mode = provider_map[provider]
    return UpstreamConfig(
        provider=provider,
        base_url=_normalize_base_url(base_url),
        api_key=api_key,
        upstream_model=target.model,
        auth_mode=auth_mode,
    )
