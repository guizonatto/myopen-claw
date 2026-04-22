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

from openclaw.cortex_mem import CortexMemClient, sanitize_session_id


class BaseAgent:
    """
    Agente base. Subclasse e implemente `decide_and_run`.
    Cada agente tem acesso ao memory DB e pode chamar pipes dinamicamente.
    """

    name: str = "base_agent"

    def run_pipe(self, pipe_name: str, **kwargs):
        """Carrega e executa um pipe pelo nome do módulo."""
        module = importlib.import_module(f"pipes.{pipe_name}")
        if not hasattr(module, "run"):
            raise AttributeError(f"pipes.{pipe_name} não tem função run()")
        print(f"[{self.name}] executando pipe: {pipe_name}")
        module.run(**kwargs)

    def remember(self, tipo: str, conteudo: str):
        """Salva uma observação como memória semântica (MemClaw/Cortex Memory)."""
        session_id = sanitize_session_id(os.getenv("MEMCLAW_SESSION_ID") or f"agent-{self.name}")
        client = CortexMemClient()
        try:
            client.add_message(
                session_id,
                role="assistant",
                content=f"[{tipo}] {conteudo}",
                metadata={"tipo": tipo, "agent": self.name},
            )
        except Exception as exc:
            print(f"[{self.name}] warn: falha ao salvar memória no MemClaw: {exc}", file=sys.stderr)

    def decide_and_run(self):
        """
        Implemente aqui a lógica do agente.
        Exemplo:
            data = fetch_something()
            if data:
                self.run_pipe("daily_trends_report")
            else:
                self.remember("alerta", "Nenhum dado disponível hoje.")
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


if __name__ == "__main__":
    BaseAgent().run()
