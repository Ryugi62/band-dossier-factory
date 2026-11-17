import unittest

from dossier import domains, pages


class Domains(unittest.TestCase):
    def test_normalise(self):
        for raw in ("Acme-Robotics.TEST.", "www.acme-robotics.test", " acme-robotics.test "):
            self.assertEqual(domains.normalise(raw), "acme-robotics.test")
        self.assertEqual(domains.normalise("www.www.x.test"), "www.x.test")

    def test_invalid(self):
        long_label = "a" * 64 + ".test"
        d254 = ".".join(["a" * 63, "b" * 63, "c" * 63, "d" * 62])
        for raw in ("localhost", long_label, d254, "-a.test", "a-.test", "a..test", "a_b.test", "a.test..",
                    ".a.test", "www.test", "a b.test", "https://a.test", "a.test/about", ""):
            self.assertIsNone(domains.normalise(raw), raw)
        self.assertIsNotNone(domains.normalise(".".join(["a" * 63, "b" * 63, "c" * 63, "d" * 61])))


class Pages(unittest.TestCase):
    def test_header_and_prose(self):
        header, prose = pages.split_prose('Kind: news\nFirst-Published-By: x.test\nFacts: {"ceo": "X"}\n\nBody.')
        self.assertEqual(prose, "Body.")
        self.assertIn("Facts:", header)

    def test_no_header(self):
        self.assertEqual(pages.split_prose("Plain text.\n\nMore."), ("", "Plain text.\n\nMore."))
        self.assertEqual(pages.split_prose("Acme CEO: Dana Ruiz.")[1], "Acme CEO: Dana Ruiz.")

    def test_truncated_drops_partial_sentence(self):
        self.assertEqual(pages.complete_sentences("One. Two.\nThree is cut sh", True), ["One.", "Two."])
        self.assertEqual(pages.complete_sentences("One. Two", False), ["One.", "Two"])

    def test_supporting_sentences_skip_header_facts(self):
        text = 'Facts: {"hq_city": "Acme is headquartered in Berlin."}\n\nAcme is headquartered in Zürich.'
        got = list(pages.supporting_sentences(pages.complete_sentences(pages.split_prose(text)[1], False), "acme.test"))
        self.assertEqual(got, [("hq_city", "Zürich", "Acme is headquartered in Zürich.")])

    def test_contains_excerpt_whitespace(self):
        self.assertTrue(pages.contains_excerpt("Acme  was\tfounded in 2014.", "Acme was founded in 2014."))
        self.assertFalse(pages.contains_excerpt("Acme was founded in 2015.", "Acme was founded in 2014."))


if __name__ == "__main__":
    unittest.main()
