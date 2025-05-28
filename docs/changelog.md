## [#121 reuse image id on relation changed](https://github.com/canonical/github-runner-image-builder-operator/pull/121)
> Reuse the already existing image in an cloud and instead of rebuilding on image relation changed.

### Performance Improvements
* Image build propagation to newly joined units should be faster as they are not rebuilt.


## [#113 fix: skip run if relation data is not ready](https://github.com/canonical/github-runner-image-builder-operator/pull/113)
> Fix: Skip image build run if relation data is not ready

### Bug Fixes
* Fixed unnecessary image build runs where unit relation data was not ready.

### Performance Improvements
* Image build propagation to newly joined units should be faster.


## [#101 feat: ppc64le images](https://github.com/canonical/github-runner-image-builder-operator/pull/101) (2025-04-02)
> Add support for building ppc64le images.

### Upgrade Steps
*  Nothing in particular to consider. If PPC64LE architecture is desired, the config option `ppc64le` or `ppc64el` has to be specified.

### Breaking Changes
* None

### New Features
* The charm is now able to build images for the `ppc64le` (`ppc64el`) architecture. `ppc64le` is not officially supported
by GitHub, but a fork of the actions runner binary has been created, which is used in the image. Note
that ppc64le support is experimental and may be removed in the future.

### Bug Fixes
* None

### Performance Improvements
* None

### Other Changes
* None
* 
## [#91 Feature: Add focal support](https://github.com/canonical/github-runner-image-builder-operator/pull/91) (2025-03-07)
> Add support for building focal images.

### Upgrade Steps
*  Nothing in particular to consider.

### Breaking Changes
* None

### New Features
* Add focal as a option for base image. To build focal images specify "focal" as the `base-image` in charm configuration. Note, the focal image does not have yarn pre-installed.

### Bug Fixes
* None

### Performance Improvements
* None

### Other Changes
* None

## [#83 feat: s390x images](https://github.com/canonical/github-runner-image-builder-operator/pull/83) (2025-03-06)
> Add support for building s390x images.

### Upgrade Steps
*  The architecture option has to be specified.

### Breaking Changes
* The charm expects the architecture to be specified in the configuration.

### New Features
* The charm is now able to build images for the `s390x` architecture. `s390x` is not officially supported
by GitHub, but a fork of the actions runner binary has been created, which is used in the image. Note
that s390x support is experimental and may be removed in the future.

### Bug Fixes
* None

### Performance Improvements
* None

### Other Changes
* None

## [#88 Fix: move external script secret out of cloud-init](https://github.com/canonical/github-runner-image-builder-operator/pull/88) (2025-03-04)
> Move running the external script out of cloud-init and use SSH instead.

### Upgrade Steps
*  Nothing in particular to consider.

### Breaking Changes
* None

### New Features
* None

### Bug Fixes
* cloud-init userdata is preserved in the image and should not contain traces of the external script and secrets.

### Performance Improvements
* None

### Other Changes
* None

## [#85 fix: Periodic rebuilding of images](https://github.com/canonical/github-runner-image-builder-operator/pull/85) (2025-02-24)
> Fix the periodic rebuilding of images.


### Upgrade Steps
*  Nothing in particular to consider.

### Breaking Changes
* None

### New Features
* None

### Bug Fixes
* Periodic image building using a cron job was not working.
* The upgrade charm hook did not re-initialize the builder, making the builder not work after an upgrade from revision 51.

### Performance Improvements
* None

### Other Changes
* None
* 


## [#82 Remove juju & microk8s](https://github.com/canonical/github-runner-image-builder-operator/pull/82) (2025-02-14)
> Drop juju and microk8s preinstallation.


### Upgrade Steps
*  Nothing in particular to consider.

### Breaking Changes
* The charm no longer supports pre-installing different Juju and MicroK8s versions in the image.
The configuration options `dockerhub-cache`, `juju-channels` and `microk8s-channels` have been removed.

### New Features
* None

### Bug Fixes
* None

### Performance Improvements
* None

### Other Changes
* None

## [#79 Drop chroot mode](https://github.com/canonical/github-runner-image-builder-operator/pull/79) (2025-02-12)

> Drop local image building (chroot) from the charm.


### Upgrade Steps
* The `experimental-build-*` config options have been removed and replaced by `build-flavor`, `build-network`.
Please specify those options when upgrading the charm.

### Breaking Changes
* The charm no longer supports local building inside the charm unit using chroot.

### New Features
* None

### Bug Fixes
* Fixed a bug where the application log level was not set correctly (due to lower case).

### Performance Improvements
* None

### Other Changes
* Increased OpenStack server timeouts to 20 minutes in the application to allow for longer build/delete times.

## [#81 Drop arm charm support](https://github.com/canonical/github-runner-image-builder-operator/pull/81) (2025-02-07)

> Drop ARM support from the charm.


### Upgrade Steps
* Nothing in particular to consider. Upgrading works for amd64 only.

### Breaking Changes
* No longer supports the `arm64` architecture for the charm (note that building ARM images is still supported,
the charm is agnostic about the build architecture as this is done in an external VM).

### New Features
* None

### Bug Fixes
* None

### Performance Improvements
* None

### Other Changes
* None


## [#65 chore: Include application repo](https://github.com/canonical/github-runner-image-builder-operator/pull/65) (2025-02-06)

> Include application repository in the charm repository.

### Upgrade Steps
* Requires no redeployment (since previous revision). Upgrades from revisions only supporting
the chroot mode require redeployment.

### Breaking Changes
* No longer supports the `app-channel` configuration option.

### New Features
* None

### Bug Fixes
* Fixed a bug where the base image name was hardcoded leading to issues when multiple builders
build images concurrently using the same build tenant.

### Performance Improvements
* None

### Other Changes
* None

## [#27 feat: external cloud](https://github.com/canonical/github-runner-image-builder-operator/pull/27) (2024-09-13)

> Builds GitHub runner images on OpenStack VMs.

### Upgrade Steps
* Requires enough capacity on the OpenStack project cloud to launch builder VMs.
* Requires GitHub Runner revision 249 and above.

### Breaking Changes
* None

### New Features
* None

### Bug Fixes
* None

### Performance Improvements
* None

### Other Changes
* None
