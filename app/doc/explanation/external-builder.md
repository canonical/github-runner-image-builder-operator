# External builder

External VMs are spawned and ran with cloud-init script that installs the required components.
The external VM is then snapshot to avoid the limitation of booting a fresh image with snaps with state persistence.
