#!/bin/bash

# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

set -euo pipefail

/snap/bin/charmcraft pack -p tests/integration/data/charm
lxc list
IP=$(lxc list -c 4 --format csv | awk '{print $1}' | head -n 1)
echo "IP=$IP"
sudo nft insert rule ip aproxy prerouting index 0 ip saddr != "$IP" return
