"""The comparison table names every public winner of the earlier Dark Factory hackathon, in README and FACTORY alike."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINNERS = ["GeekForge", "Midnight Workshop", "Nightshift", "gheware", "The Felt Five", "Coord"]


def _row(name):
    text = (ROOT / name).read_text()
    return [l for l in text.splitlines() if l.startswith("| The other four public winners")]


def test_past_winners_row_in_both_docs_and_identical():
    readme, factory = _row("README.md"), _row("FACTORY.md")
    assert len(readme) == 1 and readme == factory


def test_every_winner_named():
    text = (ROOT / "README.md").read_text()
    for w in WINNERS:
        assert w in text, w
    assert "8.210 units per correct field" in _row("README.md")[0]
