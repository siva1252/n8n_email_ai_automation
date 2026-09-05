import sqlite3
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "tmp_n8n" / "database.sqlite"
con = sqlite3.connect(p)
print("workflows", con.execute("SELECT id, name, active FROM workflow_entity").fetchall())
print("credentials", con.execute("SELECT id, name, type FROM credentials_entity").fetchall())
cols = [r[1] for r in con.execute("PRAGMA table_info(credentials_entity)").fetchall()]
print("cred_cols", cols)
