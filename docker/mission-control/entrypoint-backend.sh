#!/bin/bash
set -e

python - <<'PYEOF'
import psycopg, os, re
db_url = os.environ.get("DATABASE_URL", "")
base = re.sub(r'mission_control$', 'openclaw', db_url.replace('postgresql+psycopg', 'postgresql'))
try:
    c = psycopg.connect(base, autocommit=True)
    c.execute("SELECT 1 FROM pg_database WHERE datname='mission_control'")
    if not c.fetchone():
        c.execute("CREATE DATABASE mission_control")
        print("Database mission_control created")
    else:
        print("Database mission_control already exists")
    c.close()
except Exception as e:
    print(f"DB init warning: {e}")
PYEOF

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
