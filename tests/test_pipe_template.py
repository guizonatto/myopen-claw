"""
Template de teste para um pipe.
Copie e ajuste para cada novo processo.
"""
import unittest
from unittest.mock import patch, MagicMock


class TestMeuProcessoPipe(unittest.TestCase):
    """Substitua 'meu_processo_pipe' pelo nome real do seu pipe."""

    @patch("pipes.meu_processo_pipe.meu_output")
    @patch("pipes.meu_processo_pipe.meu_processo")
    def test_run_calls_skill_and_tool(self, mock_skill, mock_tool):
        mock_skill.run.return_value = [{"item": "valor"}]

        # from pipes.meu_processo_pipe import run
        # run()

        # mock_skill.run.assert_called_once()
        # mock_tool.send.assert_called_once()
        pass  # remova o pass e descomente as linhas acima

    def test_run_handles_empty_data(self):
        """Garante que o pipe não quebra com lista vazia."""
        pass  # implemente conforme seu pipe


if __name__ == "__main__":
    unittest.main()
