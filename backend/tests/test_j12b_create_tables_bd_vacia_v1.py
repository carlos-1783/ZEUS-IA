"""J12b: create_tables() funciona sobre una BD vacia sin que nadie haya importado app.main.
Se ejecuta en un subproceso limpio (si no, el conftest ya habria importado todos los modelos)."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_create_tables_sobre_bd_vacia_crea_company_employees_y_time_cost_checkins(tmp_path):
    db_file = tmp_path / "vacia.db"
    code = textwrap.dedent(
        """
        import json, sys
        import app.db.base as b
        assert "app.main" not in sys.modules
        b.create_tables()
        from sqlalchemy import inspect
        print("RESULT:" + json.dumps(sorted(inspect(b.engine).get_table_names())))
        """
    )
    import os

    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_file.as_posix()}", "ZEUS_DB_CREATE_TABLES_RETRIES": "1"}
    p = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True,
                       text=True, timeout=180)
    line = [l for l in p.stdout.splitlines() if l.startswith("RESULT:")]
    assert line, (p.stdout[-1500:], p.stderr[-1500:])
    tables = json.loads(line[0][len("RESULT:"):])
    assert "company_employees" in tables and "time_cost_checkins" in tables
    assert "continuará sin base de datos" not in p.stdout
