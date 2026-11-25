"""Research-only baseline for the Research economy measure, recomputed from the organizer's sample corpus.

Strategy: one 25-unit Nimble research run per company and nothing else, on the same fixed workload the cost
auditor uses (every sample company, epochs 0 and 1). The mock web answers a research run from the corpus file's
`research.nimble.<epoch>` entries (challenges/dossier/web/mockweb/research.py), and only for the six stage-1
fields, so the run can never fill the stage-3 executives or the stage-4 investors. Reads files only: no network,
no Docker. Added by the operator after the judged run (not seat output).

Usage: python3 factory/baseline/research_only.py <sf-buildathon-2026>/challenges/dossier/web/corpus/sample
"""
import json
import pathlib
import sys

RESEARCH_COST = 25  # mockweb/nimble.py
SIX = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")
LATER = ("executives", "investors")


def accepted(value, expected):
    """The organizer's rule (test/web.py Corpus.expected + fixtures.matches)."""
    if isinstance(expected, dict):
        return value == expected["list"]
    if isinstance(expected, list):
        return value in expected
    return value == expected


def main(corpus: pathlib.Path) -> None:
    key = json.loads((corpus / "key.json").read_text(encoding="utf-8"))
    runs = cited = later = keyed = correct = 0
    for domain in sorted(key):
        company = json.loads((corpus / f"{domain}.json").read_text(encoding="utf-8"))
        for epoch in (0, 1):
            runs += 1
            entries = company.get("research", {}).get("nimble", {}).get(str(epoch), [])
            for entry in entries:
                if entry["field"] in LATER:
                    later += 1
                if entry["field"] not in SIX:
                    continue
                cited += 1
                expected = key[domain].get("expected", {}).get("4", {}).get(str(epoch))
                if expected is not None:
                    keyed += 1
                    correct += accepted(entry["value"], expected[entry["field"]])
    units = runs * RESEARCH_COST
    print(f"runs {runs}, units {units}, cited fields {cited}, units per cited field {units / cited:.1f}")
    print(f"stage-4 executives/investors cited {later}")
    print(f"keyed fields correct {correct} of {keyed} (stage-4 key; companies without a key are counted as correct)")


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]))
