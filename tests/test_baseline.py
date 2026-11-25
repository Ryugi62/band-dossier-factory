"""Research-only baseline is reproducible, and the docs lead Research economy with the stage-4 figure.

Spec: `python3 factory/baseline/research_only.py <organizer corpus/sample>` reads only the organizer's sample corpus
and key (no network, no Docker) and prints, for the fixed workload of 12 sample companies x epochs 0 and 1, one
25-unit Nimble research run each and nothing else: runs 24, units 600, cited fields 20, units per cited field 30.0,
cited fields of the stage-4 executives/investors 0, and keyed fields correct 8 of 8. README and FACTORY quote
stage 4 (8.210) as the judged figure first and name the script.
"""
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS = ROOT.parent / "sf-buildathon-2026" / "challenges" / "dossier" / "web" / "corpus" / "sample"
SCRIPT = ROOT / "factory" / "baseline" / "research_only.py"


@pytest.mark.skipif(not CORPUS.is_dir(), reason="organizer repository not cloned next to this one (sh demo.sh clones it)")
def test_baseline_reproduces_30():
    out = subprocess.run([sys.executable, "-I", str(SCRIPT), str(CORPUS)], capture_output=True, text=True, check=True).stdout
    for needle in ("runs 24", "units 600", "cited fields 20", "units per cited field 30.0",
                   "stage-4 executives/investors cited 0", "keyed fields correct 8 of 8"):
        assert needle in out, (needle, out)


def test_docs_lead_with_stage_4():
    for name in ("README.md", "FACTORY.md"):
        text = (ROOT / name).read_text()
        measure = text.split("**Units per correct field**")[1].split("\n\n")[0]
        assert "factory/baseline/research_only.py" in measure, name
        assert measure.index("8.210") < measure.index("5.591"), name
        assert "1,527 units" in measure and "186 correct fields" in measure, name
        assert "3.65 times" in measure, name
