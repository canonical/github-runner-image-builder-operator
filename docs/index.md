A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) for building VM
images for [GitHub self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners).

This charm simplifies the initial deployment and "day N" operations of building images for GitHub
self-hosted runners.

Some of the charm dependencies upgrades on a schedule to migrate security risks. The
landscape-client charm can be deployed with this charm to ensure other dependencies are up to date.

The charm operates a set of isolated single-use OpenStack virtual machines, to build up-to-date
images for GitHub runners.

This charm will make operating GitHub self-hosted runners simple and straightforward for DevOps or
SRE teams through Juju's clean interface.

# Contents