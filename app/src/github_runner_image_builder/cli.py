# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Main entrypoint for github-runner-image-builder cli application."""

import os

# Subprocess module is used to execute trusted commands
import subprocess  # nosec: B404
import urllib.parse
from pathlib import Path

import click

from github_runner_image_builder import config, logging, openstack_builder, store

# Bandit thinks this is a hardcoded secret.
SECRET_PREFIX = "IMAGE_BUILDER_SECRET_"  # nosec


@click.option(
    "--log-level",
    type=click.Choice(config.LOG_LEVELS),
    default="info",
    help="Configure logging verbosity.",
)
@click.group()
def main(log_level: str | int) -> None:
    """Run entrypoint for Github runner image builder CLI.

    Args:
        log_level: The logging verbosity to apply.
    """
    logging.configure(log_level=log_level)


@main.command(name="init")
@click.option(
    "--arch",
    type=click.Choice((config.Arch.ARM64, config.Arch.X64)),
    default=None,
    help="Image architecture to initialize for. Defaults the host architecture.",
)
@click.option(
    "--cloud-name",
    default="",
    help="The cloud to use from the clouds.yaml file. The CLI looks for clouds.yaml in paths of "
    "the following order: current directory, ~/.config/openstack, /etc/openstack.",
)
@click.option(
    "--prefix",
    default="",
    help="Name of the OpenStack resources to prefix with. Used to run the image builder in "
    "parallel under same OpenStack project. Ignored if --experimental-external is not enabled",
)
def initialize(arch: config.Arch | None, cloud_name: str, prefix: str) -> None:
    """Initialize builder CLI function wrapper.

    Args:
        arch: The architecture to build for.
        cloud_name: The cloud name to use from clouds.yaml.
        prefix: The prefix to use for OpenStack resource names.
    """
    arch = arch if arch else config.get_supported_arch()

    openstack_builder.initialize(
        arch=arch,
        cloud_name=openstack_builder.determine_cloud(cloud_name=cloud_name),
        prefix=prefix,
    )


@main.command(name="latest-build-id")
@click.argument("cloud_name")
@click.argument("image_name")
def get_latest_build_id(cloud_name: str, image_name: str) -> None:
    # Click arguments do not take help parameter, display help through docstrings.
    """Get latest build ID of <image_name> from Openstack <cloud_name>.

    Args:
        cloud_name: The cloud to use from the clouds.yaml file. The CLI looks for clouds.yaml in
            paths of the following order: current directory, ~/.config/openstack, /etc/openstack.
        image_name: The image name uploaded to Openstack.
    """
    click.echo(
        message=store.get_latest_build_id(cloud_name=cloud_name, image_name=image_name),
        nl=False,
    )


# The arguments are necessary input for click validation function.
def _validate_snap_channel(
    ctx: click.Context, param: click.Parameter, value: str  # pylint: disable=unused-argument
) -> str:
    """Validate snap channel string input.

    Args:
        ctx: Click context argument.
        param: Click parameter argument.
        value: The value passed into --juju option.

    Raises:
        BadParameter: If invalid juju channel was passed in.

    Returns:
        The validated Juju channel option.
    """
    if not value:
        return ""
    try:
        track, risk = value.strip().split("/")
        return f"{track}/{risk}"
    except ValueError as exc:
        raise click.BadParameter("format must be '<track>/<list>'") from exc


# The arguments are necessary input for click validation function.
def _parse_url(
    ctx: click.Context, param: click.Parameter, value: str  # pylint: disable=unused-argument
) -> urllib.parse.ParseResult | None:
    """Validate snap channel string input.

    Args:
        ctx: Click context argument.
        param: Click parameter argument.
        value: The value passed into any URL option.

    Raises:
        BadParameter: If invalid URL was passed in.

    Returns:
        The valid URL parse result.
    """
    if not value:
        return None
    parse_result = urllib.parse.urlparse(value)
    if not parse_result.netloc or not parse_result.scheme:
        raise click.BadParameter("URL must be '<scheme>://<hostname>' format")
    return parse_result


