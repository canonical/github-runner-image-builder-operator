[![CharmHub Badge](https://charmhub.io/github-runner-image-builder/badge.svg)](https://charmhub.io/github-runner-image-builder)
[![Promote charm](https://github.com/canonical/github-runner-operator/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/github-runner-operator/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

# GitHub runner image builder

## Description

This machine charm supplies [self-hosted GitHub runner](https://charmhub.io/github-runner) charms 
with images to use to deploy it's runners on. It periodically builds and supplies the image IDs to
ensure that the latest build of the image is used.

## Development

This charm uses black and flake8 for formatting. Both run with the lint stage of tox.

## Testing

Testing is run via tox and pytest. The unit test can be ran with `tox -e unit` and the integration test on juju 3.1 with `tox -e integration`.

Dependencies are installed in virtual environments. Integration testing requires a juju controller to execute. These tests will use the existing controller, creating an ephemeral model for the tests which is removed after testing. If you do not already have a controller setup, you can configure a local instance via LXD, see the [upstream documentation](https://juju.is/docs/lxd-cloud) for details.

## Generating src docs for every commit

Run the following command:

```bash
echo -e "tox -e src-docs\ngit add src-docs\n" >> .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```
