A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) for building VM
images for [GitHub self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners).

This charm simplifies the initial deployment and building images for GitHub
self-hosted runners.

Some of the charm dependencies upgrades on a schedule to migrate security risks. The 
[Landscape Client charm](https://charmhub.io/landscape-client) can be deployed with this charm to ensure other dependencies are up to date.

The charm operates a set of isolated single-use OpenStack virtual machines, to build up-to-date
images for GitHub runners.

This charm will make operating GitHub self-hosted runners simple and straightforward for DevOps or
SRE teams through Juju's clean interface.

## In this documentation

| | |
|--|--|
|  [Tutorials](https://charmhub.io/github-runner-image-builder/docs/quick-start)</br>  Get started - a hands-on introduction to using the GitHub runner image builder charm for new users </br> | [How-to guides](https://charmhub.io/github-runner-image-builder/docs/configure-base-image) </br> Step-by-step guides covering key operations and common tasks |


## Contributing to this documentation

Documentation is an important part of this project, and we take the same open-source approach to the documentation as the code. As such, we welcome community contributions, suggestions and constructive feedback on our documentation. Our documentation is hosted on the [Charmhub forum](https://discourse.charmhub.io/t/github-runner-image-builder-documentation-overview) to enable easy collaboration. Please use the "Help us improve this documentation" links on each documentation page to either directly change something you see that's wrong, ask a question, or make a suggestion about a potential change via the comments section.

If there's a particular area of documentation that you'd like to see that's missing, please [file a bug](https://github.com/canonical/github-runner-image-builder-operator/issues).

## Project and community

The GitHub runner image builder charm is a member of the Ubuntu family. It's an open-source project that warmly welcomes community projects, contributions, suggestions, fixes, and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [Get support](https://discourse.charmhub.io/)
- [Join our online chat](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
- [Contribute](Contribute)

Thinking about using the GitHub runner image builder charm for your next project? [Get in touch](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)!

# Contents

1. [How To](how-to)
  1. [How to configure base-image](how-to/configure-base-image.md)
  1. [How to configure build-interval](how-to/configure-build-interval.md)
  1. [How to configure revision-history](how-to/configure-revision-history.md)
  1. [How to configure pin-github-runner-version](how-to/pin-github-runner-version.md)
1. [Tutorial](tutorial)
  1. [Quick start](tutorial/quick-start.md)
1. [Changelog](changelog.md)
