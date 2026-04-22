# How to pin GitHub runner version

Depending on your needs, you can pin the GitHub runner version by specifying the `runner-version`
configuration option.

```
RUNNER_VERSION=1.2.3
OPENSTACK_AUTH_URL=<openstack-auth-url, e.g. http://my-openstack-deployment/openstack-keystone>
OPENSTACK_PROJECT_DOMAIN_NAME=<openstack project domain name>
OPENSTACK_PROJECT_NAME=<openstack project name>
OPENSTACK_USER_DOMAIN_NAME=<openstack user domain name>
OPENSTACK_USERNAME=<openstack username>

juju add-secret openstack-password password=<openstack project password>
OPENSTACK_PASSWORD_SECRET=$(juju show-secret openstack-password --format json | jq -r 'keys[0]')

juju deploy github-runner-image-builder \
--config runner-version=$RUNNER_VERSION
--config openstack-auth-url=$OPENSTACK_AUTH_URL \
--config openstack-password-secret=$OPENSTACK_PASSWORD_SECRET \
--config openstack-project-domain-name=$OPENSTACK_PROJECT_DOMAIN_NAME \
--config openstack-project-name=$OPENSTACK_PROJECT_NAME \
--config openstack-user-domain-name=$OPENSTACK_USER_DOMAIN_NAME \
--config openstack-user-name=$OPENSTACK_USERNAME
```

You can find out what versions are available on the actions-runner repository's
[releases page](https://github.com/actions/runner/releases).
