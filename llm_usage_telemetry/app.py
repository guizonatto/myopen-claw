"""
Tool: app
Função: Expõe o proxy HTTP da telemetria de LLM com healthcheck e passthrough de requests.
Usar quando: O sidecar `llm-metrics-proxy` estiver rodando no docker-compose.

ENV_VARS:
  - MODEL_USAGE_DB_PATH: caminho do SQLite
  - MODEL_USAGE_PROXY_TIMEOUT_SECONDS: timeout do passthrough HTTP

DB_TABLES:
  - usage_events: leitura+escrita
  - report_dispatches: leitura+escrita
"""
from __future__ import annotations

from dataclasses import asdict
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from llm_usage_telemetry.dispatcher import dispatch_hourly_report
from llm_usage_telemetry.openclaw_sync import load_openclaw_model_refs
from llm_usage_telemetry.service import (
    MetricsProxyService,
    ProxyStreamResult,
    _bucket_start_day,
    _bucket_start_minute,
)
from llm_usage_telemetry.settings import load_settings
from llm_usage_telemetry.storage import get_model_limits, upsert_model_limits


def _to_json_response(result):
    if isinstance(result, ProxyStreamResult):
        return StreamingResponse(
            result.iterator,
            status_code=result.status_code,
            headers=result.headers or {},
            media_type=result.media_type,
        )
    if isinstance(result, dict):
        return JSONResponse(status_code=result["status_code"], content=result["body"])
    return JSONResponse(status_code=result.status_code, content=result.body)


def _headers_with_service(headers: dict[str, str], service_name: str | None = None) -> dict[str, str]:
    merged = dict(headers)
    lower_headers = {key.lower(): value for key, value in headers.items()}
    if service_name and "x-usage-service" not in lower_headers:
        merged["x-usage-service"] = service_name
    if service_name and "x-usage-origin-type" not in lower_headers:
        merged["x-usage-origin-type"] = "service"
    if service_name and "x-usage-origin-name" not in lower_headers:
        merged["x-usage-origin-name"] = service_name
    return merged


