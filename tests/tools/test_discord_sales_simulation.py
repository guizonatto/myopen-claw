from __future__ import annotations

import json
from pathlib import Path

import pytest

from openclaw.discord_sales_simulation import (
    _apply_zind_brand_guardrails,
    _chunk_text_for_qdrant,
    SimulationParseError,
    SimulationScenario,
    SimulationStorage,
    build_sales_prompt,
    load_zind_company_context,
    parse_client_simulator_payload,
    parse_client_simulator_payload_or_fallback,
    parse_sim_start_command,
    run_sales_simulation,
    sync_zind_context_to_qdrant,
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


def test_parse_client_payload_from_openclaw_envelope():
    envelope = {
        "result": {
            "payloads": [
                {
                    "text": json.dumps(
                        {
                            "reply": "Pode falar.",
                            "end": False,
                            "sentiment": "neutral",
                        },
                        ensure_ascii=False,
                    )
                }
            ]
        }
    }
    parsed = parse_client_simulator_payload(json.dumps(envelope, ensure_ascii=False))
    assert parsed["reply"] == "Pode falar."
    assert parsed["end"] is False
    assert parsed["sentiment"] == "neutral"


def test_parse_client_payload_fallback_for_plain_text_no_interest():
    payload, fallback = parse_client_simulator_payload_or_fallback("Não tenho interesse no momento, obrigado.")
    assert fallback is True
    assert payload["end"] is True
    assert payload["end_reason"] == "no_interest_unstructured"


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


def test_run_sales_simulation_uses_text_fallback_after_retry(tmp_path: Path):
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
            ("sindico-sim", "Não tenho interesse no momento, obrigado."),
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

    assert result["status"] == "completed"
    assert result["end_reason"] == "no_interest_unstructured"
    assert result["turn_count"] == 1
    assert any("fallback textual seguro" in msg["content"] for msg in publisher.messages)


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


def test_sales_prompt_enforces_zind_brand():
    scenario = SimulationScenario(
        city="curitiba",
        stage="lead",
        persona="sindico cético",
        difficulty="medium",
        command_text='sim start city=curitiba stage=lead persona="sindico cético"',
    )
    prompt = build_sales_prompt(
        scenario=scenario,
        turn=1,
        previous_client_reply="Estou sem tempo agora.",
        company_context="Zind é para síndicos profissionais.",
    )
    assert "exclusivamente a Zind" in prompt
    assert "Contexto de memória da Zind" in prompt


def test_brand_guardrail_rewrites_competitor_name():
    guarded, changed = _apply_zind_brand_guardrails("Oi, sou da CondoSeg e posso te ajudar.")
    assert changed is True
    assert "CondoSeg" not in guarded
    assert "Zind" in guarded


def test_load_zind_company_context_from_env_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    zind_file = tmp_path / "zind.md"
    zind_file.write_text("A Zind ajuda síndicos a organizar processos internos.", encoding="utf-8")
    monkeypatch.setenv("SALES_SIM_ZIND_CONTEXT_FILES", str(zind_file))
    context, sources = load_zind_company_context(max_total_chars=400, per_file_chars=250)
    assert "Zind" in context
    assert str(zind_file) in sources


def test_chunk_text_for_qdrant_respects_max_chars():
    text = " ".join(["zind"] * 500)
    chunks = _chunk_text_for_qdrant(text, max_chars=120, overlap_chars=20)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 120 for chunk in chunks)


class _FakeHttpResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


def test_sync_zind_context_to_qdrant_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    zind_file = tmp_path / "zind_sync.md"
    zind_file.write_text("Zind contexto de vendas para síndicos. " * 20, encoding="utf-8")

    put_calls: list[dict] = []

    def fake_get(url: str, timeout: int = 0):
        if url.endswith("/collections"):
            return _FakeHttpResponse({"result": {"collections": [{"name": "cortex_memories_tenant_claw"}]}})
        if url.endswith("/collections/cortex_memories_tenant_claw"):
            return _FakeHttpResponse(
                {
                    "result": {
                        "config": {
                            "params": {
                                "vectors": {"size": 4, "distance": "Cosine"},
                            }
                        }
                    }
                }
            )
        raise RuntimeError(f"unexpected GET {url}")

    def fake_post(url: str, json: dict | None = None, headers: dict | None = None, timeout: int = 0):
        if url.endswith("/api/embeddings"):
            return _FakeHttpResponse({"embedding": [0.1, 0.2, 0.3, 0.4]})
        raise RuntimeError(f"unexpected POST {url}")

    def fake_put(url: str, json: dict | None = None, timeout: int = 0):
        put_calls.append({"url": url, "json": json or {}})
        return _FakeHttpResponse({"status": "ok"})

    monkeypatch.setattr("openclaw.discord_sales_simulation.requests.get", fake_get)
    monkeypatch.setattr("openclaw.discord_sales_simulation.requests.post", fake_post)
    monkeypatch.setattr("openclaw.discord_sales_simulation.requests.put", fake_put)

    report = sync_zind_context_to_qdrant(source_paths=[str(zind_file)], qdrant_url="http://qdrant.test")
    assert report["status"] == "ok"
    assert report["upserted_points"] > 0
    assert report["collection"] == "cortex_memories_tenant_claw"
    assert put_calls
    first_point = put_calls[0]["json"]["points"][0]
    assert first_point["payload"]["brand"] == "zind"
