"""Push measures from make_semantic_model.py into the model open in Power BI Desktop (pbi-cli), without touching the
TMDL on disk. Usage: python _build/push_measures.py "Title Category" "Title Subcategory"   (no names = all measures)
Then save in Desktop (Ctrl+S) so the TMDL matches the generator."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBI = os.path.expanduser(r"~\.local\bin\pbi.exe")
tmp = Path(tempfile.mkdtemp()) / "definition"
shutil.copytree(ROOT / "RetailPulse-PBI.SemanticModel" / "definition", tmp)
subprocess.run([sys.executable, str(Path(__file__).parent / "make_semantic_model.py")], check=True,
               env={**os.environ, "RP_DEFN": str(tmp), "PYTHONUTF8": "1"}, capture_output=True)
text = (tmp / "tables" / "_Measures.tmdl").read_text(encoding="utf-8")
measures = re.findall(r"^\tmeasure (?:'(.+?)'|(\S+)) = (.*)$", text, re.M)
want = set(sys.argv[1:])
for q, plain, expr in measures:
    name = q or plain
    if want and name not in want:
        continue
    r = subprocess.run([PBI, "measure", "update", name, "-t", "_Measures", "-e", "-"], input=expr, capture_output=True,
                       text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = r.stdout + r.stderr
    print(("OK   " if r.returncode == 0 and "rror" not in out else "FAIL ") + name + ("" if r.returncode == 0 else "\n" + out[-400:]))
