# External builder

In order to pre-bootstrap LXD, MicroK8s snaps to Juju; then, external VMs are spawned and ran with
cloud-init script that installs the required components. The external VM is then snapshot to avoid
the limitation of booting a fresh image with snaps with state persistence.
