# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with proxy."""

# Ignore B404:blacklist since all subprocesses are run with predefined executables.
import subprocess  # nosec

from exceptions import ProxyInstallError
from state import ProxyConfig

UBUNTU_USER = "ubuntu"


def setup(proxy: ProxyConfig | None) -> None:
    """Install and configure aproxy.

    Args:
        proxy: The charm proxy configuration.

    Raises:
        ProxyInstallError: If there was an error setting up proxy.
    """
    if not proxy:
        return
    try:
        subprocess.run(  # nosec: B603
            ["/usr/bin/sudo", "snap", "install", "aproxy", "--channel=latest/edge"],
            timeout=5 * 60,
            check=True,
            user=UBUNTU_USER,
        )
        configure_aproxy(proxy=proxy)
        # Ignore shell=True rule since it is safe
        subprocess.run(  # nosec: B602, B603
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
            shell=True,
            user=UBUNTU_USER,
        )
    except subprocess.SubprocessError as exc:
        raise ProxyInstallError from exc


def configure_aproxy(proxy: ProxyConfig | None) -> None:
    """Configure aproxy.

    Args:
        proxy: The charm proxy configuration.

    Raises:
        ProxyInstallError: If there was an error configuring aproxy.
    """
    if not proxy:
        return
    proxy_str = (proxy.http or proxy.https).replace("http://", "").replace("https://", "")
    try:
        subprocess.run(  # nosec: B603
            ["/usr/bin/sudo", "snap", "set", "aproxy", f"proxy={proxy_str}"],
            timeout=5 * 60,
            check=True,
            user=UBUNTU_USER,
        )
    except subprocess.SubprocessError as exc:
        raise ProxyInstallError from exc
