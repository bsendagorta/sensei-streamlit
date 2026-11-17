import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from streamlit.testing.v1 import AppTest
import os; os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
for p in ["hoy","aprende","registrar","pruebas","recuperacion","nutricion","historial","ajustes"]:
    at = AppTest.from_file(f"../paginas/{p}.py", default_timeout=60).run()
    errs=[e.value for e in at.exception]
    print(p, "OK" if not errs else errs[:1])
    if p=="hoy": print("  ", [m.value for m in at.markdown][:4], [s.value for s in at.subheader][:2])
