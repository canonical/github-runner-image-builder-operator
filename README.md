# GitHub runner image builder operator
<!-- Use this space for badges -->

Provide GitHub runner workload embedded snapshot image to the 
[GitHub runner](https://charmhub.io/github-runner) charm. This charm is deployed as a VM and works
on top of OpenStack infrastructure.

Like any Juju charm, this charm supports one-line deployment, configuration, integration, scaling,
and more. For Charmed GitHub runner image builder, this includes support for configuring:
* multi-arch
* multi Ubuntu bases
* Juju/Microk8s snap channels
* external scripts

For information about how to deploy, integrate, and manage this charm, see the Official 
[CharmHub Documentation](https://charmhub.io/github-runner-image-builder).

## Get started
<!--Briefly summarize what the user will achieve in this guide.-->
Deploy GitHub runner image builder with GitHub runners.

<!--Indicate software and hardware prerequisites-->
You'll require a working [OpenStack installation](https://microstack.run/docs/single-node) with
flavors with minimum 2 CPU cores, 16GB RAM and 20GB disk.

### Set up

Follow [MicroStack's single-node](https://microstack.run/docs/single-node) starting guide to set 
up MicroStack.

Follow the [tutorial on GitHub runner](https://charmhub.io/github-runner) to deploy the GitHub
runner.

### Deploy

Deploy the charm.

```
juju deploy github-runner-image-builder \
--config experimental-external-build=True \
--config experimental-external-build-network=<OPENSTACK-NETWORK-NAME> \
--config openstack-auth-url=<OPENSTACK-AUTH-URL> \
--config openstack-password=<OPENSTACK-PASSWORD> \
--config openstack-project-domain-name=<OPENSTACK-PROJECT-DOMAIN-NAME> \
--config openstack-project-name=<OPENSTACK-PROJECT-NAME> \
--config openstack-user-name=<OPENSTACK-USER-NAME>

juju integrate github-runner-image-builder github-runner
```

### Basic operations
<!--Brief walkthrough of performing standard configurations or operations-->

After having deployed and integrated the charm with the GitHub runner charm, the image should start
to build automatically and be provided to the GitHub runner automatically. The whole process takes
around 10 minutes.

## Integrations
<!-- Information about particularly relevant interfaces, endpoints or libraries related to the charm. For example, peer relation endpoints required by other charms for integration.--> 
* image: The image relation provides the OpenStack image ID to the GitHub runners.
* cos-agent: The COS agent subordinate charm provides observability using the Canonical
Observability Stack (COS).

## Learn more
* [Read more](https://charmhub.io/github-runner-image-builder) <!--Link to the charm's official documentation-->
* [Developer documentation](https://github.com/canonical/github-runner-image-builder-operator/blob/main/CONTRIBUTING.md) <!--Link to any developer documentation-->

## Project and community
* [Issues](https://github.com/canonical/github-runner-image-builder-operator/issues) <!--Link to GitHub issues (if applicable)-->
* [Contributing](https://github.com/canonical/github-runner-image-builder-operator/blob/main/CONTRIBUTING.md) <!--Link to any contribution guides--> 
* [Matrix](https://matrix.to/#/!DYvOMMMjuXPZRJYHdy:ubuntu.com?via=ubuntu.com&via=matrix.org) <!--Link to contact info (if applicable), e.g. Matrix channel-->
