import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app

class TestUIDashboard(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_root_returns_html(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'<!DOCTYPE html>', resp.data)

    def test_static_files_exist(self):
        base = os.path.dirname(os.path.dirname(__file__))
        self.assertTrue(os.path.exists(os.path.join(base, "templates", "index.html")))
        self.assertTrue(os.path.exists(os.path.join(base, "static", "style.css")))
        self.assertTrue(os.path.exists(os.path.join(base, "static", "app.js")))

    def test_dom_security(self):
        base = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base, "static", "app.js"), "r") as f:
            js = f.read()
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("outerHTML", js)
        self.assertNotIn("insertAdjacentHTML", js)
        
    def test_no_cdn_or_external_deps(self):
        base = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base, "templates", "index.html"), "r") as f:
            html = f.read()
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("cdn", html)
        self.assertNotIn("WebSocket", html)
        self.assertNotIn("Socket.IO", html)
        
        with open(os.path.join(base, "static", "app.js"), "r") as f:
            js = f.read()
        self.assertNotIn("WebSocket", js)
        self.assertIn("EventSource('/events')", js)

    def test_buttons_exist(self):
        base = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(base, "templates", "index.html"), "r") as f:
            html = f.read()
        self.assertIn("btn-isolate", html)
        self.assertIn("btn-crime-scene", html)
        self.assertIn("btn-executive", html)
        self.assertIn("btn-reset", html)
        self.assertIn("btn-arm-audio", html)

if __name__ == '__main__':
    unittest.main()
