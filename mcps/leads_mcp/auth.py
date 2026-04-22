import os
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def verify_api_key(key: str = Security(_api_key_header)) -> None:
    expected = os.environ.get("MCP_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=500, detail="MCP_API_KEY não configurada no servidor")
    if key != expected:
        raise HTTPException(status_code=401, detail="API key inválida")

