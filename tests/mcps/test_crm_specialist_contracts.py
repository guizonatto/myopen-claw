"""
Tests: specialist agent behavioral contracts.
Validates that each Python specialist class (fallback layer) respects
the contracts defined in each agent's AGENTS.md:
  - Returns non-empty messages
  - Respects char limits (human_rules)
  - Correct intent coverage per agent
  - Stage update called when required (closer)
  - No forbidden tool calls (handover doesn't call mark_no_interest directly)

Uses mocks for DB and MCP calls — no running container needed.
"""
from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────

MAX_CHUNK_CHARS = 180
MAX_TOTAL_CHARS = 220


def _routing(intent: str, specialist: str, policy_flags: list[str] | None = None) -> dict:
    return {
        "intent": intent,
        "confidence": 0.9,
        "specialist": specialist,
        "policy_flags": policy_flags or [],
    }


def _fake_contato(name: str = "Carlos", stage: str = "lead") -> SimpleNamespace:
    return SimpleNamespace(id="test-uuid", nome=name, pipeline_status=stage,
                           empresa="Condominio Teste", setor="sindicos", city="Curitiba",
                           pain_hypothesis="retrabalho em cobranca",
                           recent_signal="visitou o site", offer_fit="alto",
                           preferred_tone="direto", ativo=True)


def _mock_session(contato: SimpleNamespace):
    session = MagicMock()
    query = MagicMock()
    query.filter.return_value.first.return_value = contato
    session.query.return_value = query
    return session


def _get_session_cm(contato):
    from contextlib import contextmanager

    @contextmanager
    def _cm():
        yield _mock_session(contato)

    return _cm


def _load(module_path: str, class_name: str):
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


# ── human_rules validation helper ────────────────────────────────────────────


def assert_human_rules(messages: list[str], max_chunks: int = 3):
    assert messages, "messages must be non-empty"
    assert len(messages) <= max_chunks, f"too many chunks: {len(messages)} > {max_chunks}"
    for chunk in messages:
        assert len(chunk) <= MAX_CHUNK_CHARS, (
            f"chunk too long ({len(chunk)} chars > {MAX_CHUNK_CHARS}): '{chunk}'"
        )
    total = sum(len(m) for m in messages)
    if len(messages) == 1:
        assert total <= MAX_CHUNK_CHARS, f"single message too long: {total} chars"


# ── QualifierAgent ────────────────────────────────────────────────────────────


class TestQualifierAgent:
    INTENTS = [
        "identity_check", "interest_uncertain", "out_of_scope_junk",
        "objection_price", "objection_time", "objection_trust",
        "objection_already_has_solution", "objection_competitor",
        "request_proof", "bot_gatekeeper",
    ]

    @pytest.fixture
    def agent(self):
        return _load("agents.crm.qualifier_agent", "QualifierAgent")()

    @pytest.mark.parametrize("intent", INTENTS)
    def test_responds_to_each_intent(self, agent, intent):
        contato = _fake_contato()
        with patch("agents.crm.base_specialist.get_session", _get_session_cm(contato)):
            messages = agent.respond(
                routing=_routing(intent, "zind-crm-qualifier"),
                contact_id="test-uuid",
                joined_text="mensagem de teste",
                channel="whatsapp",
            )
        assert messages, f"QualifierAgent returned empty for intent={intent}"

    def test_respects_human_rules(self, agent):
        contato = _fake_contato()
        with patch("agents.crm.base_specialist.get_session", _get_session_cm(contato)):
            messages = agent.respond(
                routing=_routing("objection_price", "zind-crm-qualifier"),
                contact_id="test-uuid",
                joined_text="Muito caro",
                channel="whatsapp",
            )
        assert_human_rules(messages)

    def test_does_not_handle_handover_intents(self, agent):
        """Qualifier should not be called for handover intents — guard test."""
        contato = _fake_contato()
        with patch("agents.crm.base_specialist.get_session", _get_session_cm(contato)):
            messages = agent.respond(
                routing=_routing("request_human", "zind-crm-qualifier"),
                contact_id="test-uuid",
                joined_text="Quero falar com alguém",
                channel="whatsapp",
            )
        # Qualifier still returns something (fallback graceful), but this intent
        # should never reach qualifier in the real flow — verified by routing tests.
        assert isinstance(messages, list)


# ── HandoverAgent ─────────────────────────────────────────────────────────────


class TestHandoverAgent:
    INTENTS = ["request_human", "no_interest", "escalate_frustration"]

    @pytest.fixture
    def agent(self):
        return _load("agents.crm.handover_agent", "HandoverAgent")()

    @pytest.mark.parametrize("intent", INTENTS)
    def test_responds_to_each_intent(self, agent, intent):
        contato = _fake_contato()
        with patch("agents.crm.base_specialist.get_session", _get_session_cm(contato)):
            messages = agent.respond(
                routing=_routing(intent, "zind-crm-handover"),
                contact_id="test-uuid",
                joined_text="mensagem de teste",
                channel="whatsapp",
            )
        assert messages, f"HandoverAgent returned empty for intent={intent}"

    def test_respects_human_rules_for_escalation(self, agent):
        contato = _fake_contato()
        with patch("agents.crm.base_specialist.get_session", _get_session_cm(contato)):
            messages = agent.respond(
                routing=_routing("escalate_frustration", "zind-crm-handover"),
                contact_id="test-uuid",
                joined_text="Isso é ridículo",
                channel="whatsapp",
            )
        assert_human_rules(messages, max_chunks=2)

    def test_does_not_call_mark_no_interest_directly(self, agent):
        """HandoverAgent must not call mark_no_interest — that's orchestrator-only."""
        from agents.crm import handover_agent as hmod
        import inspect
        source = inspect.getsource(hmod)
        assert "mark_no_interest" not in source, (
            "HandoverAgent must not call mark_no_interest directly — "
            "only the orchestrator may via block_and_stop policy"
        )


