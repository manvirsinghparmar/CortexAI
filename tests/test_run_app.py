from __future__ import annotations

import socket

import pytest

import run_app


def test_require_port_available_accepts_unused_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    run_app._require_port_available("Test", "127.0.0.1", port)


def test_require_port_available_rejects_listening_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]

        with pytest.raises(RuntimeError, match=rf"Test port 127\.0\.0\.1:{port} is unavailable"):
            run_app._require_port_available("Test", "127.0.0.1", port)


def test_windows_taskkill_command_targets_descendants():
    assert run_app._windows_taskkill_command(1234, force=False) == [
        "taskkill",
        "/PID",
        "1234",
        "/T",
    ]
    assert run_app._windows_taskkill_command(1234, force=True) == [
        "taskkill",
        "/PID",
        "1234",
        "/T",
        "/F",
    ]
