import importlib
import os
import sys
import types
import unittest
from unittest import mock


class _DummyResponse:
    status_code = 200
    text = "{}"

    def json(self):
        return {"id": "dummy"}


class _DummyClient:
    def __init__(self, timeout=None):
        self.timeout = timeout

    def post(self, *args, **kwargs):
        return _DummyResponse()


class _DummyFlaskApp:
    def route(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator

    def run(self, *args, **kwargs):
        return None


def _install_import_stubs():
    flask_module = types.ModuleType("flask")
    flask_module.Flask = lambda *args, **kwargs: _DummyFlaskApp()
    flask_module.abort = lambda *args, **kwargs: None
    flask_module.jsonify = lambda *args, **kwargs: args[0] if args else kwargs
    flask_module.request = types.SimpleNamespace(remote_addr="127.0.0.1", get_json=lambda **kwargs: {})

    httpx_module = types.ModuleType("httpx")
    httpx_module.Client = _DummyClient
    httpx_module.Timeout = lambda *args, **kwargs: object()

    sys.modules["flask"] = flask_module
    sys.modules["httpx"] = httpx_module


class TokenValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _install_import_stubs()
        os.environ.setdefault("BRIDGE_TOKEN", "abc")
        os.environ.setdefault("RESEND_API_KEY", "re_test")
        os.environ.setdefault("MAIL_FROM", "notify@example.com")
        os.environ.setdefault("MAIL_TO", "dest@example.com")

        if "app" in sys.modules:
            del sys.modules["app"]

        cls.app = importlib.import_module("app")

    def test_double_encoded_non_ascii_token_is_rejected_without_exception(self):
        self.assertFalse(self.app._verify_token("%25C3%25A1"))

    def test_ascii_token_still_matches(self):
        self.assertTrue(self.app._verify_token("abc"))

    def test_notify_returns_ok_for_valid_token(self):
        self.app.request = types.SimpleNamespace(
            remote_addr="127.0.0.1",
            get_json=lambda silent=True: {"title": "Hello", "body": "World"},
        )

        with mock.patch.object(self.app, "_send_via_resend") as send_mock:
            response, status = self.app.notify("abc")

        self.assertEqual(status, 200)
        self.assertEqual(response, {"status": "ok"})
        send_mock.assert_called_once_with(subject="Hello", body_html="", body_text="World")

    def test_notify_rejects_invalid_token_before_sending(self):
        class Forbidden(Exception):
            pass

        def abort(status_code):
            raise Forbidden(status_code)

        self.app.abort = abort
        self.app.request = types.SimpleNamespace(
            remote_addr="127.0.0.1",
            get_json=lambda silent=True: {"title": "Hello", "body": "World"},
        )

        with mock.patch.object(self.app, "_send_via_resend") as send_mock:
            with self.assertRaises(Forbidden) as ctx:
                self.app.notify("%25C3%25A1")

        self.assertEqual(ctx.exception.args[0], 403)
        send_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
