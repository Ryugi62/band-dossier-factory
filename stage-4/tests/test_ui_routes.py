import unittest

try:
    from dossier.ui_routes import accepts_html
except ImportError:  # aiohttp absent on a bare host: the transport is tested in the image
    accepts_html = None


@unittest.skipIf(accepts_html is None, "aiohttp not installed")
class Negotiation(unittest.TestCase):
    def test_browser_accept_gets_html(self):
        self.assertTrue(accepts_html("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"))
        self.assertTrue(accepts_html("TEXT/HTML"))

    def test_api_clients_get_json(self):
        self.assertFalse(accepts_html(""))
        self.assertFalse(accepts_html("*/*"))
        self.assertFalse(accepts_html("application/json"))
        self.assertFalse(accepts_html("text/html;q=0"))


if __name__ == "__main__":
    unittest.main()
