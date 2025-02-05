## [#65 chore: Include application repo](https://github.com/canonical/github-runner-image-builder-operator/pull/65)

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
