#!/bin/bash

# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

set -euo pipefail

# charmcraft pack runs inside the LXD container and needs to go through proxy so it 
# will be done before modifying the nftables rules.
/snap/bin/charmcraft pack -p tests/integration/data/charm
lxc list
IP=$(lxc list -c 4 --format csv | awk '{print $1}' | head -n 1)
echo "IP=$IP"
# we want only the juju controller traffic to go through aproxy to spin up machines for the charms.
# Any other charm related traffic should handle proxy by itself.
sudo nft insert rule ip aproxy prerouting index 0 ip saddr != "$IP" return
