#!/bin/bash --login

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# These need to be set as environment variables in GitHub secrets.
MISSING_ENV="false"
if [ -z ${VAULT_APPROLE_ROLE_ID+x} ]; then
    echo "VAULT_APPROLE_ROLE_ID needs to be set"
    MISSING_ENV="true"
fi
if [ -z ${VAULT_APPROLE_SECRET_ID+x} ]; then
    echo "VAULT_APPROLE_SECRET_ID needs to be set"
    MISSING_ENV="true"
fi
if [ -z ${JUJU_CONTROLLER+x} ]; then
    echo "JUJU_CONTROLLER needs to be set"
    MISSING_ENV="true"
fi
if [ -z ${JUJU_MODEL+x} ]; then
    echo "JUJU_MODEL needs to be set"
    MISSING_ENV="true"
fi
if [ -z ${PRODSTACK+x} ]; then
    echo "PRODSTACK needs to be set"
    MISSING_ENV="true"
fi
if [ -z ${VAULT_ADDR+x} ]; then
    echo "VAULT_ADDR needs to be set"
    MISSING_ENV="true"
fi

if [ ${MISSING_ENV} = "true" ]; then
    exit 1
fi

export VAULT_SECRET_PATH_ROLE=secret/${PRODSTACK}/roles/${JUJU_MODEL##*/}
export VAULT_SECRET_PATH_COMMON=secret/${PRODSTACK}/juju/common

function remove_juju_config(){
    if [ -d "${HOME}"/.local/share/juju ]; then
        rm -rf "${HOME}"/.local/share/juju/*
    fi
}

# Ensure we remove any juju config on any kind of exit
trap remove_juju_config EXIT

sudo snap install juju --channel=3.1/stable
sudo snap install vault

function vault_auth(){
    if [ -z "${VAULT_TOKEN}" ] || ([ -n "${VAULT_TOKEN}" ] && ! vault token lookup > /dev/null 2>&1 ); then
        if [ -n "$TERM" ] && [ "$TERM" != "unknown" ]; then
            echo "Authenticating to vault"
        fi
        VAULT_TOKEN=$(vault write -f -field=token auth/approle/login role_id="${VAULT_APPROLE_ROLE_ID}" secret_id="${VAULT_APPROLE_SECRET_ID}")
        export VAULT_TOKEN
    fi
}

function load_juju_controller_config(){
    vault_auth
    vault read -field=controller_config "${VAULT_SECRET_PATH_COMMON}"/controllers/"${JUJU_CONTROLLER}" | base64 -d - > "${HOME}/.local/share/juju/controllers.yaml"
}

function load_juju_account_config(){
    vault_auth
    USERNAME=$(vault read -field=username "${VAULT_SECRET_PATH_ROLE}"/juju) || return
    PASSWORD=$(vault read -field=password "${VAULT_SECRET_PATH_ROLE}"/juju) || return
    # Watch out for tabs vs spaces when editing the below. First character in each line is a tab
    # which is ignored by the heredoc, to prevent script indentation affecting the written file.
    cat <<- EOF > "${HOME}/.local/share/juju/accounts.yaml"
	controllers:
	    ${JUJU_CONTROLLER?}:
	        user: ${USERNAME}
	        password: ${PASSWORD}
	EOF
}

# Remove any existing juju config before pulling from Vault
[ -d "${HOME}/.local/share/juju" ] && rm -rf "${HOME}"/.local/share/juju/*
mkdir -p "${HOME}"/.local/share/juju

echo "Pulling Juju controller config from Vault"
load_juju_controller_config
echo "Pulling Juju account config from Vault"
load_juju_account_config

juju status