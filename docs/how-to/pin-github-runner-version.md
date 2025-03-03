# How to pin GitHub runner version

Depending on your needs, you can pin the GitHub runner version by specifying the `runner-version` 
configuration option.

```
RUNNER_VERSION=1.2.3
OPENSTACK_AUTH_URL=<openstack-auth-url, e.g. http://my-openstack-deployment/openstack-keystone>
OPENSTACK_PASSWORD=<openstack project password>
OPENSTACK_PROJECT_DOMAIN_NAME=<openstack project domain name>
OPENSTACK_PROJECT_NAME=<openstack project name>
OPENSTACK_USER_DOMAIN_NAME=<openstack user domain name>
OPENSTACK_USERNAME=<openstack username>

juju deploy github-runner-image-builder \
--config runner-version=$RUNNER_VERSION
--config openstack-auth-url=$OPENSTACK_AUTH_URL \
--config openstack-password=$OPENSTACK_PASSWORD \
--config openstack-project-domain-name=$OPENSTACK_PROJECT_DOMAIN_NAME \
--config openstack-project-name=$OPENSTACK_PROJECT_NAME \
--config openstack-user-domain-name=$OPENSTACK_USER_DOMAIN_NAME \
--config openstack-user-name=$OPENSTACK_USERNAME
```

You can find out what versions are available on the actions-runner repository's
[releases page](https://github.com/actions/runner/releases).