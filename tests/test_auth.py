import json
import base64
import pytest
from unittest.mock import patch, mock_open
from tests.conftest import _encode_chunked
import RedfishEventListener_v1 as rel


class TestAuth:
    """Authentication tests."""

    def test_no_auth_header_proceeds(self, make_handler, sample_event_payload):
        """No Authorization header, no config auth -> HTTP 204."""
        body = json.dumps(sample_event_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        with patch("builtins.open", mock_open()):
            handler.do_POST()
        assert handler._response_code == 204

    def test_valid_basic_auth(self, make_handler, sample_event_payload):
        """Correct Base64 credentials -> HTTP 204."""
        rel.config['listener_username'] = "admin"
        rel.config['listener_password'] = "secret"
        creds = base64.b64encode(b"admin:secret").decode()

        body = json.dumps(sample_event_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body)), "Authorization": f"Basic {creds}"},
            body=body
        )
        with patch("builtins.open", mock_open()):
            handler.do_POST()
        assert handler._response_code == 204

    def test_invalid_auth_format(self, make_handler, sample_event_payload):
        """Authorization header without 'Basic ' prefix -> HTTP 401."""
        body = json.dumps(sample_event_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body)), "Authorization": "Bearer some-token"},
            body=body
        )
        handler.do_POST()
        assert handler._response_code == 401

    def test_wrong_credentials(self, make_handler, sample_event_payload):
        """Valid format but wrong user/pass -> HTTP 403."""
        rel.config['listener_username'] = "admin"
        rel.config['listener_password'] = "secret"
        creds = base64.b64encode(b"wrong:creds").decode()

        body = json.dumps(sample_event_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body)), "Authorization": f"Basic {creds}"},
            body=body
        )
        handler.do_POST()
        assert handler._response_code == 403

    def test_auth_with_chunked(self, make_handler, sample_event_payload):
        """Valid auth + chunked encoding -> HTTP 204."""
        rel.config['listener_username'] = "admin"
        rel.config['listener_password'] = "secret"
        creds = base64.b64encode(b"admin:secret").decode()

        body_bytes = json.dumps(sample_event_payload).encode("utf-8")
        chunked = _encode_chunked(body_bytes)
        handler = make_handler(
            "POST", "/",
            {"Transfer-Encoding": "chunked", "Authorization": f"Basic {creds}"},
            chunked_body=chunked
        )
        with patch("builtins.open", mock_open()):
            handler.do_POST()
        assert handler._response_code == 204

    def test_auth_header_no_config(self, make_handler, sample_event_payload):
        """Auth header present but no config credentials - credentials don't match None."""
        rel.config['listener_username'] = None
        rel.config['listener_password'] = None
        creds = base64.b64encode(b"admin:secret").decode()

        body = json.dumps(sample_event_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body)), "Authorization": f"Basic {creds}"},
            body=body
        )
        handler.do_POST()
        # Credentials don't match None/None config -> 403
        assert handler._response_code == 403

    def test_validate_auth_returns_true_no_header(self, make_handler):
        """_validate_auth returns True when no Authorization header."""
        handler = make_handler("POST", "/", {})
        assert handler._validate_auth() is True

    def test_validate_auth_returns_false_bad_format(self, make_handler):
        """_validate_auth returns False for non-Basic auth."""
        handler = make_handler("POST", "/", {"Authorization": "Digest abc123"})
        assert handler._validate_auth() is False
        assert handler._response_code == 401
