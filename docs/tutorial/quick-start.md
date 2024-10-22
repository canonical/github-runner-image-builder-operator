# Deploy the GitHub runner image builder for the first time

## What you'll do

- Deploy the charm.
- Integrate with GitHub runners.

## Requirements

- A working station, e.g., a laptop, with amd64 architecture.
- Juju 3 installed and bootstrapped to a MicroK8s controller. You can accomplish this process by 
using a Multipass VM as outlined in this guide: 
[Set up / Tear down your test environment](https://juju.is/docs/juju/set-up--tear-down-your-test-environment)
- A running instance of [OpenStack](https://microstack.run/docs/single-node).

## Steps

- Deploy the [GitHub runner charm in OpenStack mode](https://charmhub.io/github-runner/docs/how-to-openstack-runner).

- Deploy the GitHub runner image builder charm. For information on OpenStack credentials, refer 
to the official [OpenStack documentation](https://docs.openstack.org/python-openstackclient/pike/configuration/index.html).

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

- Verify that the image is being built via juju logs:
```
juju debug-log --include=github-runner-image-builder/0
```

- Verify that the image is successfully built. 
```
openstack image list | grep noble-x64
```

- Integrate with GitHub runners. 
```
juju integrate github-runner-image-builder github-runner
```

## Cleanup

- Remove the github-runner-image-builder charm
```
juju remove-application github-runner-image-builder
```

- Remove the images built by the charm
```
openstack image list -f json | jq -r '.[] | select(.Name | contains("jammy-x64")) | .ID' | xargs -r openstack image delete
```
