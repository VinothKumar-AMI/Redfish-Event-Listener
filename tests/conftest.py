import io
import json
import pytest
from unittest.mock import MagicMock, patch, call
from http.server import BaseHTTPRequestHandler
from email.message import Message
import sys
import os

# Ensure the repo root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import RedfishEventListener_v1 as rel
from RedfishEventListener_v1 import RedfishEventListenerServer, config, event_count


@pytest.fixture(autouse=True)
def reset_config():
    """Reset global config and event_count before each test."""
    original = dict(config)
    event_count.clear()
    yield
    config.update(original)
    event_count.clear()


def _build_headers(header_dict):
    """Build an email.message.Message from a dict of headers."""
    msg = Message()
    for k, v in header_dict.items():
        msg[k] = v
    return msg


def _encode_chunked(data: bytes) -> bytes:
    """Encode data as a single HTTP chunked-encoding frame."""
    hex_len = format(len(data), "x")
    return f"{hex_len}\r\n".encode() + data + b"\r\n0\r\n\r\n"


def _encode_multi_chunk(chunks: list) -> bytes:
    """Encode a list of bytes as multiple HTTP chunked-encoding frames."""
    result = b""
    for chunk in chunks:
        hex_len = format(len(chunk), "x")
        result += f"{hex_len}\r\n".encode() + chunk + b"\r\n"
    result += b"0\r\n\r\n"
    return result


@pytest.fixture
def make_handler():
    """Factory fixture: builds a RedfishEventListenerServer with a crafted
    request fed via an in-memory rfile, without opening a real socket."""

    def _make(method, path, headers, body=None, chunked_body=None,
              client_ip="192.168.1.100"):
        # Build the raw body for rfile
        if chunked_body is not None:
            raw = chunked_body
        elif body is not None:
            raw = body if isinstance(body, bytes) else body.encode("utf-8")
        else:
            raw = b""

        rfile = io.BytesIO(raw)
        wfile = io.BytesIO()

        # Build the request line
        request_line = f"{method} {path} HTTP/1.1"

        # Build headers object
        hdrs = _build_headers(headers)

        # Create the handler without triggering __init__ (which needs a real socket)
        handler = object.__new__(RedfishEventListenerServer)
        handler.rfile = rfile
        handler.wfile = wfile
        handler.client_address = (client_ip, 12345)
        handler.headers = hdrs
        handler.requestline = request_line
        handler.request_version = "HTTP/1.1"
        handler.command = method

        # Mock the response methods to capture status codes
        handler._response_code = None
        handler._response_headers = []
        handler._headers_ended = False

        real_responses = []

        def mock_send_response(code, message=None):
            handler._response_code = code
            real_responses.append(code)

        def mock_send_header(keyword, value):
            handler._response_headers.append((keyword, value))

        def mock_end_headers():
            handler._headers_ended = True

        def mock_log_message(fmt, *args):
            pass  # Suppress log output during tests

        handler.send_response = mock_send_response
        handler.send_header = mock_send_header
        handler.end_headers = mock_end_headers
        handler.log_message = mock_log_message
        handler._all_responses = real_responses

        return handler

    return _make


@pytest.fixture
def sample_event_payload():
    """Minimal valid Redfish event JSON."""
    return {
        "Events": [
            {
                "EventType": "Alert",
                "MessageId": "Base.1.0.TestEvent"
            }
        ]
    }


@pytest.fixture
def sample_metric_payload():
    """Minimal valid Redfish metric report JSON."""
    return {
        "MetricValues": [
            {
                "MetricId": "CPU_Temp",
                "MetricValue": "42",
                "Timestamp": "2026-01-01T00:00:00Z"
            }
        ],
        "Name": "TestReport"
    }


@pytest.fixture
def full_event_payload():
    """Redfish event JSON with all optional fields."""
    return {
        "Events": [
            {
                "EventType": "Alert",
                "MessageId": "Base.1.0.TestEvent",
                "EventId": "EVT001",
                "EventGroupId": 42,
                "EventTimestamp": "2026-01-01 12:00:00.000000",
                "Severity": "Critical",
                "MessageSeverity": "Warning",
                "Message": "Test alert message",
                "MessageArgs": ["arg1", "arg2"]
            }
        ],
        "Context": "TestContext",
        "EventTimestamp": "2026-01-01 12:00:00.000000"
    }
