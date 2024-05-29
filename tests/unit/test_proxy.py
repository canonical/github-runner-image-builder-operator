# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for proxy module."""

from unittest.mock import MagicMock, _Call, call

import pytest

import proxy
from proxy import ProxyConfig, ProxyInstallError, subprocess


def test_setup_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a monkeypatched subprocess.run that raises an error.
    act: when proxy.setup is called.
    assert: ProxyInstallError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(side_effect=subprocess.CalledProcessError(1, "", "", "Setup error")),
    )

    with pytest.raises(ProxyInstallError) as exc:
        proxy.setup(MagicMock())

    assert "Setup error" in str(exc.getrepr())


def test_setup_no_proxy(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given no proxy configuration.
    act: when proxy.setup is called.
    assert: no setup processes are called.
    """
    monkeypatch.setattr(subprocess, "run", run_mock := MagicMock())

    proxy.setup(None)

    run_mock.assert_not_called()


def test_setup(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given a charm proxy configuration.
    act: when setup is called.
    assert: aproxy install command and nft table configuration command is called.
    """
    monkeypatch.setattr(subprocess, "run", run_mock := MagicMock())
    monkeypatch.setattr(proxy, "configure_aproxy", configure_aproxy_mock := MagicMock())

    proxy.setup(MagicMock())

    configure_aproxy_mock.assert_called_once()
    run_mock.assert_has_calls(
        [
            call(
                ["/usr/bin/sudo", "snap", "install", "aproxy", "--channel=latest/edge"],
                timeout=5 * 60,
                check=True,
                user="ubuntu",
            ),
            call(
                """/usr/bin/sudo nft -f - << EOF
define default-ip = $(ip route get $(ip route show 0.0.0.0/0 \
| grep -oP 'via \\K\\S+') | grep -oP 'src \\K\\S+')
define private-ips = { 10.0.0.0/8, 127.0.0.1/8, 172.16.0.0/12, 192.168.0.0/16 }
table ip aproxy
flush table ip aproxy
table ip aproxy {
    chain prerouting {
            type nat hook prerouting priority dstnat; policy accept;
            ip daddr != \\$private-ips tcp dport { 80, 443 } counter dnat to \\$default-ip:8443
    }

    chain output {
            type nat hook output priority -100; policy accept;
            ip daddr != \\$private-ips tcp dport { 80, 443 } counter dnat to \\$default-ip:8443
    }
}
EOF""",
                timeout=5 * 60,
                check=True,
                # This is not an actual subprocess call.
                shell=True,  # nosec: B604
                user="ubuntu",
            ),
        ]
    )


def test_configure_aproxy_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given monkeypatched subprocess run mocking aproxy setup.
    act: when configure_aproxy is run.
    assert: ProxyInstallError is raised.
    """
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(side_effect=subprocess.CalledProcessError(1, "", "", "Invalid proxy")),
    )

    with pytest.raises(ProxyInstallError) as exc:
        proxy.configure_aproxy(MagicMock())

    assert "Invalid proxy" in str(exc.getrepr())


def test_configure_aproxy_none(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: given no proxy configuration.
    act: when configure_aproxy is run.
    assert: no setup calls are made.
    """
    monkeypatch.setattr(subprocess, "run", run_mock := MagicMock())

    proxy.configure_aproxy(None)

    run_mock.assert_not_called()


@pytest.mark.parametrize(
    "proxy_config, expected_call",
    [
        pytest.param(
            ProxyConfig(http="http://proxy.internal:3128", https="", no_proxy=""),
            call(
                ["/usr/bin/sudo", "snap", "set", "aproxy", "proxy=proxy.internal:3128"],
                timeout=300,
                check=True,
                user="ubuntu",
            ),
            id="http proxy",
        ),
        pytest.param(
            ProxyConfig(http="", https="https://proxy.internal:3128", no_proxy=""),
            call(
                ["/usr/bin/sudo", "snap", "set", "aproxy", "proxy=proxy.internal:3128"],
                timeout=300,
                check=True,
                user="ubuntu",
            ),
            id="https proxy",
        ),
    ],
)
def test_configure_aproxy(
    monkeypatch: pytest.MonkeyPatch, proxy_config: ProxyConfig, expected_call: _Call
):
    """
    arrange: given no proxy configuration.
    act: when configure_aproxy is run.
    assert: no setup calls are made.
    """
    monkeypatch.setattr(subprocess, "run", run_mock := MagicMock())

    proxy.configure_aproxy(proxy_config)

    run_mock.assert_has_calls([expected_call])
