"""
Charge les CSV dans SQLite, exécute sql/analysis.sql bloc par bloc et affiche
les résultats. Écrit aussi docs/resultats_sql.txt.

Usage : python python/02_run_sql.py   (depuis la racine du projet)
"""
import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "projet.db"
if DB.exists():
    DB.unlink()

con = sqlite3.connect(DB)
for name in ["clients", "partenaires", "reservations", "factures",
             "reclamations", "taux_change"]:
    pd.read_csv(ROOT / "data" / f"{name}.csv").to_sql(name, con, index=False)

sql_text = (ROOT / "sql" / "analysis.sql").read_text(encoding="utf-8")
blocks = re.split(r"^-- name: (\S+)\s*$", sql_text, flags=re.M)[1:]
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)

report = []
for name, body in zip(blocks[0::2], blocks[1::2]):
    statements = [s.strip() for s in body.split(";") if s.strip()]
    result = None
    for stmt in statements:
        # on retire les lignes de commentaires pour détecter les SELECT
        code = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
        if not code:
            continue
        if code.upper().startswith(("SELECT", "WITH")):
            result = pd.read_sql_query(code, con)
        else:
            con.execute(code)
    if result is not None:
        title = f"\n=== {name} ===\n{result.to_string(index=False)}\n"
        print(title)
        report.append(title)

(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / "resultats_sql.txt").write_text("".join(report), encoding="utf-8")
con.commit()
con.close()
print("OK - résultats écrits dans docs/resultats_sql.txt")