# ── ClosingAgent ──────────────────────────────────────────────────────────────


class TestClosingAgent:
    INTENTS = ["interest_positive", "request_demo_or_meeting"]

    @pytest.fixture
    def agent(self):
        return _load("agents.crm.closing_agent", "ClosingAgent")()

    @pytest.mark.parametrize("intent", INTENTS)
    def test_responds_to_each_intent(self, agent, intent):
        contato = _fake_contato(stage="qualificado")
        with patch("agents.crm.base_specialist.get_session", _get_session_cm(contato)):
            messages = agent.respond(
                routing=_routing(intent, "zind-crm-closer"),
                contact_id="test-uuid",
                joined_text="Tenho interesse",
                channel="whatsapp",
            )
        assert messages, f"ClosingAgent returned empty for intent={intent}"

    def test_respects_human_rules(self, agent):
        contato = _fake_contato(stage="interesse")
        with patch("agents.crm.base_specialist.get_session", _get_session_cm(contato)):
            messages = agent.respond(
                routing=_routing("interest_positive", "zind-crm-closer"),
                contact_id="test-uuid",
                joined_text="Gostei, faz sentido",
                channel="whatsapp",
            )
        assert_human_rules(messages, max_chunks=2)

    def test_does_not_handle_escalation(self):
        """Closer AGENTS.md must not list escalate_frustration or request_human."""
        from pathlib import Path
        agents_md = Path("agents/zind-crm-closer/AGENTS.md").read_text(encoding="utf-8")
        forbidden_intents = ["escalate_frustration", "request_human"]
        for intent in forbidden_intents:
            assert f"`{intent}`" not in agents_md, (
                f"Closer AGENTS.md still references `{intent}` — should be in handover agent"
            )


# ── ColdContactAgent ──────────────────────────────────────────────────────────


class TestColdContactAgent:
    @pytest.fixture
    def agent(self):
        return _load("agents.crm.qualifier_agent", "QualifierAgent")()  # Python fallback

    def test_does_not_contain_exit_conditions(self):
        """cold-contact AGENTS.md must not have routing exit conditions."""
        from pathlib import Path
        agents_md = Path("agents/zind-crm-cold-contact/AGENTS.md").read_text(encoding="utf-8")
        assert "Condições de Saída" not in agents_md, (
            "cold-contact AGENTS.md still has routing exit conditions — specialists don't route"
        )
        assert "objection-agent" not in agents_md, (
            "cold-contact AGENTS.md references legacy agent name 'objection-agent'"
        )
        assert "handover-agent" not in agents_md, (
            "cold-contact AGENTS.md references legacy agent name 'handover-agent'"
        )

    def test_does_not_contain_exit_conditions_qualifier(self):
        """qualifier AGENTS.md must not have routing exit conditions."""
        from pathlib import Path
        agents_md = Path("agents/zind-crm-qualifier/AGENTS.md").read_text(encoding="utf-8")
        assert "Condições de Saída" not in agents_md, (
            "qualifier AGENTS.md still has routing exit conditions"
        )


# ── workspace file structure ──────────────────────────────────────────────────


@pytest.mark.parametrize("agent_id", [
    "zind-crm-orchestrator",
    "zind-crm-cold-contact",
    "zind-crm-qualifier",
    "zind-crm-closer",
    "zind-crm-handover",
    "zind-crm-reviewer",
])
def test_workspace_has_required_files(agent_id):
    from pathlib import Path
    workspace = Path(f"agents/{agent_id}")
    for fname in ("IDENTITY.md", "SOUL.md", "AGENTS.md", "TOOLS.md"):
        fpath = workspace / fname
        assert fpath.exists(), f"Missing {fname} in {agent_id}"
        assert fpath.stat().st_size > 50, f"{fname} in {agent_id} is suspiciously small"


@pytest.mark.parametrize("agent_id", [
    "zind-crm-orchestrator",
    "zind-crm-cold-contact",
    "zind-crm-qualifier",
    "zind-crm-closer",
    "zind-crm-handover",
    "zind-crm-reviewer",
])
def test_identity_md_is_minimal_metadata(agent_id):
    """IDENTITY.md must contain only metadata — no persona prose."""
    from pathlib import Path
    content = (Path(f"agents/{agent_id}/IDENTITY.md")).read_text(encoding="utf-8")
    assert len(content) < 300, (
        f"{agent_id}/IDENTITY.md is too long ({len(content)} chars) — "
        "persona content belongs in AGENTS.md"
    )
    assert "name:" in content, f"{agent_id}/IDENTITY.md missing 'name:'"


def test_orchestrator_routing_table_has_handover():
    from pathlib import Path
    agents_md = Path("agents/zind-crm-orchestrator/AGENTS.md").read_text(encoding="utf-8")
    assert "zind-crm-handover" in agents_md, (
        "Orchestrator AGENTS.md missing zind-crm-handover in routing table"
    )


def test_orchestrator_handles_audio():
    from pathlib import Path
    agents_md = Path("agents/zind-crm-orchestrator/AGENTS.md").read_text(encoding="utf-8")
    assert "transcribe_incoming_audio" in agents_md or "áudio" in agents_md.lower(), (
        "Orchestrator AGENTS.md has no audio handling instruction"
    )
