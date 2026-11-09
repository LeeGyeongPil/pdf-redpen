"""AC-10: the default install is permissive-licensed only; PyMuPDF is never imported."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_default_deps_permissive():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^dependencies = \[(.*?)\]", text, re.S | re.M).group(1)
    deps = sorted(re.findall(r'"([^"]+)"', block))
    assert deps == ["pdfplumber==0.11.10", "pillow>=13.0.0", "pypdf==7.0.0"]

    code = (
        "import sys, tempfile, pdf_redpen\n"
        "from pdf_redpen.cli import main\n"
        "assert main(['demo', '--out', tempfile.mkdtemp()]) == 0\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('pymupdf', 'fitz')]\n"
        "assert not bad, bad\n"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr


def test_version_matches_pyproject():
    import pdf_redpen

    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{pdf_redpen.__version__}"' in text
