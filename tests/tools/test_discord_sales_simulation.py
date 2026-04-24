from __future__ import annotations

import json
from pathlib import Path

import pytest

from openclaw.discord_sales_simulation import (
    SimulationParseError,
    SimulationScenario,
    SimulationStorage,
    parse_sim_start_command,
    run_sales_simulation,
    validate_isolation_config,
)


class _FakeInvoker:
    def __init__(self, responses: list[tuple[str, str]]):
        self._responses = responses
        self.calls: list[dict] = []

    def invoke(self, *, agent_id: str, session_id: str, message: str, timeout_seconds: int) -> str:
        self.calls.append(
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "message": message,
                "timeout_seconds": timeout_seconds,
            }
        )
        if not self._responses:
            raise RuntimeError("No fake response available.")
        expected_agent, payload = self._responses.pop(0)
        assert expected_agent == agent_id
        return payload


class _FakePublisher:
    def __init__(self) -> None:
        self.created_threads: list[dict] = []
        self.messages: list[dict] = []

    def create_thread(self, *, parent_channel_id: str, name: str, source_message_id: str | None = None) -> str:
        self.created_threads.append(
            {
                "parent_channel_id": parent_channel_id,
                "name": name,
                "source_message_id": source_message_id,
            }
        )
        return "thread-001"

    def send_message(self, *, channel_id: str, content: str) -> None:
        self.messages.append({"channel_id": channel_id, "content": content})


def test_parse_sim_start_command_ok():
    cmd = 'sim start city=sao_paulo stage=lead persona="sindico conservador" difficulty=hard'
    scenario = parse_sim_start_command(cmd)

    assert scenario.city == "sao_paulo"
    assert scenario.stage == "lead"
    assert scenario.persona == "sindico conservador"
    assert scenario.difficulty == "hard"


def test_parse_sim_start_command_missing_fields():
    with pytest.raises(SimulationParseError):
        parse_sim_start_command("sim start stage=lead")


def test_parse_sim_start_command_invalid_prefix():
    with pytest.raises(SimulationParseError):
        parse_sim_start_command("start sim city=sao_paulo persona=\"x\"")


def test_run_sales_simulation_end_to_end(tmp_path: Path):
    scenario = SimulationScenario(
        city="sao_paulo",
        stage="lead",
        persona="sindico conservador",
        difficulty="medium",
        command_text='sim start city=sao_paulo stage=lead persona="sindico conservador"',
    )
    invoker = _FakeInvoker(
        [
            ("sales-sim", "Oi, tudo bem? Posso te mostrar um caminho curto para reduzir retrabalho?"),
            ("sindico-sim", json.dumps({"reply": "Pode sim, mas vai direto ao ponto.", "end": False, "sentiment": "engaged"})),
            ("sales-sim", "Perfeito. Hoje qual parte mais trava sua operação?"),
            (
                "sindico-sim",
                json.dumps(
                    {
                        "reply": "Fechamos por aqui, vou analisar e te retorno.",
                        "end": True,
                        "end_reason": "avaliacao_interna",
                        "objection_type": "tempo",
                        "sentiment": "neutral",
                    }
                ),
            ),
        ]
    )
    publisher = _FakePublisher()
    storage = SimulationStorage(base_dir=tmp_path)

    result = run_sales_simulation(
        scenario=scenario,
        parent_channel_id="parent-123",
        publisher=publisher,
        invoker=invoker,
        storage=storage,
        max_turns=10,
        timeout_seconds=120,
    )

    assert result["status"] == "completed"
    assert result["turn_count"] == 2
    assert result["sessions"]["sales"] != result["sessions"]["client"]
    assert Path(result["metadata_ref"]).exists()
    assert Path(result["transcript_ref"]).exists()
    assert any(msg["channel_id"] == "parent-123" for msg in publisher.messages)
    assert any(msg["channel_id"] == "thread-001" for msg in publisher.messages)


def test_run_sales_simulation_retries_then_aborts_on_invalid_json(tmp_path: Path):
    scenario = SimulationScenario(
        city="campinas",
        stage="lead",
        persona="sindica objetiva",
        difficulty="hard",
        command_text='sim start city=campinas stage=lead persona="sindica objetiva" difficulty=hard',
    )
    invoker = _FakeInvoker(
        [
            ("sales-sim", "Oi! Quero entender seu cenário antes de propor algo."),
            ("sindico-sim", "resposta sem json"),
            ("sindico-sim", "{nao_json}"),
        ]
    )
    publisher = _FakePublisher()
    storage = SimulationStorage(base_dir=tmp_path)

    result = run_sales_simulation(
        scenario=scenario,
        parent_channel_id="parent-abc",
        publisher=publisher,
        invoker=invoker,
        storage=storage,
        max_turns=4,
        timeout_seconds=120,
    )

    assert result["status"] == "aborted_parse_error"
    assert result["end_reason"] == "client_invalid_json"
    assert result["turn_count"] == 1
    assert any("payload inválido" in msg["content"] for msg in publisher.messages)


def test_validate_isolation_config():
    config = {
        "agents": {
            "defaults": {"memorySearch": {"enabled": False}},
            "list": [
                {
                    "id": "sales-sim",
                    "workspace": "~/.openclaw/workspace-sales-sim",
                    "memorySearch": {"enabled": False},
                    "tools": {"deny": ["sessions_send", "sessions_spawn", "sessions_history"]},
                },
                {
                    "id": "sindico-sim",
                    "workspace": "~/.openclaw/workspace-sindico-sim",
                    "memorySearch": {"enabled": False},
                    "tools": {"deny": ["sessions_send", "sessions_spawn", "sessions_history"]},
                },
                {"id": "sim-control", "workspace": "~/.openclaw/workspace-sim-control"},
            ],
        }
    }
    errors = validate_isolation_config(config)
    assert errors == []

