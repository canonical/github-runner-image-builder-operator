# How to use external builder VM

This guide will cover how to use an external OpenStack builder VM to build and snapshot images.

Run the following command to create a snapshot image of a VM launched by the 
github-runner-image-builder.

Run `openstack list flavor` to find out what flavor is available.
Run `openstack list network` to find out what network is available.

```
FLAVOR=<available openstack flavor>
NETWORK=<openstack network for builder VMs>
github-runner-image-builder --flavor $FLAVOR --network $NETWORK
```
