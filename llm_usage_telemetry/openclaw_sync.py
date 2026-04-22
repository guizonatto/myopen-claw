"""
Tool: openclaw_sync
Função: Sincroniza a tabela model_limits com o conjunto de modelos configurados no OpenClaw.
Usar quando: Precisar garantir que o llm-metrics-proxy reflita (espelhe) a lista de models/providers do OpenClaw.

ENV_VARS:
  - OPENCLAW_CONFIG_PATH: caminho do openclaw.json (montado do volume openclaw-data)
  - MODEL_USAGE_SYNC_OPENCLAW_MODELS: habilita o sync no startup
  - MODEL_USAGE_SYNC_OPENCLAW_MODELS_STRICT: desabilita modelos fora do OpenClaw (opcional)

DB_TABLES:
  - model_limits: leitura+escrita
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from llm_usage_telemetry.model_limits_catalog import ModelLimitsCatalog, load_model_limits_catalog
from llm_usage_telemetry.storage import get_model_limits, upsert_model_limits
from llm_usage_telemetry.upstreams import parse_target_model


MIRROR_DISABLED_REASON = "not_in_openclaw_config"


def _add_model_ref(candidate: Any, out: set[str]) -> None:
    if isinstance(candidate, str) and candidate:
        out.add(candidate)


def extract_openclaw_model_refs(openclaw_config: Any) -> set[str]:
    refs: set[str] = set()
    if not isinstance(openclaw_config, dict):
        return refs

    agents = openclaw_config.get("agents") or {}
    if isinstance(agents, dict):
        defaults = agents.get("defaults") or {}
        if isinstance(defaults, dict):
            model_cfg = defaults.get("model") or {}
            if isinstance(model_cfg, dict):
                _add_model_ref(model_cfg.get("primary"), refs)
                fallbacks = model_cfg.get("fallbacks")
                if isinstance(fallbacks, list):
                    for item in fallbacks:
                        _add_model_ref(item, refs)

            models_map = defaults.get("models")
            if isinstance(models_map, dict):
                for key in models_map.keys():
                    _add_model_ref(key, refs)

    # Future-proofing: some configs may pin models at other scopes (agents list, skills, etc.).
    # Keep this conservative; we only need a reliable allowlist, not every possible reference.
    return refs


def load_openclaw_model_refs(config_path: str | Path) -> set[str]:
    path = Path(config_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return extract_openclaw_model_refs(payload)


def sync_model_limits_from_openclaw_config_path(
    conn: Any,
    config_path: str | Path,
    *,
    default_rpm_by_provider: dict[str, int],
    rpm_fallback: int,
    strict: bool = False,
    catalog_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        return {"ok": False, "error": "openclaw_config_not_found", "path": str(path)}
    if not path.is_file():
        return {"ok": False, "error": "openclaw_config_not_file", "path": str(path)}

    try:
        model_refs = load_openclaw_model_refs(path)
    except Exception as exc:  # pragma: no cover - defensive; invalid configs should not crash proxy
        return {
            "ok": False,
            "error": "openclaw_config_invalid_json",
            "path": str(path),
            "message": str(exc),
        }

    allowlist: set[tuple[str, str]] = set()
    invalid_refs: list[str] = []
    for model_ref in sorted(model_refs):
        if not isinstance(model_ref, str) or not model_ref.startswith("usage-router/"):
            continue
        try:
            target = parse_target_model(model_ref)
        except Exception:
            invalid_refs.append(model_ref)
            continue
        allowlist.add((target.provider, target.model))

    created = 0
    rpm_seeded = 0
    rpm_overridden = 0
    catalog_seeded = 0
    mirror_enabled = 0
    mirror_disabled = 0

    catalog: ModelLimitsCatalog | None = None
    catalog_info: dict[str, Any] = {"path": str(catalog_path) if catalog_path else None, "loaded": False}
    if catalog_path:
        try:
            path_obj = Path(catalog_path)
            if path_obj.exists() and path_obj.is_file():
                catalog = load_model_limits_catalog(path_obj)
                catalog_info["loaded"] = True
            else:
                catalog_info["error"] = "catalog_not_found"
        except Exception as exc:  # pragma: no cover - defensive: bad JSON should not crash the proxy
            catalog_info["error"] = "catalog_invalid"
            catalog_info["message"] = str(exc)

    # Ensure allowlisted models exist in model_limits.
    for provider, model in sorted(allowlist):
        existing = get_model_limits(conn, provider, model)
        default_rpm = int(default_rpm_by_provider.get(provider, rpm_fallback))
        seed = catalog.lookup(provider, model) if catalog else None
        desired_rpm = seed.rpm if seed and seed.rpm is not None else default_rpm

        fields: dict[str, int | None] = {}
        if existing is None or (existing.context_window is None and seed and seed.context_window is not None):
            fields["context_window"] = seed.context_window if seed else None
        if existing is None or (
            existing.max_output_tokens is None and seed and seed.max_output_tokens is not None
        ):
            fields["max_output_tokens"] = seed.max_output_tokens if seed else None
        if existing is None:
            fields["rpm"] = desired_rpm
        elif existing.rpm is None:
            fields["rpm"] = desired_rpm
        elif seed and seed.rpm is not None and existing.rpm != desired_rpm and (
            int(existing.rpm) <= 0 or int(existing.rpm) in {rpm_fallback, default_rpm}
        ):
            # If a previous run seeded a placeholder RPM (fallback/default), upgrade to the catalog value.
            fields["rpm"] = desired_rpm
            rpm_overridden += 1
        if existing is None or (existing.rpd is None and seed and seed.rpd is not None):
            fields["rpd"] = seed.rpd if seed else None
        if existing is None or (existing.tpm is None and seed and seed.tpm is not None):
            fields["tpm"] = seed.tpm if seed else None
        if existing is None or (existing.tpd is None and seed and seed.tpd is not None):
            fields["tpd"] = seed.tpd if seed else None

        if existing is None:
            upsert_model_limits(
                conn,
                provider,
                model,
                context_window=fields.get("context_window"),
                max_output_tokens=fields.get("max_output_tokens"),
                rpm=fields.get("rpm"),
                rpd=fields.get("rpd"),
                tpm=fields.get("tpm"),
                tpd=fields.get("tpd"),
            )
            created += 1
            continue
        else:
            rpm_to_seed = fields.get("rpm")
            if rpm_to_seed is not None and existing.rpm is None:
                rpm_seeded += 1
            catalog_seeded += sum(
                1
                for key in ("context_window", "max_output_tokens", "rpd", "tpm", "tpd")
                if fields.get(key) is not None
            )
            if any(value is not None for value in fields.values()):
                upsert_model_limits(
                    conn,
                    provider,
                    model,
                    context_window=fields.get("context_window"),
                    max_output_tokens=fields.get("max_output_tokens"),
                    rpm=fields.get("rpm"),
                    rpd=fields.get("rpd"),
                    tpm=fields.get("tpm"),
                    tpd=fields.get("tpd"),
                )

        if strict and not existing.enabled and existing.disabled_reason in {
            MIRROR_DISABLED_REASON,
            "model_not_found",
        }:
            conn.execute(
                """
                UPDATE model_limits
                SET enabled = 1,
                    disabled_reason = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE provider = ? AND model = ? AND disabled_reason = ?
                """,
                (provider, model, existing.disabled_reason),
            )
            mirror_enabled += 1

    extras: list[tuple[str, str]] = []
    if strict and allowlist:
        rows = conn.execute("SELECT provider, model, enabled FROM model_limits").fetchall()
        for row in rows:
            key = (row["provider"], row["model"])
            if key in allowlist:
                continue
            extras.append(key)
            if int(row["enabled"] or 0) != 1:
                continue
            conn.execute(
                """
                UPDATE model_limits
                SET enabled = 0,
                    disabled_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE provider = ? AND model = ? AND enabled = 1
                """,
                (MIRROR_DISABLED_REASON, key[0], key[1]),
            )
            mirror_disabled += 1
        conn.commit()

    return {
        "ok": True,
        "openclaw_config_path": str(path),
        "allowlist_models": len(allowlist),
        "created": created,
        "rpm_seeded": rpm_seeded,
        "rpm_overridden": rpm_overridden,
        "catalog_seeded": catalog_seeded,
        "catalog": catalog_info,
        "strict": bool(strict),
        "mirror_enabled": mirror_enabled,
        "mirror_disabled": mirror_disabled,
        "extras": [{"provider": p, "model": m} for p, m in sorted(extras)],
        "invalid_refs": invalid_refs,
    }
