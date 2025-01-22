# External builder

In order to pre-bootstrap LXD, MicroK8s snaps to Juju; then, external VMs are spawned and ran with
cloud-init script that installs the required components. Then, it is snapshot to work around
the limitation of booting up a fresh image with snaps with state perseverance.
