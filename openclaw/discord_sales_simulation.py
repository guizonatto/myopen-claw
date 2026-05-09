from __future__ import annotations

import json
import hashlib
import logging
import math
import os
import re
import shlex
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import requests


LOGGER = logging.getLogger(__name__)
SIM_COMMAND_PREFIX = "sim start"
DEFAULT_STAGE = "lead"
DEFAULT_DIFFICULTY = "medium"
DEFAULT_MAX_TURNS = 20
DEFAULT_TIMEOUT_SECONDS = 900
DISCORD_CONTENT_LIMIT = 1800
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_QDRANT_COLLECTIONS_PREFERRED = ("cortex_memories_tenant_claw", "cortex_memories")
DEFAULT_ZIND_CONTEXT_RELATIVE_FILES = (
    "2000-Knowledge/Empresas/Zind/ZIND_MOC.md",
    "2000-Knowledge/Empresas/Zind/PITCH_VENDAS.md",
    "0000-Atlas/Zind.md",
)
DEFAULT_ZIND_BRAND_GUARDRAIL = (
    "Você representa exclusivamente a Zind (https://zind.pro). "
    "Nunca cite outra empresa/marca como se fosse sua."
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    normalized = normalized.strip("_")
    return normalized or "unknown"


def _split_env_list(raw_value: str) -> list[str]:
    chunks = re.split(r"[;,]", raw_value or "")
    return [chunk.strip() for chunk in chunks if chunk and chunk.strip()]


def _compact_excerpt(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) <= max_chars:
        return compact
    clipped = compact[:max_chars].rstrip()
    return f"{clipped}..."


def _candidate_zind_context_paths() -> list[Path]:
    explicit_paths = _split_env_list(os.environ.get("SALES_SIM_ZIND_CONTEXT_FILES", ""))
    if explicit_paths:
        return [Path(path) for path in explicit_paths]

    explicit_roots = _split_env_list(os.environ.get("SALES_SIM_VAULT_ROOTS", ""))
    if explicit_roots:
        roots = [Path(root) for root in explicit_roots]
    else:
        roots = [Path("/vault/Pessoal"), Path("/vault")]

    candidates: list[Path] = []
    for root in roots:
        for relative_file in DEFAULT_ZIND_CONTEXT_RELATIVE_FILES:
            candidates.append(root / relative_file)
    return candidates


def load_zind_company_context(*, max_total_chars: int = 1800, per_file_chars: int = 700) -> tuple[str, list[str]]:
    remaining = max(max_total_chars, 200)
    snippets: list[str] = []
    sources: list[str] = []
    seen_sources: set[str] = set()

    for path in _candidate_zind_context_paths():
        resolved = str(path)
        if resolved in seen_sources:
            continue
        seen_sources.add(resolved)
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        excerpt_cap = max(220, min(per_file_chars, remaining))
        excerpt = _compact_excerpt(text, excerpt_cap)
        if not excerpt:
            continue
        snippets.append(f"[{path.name}] {excerpt}")
        sources.append(str(path))
        remaining -= len(excerpt)
        if remaining <= 0:
            break

    if not snippets:
        fallback = (
            "Zind é uma plataforma para síndicos profissionais, focada em organizar processos internos "
            "do síndico (não do condomínio)."
        )
        return fallback, sources

    return "\n".join(snippets), sources


def _load_zind_context_documents(source_paths: list[str] | None = None) -> list[dict[str, str]]:
    paths = [Path(path) for path in source_paths] if source_paths else _candidate_zind_context_paths()
    docs: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in paths:
        resolved = str(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        if not path.exists() or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not content.strip():
            continue
        docs.append({"source_path": resolved, "content": content})
    return docs


def _chunk_text_for_qdrant(text: str, *, max_chars: int = 1100, overlap_chars: int = 180) -> list[str]:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if not compact:
        return []
    if len(compact) <= max_chars:
        return [compact]

    chunks: list[str] = []
    start = 0
    step = max(120, max_chars - max(0, overlap_chars))
    while start < len(compact):
        end = min(len(compact), start + max_chars)
        chunks.append(compact[start:end].strip())
        if end >= len(compact):
            break
        start += step
    return [chunk for chunk in chunks if chunk]


def _ensure_vector_dim(vector: list[float], *, dim: int) -> list[float]:
    if dim <= 0:
        return vector
    if len(vector) == dim:
        return vector
    if len(vector) > dim:
        return vector[:dim]
    return vector + [0.0] * (dim - len(vector))


def _pseudo_embedding(text: str, *, dim: int) -> list[float]:
    digest = hashlib.sha256((text or "").encode("utf-8")).digest()
    if dim <= 0:
        return []
    values: list[float] = []
    for idx in range(dim):
        value = digest[idx % len(digest)]
        values.append((value / 127.5) - 1.0)
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def _embed_text_for_qdrant(text: str, *, vector_dim: int) -> tuple[list[float], str]:
    embedding_model = (
        os.environ.get("EMBEDDING_MODEL")
        or os.environ.get("MEMORY_EMBEDDING_MODEL")
        or "qwen3-embedding:0.6b"
    )

    # 1) OpenAI-compatible embeddings endpoint (preferred)
    openai_candidates = [
        (os.environ.get("EMBEDDING_API_BASE_URL") or "").strip(),
        (os.environ.get("MEMORY_EMBEDDING_API_BASE_URL") or "").strip(),
        "http://localhost:8080/memclaw/v1",
        "http://llm-metrics-proxy:8080/memclaw/v1",
    ]
    openai_key = (
        os.environ.get("EMBEDDING_API_KEY")
        or os.environ.get("MEMORY_EMBEDDING_API_KEY")
        or "ollama"
    )
    for openai_base in [item for item in openai_candidates if item]:
        try:
            response = requests.post(
                f"{openai_base.rstrip('/')}/embeddings",
                json={"model": embedding_model, "input": text},
                headers={"Authorization": f"Bearer {openai_key}"},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            if rows and isinstance(rows[0], dict):
                embedding = rows[0].get("embedding")
                if isinstance(embedding, list) and embedding:
                    return _ensure_vector_dim([float(v) for v in embedding], dim=vector_dim), "openai-compatible"
        except Exception:
            pass

    # 2) Ollama embeddings API fallback
    ollama_candidates = [
        (os.environ.get("OLLAMA_BASE_URL") or "").strip(),
        "http://localhost:11434",
        "http://host.docker.internal:11434",
    ]
    for ollama_base in [item for item in ollama_candidates if item]:
        try:
            response = requests.post(
                f"{ollama_base.rstrip('/')}/api/embeddings",
                json={"model": embedding_model, "prompt": text},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            embedding = payload.get("embedding") if isinstance(payload, dict) else None
            if isinstance(embedding, list) and embedding:
                return _ensure_vector_dim([float(v) for v in embedding], dim=vector_dim), "ollama"
        except Exception:
            pass

    # 3) Deterministic fallback (keeps indexable payload even if embedding provider is down)
    return _pseudo_embedding(text, dim=vector_dim), "pseudo"


def _extract_qdrant_vector_spec(collection_payload: dict[str, Any]) -> tuple[int, str | None]:
    result = collection_payload.get("result", {}) if isinstance(collection_payload, dict) else {}
    config = result.get("config", {}) if isinstance(result, dict) else {}
    params = config.get("params", {}) if isinstance(config, dict) else {}
    vectors = params.get("vectors")
    if isinstance(vectors, dict):
        if isinstance(vectors.get("size"), int):
            return int(vectors["size"]), None
        for name, cfg in vectors.items():
            if isinstance(cfg, dict) and isinstance(cfg.get("size"), int):
                return int(cfg["size"]), str(name)
    return 256, None


def _resolve_qdrant_target_collection(qdrant_base: str) -> tuple[str | None, int, str | None, list[str]]:
    response = requests.get(f"{qdrant_base}/collections", timeout=10)
    response.raise_for_status()
    payload = response.json()
    collections = payload.get("result", {}).get("collections", []) if isinstance(payload, dict) else []
    names = [str(item.get("name")) for item in collections if isinstance(item, dict) and item.get("name")]
    if not names:
        return None, 256, None, []
    collection_name = next((name for name in DEFAULT_QDRANT_COLLECTIONS_PREFERRED if name in names), names[0])
    detail_response = requests.get(f"{qdrant_base}/collections/{collection_name}", timeout=10)
    detail_response.raise_for_status()
    vector_dim, vector_name = _extract_qdrant_vector_spec(detail_response.json())
    return collection_name, vector_dim, vector_name, names


def sync_zind_context_to_qdrant(
    *,
    source_paths: list[str] | None = None,
    qdrant_url: str | None = None,
    chunk_chars: int = 1100,
    overlap_chars: int = 180,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "skipped",
        "upserted_points": 0,
        "collection": None,
        "vector_dim": None,
        "vector_name": None,
        "embedding_provider": None,
        "warnings": [],
    }
    docs = _load_zind_context_documents(source_paths=source_paths)
    if not docs:
        report["warnings"].append("Nenhum documento Zind encontrado para sincronizar.")
        return report

    qdrant_base = (qdrant_url or os.environ.get("QDRANT_URL") or DEFAULT_QDRANT_URL).rstrip("/")
    try:
        collection, vector_dim, vector_name, all_collections = _resolve_qdrant_target_collection(qdrant_base)
    except Exception as exc:
        report["status"] = "error"
        report["error"] = f"Falha ao resolver coleção Qdrant: {exc}"
        return report

    if not collection:
        report["status"] = "error"
        report["error"] = "Nenhuma coleção disponível no Qdrant."
        return report

    report["collection"] = collection
    report["vector_dim"] = vector_dim
    report["vector_name"] = vector_name
    report["collections_seen"] = all_collections

    points: list[dict[str, Any]] = []
    provider_last = "pseudo"
    for doc in docs:
        source_path = doc["source_path"]
        chunks = _chunk_text_for_qdrant(doc["content"], max_chars=chunk_chars, overlap_chars=overlap_chars)
        for chunk_index, chunk in enumerate(chunks):
            embedding, provider = _embed_text_for_qdrant(chunk, vector_dim=vector_dim)
            provider_last = provider
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"zind-vault::{source_path}::{chunk_index}"))
            payload = {
                "brand": "zind",
                "source": "zind_vault_sync",
                "source_path": source_path,
                "chunk_index": chunk_index,
                "content": chunk,
                "created_at": _utcnow().isoformat(),
            }
            vector_payload: Any
            if vector_name:
                vector_payload = {vector_name: embedding}
            else:
                vector_payload = embedding
            points.append({"id": point_id, "vector": vector_payload, "payload": payload})

    if not points:
        report["warnings"].append("Documentos encontrados, mas nenhum chunk gerado para sincronização.")
        return report

    try:
        for start in range(0, len(points), 16):
            batch = points[start : start + 16]
            response = requests.put(
                f"{qdrant_base}/collections/{collection}/points?wait=true",
                json={"points": batch},
                timeout=30,
            )
            response.raise_for_status()
        report["status"] = "ok"
        report["upserted_points"] = len(points)
        report["embedding_provider"] = provider_last
        report["source_paths"] = [doc["source_path"] for doc in docs]
        return report
    except Exception as exc:
        report["status"] = "error"
        report["error"] = f"Falha no upsert Qdrant: {exc}"
        report["upserted_points"] = 0
        return report


def probe_memory_health(*, qdrant_url: str | None = None, sample_limit: int = 120) -> dict[str, Any]:
    health: dict[str, Any] = {
        "vault_has_zind_context": False,
        "qdrant_has_zind_context": None,
        "qdrant_collections": [],
    }
    qdrant_base = (qdrant_url or os.environ.get("QDRANT_URL") or DEFAULT_QDRANT_URL).rstrip("/")
    try:
        response = requests.get(f"{qdrant_base}/collections", timeout=8)
        response.raise_for_status()
        payload = response.json()
        collections = payload.get("result", {}).get("collections", []) if isinstance(payload, dict) else []
        names = [str(item.get("name")) for item in collections if isinstance(item, dict) and item.get("name")]
        health["qdrant_collections"] = names

        has_zind = False
        for name in names:
            body = {"limit": sample_limit, "with_payload": True, "with_vector": False}
            scroll = requests.post(
                f"{qdrant_base}/collections/{name}/points/scroll",
                json=body,
                timeout=10,
            )
            scroll.raise_for_status()
            scroll_payload = scroll.json()
            points = scroll_payload.get("result", {}).get("points", []) if isinstance(scroll_payload, dict) else []
            for point in points:
                if not isinstance(point, dict):
                    continue
                payload_value = point.get("payload", {})
                payload_text = json.dumps(payload_value, ensure_ascii=False).lower()
                if "zind" in payload_text:
                    has_zind = True
                    break
            if has_zind:
                break
        health["qdrant_has_zind_context"] = has_zind
    except Exception as exc:  # pragma: no cover - non-deterministic infra conditions
        health["qdrant_has_zind_context"] = None
        health["qdrant_error"] = str(exc)

    return health


def _apply_zind_brand_guardrails(text: str) -> tuple[str, bool]:
    if not text:
        return text, False
    guarded = text
    replaced = False
    brand_patterns = [
        r"(?i)\bcondoseg\b",
        r"(?i)\bcondoconta\b",
        r"(?i)\bc[oó]digo\s+do\s+s[ií]ndico\b",
        r"(?i)\bvida\s+de\s+s[ií]ndico\b",
    ]
    for pattern in brand_patterns:
        updated = re.sub(pattern, "Zind", guarded)
        if updated != guarded:
            replaced = True
            guarded = updated
    return guarded, replaced


def command_examples() -> list[str]:
    return [
        'sim start city=sao_paulo stage=lead persona="sindico conservador"',
        'sim start city=campinas stage=qualificado persona="sindica objetiva focada em custo" difficulty=hard',
        'sim start city=sao_paulo stage=lead persona="sindico profissional" --human',
    ]


class SimulationParseError(ValueError):
    pass


@dataclass(frozen=True)
class SimulationScenario:
    city: str
    stage: str
    persona: str
    difficulty: str
    command_text: str
    human_mode: bool = False


@dataclass(frozen=True)
class SimulationSessionIds:
    sales: str
    client: str


@dataclass(frozen=True)
class SimulationTurnRecord:
    turn: int
    role: str
    agent_id: str
    message: str
    created_at: str
    payload: dict[str, Any] | None = None

    def to_json(self) -> str:
        body = {
            "turn": self.turn,
            "role": self.role,
            "agent_id": self.agent_id,
            "message": self.message,
            "created_at": self.created_at,
            "payload": self.payload or {},
        }
        return json.dumps(body, ensure_ascii=False)


class AgentInvoker(Protocol):
    def invoke(self, *, agent_id: str, session_id: str, message: str, timeout_seconds: int) -> str:
        ...


class ChannelPublisher(Protocol):
    def create_thread(self, *, parent_channel_id: str, name: str, source_message_id: str | None = None) -> str:
        ...

    def send_message(self, *, channel_id: str, content: str) -> str | None:
        ...


@dataclass
class SimulationStorage:
    base_dir: Path

    def persist(
        self,
        *,
        run_id: str,
        metadata: dict[str, Any],
        transcript: list[SimulationTurnRecord],
    ) -> dict[str, str]:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = self.base_dir / f"{run_id}.json"
        transcript_path = self.base_dir / f"{run_id}.transcript.jsonl"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        with transcript_path.open("w", encoding="utf-8") as fh:
            for item in transcript:
                fh.write(item.to_json() + "\n")
        return {
            "metadata_path": str(metadata_path.resolve()),
            "transcript_path": str(transcript_path.resolve()),
        }


def parse_sim_start_command(command_text: str) -> SimulationScenario:
    raw = (command_text or "").strip()
    if not raw.lower().startswith(SIM_COMMAND_PREFIX):
        raise SimulationParseError(
            f"Comando inválido. Use '{SIM_COMMAND_PREFIX} ...'. Exemplo: {command_examples()[0]}"
        )

    tail = raw[len(SIM_COMMAND_PREFIX) :].strip()
    if not tail:
        raise SimulationParseError(
            "Parâmetros ausentes. Obrigatório: city=..., persona=... "
            f"Exemplo: {command_examples()[0]}"
        )

    # Detect --human flag before shlex parsing (it's not a key=value token)
    human_mode = "--human" in tail
    tail_clean = tail.replace("--human", "").strip()

    try:
        tokens = shlex.split(tail_clean)
    except ValueError as exc:
        raise SimulationParseError(f"Erro de parsing do comando: {exc}") from exc

    data: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            raise SimulationParseError(
                f"Parâmetro inválido '{token}'. Use formato chave=valor. Exemplo: {command_examples()[0]}"
            )
        key, value = token.split("=", 1)
        key_clean = _slug(key)
        value_clean = value.strip()
        if not value_clean:
            raise SimulationParseError(f"Parâmetro '{key}' vazio.")
        data[key_clean] = value_clean

    city = data.get("city", "").strip()
    persona = data.get("persona", "").strip()
    if not city or not persona:
        raise SimulationParseError(
            "Campos obrigatórios ausentes: city e persona. "
            f"Exemplo: {command_examples()[0]}"
        )

    stage_raw = _slug(data.get("stage", DEFAULT_STAGE))
    stage_aliases = {
        "qualificacao": "qualificado",
        "qualifica_o": "qualificado",
        "qualification": "qualificado",
    }
    stage = stage_aliases.get(stage_raw, stage_raw)
    difficulty = _slug(data.get("difficulty", DEFAULT_DIFFICULTY))
    allowed_stages = {"lead", "qualificado", "interesse", "proposta", "follow_up"}
    if stage not in allowed_stages:
        raise SimulationParseError(f"stage inválido '{stage}'. Permitidos: {', '.join(sorted(allowed_stages))}.")

    allowed_difficulties = {"easy", "medium", "hard"}
    if difficulty not in allowed_difficulties:
        raise SimulationParseError(
            f"difficulty inválido '{difficulty}'. Permitidos: {', '.join(sorted(allowed_difficulties))}."
        )

    return SimulationScenario(
        city=_slug(city),
        stage=stage,
        persona=persona,
        difficulty=difficulty,
        command_text=raw,
        human_mode=human_mode,
    )


SALES_AGENT_ID = "zind-crm-cold-contact"


def build_session_ids(run_id: str) -> SimulationSessionIds:
    rid = _slug(run_id)
    return SimulationSessionIds(
        sales=f"agent:{SALES_AGENT_ID}:session:sim:{rid}:sales",
        client=f"agent:sindico-sim:session:sim:{rid}:client",
    )


def _extract_json_object(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _normalize_bool_flag(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "sim"}:
            return True
        if lowered in {"false", "0", "no", "nao", "não"}:
            return False
    return None


def _normalize_client_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    reply = parsed.get("reply")
    end = _normalize_bool_flag(parsed.get("end"))
    if not isinstance(reply, str) or not reply.strip():
        raise SimulationParseError("Campo obrigatório 'reply' ausente ou vazio.")
    if end is None:
        raise SimulationParseError("Campo obrigatório 'end' ausente ou inválido (bool).")

    output = {
        "reply": reply.strip(),
        "end": end,
        "end_reason": str(parsed.get("end_reason", "")).strip() or None,
        "objection_type": str(parsed.get("objection_type", "")).strip() or None,
        "sentiment": str(parsed.get("sentiment", "")).strip() or None,
    }
    return output


def _extract_json_candidates(text: str) -> list[str]:
    if not text:
        return []
    stripped = text.strip()
    candidates: list[str] = []
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)
    if stripped.startswith("```"):
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
        if fence:
            candidates.append(fence.group(1).strip())
    extracted = _extract_json_object(stripped)
    if extracted:
        candidates.append(extracted)
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def parse_client_simulator_payload(raw_payload: str) -> dict[str, Any]:
    extracted_reply = _extract_agent_reply(raw_payload)
    payload_sources = [extracted_reply, raw_payload]
    candidate_pool: list[str] = []
    for source in payload_sources:
        candidate_pool.extend(_extract_json_candidates(source))
    # keep order, remove duplicates
    candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidate_pool:
        if candidate in seen:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    if not candidates:
        raise SimulationParseError("Resposta do simulador sem JSON válido.")

    errors: list[str] = []
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            errors.append(str(exc))
            continue
        if not isinstance(parsed, dict):
            errors.append("payload não é objeto JSON")
            continue
        try:
            return _normalize_client_payload(parsed)
        except SimulationParseError as exc:
            errors.append(str(exc))
            continue

    joined = "; ".join(errors[:3]) if errors else "sem detalhes"
    raise SimulationParseError(f"JSON inválido do simulador: {joined}")


def _coerce_unstructured_client_payload(raw_payload: str) -> dict[str, Any] | None:
    text = _extract_agent_reply(raw_payload).strip()
    if not text:
        return None
    # Keep strict JSON failure for clearly broken JSON-looking payloads.
    if text.startswith("{") or text.startswith("["):
        try:
            json.loads(text)
        except json.JSONDecodeError:
            return None
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return None
    if len(compact) > 360:
        compact = compact[:357].rstrip() + "..."
    lowered = compact.lower()
    slugged = _slug(compact)
    no_interest_markers = {
        "sem_interesse",
        "nao_tenho_interesse",
        "não_tenho_interesse",
        "no_interest",
    }
    no_interest_phrases = {
        "não tenho interesse",
        "nao tenho interesse",
        "sem interesse",
        "no interest",
    }
    end = any(marker in slugged for marker in no_interest_markers) or any(
        phrase in lowered for phrase in no_interest_phrases
    )
    end_reason = "no_interest_unstructured" if end else None
    return {
        "reply": compact,
        "end": end,
        "end_reason": end_reason,
        "objection_type": None,
        "sentiment": None,
        "_fallback_unstructured": True,
    }


def parse_client_simulator_payload_or_fallback(raw_payload: str) -> tuple[dict[str, Any], bool]:
    try:
        return parse_client_simulator_payload(raw_payload), False
    except SimulationParseError:
        fallback = _coerce_unstructured_client_payload(raw_payload)
        if fallback is None:
            raise
        return fallback, True


def _json_dumps_short(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


_AGENTS_MD_CACHE: dict[str, str] = {}

def _load_agent_config(agent_dir: str, filename: str = "AGENTS.md") -> str:
    """Load agent config file, cache it for the process lifetime."""
    key = f"{agent_dir}/{filename}"
    if key not in _AGENTS_MD_CACHE:
        path = Path(agent_dir) / filename
        try:
            _AGENTS_MD_CACHE[key] = path.read_text(encoding="utf-8")
        except OSError:
            _AGENTS_MD_CACHE[key] = ""
    return _AGENTS_MD_CACHE[key]


def _detect_action_from_turn(turn: int) -> int:
    """Map simulation turn to Protocol 1 action number (1-4)."""
    return min(turn, 4)


_COLD_CONTACT_DIR = str(Path(__file__).parent.parent / "agents" / "zind-crm-cold-contact")
_SKILLS_DIR = str(Path(__file__).parent.parent / "skills" / "crm" / "library")


def build_sales_prompt(
    *,
    scenario: SimulationScenario,
    turn: int,
    previous_client_reply: str | None,
    company_context: str | None = None,
) -> str:
    context = previous_client_reply or "(início da conversa — nenhuma fala do cliente ainda)"
    company_context_block = _compact_excerpt(company_context or "", 600)
    memory_block = f"Contexto de memória da Zind (Vault):\n{company_context_block}\n\n" if company_context_block else ""

    action = _detect_action_from_turn(turn)
    outbound_events = turn - 1

    # Structured context in the format zind-crm-cold-contact expects
    # The agent already has AGENTS.md / SOUL.md loaded from its workspace
    return (
        f"{memory_block}"
        f"LEAD_ID: sim-test\n"
        f"INTENT: {'greeting' if turn == 1 else 'interest_uncertain'}\n"
        f"STAGE: {scenario.stage}\n"
        f"DOR: retrabalho em follow-up e pagamento no dia a dia de síndico profissional\n"
        f"SINAL: grupo de síndicos profissionais\n"
        f"FIT: alta\n"
        f"TOM: direto e casual\n"
        f"MENSAGEM_DO_LEAD: {context}\n"
        f"\n"
        f"CONTEXTO PRÉ-CARREGADO (não chame search_contact — dados já resolvidos):\n"
        f"nome: síndico\n"
        f"setor: gestão condominial\n"
        f"cidade: {scenario.city}\n"
        f"empresa: {scenario.persona}\n"
        f"interaction_history: {outbound_events} evento(s) outbound de cold-contact — "
        f"portanto estamos na Ação {action} do Protocolo 1\n"
        f"\n"
        f"{DEFAULT_ZIND_BRAND_GUARDRAIL}\n"
        f"Retorne APENAS o texto da mensagem (sem aspas, sem prefixo, sem explicação)."
    )


def build_client_prompt(
    *,
    scenario: SimulationScenario,
    turn: int,
    sales_message: str,
    previous_client_reply: str | None,
) -> str:
    previous = previous_client_reply or "Sem resposta anterior do cliente."
    schema = {
        "reply": "string",
        "end": "boolean",
        "end_reason": "string|null",
        "objection_type": "string|null",
        "sentiment": "string|null",
    }
    return (
        "Você é sindico-sim, um simulador de cliente síndico.\n"
        f"Persona fixa: {scenario.persona}\n"
        f"Cidade: {scenario.city}\n"
        f"Estágio atual: {scenario.stage}\n"
        f"Dificuldade: {scenario.difficulty}\n"
        f"Turno: {turn}\n"
        f"Mensagem do vendedor: {sales_message}\n"
        f"Resposta anterior do cliente: {previous}\n"
        "Retorne SOMENTE JSON válido no schema abaixo, sem texto extra:\n"
        f"{_json_dumps_short(schema)}\n"
        "Use end=true apenas quando decidir encerrar a conversa."
    )


def build_client_retry_prompt(previous_prompt: str) -> str:
    return (
        previous_prompt
        + "\nATENÇÃO: resposta inválida no formato. Retorne APENAS JSON puro, sem markdown e sem comentários."
    )


def _extract_agent_reply(raw: str) -> str:
    def _extract_from_payload_list(payloads: Any) -> str:
        if not isinstance(payloads, list):
            return ""
        texts: list[str] = []
        for item in payloads:
            if not isinstance(item, dict):
                continue
            for key in ("text", "content", "message", "response"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    texts.append(value.strip())
                    break
        return "\n\n".join(texts).strip()

    text = (raw or "").strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text

    if isinstance(parsed, str):
        return parsed.strip()
    if isinstance(parsed, dict):
        # Common OpenClaw envelope: {"result":{"payloads":[{"text":"..."}]}}
        result = parsed.get("result")
        if isinstance(result, dict):
            payload_text = _extract_from_payload_list(result.get("payloads"))
            if payload_text:
                return payload_text

        # Alternative envelope: {"payloads":[{"text":"..."}]}
        payload_text = _extract_from_payload_list(parsed.get("payloads"))
        if payload_text:
            return payload_text

        # Legacy/simple shapes
        for key in ("result", "message", "output", "text", "response", "content"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(result, dict):
            nested = result
            for key in ("message", "text", "response", "content"):
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        # Avoid leaking raw runtime metadata JSON to Discord/client prompts.
        return ""
    return text


def _split_discord_message(content: str, limit: int = DISCORD_CONTENT_LIMIT) -> list[str]:
    if len(content) <= limit:
        return [content]
    chunks: list[str] = []
    current = ""
    for line in content.splitlines():
        candidate = line if not current else f"{current}\n{line}"
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = line
        while len(current) > limit:
            chunks.append(current[:limit])
            current = current[limit:]
    if current:
        chunks.append(current)
    return chunks


def _render_outcomes(transcript: list[SimulationTurnRecord], status: str, end_reason: str | None) -> dict[str, Any]:
    objection_types: set[str] = set()
    sentiments: list[str] = []
    for item in transcript:
        payload = item.payload or {}
        objection = payload.get("objection_type")
        sentiment = payload.get("sentiment")
        if isinstance(objection, str) and objection.strip():
            objection_types.add(objection.strip())
        if isinstance(sentiment, str) and sentiment.strip():
            sentiments.append(sentiment.strip().lower())

    worked: list[str] = []
    failed: list[str] = []

    if any(s in {"positivo", "positive", "engaged", "aberto"} for s in sentiments):
        worked.append("Mensagem do vendedor gerou engajamento em pelo menos um turno.")
    if end_reason and "reuniao" in _slug(end_reason):
        worked.append("Conversa encerrou com sinal de avanço para reunião.")
    if status == "max_turns":
        failed.append("Conversa não convergiu dentro do limite técnico de turnos.")
    if status == "aborted_parse_error":
        failed.append("Simulação interrompida por resposta inválida do simulador cliente.")
    if end_reason and any(word in _slug(end_reason) for word in {"sem_interesse", "nao_interesse", "no_interest"}):
        failed.append("Cliente encerrou por desinteresse explícito.")

    closing_path = end_reason or status
    return {
        "what_worked": worked,
        "what_failed": failed,
        "objections": sorted(objection_types),
        "closing_path": closing_path,
    }


def _render_full_transcript(transcript: list[SimulationTurnRecord]) -> str:
    lines = ["Full transcript"]
    for item in transcript:
        label = "Vendedor" if item.role == "sales" else "Síndico"
        lines.append(f"T{item.turn} [{label}] {item.message}")
    return "\n".join(lines)


def validate_isolation_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    agents = (config.get("agents") or {}).get("list") or []
    by_id = {str(agent.get("id")): agent for agent in agents if isinstance(agent, dict)}
    required = {"sales-sim", "sindico-sim", "sim-control"}
    missing = sorted(required - set(by_id))
    if missing:
        errors.append(f"Agentes ausentes: {', '.join(missing)}")
        return errors

    workspaces = [str(by_id[agent_id].get("workspace", "")).strip() for agent_id in ("sales-sim", "sindico-sim")]
    if any(not ws for ws in workspaces):
        errors.append("sales-sim e sindico-sim precisam de workspace explícito.")
    if len(set(workspaces)) != 2:
        errors.append("sales-sim e sindico-sim não podem compartilhar workspace.")

    defaults_memory = ((config.get("agents") or {}).get("defaults") or {}).get("memorySearch") or {}
    default_memory_enabled = bool(defaults_memory.get("enabled", False))
    for agent_id in ("sales-sim", "sindico-sim"):
        agent = by_id[agent_id]
        memory_cfg = agent.get("memorySearch") or {}
        if bool(memory_cfg.get("enabled", default_memory_enabled)):
            errors.append(f"{agent_id} deve operar com memorySearch.enabled=false.")

        tools = agent.get("tools") or {}
        deny = set(tools.get("deny") or [])
        required_denies = {"sessions_send", "sessions_spawn", "sessions_history"}
        missing_denies = required_denies - deny
        if missing_denies:
            errors.append(f"{agent_id} está sem deny obrigatório: {', '.join(sorted(missing_denies))}.")

    return errors


class OpenClawCLIInvoker:
    def __init__(self, *, openclaw_bin: str = "openclaw") -> None:
        self._openclaw_bin = openclaw_bin

    def invoke(self, *, agent_id: str, session_id: str, message: str, timeout_seconds: int) -> str:
        command = [
            self._openclaw_bin,
            "agent",
            "--agent",
            agent_id,
            "--session-id",
            session_id,
            "--message",
            message,
            "--json",
            "--timeout",
            str(timeout_seconds),
        ]
        # Allow plaintext WS to non-loopback gateway (Docker internal network)
        env = {**os.environ, "OPENCLAW_ALLOW_INSECURE_PRIVATE_WS": "1"}
        proc = subprocess.run(
            command,
            check=False,
            capture_output=True,
            env=env,
            text=True,
            timeout=max(timeout_seconds, 30),
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Falha ao invocar agente {agent_id}: {(proc.stderr or proc.stdout).strip()}")
        return (proc.stdout or "").strip()


class DiscordAPITransport:
    def __init__(self, *, bot_token: str, timeout_seconds: int = 20) -> None:
        token = (bot_token or "").strip()
        if not token:
            raise ValueError("DISCORD_BOT_TOKEN é obrigatório para simulação no Discord.")
        self._bot_token = token
        self._timeout = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bot {self._bot_token}",
            "Content-Type": "application/json",
        }

    def _channel_is_thread(self, channel_id: str) -> bool:
        """Returns True if the channel is already a thread (type 11 or 12)."""
        try:
            response = requests.get(
                f"https://discord.com/api/v10/channels/{channel_id}",
                headers=self._headers(),
                timeout=self._timeout,
            )
            if response.status_code == 200:
                return int(response.json().get("type", 0)) in {11, 12}
        except Exception:
            pass
        return False

    def create_thread(self, *, parent_channel_id: str, name: str, source_message_id: str | None = None) -> str:
        # If already inside a thread, reuse the current channel directly
        if self._channel_is_thread(parent_channel_id):
            return parent_channel_id

        if source_message_id:
            url = f"https://discord.com/api/v10/channels/{parent_channel_id}/messages/{source_message_id}/threads"
            payload: dict[str, Any] = {"name": name, "auto_archive_duration": 60}
        else:
            url = f"https://discord.com/api/v10/channels/{parent_channel_id}/threads"
            payload = {"name": name, "auto_archive_duration": 60, "type": 11}
        response = requests.post(url, headers=self._headers(), json=payload, timeout=self._timeout)
        if response.status_code not in {200, 201}:
            # Fallback: if thread creation fails (e.g. already in a thread), use current channel
            LOGGER.warning("create_thread failed (%s) — using parent_channel_id as fallback", response.status_code)
            return parent_channel_id
        data = response.json()
        thread_id = str(data.get("id") or "").strip()
        if not thread_id:
            return parent_channel_id
        return thread_id

    def send_message(self, *, channel_id: str, content: str) -> str | None:
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        chunks = _split_discord_message(content, limit=DISCORD_CONTENT_LIMIT)
        last_message_id: str | None = None
        for chunk in chunks:
            if not chunk:
                continue
            response = requests.post(
                url,
                headers=self._headers(),
                json={"content": chunk},
                timeout=self._timeout,
            )
            if response.status_code not in {200, 201}:
                raise RuntimeError(f"Falha ao enviar mensagem Discord: {response.status_code} - {response.text[:500]}")
            last_message_id = str(response.json().get("id") or "").strip() or last_message_id
        return last_message_id

    def get_messages_after(self, channel_id: str, after_message_id: str) -> list[dict]:
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        response = requests.get(
            url,
            headers=self._headers(),
            params={"after": after_message_id, "limit": 10},
            timeout=self._timeout,
        )
        if response.status_code != 200:
            return []
        messages = response.json()
        if not isinstance(messages, list):
            return []
        return sorted(messages, key=lambda m: int(m.get("id", 0)))


class DiscordHumanWaiter:
    END_COMMANDS = {"/fim", "fim", "/end", "end", "/encerrar", "encerrar", "/sair", "sair"}

    def __init__(
        self,
        *,
        transport: DiscordAPITransport,
        human_timeout_seconds: int = 300,
        poll_interval_seconds: float = 3.0,
    ) -> None:
        self._transport = transport
        self._human_timeout = human_timeout_seconds
        self._poll_interval = poll_interval_seconds

    def wait_for_reply(
        self,
        *,
        channel_id: str,
        after_message_id: str,
        publisher: ChannelPublisher,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + self._human_timeout
        while time.monotonic() < deadline:
            messages = self._transport.get_messages_after(channel_id, after_message_id)
            human_msgs = [m for m in messages if not m.get("author", {}).get("bot", False)]
            if human_msgs:
                content = (human_msgs[0].get("content") or "").strip()
                is_end = content.lower() in self.END_COMMANDS
                return {
                    "reply": content,
                    "end": is_end,
                    "end_reason": "human_ended" if is_end else None,
                    "objection_type": None,
                    "sentiment": None,
                }
            time.sleep(self._poll_interval)

        publisher.send_message(
            channel_id=channel_id,
            content=f"⏱ Sem resposta em {self._human_timeout}s. Simulação encerrada por timeout.",
        )
        return {"reply": "", "end": True, "end_reason": "human_timeout", "objection_type": None, "sentiment": None}


def run_sales_simulation(
    *,
    scenario: SimulationScenario,
    parent_channel_id: str,
    publisher: ChannelPublisher,
    invoker: AgentInvoker,
    storage: SimulationStorage,
    source_message_id: str | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    human_waiter: DiscordHumanWaiter | None = None,
) -> dict[str, Any]:
    started_at = _utcnow()
    run_id = f"{_slug(scenario.city)}-{uuid.uuid4().hex[:10]}"
    sessions = build_session_ids(run_id)

    LOGGER.info(
        "Starting sales simulation run_id=%s city=%s stage=%s difficulty=%s",
        run_id,
        scenario.city,
        scenario.stage,
        scenario.difficulty,
    )

    thread_name = f"sim-{scenario.city}-{run_id}"
    thread_id = publisher.create_thread(
        parent_channel_id=parent_channel_id,
        name=thread_name,
        source_message_id=source_message_id,
    )

    scenario_header = (
        "Simulation started\n"
        f"- run_id: {run_id}\n"
        f"- city: {scenario.city}\n"
        f"- stage: {scenario.stage}\n"
        f"- persona: {scenario.persona}\n"
        f"- difficulty: {scenario.difficulty}\n"
        f"- mode: {'**HUMANO** (você é o síndico)' if scenario.human_mode else 'bot'}"
    )
    publisher.send_message(channel_id=thread_id, content=scenario_header)

    if scenario.human_mode:
        publisher.send_message(
            channel_id=thread_id,
            content=(
                "**Como participar:** responda nesta thread após cada mensagem do vendedor.\n"
                f"Persona sugerida: _{scenario.persona}_\n"
                "Para encerrar antes do fim: responda `/fim`."
            ),
        )

    transcript: list[SimulationTurnRecord] = []
    status = "max_turns"
    end_reason: str | None = None
    last_client_reply: str | None = None
    loop_start = time.monotonic()
    zind_context, zind_context_sources = load_zind_company_context()
    should_sync_qdrant = str(os.environ.get("SALES_SIM_SYNC_ZIND_TO_QDRANT", "true")).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    if should_sync_qdrant:
        qdrant_sync = sync_zind_context_to_qdrant(source_paths=zind_context_sources)
    else:
        qdrant_sync = {"status": "disabled", "upserted_points": 0}
    memory_health = probe_memory_health()
    memory_health["vault_has_zind_context"] = bool(zind_context_sources)
    memory_health["qdrant_sync_status"] = qdrant_sync.get("status")
    if not zind_context_sources:
        publisher.send_message(
            channel_id=thread_id,
            content="Aviso: contexto Zind não encontrado no Vault. Usando contexto mínimo de fallback.",
        )
    if qdrant_sync.get("status") == "error":
        publisher.send_message(
            channel_id=thread_id,
            content=f"Aviso: falha ao sincronizar contexto Zind no Qdrant ({qdrant_sync.get('error', 'erro desconhecido')}).",
        )

    for turn in range(1, max_turns + 1):
        if time.monotonic() - loop_start > timeout_seconds:
            status = "timeout"
            end_reason = "tempo_total_excedido"
            break

        sales_prompt = build_sales_prompt(
            scenario=scenario,
            turn=turn,
            previous_client_reply=last_client_reply,
            company_context=zind_context,
        )
        sales_raw = invoker.invoke(
            agent_id=SALES_AGENT_ID,
            session_id=sessions.sales,
            message=sales_prompt,
            timeout_seconds=timeout_seconds,
        )
        sales_reply = _extract_agent_reply(sales_raw)
        sales_reply, brand_guard_applied = _apply_zind_brand_guardrails(sales_reply)
        if not sales_reply:
            status = "aborted_sales_empty"
            end_reason = "sales_empty_reply"
            publisher.send_message(channel_id=thread_id, content=f"Erro: {SALES_AGENT_ID} retornou resposta vazia.")
            break

        sales_record = SimulationTurnRecord(
            turn=turn,
            role="sales",
            agent_id=SALES_AGENT_ID,
            message=sales_reply,
            created_at=_utcnow().isoformat(),
            payload={"brand_guard_applied": brand_guard_applied},
        )
        transcript.append(sales_record)
        last_sales_msg_id = publisher.send_message(channel_id=thread_id, content=f"[Vendedor][T{turn}] {sales_reply}")

        parse_error: Exception | None = None
        fallback_applied = False

        if scenario.human_mode and human_waiter is not None:
            client_payload = human_waiter.wait_for_reply(
                channel_id=thread_id,
                after_message_id=last_sales_msg_id or "",
                publisher=publisher,
            )
            if client_payload.get("end_reason") == "human_timeout":
                status = "timeout"
                end_reason = "human_timeout"
                break
        else:
            client_prompt = build_client_prompt(
                scenario=scenario,
                turn=turn,
                sales_message=sales_reply,
                previous_client_reply=last_client_reply,
            )

            client_raw = invoker.invoke(
                agent_id="sindico-sim",
                session_id=sessions.client,
                message=client_prompt,
                timeout_seconds=timeout_seconds,
            )
            try:
                client_payload = parse_client_simulator_payload(client_raw)
            except SimulationParseError as exc:
                parse_error = exc
                retry_prompt = build_client_retry_prompt(client_prompt)
                retry_raw = invoker.invoke(
                    agent_id="sindico-sim",
                    session_id=sessions.client,
                    message=retry_prompt,
                    timeout_seconds=timeout_seconds,
                )
                try:
                    client_payload, fallback_applied = parse_client_simulator_payload_or_fallback(retry_raw)
                except SimulationParseError as retry_exc:
                    status = "aborted_parse_error"
                    end_reason = "client_invalid_json"
                    diagnostic = (
                        "Erro: sindico-sim retornou payload inválido após retry JSON-only.\n"
                        f"Detalhe: {retry_exc}"
                    )
                    publisher.send_message(channel_id=thread_id, content=diagnostic)
                    break

            if parse_error:
                publisher.send_message(
                    channel_id=thread_id,
                    content=f"Aviso: payload cliente inválido no primeiro parse, retry aplicado ({parse_error}).",
                )
            if fallback_applied:
                publisher.send_message(
                    channel_id=thread_id,
                    content="Aviso: sindico-sim não retornou JSON válido após retry; aplicado fallback textual seguro.",
                )

        client_reply = client_payload["reply"]
        client_agent_id = "human" if scenario.human_mode else "sindico-sim"
        client_record = SimulationTurnRecord(
            turn=turn,
            role="client",
            agent_id=client_agent_id,
            message=client_reply,
            created_at=_utcnow().isoformat(),
            payload=client_payload,
        )
        transcript.append(client_record)
        # In human mode the user already posted in the thread; no need to re-post their message
        if not scenario.human_mode:
            publisher.send_message(channel_id=thread_id, content=f"[Síndico][T{turn}] {client_reply}")

        last_client_reply = client_reply
        if client_payload["end"]:
            status = "completed"
            end_reason = client_payload.get("end_reason") or "client_ended"
            break

    ended_at = _utcnow()
    outcomes = _render_outcomes(transcript, status, end_reason)
    metadata = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "city": scenario.city,
        "stage": scenario.stage,
        "persona": scenario.persona,
        "difficulty": scenario.difficulty,
        "status": status,
        "end_reason": end_reason,
        "turn_count": max((item.turn for item in transcript), default=0),
        "sessions": {"sales": sessions.sales, "client": sessions.client},
        "outcome_summary": outcomes,
        "command_text": scenario.command_text,
        "zind_context_sources": zind_context_sources,
        "zind_qdrant_sync": qdrant_sync,
        "memory_health": memory_health,
    }
    paths = storage.persist(run_id=run_id, metadata=metadata, transcript=transcript)
    metadata["transcript_ref"] = paths["transcript_path"]
    metadata["metadata_ref"] = paths["metadata_path"]
    Path(paths["metadata_path"]).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    full_transcript = _render_full_transcript(transcript)
    for chunk in _split_discord_message(full_transcript):
        publisher.send_message(channel_id=thread_id, content=chunk)

    summary = (
        f"Simulation finished | run_id={run_id} | status={status} | turns={metadata['turn_count']} "
        f"| city={scenario.city} | stage={scenario.stage} | end_reason={end_reason or '-'}"
    )
    publisher.send_message(channel_id=parent_channel_id, content=summary)

    return metadata


def run_from_command(
    *,
    command_text: str,
    parent_channel_id: str,
    publisher: ChannelPublisher,
    invoker: AgentInvoker,
    storage: SimulationStorage,
    source_message_id: str | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    discord_transport: DiscordAPITransport | None = None,
    human_timeout_seconds: int = 300,
) -> dict[str, Any]:
    scenario = parse_sim_start_command(command_text)

    human_waiter: DiscordHumanWaiter | None = None
    if scenario.human_mode:
        if discord_transport is None:
            raise ValueError("discord_transport é obrigatório para modo --human.")
        human_waiter = DiscordHumanWaiter(
            transport=discord_transport,
            human_timeout_seconds=human_timeout_seconds,
        )

    return run_sales_simulation(
        scenario=scenario,
        parent_channel_id=parent_channel_id,
        publisher=publisher,
        invoker=invoker,
        storage=storage,
        source_message_id=source_message_id,
        max_turns=max_turns,
        timeout_seconds=timeout_seconds,
        human_waiter=human_waiter,
    )
