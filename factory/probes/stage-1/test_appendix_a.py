"""Self-test of the verifier's Appendix A oracle against the examples the specification gives.
Run: python3 test_appendix_a.py   (no service needed)
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from appendix_a import (supported_value, split_sentences, is_single_sentence, split_prose,
                        find_amounts, headcount_range)

D = "acme-robotics.test"
CASES = [
    # (excerpt, field, expected value or None)   -- A.2 example table
    ("Dana Ruiz has led Acme Robotics as chief executive since 2021.", "ceo", "Dana Ruiz"),
    ("Acme Robotics CEO: Sam Ortiz.", "ceo", "Sam Ortiz"),
    ("Acme Robotics was founded in 2014.", "founded_year", 2014),
    ("Acme Robotics employs about 120 people.", "headcount_range", "51-200"),
    ("Acme Robotics is reportedly in talks to raise $40M.", "funding_total", None),
    ("Acme Robotics opened a sales office in Porto.", "hq_city", None),
    # §4 examples
    ("Acme Robotics has raised $12M.", "funding_total", 12000000),
    ("Acme Robotics has raised 12 million dollars.", "funding_total", 12000000),
    # A.4 amount forms
    ("Acme Robotics raised $12.5 million.", "funding_total", 12500000),
    ("Acme Robotics raised US$12 million.", "funding_total", 12000000),
    ("Acme Robotics raised USD 12 million.", "funding_total", 12000000),
    ("Acme Robotics raised $12m.", "funding_total", 12000000),
    ("Acme Robotics raised $12,000,000.", "funding_total", 12000000),
    ("Acme Robotics raised 12,000,000 US dollars.", "funding_total", 12000000),
    ("Acme Robotics raised $3bn in funding.", "funding_total", 3000000000),
    ("Acme Robotics raised $250k.", "funding_total", 250000),
    ("Acme Robotics raised €12 million.", "funding_total", None),          # other currency
    ("Acme Robotics raised $12.3456k.", "funding_total", None),                 # not whole dollars
    ("Acme Robotics raised $12M and later $15M.", "funding_total", None),        # two values
    ("Acme Robotics has not raised $12M.", "funding_total", None),               # negation
    # legal name
    ("The registered name of the company is Acme Robotics, Inc.", "legal_name", "Acme Robotics, Inc."),
    ("Acme Robotics trades under the registered name Acme Robotics Systems GmbH in all markets.",
     "legal_name", "Acme Robotics Systems GmbH"),
    ("The legal entity behind acme-robotics.test is Acme Robotics AS.", "legal_name", "Acme Robotics AS"),
    # hq city
    ("Acme Robotics is headquartered in Lisbon.", "hq_city", "Lisbon"),
    ("Based in Valencia, Acme Robotics serves customers across the region.", "hq_city", "Valencia"),
    ("Acme Robotics is headquartered in Zürich.", "hq_city", "Zürich"),
    ("Acme Robotics is based in Aix-en-Provence.", "hq_city", "Aix"),
    ("Acme Robotics is based in New York City.", "hq_city", "New York City"),
    ("Acme Robotics is based in Stratford-Upon-Avon.", "hq_city", "Stratford-Upon-Avon"),
    # ceo
    ("As CEO of Acme Robotics, Priya Dalton sets the company's direction.", "ceo", "Priya Dalton"),
    ("Former CEO of Acme Robotics Tom Baker left.", "ceo", None),
    ("Acme Robotics named Hans Müller chief executive officer.", "ceo", "Hans Müller"),
    # founded / headcount
    ("Acme Robotics Inc. was founded in 2011.", "founded_year", 2011),           # Inc. does not end sentence
    ("Acme Robotics employs 51-200 people.", "headcount_range", "51-200"),
    ("Acme Robotics grew from 40 employees to 300 employees.", "headcount_range", None),
    ("Estimated staff at Acme Robotics: 3,148 employees.", "headcount_range", "1001-5000"),
    ("Acme Robotics employs 12000 people.", "headcount_range", "10001+"),
    ("Acme Robotics was founded in 1799.", "founded_year", None),
    # single sentence
    ("Acme Robotics was founded in 2014. It is great.", "founded_year", None),
    # company naming: whole word
    ("Acme Roboticsx was founded in 2014.", "founded_year", None),
    ("ACME ROBOTICS was founded in 2014.", "founded_year", 2014),
]

SPLITS = [
    ("One. Two! Three? Four", ["One.", "Two!", "Three?", "Four"]),
    ("He said \"yes.\" Then left.", ["He said \"yes.\"", "Then left."]),
    ("Acme Inc. is big. Next", ["Acme Inc. is big.", "Next"]),
    ("Version 2.0 shipped.\nLine two.", ["Version 2.0 shipped.", "Line two."]),
    ("(See note.) After", ["(See note.)", "After"]),
]


def main():
    bad = 0
    for ex, f, want in CASES:
        got = supported_value(ex, f, D)
        if got != want:
            bad += 1
            print(f"FAIL supports {f!r}: {ex!r} -> {got!r}, want {want!r}")
    for text, want in SPLITS:
        got = split_sentences(text)
        if got != want:
            bad += 1
            print(f"FAIL split {text!r} -> {got!r}, want {want!r}")
    h, p = split_prose("Kind: news\nFacts: {\"ceo\": \"X\"}\n\nBody line.")
    if h != ["Kind: news", "Facts: {\"ceo\": \"X\"}"] or p != "Body line.":
        bad += 1
        print("FAIL split_prose", h, p)
    h, p = split_prose("Plain text first.\n\nMore.")
    if h != [] or p != "Plain text first.\n\nMore.":
        bad += 1
        print("FAIL split_prose no header", h, p)
    if headcount_range(10000) != "5001-10000" or headcount_range(10001) != "10001+":
        bad += 1
        print("FAIL headcount boundaries")
    print(f"appendix_a self-test: {len(CASES) + len(SPLITS) + 3 - bad} passed, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
