"""
Package: llm_usage_telemetry
Função: Agrupa parsing, storage, agregação e renderização da telemetria de uso de LLM.
Usar quando: Precisar registrar ou renderizar métricas determinísticas de model/provider.

ENV_VARS:
  - (nenhuma)

DB_TABLES:
  - usage_events: leitura+escrita
  - report_dispatches: leitura+escrita
"""

