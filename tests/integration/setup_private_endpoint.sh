#!/bin/bash --login

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# These need to be set as environment variables in GitHub secrets.
MISSING_ENV="false"
if [ -z ${VAULT_APPROLE_ROLE_ID_ALT+x} ]; then
    echo "VAULT_APPROLE_ROLE_ID_ALT needs to be set"
    MISSING_ENV="true"
fi
if [ -z ${VAULT_APPROLE_SECRET_ID_ALT+x} ]; then
    echo "VAULT_APPROLE_SECRET_ID_ALT needs to be set"
    MISSING_ENV="true"
fi
if [ -z ${JUJU_CONTROLLER_ALT+x} ]; then
    echo "JUJU_CONTROLLER_ALT needs to be set"
    MISSING_ENV="true"
fi
if [ -z ${JUJU_MODEL_ALT+x} ]; then
    echo "JUJU_MODEL_ALT needs to be set"
    MISSING_ENV="true"
fi
if [ -z ${PRODSTACK_ALT+x} ]; then
    echo "PRODSTACK_ALT needs to be set"
    MISSING_ENV="true"
fi
if [ -z ${VAULT_ADDR_ALT+x} ]; then
    echo "VAULT_ADDR_ALT needs to be set"
    MISSING_ENV="true"
fi

if [ ${MISSING_ENV} = "true" ]; then
    exit 1
fi

export VAULT_SECRET_PATH_ROLE=secret/${PRODSTACK_ALT}/roles/${JUJU_MODEL_ALT##*/}
export VAULT_SECRET_PATH_COMMON=secret/${PRODSTACK_ALT}/juju/common

function remove_juju_config(){
    if [ -d "${HOME}"/.local/share/juju ]; then
        rm -rf "${HOME}"/.local/share/juju/*
    fi
}

# Ensure we remove any juju config on error
trap remove_juju_config ERR

sudo snap install juju --channel=3.1/stable
sudo snap install vault

[[ $- == *x* ]] && TRACE_ENABLED=0 || TRACE_ENABLED=1

function vault_auth(){
    if [ -z "${VAULT_TOKEN}" ] || ([ -n "${VAULT_TOKEN}" ] && ! vault token lookup > /dev/null 2>&1 ); then
        if [ -n "$TERM" ] && [ "$TERM" != "unknown" ]; then
            echo "Authenticating to vault"
        fi
        # temporarily disable trace
        set -x
        VAULT_TOKEN=$(vault write -f -field=token auth/approle/login role_id="${VAULT_APPROLE_ROLE_ID_ALT}" secret_id="${VAULT_APPROLE_SECRET_ID_ALT}")
        export VAULT_TOKEN
        # reset trace if it was enabled
        [[ $TRACE_ENABLED -eq 0 ]] && set +x
    fi
}

function load_juju_controller_config(){
    vault_auth
    vault read -field=controller_config "${VAULT_SECRET_PATH_COMMON}"/controllers/"${JUJU_CONTROLLER_ALT}" | base64 -d - > "${HOME}/.local/share/juju/controllers.yaml"
}

function load_juju_account_config(){
    vault_auth
    # temporarily disable trace
    set -x
    USERNAME=$(vault read -field=username "${VAULT_SECRET_PATH_ROLE}"/juju) || return
    PASSWORD=$(vault read -field=password "${VAULT_SECRET_PATH_ROLE}"/juju) || return
    # reset trace if it was enabled
    [[ $TRACE_ENABLED -eq 0 ]] && set +x

    # Watch out for tabs vs spaces when editing the below. First character in each line is a tab
    # which is ignored by the heredoc, to prevent script indentation affecting the written file.
    cat <<- EOF > "${HOME}/.local/share/juju/accounts.yaml"
	controllers:
	    ${JUJU_CONTROLLER_ALT?}:
	        user: ${USERNAME}
	        password: ${PASSWORD}
	EOF
}

function switch_juju_model(){
    # cannot switch if these environment variables are set
    # by default, the model is not selected and `juju status` will fail
    unset JUJU_CONTROLLER_ALT JUJU_MODEL_ALT
    juju switch "$(juju models --format json | jq -r '.models[0].name')"
}

# Remove any existing juju config before pulling from Vault
[ -d "${HOME}/.local/share/juju" ] && rm -rf "${HOME}"/.local/share/juju/*
mkdir -p "${HOME}"/.local/share/juju

echo "Pulling Juju controller config from Vault"
load_juju_controller_config
echo "Pulling Juju account config from Vault"
load_juju_account_config
echo "Switching to model"
switch_juju_model

juju status
