import os
import sys
import tempfile
import pytest
from RedfishEventListener_v1 import parse_list, load_config


class TestParseList:
    """Configuration list parsing tests."""

    def test_parse_list_bracketed(self):
        """'["a","b","c"]' -> ['a', 'b', 'c']"""
        assert parse_list('["a","b","c"]') == ["a", "b", "c"]

    def test_parse_list_unbracketed(self):
        """'a, b, c' -> ['a', 'b', 'c']"""
        assert parse_list("a, b, c") == ["a", "b", "c"]

    def test_parse_list_empty_brackets(self):
        """'[]' -> []"""
        assert parse_list("[]") == []

    def test_parse_list_empty_string(self):
        """'' -> []"""
        assert parse_list("") == []

    def test_parse_list_quoted_values(self):
        """Mixed quote styles -> stripped correctly."""
        assert parse_list("['a', \"b\"]") == ["a", "b"]

    def test_parse_list_whitespace(self):
        """'  [ a , b ]  ' -> ['a', 'b']"""
        assert parse_list("  [ a , b ]  ") == ["a", "b"]

    def test_parse_list_single_item(self):
        """Single item without brackets."""
        assert parse_list("hello") == ["hello"]

    def test_parse_list_single_item_bracketed(self):
        """Single item with brackets."""
        assert parse_list("[hello]") == ["hello"]


def _write_config(path, sections):
    """Helper to write an INI config file from a dict of sections."""
    with open(path, 'w') as f:
        for section, options in sections.items():
            f.write(f"[{section}]\n")
            for key, value in options.items():
                f.write(f"{key} = {value}\n")
            f.write("\n")


