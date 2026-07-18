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


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "127.10.20.30", "::1", "[::1]"])
def test_vite_dev_server_accepts_loopback_hosts(host):
    run_app._validate_vite_dev_server(
        frontend_host=host,
        allow_public_dev_server=False,
        env={},
    )


@pytest.mark.parametrize("name", ["APP_ENV", "ENVIRONMENT", "ENV"])
def test_vite_dev_server_rejects_production_environment_even_with_public_override(name):
    with pytest.raises(RuntimeError, match=rf"{name} is production-like"):
        run_app._validate_vite_dev_server(
            frontend_host="127.0.0.1",
            allow_public_dev_server=True,
            env={name: "production"},
        )


def test_vite_dev_server_rejects_public_host_by_default():
    with pytest.raises(RuntimeError, match=r"Refusing to expose the Vite development server"):
        run_app._validate_vite_dev_server(
            frontend_host="0.0.0.0",
            allow_public_dev_server=False,
            env={},
        )


def test_vite_dev_server_accepts_public_host_for_trusted_network_development():
    run_app._validate_vite_dev_server(
        frontend_host="0.0.0.0",
        allow_public_dev_server=True,
        env={"APP_ENV": "local"},
    )
