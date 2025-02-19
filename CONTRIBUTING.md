# Contributing

To make contributions to this charm, you'll need a working [development setup](https://juju.is/docs/sdk/dev-setup).

You can create an environment for development with `tox`:

```shell
tox devenv -e integration
source venv/bin/activate
```

## Testing

This project uses `tox` for managing test environments.
There are two tox working directories, one in the root directory and one in the directory
`app` for the application. For each tox working directory, there are some pre-configured environments 
that can be used for linting and formatting code when you're preparing contributions to the charm:


```shell
tox run -e format        # update your code according to linting rules
tox run -e lint          # code style
tox run -e unit          # unit tests
tox run -e integration   # integration tests
tox                      # runs 'format', 'lint', and 'unit' environments
```


The integration tests (both of the charm and the app)
require options to be passed via the command line (see `tests/conftest.py`) and 
environment variables `OPENSTACK_PASSWORD` to be able to deploy the charm and/or upload images to OpenStack.

## Build the charm

Build the charm in this git repository using:

```shell
charmcraft pack
```

<!-- You may want to include any contribution/style guidelines in this document>
