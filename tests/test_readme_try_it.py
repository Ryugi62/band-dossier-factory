"""README first screen: a reader can put in their own input (a company domain, a budget) and see the spend cap.

Spec: within the first 30 lines of README.md there is a "Try it with your own company" section that has
a signup command, a POST /dossiers command with a domain, a POST /batches command with budget_units,
and says that the mock web knows only the organizer's sample companies (an unknown domain returns all-unknown fields).
"""
import pathlib

HEAD = "\n".join((pathlib.Path(__file__).resolve().parents[1] / "README.md").read_text().splitlines()[:30])


def test_try_it_section_with_own_input_and_cap():
    for needle in ("Try it with your own company", "/auth/signup", "/dossiers", '"domain"', "/batches", "budget_units",
                   "spent_units", "sample companies"):
        assert needle in HEAD, needle
