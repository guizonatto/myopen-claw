"""
Tool: model_limits_catalog
Função: Carrega um catálogo (JSON) opcional com limites por provider/model para preencher a tabela `model_limits`.
Usar quando: Precisar definir valores de rpm/tpm/rpd/tpd/context_window/max_output_tokens sem hardcode no banco.

Formato esperado (exemplo):
{
  "version": "2026-04-21",
  "providers": {
    "google": {
      "defaults": {"rpm": 5, "tpm": 250000, "rpd": 20},
      "models": {
        "gemini-3.1-flash-lite-preview": {"rpm": 15, "rpd": 500}
      }
    }
  }
}
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


DEFAULT_MODEL_LIMITS_CATALOG_PATH = "/openclaw/workspace/configs/model-limits.json"


@dataclass(frozen=True, slots=True)
class ModelLimitSeed:
    context_window: int | None = None
    max_output_tokens: int | None = None
    rpm: int | None = None
    rpd: int | None = None
    tpm: int | None = None
    tpd: int | None = None

    def merge(self, override: "ModelLimitSeed") -> "ModelLimitSeed":
        return ModelLimitSeed(
            context_window=self.context_window if override.context_window is None else override.context_window,
            max_output_tokens=self.max_output_tokens
            if override.max_output_tokens is None
            else override.max_output_tokens,
            rpm=self.rpm if override.rpm is None else override.rpm,
            rpd=self.rpd if override.rpd is None else override.rpd,
            tpm=self.tpm if override.tpm is None else override.tpm,
            tpd=self.tpd if override.tpd is None else override.tpd,
        )


@dataclass(frozen=True, slots=True)
class ProviderCatalog:
    defaults: ModelLimitSeed
    models: dict[str, ModelLimitSeed]

    def lookup(self, model: str) -> ModelLimitSeed | None:
        if not model:
            return None
        override = self.models.get(model)
        return self.defaults.merge(override) if override else self.defaults


@dataclass(frozen=True, slots=True)
class ModelLimitsCatalog:
    providers: dict[str, ProviderCatalog]

    def lookup(self, provider: str, model: str) -> ModelLimitSeed | None:
        if not provider or not model:
            return None
        provider_cfg = self.providers.get(provider)
        if provider_cfg is None:
            return None
        return provider_cfg.lookup(model)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except Exception:
            return None
    return None


def _seed_from_mapping(mapping: Any) -> ModelLimitSeed:
    if not isinstance(mapping, dict):
        return ModelLimitSeed()
    return ModelLimitSeed(
        context_window=_as_int(mapping.get("context_window")),
        max_output_tokens=_as_int(mapping.get("max_output_tokens")),
        rpm=_as_int(mapping.get("rpm")),
        rpd=_as_int(mapping.get("rpd")),
        tpm=_as_int(mapping.get("tpm")),
        tpd=_as_int(mapping.get("tpd")),
    )


def load_model_limits_catalog(path: str | Path) -> ModelLimitsCatalog:
    raw = Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("model limits catalog must be a JSON object")

    providers_raw = payload.get("providers") or {}
    if not isinstance(providers_raw, dict):
        raise ValueError("'providers' must be an object")

    providers: dict[str, ProviderCatalog] = {}
    for provider, provider_payload in providers_raw.items():
        if not isinstance(provider, str) or not provider.strip():
            continue
        if not isinstance(provider_payload, dict):
            continue

        defaults = _seed_from_mapping(provider_payload.get("defaults") or {})
        models_raw = provider_payload.get("models") or {}
        models: dict[str, ModelLimitSeed] = {}
        if isinstance(models_raw, dict):
            for model, model_payload in models_raw.items():
                if not isinstance(model, str) or not model.strip():
                    continue
                models[model] = _seed_from_mapping(model_payload)

        providers[provider.strip()] = ProviderCatalog(defaults=defaults, models=models)

    return ModelLimitsCatalog(providers=providers)

