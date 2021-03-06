import pytest
import http
import json
from unittest.mock import Mock
from http.server import HTTPServer
from io import BytesIO

from lambda_log_shipper.logs_subscriber import (
    subscribe_to_logs,
    LogsHttpRequestHandler,
)
from lambda_log_shipper.handlers.base_handler import LogRecord
from lambda_log_shipper.logs_manager import LogsManager


@pytest.fixture
def logs_server_mock(monkeypatch):
    class MockRequest:
        def makefile(self, *args, **kwargs):
            return BytesIO(b"POST /")

        def sendall(self, _):
            pass

    handler = LogsHttpRequestHandler(MockRequest(), ("0.0.0.0", 8888), Mock())
    monkeypatch.setattr(handler, "headers", {"Content-Length": "1000"}, False)
    return handler


def test_subscribe_to_logs(monkeypatch):
    mock = Mock()
    monkeypatch.setattr(http.client, "HTTPConnection", mock)
    monkeypatch.setattr(HTTPServer, "serve_forever", lambda: None)
    monkeypatch.setattr(HTTPServer, "server_bind", lambda _: None)

    subscribe_to_logs("eid")

    expected = '{"destination": {"protocol": "HTTP", "URI": "http://sandbox:1060"}, "types": ["platform", "function"]}'
    mock("127.0.0.1").request.assert_called_once_with(
        "PUT",
        "/2020-08-15/logs",
        expected,
        headers={"Lambda-Extension-Identifier": "eid"},
    )


def test_do_POST_happy_flow(logs_server_mock, monkeypatch, raw_record):
    monkeypatch.setattr(
        logs_server_mock,
        "rfile",
        BytesIO(b"[" + json.dumps(raw_record).encode() + b"]"),
        False,
    )
    logs_server_mock.do_POST()

    assert LogsManager.get_manager().pending_logs == [LogRecord.parse(raw_record)]


def test_do_POST_exception(logs_server_mock, monkeypatch, raw_record, caplog):
    monkeypatch.setattr(logs_server_mock, "rfile", BytesIO(b"no json"), False)
    logs_server_mock.do_POST()

    assert caplog.records[-1].exc_info[0].__name__ == "JSONDecodeError"
