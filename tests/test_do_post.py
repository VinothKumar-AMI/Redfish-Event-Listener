import json
import os
import pytest
from unittest.mock import patch, mock_open, MagicMock
from tests.conftest import _encode_chunked, _build_headers
import RedfishEventListener_v1 as rel


class TestDoPost:
    """Core POST handler tests."""

    def test_post_with_content_length_valid_json(self, make_handler, sample_event_payload, tmp_path):
        """POST with Content-Length + valid event JSON returns HTTP 204."""
        body = json.dumps(sample_event_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        with patch("builtins.open", mock_open()):
            handler.do_POST()
        assert handler._response_code == 204

    def test_post_with_content_length_invalid_json(self, make_handler, tmp_path):
        """POST with Content-Length + malformed body returns HTTP 400."""
        body = b"not-valid-json{{"
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        handler.do_POST()
        assert handler._response_code == 400

    def test_post_with_no_headers(self, make_handler):
        """POST with neither Content-Length nor Transfer-Encoding returns HTTP 411."""
        handler = make_handler("POST", "/", {})
        handler.do_POST()
        assert handler._response_code == 411

    def test_post_event_file_written(self, make_handler, sample_event_payload, tmp_path):
        """Verify Events_<ip>.txt file is created/appended."""
        body = json.dumps(sample_event_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        m = mock_open()
        with patch("builtins.open", m):
            handler.do_POST()

        assert handler._response_code == 204
        # Verify the event file was opened for appending
        calls = [c for c in m.call_args_list if "Events_" in str(c)]
        assert len(calls) > 0

    def test_post_timestamp_log_written(self, make_handler, tmp_path):
        """Verify TimeStamp.log is appended."""
        payload = {
            "Events": [{"EventType": "Alert", "MessageId": "Test.1.0.Test"}],
            "EventTimestamp": "2026-01-01 12:00:00.000000"
        }
        body = json.dumps(payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        m = mock_open()
        with patch("builtins.open", m):
            handler.do_POST()

        assert handler._response_code == 204
        # Check that TimeStamp.log was opened
        ts_calls = [c for c in m.call_args_list if "TimeStamp.log" in str(c)]
        assert len(ts_calls) > 0

    def test_post_timestamp_bad_format(self, make_handler):
        """Payload has EventTimestamp in wrong format - 'Timestamp not in correct format' logged."""
        payload = {
            "Events": [{"EventType": "Alert", "MessageId": "Test.1.0.Test"}],
            "EventTimestamp": "not-a-timestamp"
        }
        body = json.dumps(payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        m = mock_open()
        with patch("builtins.open", m):
            handler.do_POST()

        assert handler._response_code == 204
        # Verify the bad timestamp message was written
        written = "".join(
            call.args[0] for call in m().write.call_args_list
            if call.args
        )
        assert "Timestamp not in the correct format" in written

    def test_post_no_timestamp(self, make_handler):
        """Payload has no EventTimestamp - 'No available timestamp' logged."""
        payload = {
            "Events": [{"EventType": "Alert", "MessageId": "Test.1.0.Test"}]
        }
        body = json.dumps(payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        m = mock_open()
        with patch("builtins.open", m):
            handler.do_POST()

        assert handler._response_code == 204
        written = "".join(
            call.args[0] for call in m().write.call_args_list
            if call.args
        )
        assert "No available timestamp" in written

    def test_post_event_counter_increments(self, make_handler, sample_event_payload):
        """Two POSTs from same IP increment counter to 2."""
        body = json.dumps(sample_event_payload).encode("utf-8")
        ip = "10.0.0.1"

        m = mock_open()
        with patch("builtins.open", m):
            h1 = make_handler(
                "POST", "/",
                {"Content-Length": str(len(body))},
                body=body, client_ip=ip
            )
            h1.do_POST()
            h2 = make_handler(
                "POST", "/",
                {"Content-Length": str(len(body))},
                body=body, client_ip=ip
            )
            h2.do_POST()

        assert rel.event_count[ip] == 2

    def test_post_event_counter_separate_ips(self, make_handler, sample_event_payload):
        """POSTs from different IPs have independent counters."""
        body = json.dumps(sample_event_payload).encode("utf-8")

        m = mock_open()
        with patch("builtins.open", m):
            h1 = make_handler(
                "POST", "/",
                {"Content-Length": str(len(body))},
                body=body, client_ip="10.0.0.1"
            )
            h1.do_POST()
            h2 = make_handler(
                "POST", "/",
                {"Content-Length": str(len(body))},
                body=body, client_ip="10.0.0.2"
            )
            h2.do_POST()

        assert rel.event_count["10.0.0.1"] == 1
        assert rel.event_count["10.0.0.2"] == 1
