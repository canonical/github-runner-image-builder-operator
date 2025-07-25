# How to configure `revision-history-limit`

You can limit how many revisions of the images are kept in OpenStack Glance by specifying the
`revision-history-limit` configuration option. By default, 5 most recent images are kept.

```
REVISION_HISTORY_LIMIT=2
OPENSTACK_AUTH_URL=<openstack-auth-url, e.g. http://my-openstack-deployment/openstack-keystone>
OPENSTACK_PASSWORD=<openstack project password>
OPENSTACK_PROJECT_DOMAIN_NAME=<openstack project domain name>
OPENSTACK_PROJECT_NAME=<openstack project name>
OPENSTACK_USER_DOMAIN_NAME=<openstack user domain name>
OPENSTACK_USERNAME=<openstack username>

juju deploy github-runner-image-builder \
--config revision-history-limit=$REVISION_HISTORY_LIMIT
--config openstack-auth-url=$OPENSTACK_AUTH_URL \
--config openstack-password=$OPENSTACK_PASSWORD \
--config openstack-project-domain-name=$OPENSTACK_PROJECT_DOMAIN_NAME \
--config openstack-project-name=$OPENSTACK_PROJECT_NAME \
--config openstack-user-domain-name=$OPENSTACK_USER_DOMAIN_NAME \
--config openstack-user-name=$OPENSTACK_USERNAME
```

The example above would keep the two most recent revisions of the image before deletion.