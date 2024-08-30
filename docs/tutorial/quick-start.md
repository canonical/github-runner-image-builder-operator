# # Quick start

## What you'll do

- Deploy the charm.
- Provide GitHub runners on OpenStack mode with images.

## Requirements

- GitHub runner running in OpenStack mode.
- A running instance of [OpenStack](https://microstack.run/docs/single-node).

## Steps

1. Deploy the [GitHub runner charm in OpenStack mode](https://charmhub.io/github-runner/docs/how-to-openstack-runner).

2. Deploy the GitHub runner image builder charm. For information on openstack credentials, refer 
to the official [OpenStack configuration documentation](https://docs.openstack.org/python-openstackclient/pike/configuration/index.html).

```
OPENSTACK_AUTH_URL=<openstack-auth-url, e.g. http://my-openstack-deployment/openstack-keystone>
OPENSTACK_PASSWORD=<openstack project password>
OPENSTACK_PROJECT_DOMAIN_NAME=<openstack project domain name>
OPENSTACK_PROJECT_NAME=<openstack project name>
OPENSTACK_USER_DOMAIN_NAME=<openstack user domain name>
OPENSTACK_USERNAME=<openstack username>
juju deploy github-runner-image-builder \
--config openstack-auth-url=$OPENSTACK_AUTH_URL \
--config openstack-password=$OPENSTACK_PASSWORD \
--config openstack-project-domain-name=$OPENSTACK_PROJECT_DOMAIN_NAME \
--config openstack-project-name=$OPENSTACK_PROJECT_NAME \
--config openstack-user-domain-name=$OPENSTACK_USER_DOMAIN_NAME \
--config openstack-user-name=$OPENSTACK_USERNAME
```

3. Verify that the image is getting built via juju logs! `juju debug-log --include=github-runner-image-builder/0`

4. Verify that the image is successfully built. `openstack image list | grep noble-x64`