@main.command(name="run")
@click.argument("cloud_name")
@click.argument("image_name")
@click.option(
    "--arch",
    type=click.Choice((config.Arch.ARM64, config.Arch.X64)),
    default=None,
    help="Image architecture to initialize for. Defaults the host architecture.",
)
@click.option(
    "-b",
    "--base-image",
    type=click.Choice(config.BASE_CHOICES),
    default="noble",
    help=("The Ubuntu base image to use as build base."),
)
@click.option(
    "--dockerhub-cache",
    type=str,
    callback=_parse_url,
    default=None,
    help=(
        "The DockerHub cache to use to instantiate builder VMs with. Useful when creating images"
        "with MicroK8s."
    ),
)
@click.option(
    "-s",
    "--callback-script",
    type=click.Path(exists=True),
    default=None,
    help=(
        "The callback script to trigger after image is built. The callback script is called"
        "with the first argument as the image ID."
    ),
)
@click.option(
    "-k",
    "--keep-revisions",
    default=5,
    help="The maximum number of images to keep before deletion.",
)
@click.option(
    "--runner-version",
    default="",
    help=(
        "The GitHub runner version to install, e.g. 2.317.0. "
        "See github.com/actions/runner/releases/."
        "Defaults to latest version."
    ),
)
@click.option(
    "--flavor", default="", help="OpenStack flavor to launch for external build run VMs. "
)
@click.option(
    "--juju",
    callback=_validate_snap_channel,
    default="",
    help="Juju channel to install and bootstrap. E.g. to install Juju 3.1/stable, pass the values "
    "--juju=3.1/stable",
)
@click.option(
    "--microk8s",
    callback=_validate_snap_channel,
    default="",
    help="Microk8s channel to install and bootstrap. E.g. to install Microk8s 1.31-strict/stable, "
    "pass the values --microk8s=1.31-strict/stable",
)
@click.option(
    "--network", default="", help="OpenStack network to launch the external build run VMs under. "
)
@click.option(
    "--prefix",
    default="",
    help="Name of the OpenStack resources to prefix with. Used to run the image builder in "
    "parallel under same OpenStack project.",
)
@click.option(
    "--proxy",
    default="",
    help="Proxy to use for external build VMs in host:port format (without scheme). ",
)
@click.option(
    "--script-url",
    callback=_parse_url,
    default=None,
    help="Run an external bash setup script fetched from the URL on the runners during cloud-init."
    "Installation is run as root within the cloud-init script after the bare image default setup.",
)
@click.option(
    "--upload-clouds",
    default="",
    help="Comma separated list of different clouds to use to upload the externally "
    "built image. The cloud connection parameters should exist in the clouds.yaml.",
)
# click doesn't yet support dataclasses, hence all arguments are required.
def run(  # pylint: disable=too-many-arguments, too-many-locals, too-many-positional-arguments
    arch: config.Arch | None,
    cloud_name: str,
    dockerhub_cache: urllib.parse.ParseResult | None,
    image_name: str,
    base_image: str,
    keep_revisions: int,
    callback_script: Path | None,
    runner_version: str,
    flavor: str,
    juju: str,
    microk8s: str,
    network: str,
    prefix: str,
    proxy: str,
    script_url: urllib.parse.ParseResult | None,
    upload_clouds: str,
) -> None:
    """Build a cloud image using chroot and upload it to OpenStack.

    Args:
        arch: The architecture to run build for.
        cloud_name: The cloud to use from the clouds.yaml file. The CLI looks for clouds.yaml in
            paths of the following order: current directory, ~/.config/openstack, /etc/openstack.
        dockerhub_cache: The DockerHub cache to use for using cached images.
        image_name: The image name uploaded to Openstack.
        base_image: The Ubuntu base image to use as build base.
        keep_revisions: Number of past revisions to keep before deletion.
        callback_script: Script to callback after a successful build.
        runner_version: GitHub runner version to pin.
        flavor: The Openstack flavor to create server to build images.
        juju: The Juju channel to install and bootstrap.
        microk8s: The Microk8s channel to install and bootstrap.
        network: The Openstack network to assign to server to build images.
        prefix: The prefix to use for OpenStack resource names.
        proxy: Proxy to use for external build VMs.
        script_url: The external setup bash script URL.
        upload_clouds: The Openstack cloud to use to upload externally built image.
    """
    arch = arch if arch else config.get_supported_arch()
    base = config.BaseImage.from_str(base_image)
    upload_cloud_names = (
        [cloud_name.strip() for cloud_name in upload_clouds.split(",")] if upload_clouds else None
    )
    image_ids = openstack_builder.run(
        cloud_config=openstack_builder.CloudConfig(
            cloud_name=cloud_name,
            dockerhub_cache=dockerhub_cache,
            flavor=flavor,
            network=network,
            prefix=prefix,
            proxy=proxy,
            upload_cloud_names=upload_cloud_names,
        ),
        image_config=config.ImageConfig(
            arch=arch,
            base=base,
            microk8s=microk8s,
            juju=juju,
            runner_version=runner_version,
            script_config=config.ScriptConfig(
                script_url=script_url,
                script_secrets=_load_secrets(),
            ),
            name=image_name,
        ),
        keep_revisions=keep_revisions,
    )
    click.echo(f"Image build success:\n{image_ids}", nl=False)
    if callback_script:
        # The callback script is a user trusted script.
        subprocess.check_call([str(callback_script), image_ids])  # nosec: B603


def _load_secrets() -> dict[str, str]:
    """Load image builder secrets set as environment variables.

    Returns:
        The secrets key value pairs.
    """
    return {
        key.removeprefix(SECRET_PREFIX): value
        for key, value in os.environ.items()
        if key.startswith(SECRET_PREFIX)
    }
