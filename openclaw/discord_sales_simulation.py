from __future__ import annotations

import json
import logging
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    normalized = normalized.strip("_")
    return normalized or "unknown"


def command_examples() -> list[str]:
    return [
        'sim start city=sao_paulo stage=lead persona="sindico conservador"',
        'sim start city=campinas stage=qualificado persona="sindica objetiva focada em custo" difficulty=hard',
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

    def send_message(self, *, channel_id: str, content: str) -> None:
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

    try:
        tokens = shlex.split(tail)
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

    stage = _slug(data.get("stage", DEFAULT_STAGE))
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
    )


def build_session_ids(run_id: str) -> SimulationSessionIds:
    rid = _slug(run_id)
    return SimulationSessionIds(
        sales=f"agent:sales-sim:session:sim:{rid}:sales",
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


def parse_client_simulator_payload(raw_payload: str) -> dict[str, Any]:
    candidate = _extract_json_object(raw_payload)
    if candidate is None:
        raise SimulationParseError("Resposta do simulador sem JSON válido.")

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise SimulationParseError(f"JSON inválido do simulador: {exc}") from exc

    if not isinstance(parsed, dict):
        raise SimulationParseError("Payload do simulador deve ser objeto JSON.")

    reply = parsed.get("reply")
    end = parsed.get("end")
    if not isinstance(reply, str) or not reply.strip():
        raise SimulationParseError("Campo obrigatório 'reply' ausente ou vazio.")

    if isinstance(end, str):
        lowered = end.strip().lower()
        if lowered in {"true", "1", "yes", "sim"}:
            end = True
        elif lowered in {"false", "0", "no", "nao", "não"}:
            end = False
    if not isinstance(end, bool):
        raise SimulationParseError("Campo obrigatório 'end' ausente ou inválido (bool).")

    output = {
        "reply": reply.strip(),
        "end": end,
        "end_reason": str(parsed.get("end_reason", "")).strip() or None,
        "objection_type": str(parsed.get("objection_type", "")).strip() or None,
        "sentiment": str(parsed.get("sentiment", "")).strip() or None,
    }
    return output


def _json_dumps_short(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def build_sales_prompt(
    *,
    scenario: SimulationScenario,
    turn: int,
    previous_client_reply: str | None,
) -> str:
    context = previous_client_reply or "Sem mensagem anterior do cliente."
    return (
        "Você é sales-sim em uma simulação de venda para síndicos.\n"
        f"Cidade: {scenario.city}\n"
        f"Estágio alvo: {scenario.stage}\n"
        f"Dificuldade: {scenario.difficulty}\n"
        f"Perfil do cliente: {scenario.persona}\n"
        f"Turno: {turn}\n"
        "Regras: frases curtas, tom humano, 1 objetivo por resposta, CTA simples no fim.\n"
        f"Última fala do cliente: {context}\n"
        "Responda apenas com a mensagem do vendedor (texto puro)."
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
        for key in ("result", "message", "output", "text", "response", "content"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if "result" in parsed and isinstance(parsed["result"], dict):
            nested = parsed["result"]
            for key in ("message", "text", "response", "content"):
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
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
        proc = subprocess.run(
            command,
            check=False,
            capture_output=True,
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

    def create_thread(self, *, parent_channel_id: str, name: str, source_message_id: str | None = None) -> str:
        if source_message_id:
            url = f"https://discord.com/api/v10/channels/{parent_channel_id}/messages/{source_message_id}/threads"
            payload: dict[str, Any] = {"name": name, "auto_archive_duration": 60}
        else:
            url = f"https://discord.com/api/v10/channels/{parent_channel_id}/threads"
            payload = {"name": name, "auto_archive_duration": 60, "type": 11}
        response = requests.post(url, headers=self._headers(), json=payload, timeout=self._timeout)
        if response.status_code not in {200, 201}:
            raise RuntimeError(f"Falha ao criar thread Discord: {response.status_code} - {response.text[:500]}")
        data = response.json()
        thread_id = str(data.get("id") or "").strip()
        if not thread_id:
            raise RuntimeError("Discord não retornou id da thread.")
        return thread_id

    def send_message(self, *, channel_id: str, content: str) -> None:
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        response = requests.post(
            url,
            headers=self._headers(),
            json={"content": content},
            timeout=self._timeout,
        )
        if response.status_code not in {200, 201}:
            raise RuntimeError(f"Falha ao enviar mensagem Discord: {response.status_code} - {response.text[:500]}")


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
        f"- difficulty: {scenario.difficulty}"
    )
    publisher.send_message(channel_id=thread_id, content=scenario_header)

    transcript: list[SimulationTurnRecord] = []
    status = "max_turns"
    end_reason: str | None = None
    last_client_reply: str | None = None
    loop_start = time.monotonic()

    for turn in range(1, max_turns + 1):
        if time.monotonic() - loop_start > timeout_seconds:
            status = "timeout"
            end_reason = "tempo_total_excedido"
            break

        sales_prompt = build_sales_prompt(
            scenario=scenario,
            turn=turn,
            previous_client_reply=last_client_reply,
        )
        sales_raw = invoker.invoke(
            agent_id="sales-sim",
            session_id=sessions.sales,
            message=sales_prompt,
            timeout_seconds=timeout_seconds,
        )
        sales_reply = _extract_agent_reply(sales_raw)
        if not sales_reply:
            status = "aborted_sales_empty"
            end_reason = "sales_empty_reply"
            publisher.send_message(channel_id=thread_id, content="Erro: sales-sim retornou resposta vazia.")
            break

        sales_record = SimulationTurnRecord(
            turn=turn,
            role="sales",
            agent_id="sales-sim",
            message=sales_reply,
            created_at=_utcnow().isoformat(),
        )
        transcript.append(sales_record)
        publisher.send_message(channel_id=thread_id, content=f"[Vendedor][T{turn}] {sales_reply}")

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
        parse_error: Exception | None = None
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
                client_payload = parse_client_simulator_payload(retry_raw)
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

        client_reply = client_payload["reply"]
        client_record = SimulationTurnRecord(
            turn=turn,
            role="client",
            agent_id="sindico-sim",
            message=client_reply,
            created_at=_utcnow().isoformat(),
            payload=client_payload,
        )
        transcript.append(client_record)
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
) -> dict[str, Any]:
    scenario = parse_sim_start_command(command_text)
    return run_sales_simulation(
        scenario=scenario,
        parent_channel_id=parent_channel_id,
        publisher=publisher,
        invoker=invoker,
        storage=storage,
        source_message_id=source_message_id,
        max_turns=max_turns,
        timeout_seconds=timeout_seconds,
    )
