import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from streamlit.testing.v1 import AppTest  # noqa: E402

from sensei.ui import PAGINAS, PAGINAS_EXTRA  # noqa: E402

fallos = 0
for archivo, titulo, slug in PAGINAS + PAGINAS_EXTRA:
    at = AppTest.from_file("../streamlit_app.py", default_timeout=60)
    at.run()
    at.switch_page(archivo).run()
    errs = [e.value for e in at.exception]
    fallos += bool(errs)
    print(f"{slug:16} {'OK' if not errs else errs[0][:300]}")
sys.exit(1 if fallos else 0)
