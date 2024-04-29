#!/usr/bin/env bash

#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

# Script to setup microstack for testing
# This script is intended to be run in a self-hosted runner, which uses proxy settings,
# and we encountered some issues with no_proxy not being interpreted correctly.

set -e

retry() {
    local command="$1"
    local wait_message="$2"
    local max_try="$3"

    local attempt=0

    while ! $command
    do
        attempt=$((attempt + 1))
        if [[ attempt -ge $max_try ]]; then
            return
        fi

        echo "$wait_message"
        sleep 10
    done
}

# microk8s charm installed by microstack tries to create an alias for kubectl and fails otherwise
sudo snap remove kubectl
# Install microstack
sudo snap install openstack --channel 2023.1 --devmode
sunbeam prepare-node-script | bash -x
sleep 10
# The following can take a while....
sudo -g snap_daemon timeout 1200 sunbeam cluster bootstrap --accept-defaults
sudo -g snap_daemon sunbeam configure --accept-defaults --openrc demo-openrc
clouds_yaml="${PWD}/clouds.yaml"
sg snap_daemon -c "sunbeam cloud-config" | tee "$clouds_yaml"
# Test connection
OS_CLIENT_CONFIG_FILE="$clouds_yaml" openstack --os-cloud sunbeam user show demo

juju clouds || echo "Failed to list clouds"
juju bootstrap localhost lxd
echo "PYTEST_ADDOPTS=--openstack-clouds-yaml=$clouds_yaml" >> "${GITHUB_ENV}"
