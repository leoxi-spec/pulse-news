import gzip
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

from pulse.db import db
from pulse.server import Handler
from pulse.sources import FEEDS, SOURCES


def setUpModule():
    db.init()
    db.seed_catalog(SOURCES, FEEDS)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.httpd.daemon_threads = True
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        payload = response.read()
        result = (response.status, dict(response.getheaders()), payload)
        conn.close()
        return result

    def test_home_page(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"Pulse", body)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_spa_route_serves_shell(self):
        status, headers, body = self.request("GET", "/article/123")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])

    def test_static_js_and_gzip(self):
        status, headers, body = self.request("GET", "/js/app.js", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["Content-Type"])
        self.assertEqual(headers.get("Content-Encoding"), "gzip")
        self.assertIn(b"registerRoutes", gzip.decompress(body))

    def test_etag_304(self):
        status, headers, _ = self.request("GET", "/app.css")
        etag = headers["ETag"]
        status2, headers2, body2 = self.request("GET", "/app.css", headers={"If-None-Match": etag})
        self.assertEqual(status2, 304)
        self.assertEqual(body2, b"")

    def test_api_health(self):
        status, headers, body = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        payload = json.loads(body)
        self.assertTrue(payload["ok"])

    def test_api_404_is_json(self):
        status, _, body = self.request("GET", "/api/does-not-exist")
        self.assertEqual(status, 404)
        self.assertIn("error", json.loads(body))

    def test_csrf_requires_header(self):
        status, _, body = self.request(
            "POST", "/api/events",
            body=json.dumps({"kind": "view"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["code"], "csrf")

    def test_post_with_client_header_sets_profile_cookie(self):
        status, headers, body = self.request(
            "POST", "/api/events",
            body=json.dumps({"kind": "view"}),
            headers={"Content-Type": "application/json", "X-Pulse-Client": "web"},
        )
        self.assertEqual(status, 200)
        cookie = headers.get("Set-Cookie", "")
        self.assertIn("pulse_profile=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("progress", json.loads(body))

    def test_profile_switch_redirects(self):
        status, headers, _ = self.request("GET", "/?profile=0123456789abcdef01234567")
        self.assertEqual(status, 302)
        self.assertIn("pulse_profile=0123456789abcdef01234567", headers["Set-Cookie"])

    def test_bad_profile_switch_ignored(self):
        status, _, _ = self.request("GET", "/?profile=not-a-real-id")
        self.assertEqual(status, 200)

    def test_path_traversal_blocked(self):
        status, _, body = self.request("GET", "/../../etc/passwd")
        self.assertIn(status, (403, 404))
        self.assertNotIn(b"root:", body)

    def test_head_request_has_no_body(self):
        status, headers, body = self.request("HEAD", "/")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")

    def test_options(self):
        status, headers, _ = self.request("OPTIONS", "/api/health")
        self.assertEqual(status, 204)
        self.assertIn("GET", headers["Allow"])


if __name__ == "__main__":
    unittest.main()
