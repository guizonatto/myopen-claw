"""
Agent: base_agent
Função: Template base para agentes que orquestram múltiplos pipes com lógica condicional.
Usar quando: o processo exige decisão (se X então pipe A, senão pipe B).

Copie e customize: cp agents/base_agent.py agents/meu_agente.py
Executar: python -m agents.meu_agente
"""
import importlib
import os
import sys
from typing import Any, Literal

from openclaw.cortex_mem import CortexMemClient, sanitize_session_id


class BaseAgent:
    """
    Agente base. Subclasse e implemente `decide_and_run`.

    Padrão de memória eficiente:
    - recall()   → busca L0 primeiro (barato); só escala para L1/L2 se necessário
    - remember() → buffer local; zero chamadas de API até flush_memory()
    - flush_memory() → 1 chamada add_message por item + 1 commit_session no fim
    - run()      → chama flush_memory() automaticamente ao concluir
    """

    name: str = "base_agent"

    def __init__(self) -> None:
        self._mem_buffer: list[dict[str, Any]] = []
        self._memclaw: CortexMemClient | None = None

    @property
    def _session_id(self) -> str:
        return sanitize_session_id(os.getenv("MEMCLAW_SESSION_ID") or f"agent-{self.name}")

    @property
    def _mem(self) -> CortexMemClient:
        """Cliente MemClaw — instanciado uma vez por sessão."""
        if self._memclaw is None:
            self._memclaw = CortexMemClient()
        return self._memclaw

    # ── pipes ──────────────────────────────────────────────────────────────

    def run_pipe(self, pipe_name: str, **kwargs):
        """Carrega e executa um pipe pelo nome do módulo."""
        module = importlib.import_module(f"pipes.{pipe_name}")
        if not hasattr(module, "run"):
            raise AttributeError(f"pipes.{pipe_name} não tem função run()")
        print(f"[{self.name}] executando pipe: {pipe_name}")
        module.run(**kwargs)

    # ── memória ────────────────────────────────────────────────────────────

    def recall(
        self,
        query: str,
        *,
        limit: int = 10,
        min_score: float = 0.6,
        layers: list[Literal["L0", "L1", "L2"]] | None = None,
    ) -> list[dict[str, Any]]:
        """Busca semântica no MemClaw. Usa L0 por padrão (mais barato)."""
        try:
            return self._mem.search(
                query,
                scope=f"cortex://session/{self._session_id}",
                limit=limit,
                min_score=min_score,
                return_layers=layers or ["L0"],
            )
        except Exception as exc:
            print(f"[{self.name}] warn: recall falhou: {exc}", file=sys.stderr)
            return []

    def remember(self, tipo: str, conteudo: str, **metadata):
        """Enfileira uma observação no buffer local. Sem chamada de API."""
        self._mem_buffer.append({
            "content": f"[{tipo}] {conteudo}",
            "metadata": {"tipo": tipo, "agent": self.name, **metadata},
        })

    def flush_memory(self):
        """Envia o buffer para o MemClaw e commita a sessão. Chamado automaticamente em run()."""
        if not self._mem_buffer:
            return
        try:
            for entry in self._mem_buffer:
                self._mem.add_message(
                    self._session_id,
                    role="assistant",
                    content=entry["content"],
                    metadata=entry["metadata"],
                )
            self._mem.commit_session(self._session_id)
            print(f"[{self.name}] memória: {len(self._mem_buffer)} item(s) consolidado(s).")
        except Exception as exc:
            print(f"[{self.name}] warn: flush_memory falhou: {exc}", file=sys.stderr)
        finally:
            self._mem_buffer.clear()

    # ── ciclo de vida ──────────────────────────────────────────────────────

    def decide_and_run(self):
        """
        Implemente aqui a lógica do agente.
        Exemplo:
            ctx = self.recall("estrategia ontem")
            if ctx:
                self.run_pipe("daily_trends_report")
            else:
                self.remember("alerta", "Nenhum contexto disponível.")
        """
        raise NotImplementedError("Implemente decide_and_run no seu agente.")

    def run(self):
        print(f"[{self.name}] iniciando...")
        try:
            self.decide_and_run()
            print(f"[{self.name}] concluído.")
        except Exception as e:
            print(f"[{self.name}] erro: {e}")
            raise
        finally:
            self.flush_memory()


if __name__ == "__main__":
    BaseAgent().run()
