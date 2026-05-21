import json
import pytest
from unittest.mock import patch, mock_open
from tests.conftest import _encode_chunked, _encode_multi_chunk
import RedfishEventListener_v1 as rel


class TestChunkedEncoding:
    """Chunked transfer encoding tests (new feature)."""

    def test_chunked_single_chunk(self, make_handler, sample_event_payload):
        """Transfer-Encoding: chunked with one data chunk + terminator returns HTTP 204."""
        body_bytes = json.dumps(sample_event_payload).encode("utf-8")
        chunked = _encode_chunked(body_bytes)
        handler = make_handler(
            "POST", "/",
            {"Transfer-Encoding": "chunked"},
            chunked_body=chunked
        )
        with patch("builtins.open", mock_open()):
            handler.do_POST()
        assert handler._response_code == 204

    def test_chunked_multiple_chunks(self, make_handler, sample_event_payload):
        """Body split across 3+ chunks returns HTTP 204, reassembled correctly."""
        body_bytes = json.dumps(sample_event_payload).encode("utf-8")
        # Split the body into 3 chunks
        chunk_size = len(body_bytes) // 3
        chunks = [
            body_bytes[:chunk_size],
            body_bytes[chunk_size:2 * chunk_size],
            body_bytes[2 * chunk_size:]
        ]
        chunked = _encode_multi_chunk(chunks)
        handler = make_handler(
            "POST", "/",
            {"Transfer-Encoding": "chunked"},
            chunked_body=chunked
        )
        with patch("builtins.open", mock_open()):
            handler.do_POST()
        assert handler._response_code == 204

    def test_chunked_empty_body(self, make_handler):
        """Only terminator chunk (0\\r\\n\\r\\n) returns HTTP 400 (empty body = invalid JSON)."""
        chunked = b"0\r\n\r\n"
        handler = make_handler(
            "POST", "/",
            {"Transfer-Encoding": "chunked"},
            chunked_body=chunked
        )
        handler.do_POST()
        assert handler._response_code == 400

    def test_chunked_invalid_json(self, make_handler):
        """Chunked body containing non-JSON returns HTTP 400."""
        body = b"this is not json at all"
        chunked = _encode_chunked(body)
        handler = make_handler(
            "POST", "/",
            {"Transfer-Encoding": "chunked"},
            chunked_body=chunked
        )
        handler.do_POST()
        assert handler._response_code == 400

    def test_chunked_with_trailers(self, make_handler, sample_event_payload):
        """Chunks followed by trailer headers before final CRLF returns HTTP 204."""
        body_bytes = json.dumps(sample_event_payload).encode("utf-8")
        hex_len = format(len(body_bytes), "x")
        # Include trailer headers after the terminal chunk
        chunked = (
            f"{hex_len}\r\n".encode() + body_bytes + b"\r\n"
            + b"0\r\n"
            + b"Trailer-Header: some-value\r\n"
            + b"\r\n"
        )
        handler = make_handler(
            "POST", "/",
            {"Transfer-Encoding": "chunked"},
            chunked_body=chunked
        )
        with patch("builtins.open", mock_open()):
            handler.do_POST()
        assert handler._response_code == 204

    def test_chunked_large_payload(self, make_handler):
        """Single chunk >64KB returns HTTP 204."""
        large_event = {
            "Events": [
                {
                    "EventType": "Alert",
                    "MessageId": "Base.1.0.LargeEvent",
                    "Message": "x" * 70000
                }
            ]
        }
        body_bytes = json.dumps(large_event).encode("utf-8")
        assert len(body_bytes) > 65536
        chunked = _encode_chunked(body_bytes)
        handler = make_handler(
            "POST", "/",
            {"Transfer-Encoding": "chunked"},
            chunked_body=chunked
        )
        with patch("builtins.open", mock_open()):
            handler.do_POST()
        assert handler._response_code == 204

    def test_read_chunked_body_direct(self, make_handler, sample_event_payload):
        """Call _read_chunked_body() directly, verify byte output."""
        body_bytes = json.dumps(sample_event_payload).encode("utf-8")
        chunked = _encode_chunked(body_bytes)
        handler = make_handler(
            "POST", "/",
            {"Transfer-Encoding": "chunked"},
            chunked_body=chunked
        )
        result = handler._read_chunked_body()
        assert result == body_bytes

    def test_read_request_body_selects_chunked(self, make_handler, sample_event_payload):
        """_read_request_body() with Transfer-Encoding header delegates to chunked."""
        body_bytes = json.dumps(sample_event_payload).encode("utf-8")
        chunked = _encode_chunked(body_bytes)
        handler = make_handler(
            "POST", "/",
            {"Transfer-Encoding": "chunked"},
            chunked_body=chunked
        )
        result = handler._read_request_body()
        assert result == body_bytes

    def test_read_request_body_selects_content_length(self, make_handler, sample_event_payload):
        """_read_request_body() with Content-Length header uses content-length path."""
        body_bytes = json.dumps(sample_event_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body_bytes))},
            body=body_bytes
        )
        result = handler._read_request_body()
        assert result == body_bytes

    def test_read_request_body_no_encoding_raises(self, make_handler):
        """Neither header present raises ValueError."""
        handler = make_handler("POST", "/", {})
        with pytest.raises(ValueError, match="No Content-Length or Transfer-Encoding"):
            handler._read_request_body()

    def test_chunked_event_with_verbose(self, make_handler, sample_event_payload):
        """Chunked event POST with verbose=True logs events to stdout."""
        rel.config['verbose'] = True
        body_bytes = json.dumps(sample_event_payload).encode("utf-8")
        chunked = _encode_chunked(body_bytes)
        handler = make_handler(
            "POST", "/",
            {"Transfer-Encoding": "chunked"},
            chunked_body=chunked
        )
        with patch("builtins.open", mock_open()):
            handler.do_POST()
        assert handler._response_code == 204

    def test_chunked_metric_report(self, make_handler, sample_metric_payload):
        """Chunked POST with MetricValues payload returns HTTP 204."""
        body_bytes = json.dumps(sample_metric_payload).encode("utf-8")
        chunked = _encode_chunked(body_bytes)
        handler = make_handler(
            "POST", "/",
            {"Transfer-Encoding": "chunked"},
            chunked_body=chunked
        )
        with patch("builtins.open", mock_open()):
            handler.do_POST()
        assert handler._response_code == 204

    def test_read_chunked_body_premature_eof(self, make_handler):
        """_read_chunked_body handles premature EOF (empty readline) gracefully."""
        # Empty rfile simulates premature stream end
        handler = make_handler(
            "POST", "/",
            {"Transfer-Encoding": "chunked"},
            chunked_body=b""
        )
        result = handler._read_chunked_body()
        assert result == b""

    def test_post_body_read_generic_exception(self, make_handler):
        """Generic exception from _read_request_body returns HTTP 400."""
        handler = make_handler(
            "POST", "/",
            {"Content-Length": "10"},
            body=b"some data"
        )
        # Patch _read_request_body to raise a non-ValueError exception
        with patch.object(type(handler), '_read_request_body', side_effect=IOError("read error")):
            handler.do_POST()
        assert handler._response_code == 400
