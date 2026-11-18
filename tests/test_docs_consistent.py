"""Docs say one spend figure and the true UI fact.

Spec: SPEC.md and README.md quote the model-spend estimate only as USD 93.53 (the figure docs/model-spend/aggregate.py
produces); "96.94" may appear only in the single README sentence that says it was corrected. README must not say there is
no web page, because stage 4 serves a browser UI at "/" (stage-4/dossier/ui_routes.py), and must say where to open it.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()
SPEC = (ROOT / "SPEC.md").read_text()


def test_spec_has_only_the_measured_figure():
    assert "96.94" not in SPEC
    assert "93.53" in SPEC


def test_readme_old_figure_only_in_correction_sentence():
    lines = [l for l in README.splitlines() if "96.94" in l]
    assert len(lines) == 1 and "corrected" in README.split("96.94")[0][-80:], lines
    assert "reproduces 287,781,523 tokens and USD 93.53" in README


def test_readme_does_not_deny_the_web_page():
    assert "There is no web page" not in README
    assert "http://localhost:8080/" in README


def test_limit_section_names_the_measured_cause():
    """18 Nov re-measure: the cap went to research 25 + 13 searches + plain probes and lost calls, not to search alone."""
    assert "the search step spent 79 of the 80-unit per-build cap" not in README
    limit = README.split("## Limit on the live web")[1].split("## Model spend")[0]
    for needle in ("25", "13 searches", "probe", "rendered"):
        assert needle in limit, needle
