# Tests never touch the real app database: isolate before importing pulse.
import os as _os
import tempfile as _tempfile

_os.environ.setdefault("PULSE_DATA_DIR", _tempfile.mkdtemp(prefix="pulse-tests-"))
_os.environ.setdefault("PULSE_INGEST", "0")
_os.environ.setdefault("PULSE_EXTRACT_BODIES", "0")

import unittest

from pulse import auth, profiles
from pulse.db import db
from pulse.sources import FEEDS, SOURCES


class FakeRequest:
    def __init__(self, token=None):
        self.headers = {"cookie": f"pulse_session={token}"} if token else {}
        self.remote = "127.0.0.1"


def setUpModule():
    db.init()
    db.seed_catalog(SOURCES, FEEDS)


class AuthTests(unittest.TestCase):
    def setUp(self):
        db.execute("DELETE FROM sessions")
        db.execute("DELETE FROM users")

    def test_signup_login_and_admin(self):
        profile = profiles.create("Ada")
        result = auth.signup("Ada@Example.com", "correct horse 9", "Ada", profile["id"])
        self.assertEqual(result["account"]["email"], "ada@example.com")
        self.assertTrue(result["account"]["is_admin"])
        self.assertEqual(result["profile"]["id"], profile["id"])

        session = auth.session_user(FakeRequest(result["token"]))
        self.assertEqual(session["email"], "ada@example.com")

        with self.assertRaises(auth.AuthError):
            auth.signup("ada@example.com", "another password", "Ada", None)
        with self.assertRaises(auth.AuthError):
            auth.login("ada@example.com", "wrong password")

        second = auth.signup("bob@example.com", "another horse 9", "Bob", None)
        self.assertFalse(second["account"]["is_admin"])
        self.assertNotEqual(second["profile"]["id"], profile["id"])
        self.assertGreaterEqual(len(auth.all_users()), 2)
        self.assertTrue(auth.users_csv().startswith(b"email,name,admin"))
        self.assertIn(b"ada@example.com", auth.users_csv())

    def test_logout_clears_session(self):
        result = auth.signup("logout@example.com", "correct horse 9", "Log", None)
        request = FakeRequest(result["token"])
        self.assertIsNotNone(auth.session_user(request))
        auth.logout(request)
        self.assertIsNone(auth.session_user(request))
