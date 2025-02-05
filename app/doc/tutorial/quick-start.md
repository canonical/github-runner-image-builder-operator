# Build your first image

## What you'll do

- Install the CLI
- Initialize the builder
- Run the image build

## Requirements

- [Pipx installed](https://pipx.pypa.io/stable/installation/)
- Apt packages gcc, pipx, python3-dev
  - `sudo apt-get install -y python3-dev gcc pipx`
- Working [OpenStack environment](https://microstack.run/docs/single-node)
- A clouds.yaml configuration with the OpenStack environment

## Steps

### Install the CLI

- Install the CLI
  - `pipx install git+https://github.com/canonical/github-runner-image-builder@stable`

### Initialize the builder

- Run `github-runner-image-builder init` to install the dependencies for building the image.

### Run the image build

- Choose the OpenStack `<cloud-name>` from the clouds.yaml file, and set the desired image name as `<image-name>`.
```
CLOUD_NAME=<cloud-name>
IMAGE_NAME=<image-name>
github-runner-image-builder run $CLOUD_NAME $IMAGE_NAME
```

This event begins building the image.

### Verify that the image is available on OpenStack

- Run `openstack image list | grep <image-name>` to see the image in "active" status.
- You can also create a server with the image above to check the contents installed on the image.
For more information, refer to the official OpenStack documentation on creating servers here:
https://docs.openstack.org/python-openstackclient/pike/cli/command-objects/server.html#server-create

### Clean up

- To clean up, run `openstack image delete <image-name>` after you're done following the tutorial .
