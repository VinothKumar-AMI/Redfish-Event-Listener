import json
import pytest
from unittest.mock import patch, mock_open, MagicMock
import RedfishEventListener_v1 as rel


class TestEventLogging:
    """Verbose output and event display tests."""

    def test_verbose_events_all_fields(self, make_handler, full_event_payload):
        """Event with all optional fields, verbose=True -> All fields logged."""
        rel.config['verbose'] = True
        body = json.dumps(full_event_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        with patch("builtins.open", mock_open()):
            with patch.object(rel.my_logger, "info") as mock_info:
                handler.do_POST()
        assert handler._response_code == 204
        logged = " ".join(str(c) for c in mock_info.call_args_list)
        assert "EventType" in logged
        assert "MessageId" in logged
        assert "EventId" in logged
        assert "Severity" in logged
        assert "Context" in logged

    def test_verbose_events_minimal(self, make_handler, sample_event_payload):
        """Event with only EventType+MessageId -> Only those logged."""
        rel.config['verbose'] = True
        body = json.dumps(sample_event_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        with patch("builtins.open", mock_open()):
            with patch.object(rel.my_logger, "info") as mock_info:
                handler.do_POST()
        assert handler._response_code == 204
        logged = " ".join(str(c) for c in mock_info.call_args_list)
        assert "EventType" in logged
        assert "MessageId" in logged

    def test_verbose_metric_report(self, make_handler, sample_metric_payload):
        """MetricValues payload, verbose=True -> Metrics logged."""
        rel.config['verbose'] = True
        body = json.dumps(sample_metric_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        with patch("builtins.open", mock_open()):
            with patch.object(rel.my_logger, "info") as mock_info:
                handler.do_POST()
        assert handler._response_code == 204
        logged = " ".join(str(c) for c in mock_info.call_args_list)
        assert "MetricId" in logged
        assert "MetricValue" in logged

    def test_non_verbose_events_silent(self, make_handler, full_event_payload):
        """Event with verbose=False -> No event detail logged."""
        rel.config['verbose'] = False
        body = json.dumps(full_event_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        with patch("builtins.open", mock_open()):
            with patch.object(rel.my_logger, "info") as mock_info:
                handler.do_POST()
        assert handler._response_code == 204
        logged = " ".join(str(c) for c in mock_info.call_args_list)
        # Should NOT contain individual event field logs
        assert "EventId" not in logged
        assert "MessageSeverity" not in logged

    def test_event_with_context(self, make_handler):
        """Payload with Context field -> Context logged."""
        rel.config['verbose'] = True
        payload = {
            "Events": [{"EventType": "Alert", "MessageId": "Test.1.0.Test"}],
            "Context": "MyContext123"
        }
        body = json.dumps(payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        with patch("builtins.open", mock_open()):
            with patch.object(rel.my_logger, "info") as mock_info:
                handler.do_POST()
        assert handler._response_code == 204
        logged = " ".join(str(c) for c in mock_info.call_args_list)
        assert "Context" in logged

    def test_verbose_metric_with_property(self, make_handler):
        """MetricValues with MetricProperty field, verbose=True -> MetricProperty logged."""
        rel.config['verbose'] = True
        payload = {
            "MetricValues": [
                {
                    "MetricId": "CPU_Temp",
                    "MetricValue": "42",
                    "Timestamp": "2026-01-01T00:00:00Z",
                    "MetricProperty": "/Chassis/1/Thermal"
                }
            ],
            "Name": "TestReport"
        }
        body = json.dumps(payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )
        with patch("builtins.open", mock_open()):
            with patch.object(rel.my_logger, "info") as mock_info:
                handler.do_POST()
        assert handler._response_code == 204
        logged = " ".join(str(c) for c in mock_info.call_args_list)
        assert "MetricProperty" in logged

    def test_event_file_exception_handling(self, make_handler, sample_event_payload):
        """Mock file open to raise exception on event file -> Handled gracefully."""
        body = json.dumps(sample_event_payload).encode("utf-8")
        handler = make_handler(
            "POST", "/",
            {"Content-Length": str(len(body))},
            body=body
        )

        call_count = [0]
        original_open = open

        def side_effect_open(path, *args, **kwargs):
            if "Events_" in str(path):
                raise IOError("Disk full")
            # For TimeStamp.log, return a mock
            return mock_open()()

        with patch("builtins.open", side_effect=side_effect_open):
            handler.do_POST()
        # Should still return 204 - the event file error is caught
        assert handler._response_code == 204
