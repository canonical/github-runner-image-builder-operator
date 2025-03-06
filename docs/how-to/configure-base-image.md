# How to configure `base-image`

By default, github-runner-image-builder uses the `noble` Ubuntu OS base. To choose a different
base, you can use the `base-image` configuration option.

```
BASE_IMAGE=jammy
OPENSTACK_AUTH_URL=<openstack-auth-url, e.g. http://my-openstack-deployment/openstack-keystone>
OPENSTACK_PASSWORD=<openstack project password>
OPENSTACK_PROJECT_DOMAIN_NAME=<openstack project domain name>
OPENSTACK_PROJECT_NAME=<openstack project name>
OPENSTACK_USER_DOMAIN_NAME=<openstack user domain name>
OPENSTACK_USERNAME=<openstack username>

juju deploy github-runner-image-builder \
--config base-image=$BASE_IMAGE
--config openstack-auth-url=$OPENSTACK_AUTH_URL \
--config openstack-password=$OPENSTACK_PASSWORD \
--config openstack-project-domain-name=$OPENSTACK_PROJECT_DOMAIN_NAME \
--config openstack-project-name=$OPENSTACK_PROJECT_NAME \
--config openstack-user-domain-name=$OPENSTACK_USER_DOMAIN_NAME \
--config openstack-user-name=$OPENSTACK_USERNAME
```

Currently, jammy (22.04) and noble (24.04) are supported.