class TestLoadConfig:
    """Configuration file loading tests."""

    def test_load_config_minimal(self, tmp_path):
        """Config with only required sections returns valid config dict."""
        cfg_file = tmp_path / "test.ini"
        _write_config(str(cfg_file), {
            "SystemInformation": {
                "ListenerIP": "0.0.0.0",
                "ListenerPort": "8080",
                "UseSSL": "off"
            },
            "SubscriptionDetails": {
                "Destination": "https://example.com/"
            },
            "ServerInformation": {
                "ServerIPs": "[]",
                "UserNames": "[]",
                "Passwords": "[]"
            }
        })
        cfg = load_config(str(cfg_file))
        assert cfg['listenerip'] == "0.0.0.0"
        assert cfg['listenerport'] == 8080
        assert cfg['usessl'] is False
        assert cfg['destination'] == "https://example.com/"

    def test_load_config_full(self, tmp_path):
        """Config with all optional sections populates all values."""
        cfg_file = tmp_path / "test.ini"
        _write_config(str(cfg_file), {
            "SystemInformation": {
                "ListenerIP": "0.0.0.0",
                "ListenerPort": "443",
                "UseSSL": "on"
            },
            "CertificateDetails": {
                "certfile": "my.pem",
                "keyfile": "my.key"
            },
            "ListenerAuthentication": {
                "UserName": "admin",
                "Password": "pass123"
            },
            "SubscriptionDetails": {
                "Destination": "https://listener.example.com/",
                "Context": "TestCtx",
                "EventTypes": '["Alert", "StatusChange"]',
                "Format": "Event",
                "Expand": "true",
                "ResourceTypes": '["Chassis"]',
                "Registries": '["ResourceEvent"]'
            },
            "ServerInformation": {
                "ServerIPs": '["https://server1"]',
                "UserNames": '["user1"]',
                "Passwords": '["pass1"]',
                "LoginType": '["Session"]'
            }
        })
        cfg = load_config(str(cfg_file), verbose=1)
        assert cfg['usessl'] is True
        assert cfg['certfile'] == "my.pem"
        assert cfg['listener_username'] == "admin"
        assert cfg['listener_password'] == "pass123"
        assert cfg['eventtypes'] == ["Alert", "StatusChange"]
        assert cfg['format'] == "Event"
        assert cfg['expand'] == "true"
        assert cfg['resourcetypes'] == ["Chassis"]
        assert cfg['registries'] == ["ResourceEvent"]
        assert cfg['verbose'] == 1

    def test_load_config_no_ssl(self, tmp_path):
        """UseSSL = off -> certfile/keyfile not loaded from CertificateDetails."""
        cfg_file = tmp_path / "test.ini"
        _write_config(str(cfg_file), {
            "SystemInformation": {
                "ListenerIP": "0.0.0.0",
                "ListenerPort": "80",
                "UseSSL": "off"
            },
            "SubscriptionDetails": {
                "Destination": "http://example.com/"
            },
            "ServerInformation": {
                "ServerIPs": "[]",
                "UserNames": "[]",
                "Passwords": "[]"
            }
        })
        cfg = load_config(str(cfg_file))
        assert cfg['usessl'] is False
        # certfile/keyfile remain at defaults since SSL is off
        assert cfg['certfile'] == "cert.pem"
        assert cfg['keyfile'] == "server.key"

    def test_load_config_with_auth(self, tmp_path):
        """ListenerAuthentication section -> credentials loaded."""
        cfg_file = tmp_path / "test.ini"
        _write_config(str(cfg_file), {
            "SystemInformation": {
                "ListenerIP": "0.0.0.0",
                "ListenerPort": "443",
                "UseSSL": "off"
            },
            "ListenerAuthentication": {
                "UserName": "testuser",
                "Password": "testpass"
            },
            "SubscriptionDetails": {
                "Destination": "https://example.com/"
            },
            "ServerInformation": {
                "ServerIPs": "[]",
                "UserNames": "[]",
                "Passwords": "[]"
            }
        })
        cfg = load_config(str(cfg_file))
        assert cfg['listener_username'] == "testuser"
        assert cfg['listener_password'] == "testpass"

    def test_load_config_old_spelling(self, tmp_path):
        """SubsciptionDetails (typo variant) -> parsed correctly."""
        cfg_file = tmp_path / "test.ini"
        _write_config(str(cfg_file), {
            "SystemInformation": {
                "ListenerIP": "0.0.0.0",
                "ListenerPort": "443",
                "UseSSL": "off"
            },
            "SubsciptionDetails": {
                "Destination": "https://old-spelling.com/"
            },
            "ServerInformation": {
                "ServerIPs": "[]",
                "UserNames": "[]",
                "Passwords": "[]"
            }
        })
        cfg = load_config(str(cfg_file))
        assert cfg['destination'] == "https://old-spelling.com/"

    def test_load_config_both_spellings_error(self, tmp_path):
        """Both section names present -> raises SystemExit."""
        cfg_file = tmp_path / "test.ini"
        _write_config(str(cfg_file), {
            "SystemInformation": {
                "ListenerIP": "0.0.0.0",
                "ListenerPort": "443",
                "UseSSL": "off"
            },
            "SubsciptionDetails": {
                "Destination": "https://old.com/"
            },
            "SubscriptionDetails": {
                "Destination": "https://new.com/"
            },
            "ServerInformation": {
                "ServerIPs": "[]",
                "UserNames": "[]",
                "Passwords": "[]"
            }
        })
        with pytest.raises(SystemExit):
            load_config(str(cfg_file))

    def test_load_config_empty_optional_fields(self, tmp_path):
        """Empty EventTypes, Format, etc. -> set to None."""
        cfg_file = tmp_path / "test.ini"
        _write_config(str(cfg_file), {
            "SystemInformation": {
                "ListenerIP": "0.0.0.0",
                "ListenerPort": "443",
                "UseSSL": "off"
            },
            "SubscriptionDetails": {
                "Destination": "https://example.com/",
                "EventTypes": "",
                "Format": "",
                "Expand": "",
                "ResourceTypes": "",
                "Registries": "",
                "Context": ""
            },
            "ServerInformation": {
                "ServerIPs": "[]",
                "UserNames": "[]",
                "Passwords": "[]"
            }
        })
        cfg = load_config(str(cfg_file))
        assert cfg['eventtypes'] is None
        assert cfg['format'] is None
        assert cfg['expand'] is None
        assert cfg['resourcetypes'] is None
        assert cfg['registries'] is None
        assert cfg['contextdetail'] is None
