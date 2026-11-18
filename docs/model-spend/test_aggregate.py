"""SPEC: aggregate.py re-sums usage.jsonl (usage fields only, from the four seats' session logs) at public list prices.
Given the committed usage.jsonl, When aggregate.run() is called, Then ALL = 287,781,523 tokens and USD 93.53,
the room-window figure is identical, and no model is unpriced. Non-goal: reading the session logs themselves."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(__file__))
import aggregate

class Reproduce(unittest.TestCase):
    def test_total_and_cost(self):
        for lo, hi in ((None, None), ('2026-11-17T04:57:00', '2026-11-17T10:30:59')):
            tot, cost, unk = aggregate.run(lo, hi)
            self.assertEqual(unk, set())
            self.assertEqual(sum(sum(c[k] for k in ('in', 'out', 'cr', 'w5', 'w1')) for c in tot.values()), 287781523)
            self.assertEqual(round(sum(cost.values()), 2), 93.53)

if __name__ == '__main__': unittest.main()