def create_app(
    proxy_service: MetricsProxyService | None = None,
    enable_scheduler: bool | None = None,
) -> FastAPI:
    settings = load_settings()
    run_scheduler = enable_scheduler if enable_scheduler is not None else proxy_service is None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime_service = proxy_service or MetricsProxyService(settings)
        scheduler: AsyncIOScheduler | None = None
        sync_task: asyncio.Task | None = None
        app.state.proxy_service = runtime_service

        if run_scheduler:
            scheduler = AsyncIOScheduler(timezone=settings.report_timezone)
            scheduler.add_job(
                dispatch_hourly_report,
                "cron",
                minute=5,
                kwargs={"settings": settings},
                id="llm-usage-hourly-dispatch",
                replace_existing=True,
            )
            scheduler.start()

        async def retry_openclaw_sync():
            delays = (1, 2, 5, 10, 20)
            for delay in delays:
                last = getattr(runtime_service, "last_openclaw_sync", None)
                if isinstance(last, dict) and last.get("ok") and int(last.get("allowlist_models") or 0) > 0:
                    return
                await asyncio.sleep(delay)
                try:
                    result = runtime_service.sync_openclaw_models()
                except Exception as exc:  # pragma: no cover - defensive
                    result = {"ok": False, "error": "openclaw_sync_failed", "message": str(exc)}
                runtime_service.last_openclaw_sync = result
                if isinstance(result, dict) and result.get("ok"):
                    return

        if proxy_service is None and getattr(settings, "sync_openclaw_models", False):
            sync_task = asyncio.create_task(retry_openclaw_sync())

        try:
            yield
        finally:
            if sync_task is not None:
                sync_task.cancel()
            if scheduler is not None and scheduler.running:
                scheduler.shutdown(wait=False)
            runtime_service.close()

    app = FastAPI(title="llm-metrics-proxy", lifespan=lifespan)
    if proxy_service is not None:
        app.state.proxy_service = proxy_service

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    def _require_sqlite(request: Request):
        proxy = getattr(request.app.state, "proxy_service", None)
        conn = getattr(proxy, "conn", None)
        settings = getattr(proxy, "settings", None)
        if conn is None or settings is None:
            raise HTTPException(status_code=503, detail="proxy storage unavailable")
        return proxy, conn, settings

    @app.get("/admin/openclaw/models")
    async def admin_openclaw_models(request: Request):
        _proxy, _conn, settings = _require_sqlite(request)
        try:
            refs = load_openclaw_model_refs(settings.openclaw_config_path)
        except FileNotFoundError:
            raise HTTPException(status_code=503, detail="openclaw config not found")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"failed to read openclaw config: {exc}") from exc

        usage_router_refs = sorted(
            ref for ref in refs if isinstance(ref, str) and ref.startswith("usage-router/")
        )
        return {
            "openclaw_config_path": settings.openclaw_config_path,
            "models": usage_router_refs,
            "count": len(usage_router_refs),
        }

    @app.post("/admin/openclaw/sync-model-limits")
    async def admin_openclaw_sync_model_limits(request: Request):
        proxy, _conn, _settings = _require_sqlite(request)
        result = proxy.sync_openclaw_models()
        proxy.last_openclaw_sync = result
        return result

    @app.get("/admin/openclaw/sync-status")
    async def admin_openclaw_sync_status(request: Request):
        proxy, _conn, _settings = _require_sqlite(request)
        return {"last_sync": getattr(proxy, "last_openclaw_sync", None)}

    @app.get("/admin/model-limits")
    async def admin_model_limits(request: Request):
        _, conn, _settings = _require_sqlite(request)
        rows = conn.execute(
            """
            SELECT
              provider,
              model,
              enabled,
              disabled_reason,
              context_window,
              max_output_tokens,
              rpm,
              rpd,
              tpm,
              tpd,
              updated_at
            FROM model_limits
            ORDER BY provider, model
            """
        ).fetchall()
        return {"models": [dict(row) for row in rows]}

    @app.get("/admin/model-limits/{provider}/{model:path}")
    async def admin_model_limit(provider: str, model: str, request: Request):
        _, conn, _settings = _require_sqlite(request)
        limits = get_model_limits(conn, provider, model)
        if limits is None:
            raise HTTPException(status_code=404, detail="model limits not found")
        return {"model": asdict(limits)}

    @app.post("/admin/model-limits/{provider}/{model:path}")
    async def admin_update_model_limit(provider: str, model: str, request: Request):
        _, conn, _settings = _require_sqlite(request)
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="invalid payload")

        def as_int(key: str):
            if key not in payload:
                return None
            value = payload.get(key)
            if value is None:
                return None
            try:
                return int(value)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"invalid int for {key}") from exc

        enabled = payload.get("enabled") if "enabled" in payload else None
        if enabled is not None:
            enabled = bool(enabled)

        upsert_model_limits(
            conn,
            provider,
            model,
            enabled=enabled,
            disabled_reason=payload.get("disabled_reason")
            if "disabled_reason" in payload
            else None,
            context_window=as_int("context_window"),
            max_output_tokens=as_int("max_output_tokens"),
            rpm=as_int("rpm"),
            rpd=as_int("rpd"),
            tpm=as_int("tpm"),
            tpd=as_int("tpd"),
        )
        limits = get_model_limits(conn, provider, model)
        return {"ok": True, "model": asdict(limits) if limits else None}

    @app.get("/admin/model-usage/{provider}/{model:path}")
    async def admin_model_usage(provider: str, model: str, request: Request):
        proxy, conn, settings = _require_sqlite(request)
        limits = get_model_limits(conn, provider, model)
        now = datetime.now(timezone.utc)
        minute_start = _bucket_start_minute(now).isoformat()
        day_start = _bucket_start_day(now, settings.report_timezone).isoformat()

        def bucket(kind: str, start: str):
            row = conn.execute(
                """
                SELECT requests, tokens
                FROM model_rate_buckets
                WHERE provider = ? AND model = ? AND bucket_kind = ? AND bucket_start = ?
                """,
                (provider, model, kind, start),
            ).fetchone()
            if not row:
                return {"bucket_start": start, "requests": 0, "tokens": 0}
            return {"bucket_start": start, "requests": int(row["requests"]), "tokens": int(row["tokens"])}

        current_minute = bucket("minute", minute_start)
        current_day = bucket("day", day_start)

        response = {
            "provider": provider,
            "model": model,
            "limits": asdict(limits) if limits else None,
            "minute": current_minute,
            "day": current_day,
            "timezone": settings.report_timezone,
        }
        return response

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        payload = await request.json()
        result = await request.app.state.proxy_service.handle_openai_request(
            request_kind="chat",
            payload=payload,
            headers=_headers_with_service(dict(request.headers)),
        )
        return _to_json_response(result)

    @app.post("/v1/responses")
    async def responses(request: Request):
        payload = await request.json()
        result = await request.app.state.proxy_service.handle_openai_request(
            request_kind="responses",
            payload=payload,
            headers=_headers_with_service(dict(request.headers)),
        )
        return _to_json_response(result)

    @app.post("/v1/embeddings")
    async def embeddings(request: Request):
        payload = await request.json()
        result = await request.app.state.proxy_service.handle_openai_request(
            request_kind="embedding",
            payload=payload,
            headers=_headers_with_service(dict(request.headers)),
        )
        return _to_json_response(result)

    @app.post("/api/embeddings")
    async def ollama_embeddings(request: Request):
        payload = await request.json()
        result = await request.app.state.proxy_service.handle_ollama_embedding(
            payload=payload,
            headers=_headers_with_service(dict(request.headers)),
        )
        return _to_json_response(result)

    @app.post("/{service_name}/v1/chat/completions")
    async def scoped_chat_completions(service_name: str, request: Request):
        payload = await request.json()
        result = await request.app.state.proxy_service.handle_openai_request(
            request_kind="chat",
            payload=payload,
            headers=_headers_with_service(dict(request.headers), service_name),
        )
        return _to_json_response(result)

    @app.post("/{service_name}/v1/responses")
    async def scoped_responses(service_name: str, request: Request):
        payload = await request.json()
        result = await request.app.state.proxy_service.handle_openai_request(
            request_kind="responses",
            payload=payload,
            headers=_headers_with_service(dict(request.headers), service_name),
        )
        return _to_json_response(result)

    @app.post("/{service_name}/v1/embeddings")
    async def scoped_embeddings(service_name: str, request: Request):
        payload = await request.json()
        result = await request.app.state.proxy_service.handle_openai_request(
            request_kind="embedding",
            payload=payload,
            headers=_headers_with_service(dict(request.headers), service_name),
        )
        return _to_json_response(result)

    @app.post("/{service_name}/api/embeddings")
    async def scoped_ollama_embeddings(service_name: str, request: Request):
        payload = await request.json()
        result = await request.app.state.proxy_service.handle_ollama_embedding(
            payload=payload,
            headers=_headers_with_service(dict(request.headers), service_name),
        )
        return _to_json_response(result)

    return app


app = create_app()
