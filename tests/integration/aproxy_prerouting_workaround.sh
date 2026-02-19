#!/bin/bash

# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# Aproxy is installed on the CI runners and we want to test if the charm and workload respect the 
# proxy values without aproxy. This script adds a nftables rule to bypass aproxy for any traffic 
# originating from the LXD container, except for the juju controller traffic which is needed 
# to spin up machines for the charms.

set -euo pipefail

# charmcraft pack runs inside the LXD container and needs to go through proxy so it 
# will be done before modifying the nftables rules.
/snap/bin/charmcraft pack -p tests/integration/data/charm

IP=$(lxc list -c 4 --format csv | awk '{print $1}' | head -n 1)

if [[ -z "${IP:-}" ]]; then
    echo "Error: no IPv4 address found from 'lxc list'. Ensure an LXC container with an IPv4 address is running." >&2
    exit 1
fi

echo "IP=$IP"

if ! sudo nft list chain ip aproxy prerouting >/dev/null 2>&1; then
    echo "Error: nftables chain 'ip aproxy prerouting' not found. Ensure aproxy is configured before running this script." >&2
    exit 1
fi

# we want only the juju controller traffic to go through aproxy to spin up machines for the charms.
# Any other charm related traffic should handle proxy by itself.
sudo nft insert rule ip aproxy prerouting index 0 ip saddr != "$IP" return
