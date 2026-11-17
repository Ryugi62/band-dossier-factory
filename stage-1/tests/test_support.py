import unittest

from dossier import support as S

D = "acme-robotics.test"


class SpecExamples(unittest.TestCase):
    def test_appendix_a_table(self):
        self.assertEqual(S.supported_value("Dana Ruiz has led Acme Robotics as chief executive since 2021.", "ceo", D),
                         "Dana Ruiz")
        self.assertEqual(S.supported_value("Acme Robotics CEO: Sam Ortiz.", "ceo", D), "Sam Ortiz")
        self.assertEqual(S.supported_value("Acme Robotics was founded in 2014.", "founded_year", D), 2014)
        self.assertEqual(S.supported_value("Acme Robotics employs about 120 people.", "headcount_range", D), "51-200")
        for f in S.FIELDS:
            self.assertIsNone(S.supported_value("Acme Robotics is reportedly in talks to raise $40M.", f, D))
        self.assertIsNone(S.supported_value("Acme Robotics opened a sales office in Porto.", "hq_city", D))

    def test_funding_spellings(self):
        for text in ("Acme Robotics has raised $12M.", "Acme Robotics has raised 12 million dollars.",
                     "Acme Robotics has raised US$12 million.", "Acme Robotics has raised USD 12 million.",
                     "Acme Robotics has raised $12,000,000."):
            self.assertEqual(S.supported_value(text, "funding_total", D), 12_000_000, text)
        self.assertEqual(S.supported_value("Acme Robotics has raised $12.5 million.", "funding_total", D), 12_500_000)
        self.assertIsNone(S.supported_value("Acme Robotics has raised €30 million.", "funding_total", D))
        self.assertIsNone(S.supported_value("Acme Robotics has raised $0.5.", "funding_total", D))
        self.assertIsNone(S.supported_value("Acme Robotics has raised $12M and $15M.", "funding_total", D))
        self.assertIsNone(S.supported_value("Acme Robotics has raised A$12M.", "funding_total", D))


class Sentences(unittest.TestCase):
    def test_split(self):
        self.assertEqual(S.split_sentences("One here. Two (there.) Three!\nFour? five"),
                         ["One here.", "Two (there.)", "Three!", "Four?", "five"])

    def test_legal_suffix_does_not_end(self):
        self.assertEqual(S.split_sentences("Acme Labs Inc. was founded in 2011. Next."),
                         ["Acme Labs Inc. was founded in 2011.", "Next."])

    def test_no_space_no_end(self):
        self.assertEqual(S.split_sentences("Version 1.2 is out.Really"), ["Version 1.2 is out.Really"])

    def test_single_sentence(self):
        self.assertTrue(S.is_single_sentence("Acme  was\nfounded in 2014."))
        self.assertFalse(S.is_single_sentence("One. Two."))


class Formats(unittest.TestCase):
    def test_legal_name(self):
        self.assertEqual(S.supported_value("The registered name is Acme Robotics, Inc. today.", "legal_name", D),
                         "Acme Robotics, Inc.")
        self.assertEqual(S.supported_value("Acme Robotics Systems GmbH is the legal entity.", "legal_name", D),
                         "Acme Robotics Systems GmbH")
        self.assertEqual(S.supported_value("Acme Robotics Pty Ltd is the registered name.", "legal_name", D),
                         "Acme Robotics Pty Ltd")
        self.assertIsNone(S.supported_value("Acme Robotics is the legal name.", "legal_name", D))

    def test_hq_city(self):
        self.assertEqual(S.supported_value("Acme Robotics is headquartered in Zürich.", "hq_city", D), "Zürich")
        self.assertEqual(S.supported_value("Acme Robotics is based in New York, USA.", "hq_city", D), "New York")
        self.assertEqual(S.supported_value("Acme Robotics is based in Winston-Salem.", "hq_city", D), "Winston-Salem")
        self.assertIsNone(S.supported_value("Acme Robotics is based in the north.", "hq_city", D))

    def test_ceo_masks_company_and_phrase(self):
        self.assertEqual(S.supported_value("Acme Robotics named Oskar Lind chief executive officer.", "ceo", D),
                         "Oskar Lind")
        self.assertIsNone(S.supported_value("Acme Robotics CEO Ana Maria Lopez Diaz spoke.", "ceo", D))

    def test_headcount(self):
        self.assertEqual(S.supported_value("Acme Robotics employs between 60 and 150 people.", "headcount_range", D),
                         "51-200")
        self.assertEqual(S.supported_value("Acme Robotics has 1,575 employees.", "headcount_range", D), "1001-5000")
        self.assertIsNone(S.supported_value("Acme Robotics has 40 to 60 employees.", "headcount_range", D))
        self.assertEqual(S.headcount_range(10000), "5001-10000")
        self.assertEqual(S.headcount_range(10001), "10001+")

    def test_numbers(self):
        self.assertEqual([n for _, _, n in S.find_numbers("120 and 1,200 and 12.5")], [120, 1200, 12.5])
        self.assertEqual(S.find_numbers("Q3 1,20 4a"), [])

    def test_founded_year_not_in_amount(self):
        self.assertIsNone(S.supported_value("Acme Robotics was founded with $2014.", "founded_year", D))

    def test_names_company_whole_word(self):
        self.assertTrue(S.names_company("Visit acme-robotics.test today", D))
        self.assertFalse(S.names_company("Acme Roboticsx is here", D))


class Claims(unittest.TestCase):
    def test_normalise_claim(self):
        self.assertEqual(S.normalise_claim("founded_year", "2019"), 2019)
        self.assertEqual(S.normalise_claim("funding_total", 8000000), 8000000)
        self.assertEqual(S.normalise_claim("headcount_range", 416), "201-500")
        self.assertEqual(S.normalise_claim("ceo", " Ines Brandt "), "Ines Brandt")
        self.assertIsNone(S.normalise_claim("founded_year", True))


if __name__ == "__main__":
    unittest.main()
