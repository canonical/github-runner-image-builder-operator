A [Juju](https://juju.is/) [charm](https://documentation.ubuntu.com/juju/3.6/reference/charm/) deploying
and managing VM image builds for [GitHub self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners).

The charm operates a set of isolated, single-use OpenStack virtual machines to build up-to-date
images for GitHub runners. Images are rebuilt on a configurable schedule so that runner VMs always
include the latest software and security patches. The
[Landscape Client charm](https://charmhub.io/landscape-client) can be integrated to keep additional
charm dependencies up to date between scheduled builds.

This charm makes operating GitHub self-hosted runner image builds simple and straightforward for
DevOps or SRE teams through Juju's clean interface.

## In this documentation

| | |
|--|--|
| **Get started** | [Quick-start tutorial](https://charmhub.io/github-runner-image-builder/docs/tutorial-quick-start) — deploy the charm and build your first runner image |
| **Deployment** | [Configure base image](https://charmhub.io/github-runner-image-builder/docs/how-to-configure-base-image) \| [Configure build interval](https://charmhub.io/github-runner-image-builder/docs/how-to-configure-build-interval) \| [Configure revision history](https://charmhub.io/github-runner-image-builder/docs/how-to-configure-revision-history) \| [Pin GitHub runner version](https://charmhub.io/github-runner-image-builder/docs/how-to-pin-github-runner-version) |
| **Operations** | [Upgrade](https://charmhub.io/github-runner-image-builder/docs/how-to-upgrade) |
| **Design** | [Charm architecture](https://charmhub.io/github-runner-image-builder/docs/explanation-charm-architecture) |

## How this documentation is organised

This documentation follows the [Diátaxis](https://diataxis.fr/) structure:

- The [Tutorial](https://charmhub.io/github-runner-image-builder/docs/tutorial-quick-start) takes you step-by-step through deploying the charm and building your first runner image.
- [How-to guides](https://charmhub.io/github-runner-image-builder/docs/how-to-configure-base-image) assume basic familiarity with the charm. They cover configuring, operating, and upgrading your deployment.
- [Explanation](https://charmhub.io/github-runner-image-builder/docs/explanation-charm-architecture) provides technical details on the charm architecture and design.

## Contributing to this documentation

Documentation is an important part of this project, and we take the same open-source approach to the documentation as the code. As such, we welcome community contributions, suggestions, and constructive feedback on our documentation. Our documentation is hosted on the [Charmhub forum](https://discourse.charmhub.io/t/github-runner-image-builder-documentation-overview) to enable easy collaboration. Please use the "Help us improve this documentation" links on each documentation page to either directly change something you see that's wrong, ask a question, or make a suggestion about a potential change through the comments section.

If there's a particular area of documentation that you'd like to see that's missing, please [file a bug](https://github.com/canonical/github-runner-image-builder-operator/issues).

## Project and community

The GitHub runner image builder charm is a member of the Ubuntu family. It's an open-source project that warmly welcomes community projects, contributions, suggestions, fixes, and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [Get support](https://discourse.charmhub.io/)
- [Join our online chat](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
- [Contribute](https://github.com/canonical/github-runner-image-builder-operator/blob/main/CONTRIBUTING.md)

Thinking about using the GitHub runner image builder charm for your next project? [Get in touch](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)! 
