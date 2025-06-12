# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Main entrypoint for github-runner-image-builder cli application."""

import os
import urllib.parse
from dataclasses import dataclass
from typing import cast

import click

from github_runner_image_builder import config, logging, openstack_builder, store

# Bandit thinks this is a hardcoded secret.
SECRET_PREFIX = "IMAGE_BUILDER_SECRET_"  # nosec


@dataclass
class SharedState:
    """Class to hold shared state for the CLI application.

    Attributes:
        cloud: The OpenStack cloud name.
    """

    cloud: str


@click.group()
@click.option(
    "--log-level",
    type=click.Choice(config.LOG_LEVELS),
    default="info",
    help="Configure logging verbosity.",
)
@click.option(
    "--os-cloud",
    default=None,
    help="The cloud to use from the clouds.yaml file. The CLI looks for clouds.yaml in paths of "
    "the following order: current directory, ~/.config/openstack, /etc/openstack.",
    required=True,
)
@click.pass_context
def main(ctx: click.Context, log_level: str | int, os_cloud: str) -> None:
    """Run entrypoint for Github runner image builder CLI.

    \f # this is to prevent click from using Args section of the docstring as help documentation.

    Args:
        ctx: click.Context object for passing shared state.
        log_level: The logging verbosity to apply.
        os_cloud: The name of the OpenStack cloud to use from clouds.yaml file.
    """  # noqa: D301 - the \f should not be escaped for click to properly format the docstring.
    logging.configure(log_level=log_level)
    ctx.obj = SharedState(cloud=openstack_builder.determine_cloud(cloud_name=os_cloud))


@main.command(name="init")
@click.option(
    "--arch",
    type=click.Choice(
        (config.Arch.ARM64, config.Arch.X64, config.Arch.S390X, config.Arch.PPC64LE)
    ),
    help="Image architecture to initialize for.",
    required=True,
)
@click.option(
    "--prefix",
    default="",
    help="Name of the OpenStack resources to prefix with. Used to run the image builder in "
    "parallel under same OpenStack project.",
)
@click.pass_context
def initialize(ctx: click.Context, arch: config.Arch, prefix: str) -> None:
    """Initialize builder CLI function wrapper.

    \f # this is to prevent click from using Args section of the docstring as help documentation.

    Args:
        ctx: click.Context object for passing shared state.
        arch: The architecture to build for.
        prefix: The prefix to use for OpenStack resource names.
    """  # noqa: D301 - the \f should not be escaped for click to properly format the docstring.
    state = cast(SharedState, ctx.obj)
    openstack_builder.initialize(
        arch=arch,
        cloud_name=openstack_builder.determine_cloud(cloud_name=state.cloud),
        prefix=prefix,
    )


@main.command(name="latest-build-id")
@click.argument("image_name")
@click.pass_context
def get_latest_build_id(ctx: click.Context, image_name: str) -> None:
    # Click arguments do not take help parameter, display help through docstrings.
    """Get latest build ID of <IMAGE_NAME> from Openstack <--os-cloud>.

    \f # this is to prevent click from using Args section of the docstring as help documentation.

    Args:
        ctx: click.Context object for passing shared state.
        image_name: The image name uploaded to Openstack.
    """  # noqa: D301 - the \f should not be escaped for click to properly format the docstring.
    state = cast(SharedState, ctx.obj)
    click.echo(
        message=store.get_latest_build_id(cloud_name=state.cloud, image_name=image_name),
        nl=False,
    )


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
@click.argument("image_name")
@click.option(
    "--arch",
    type=click.Choice(
        (config.Arch.ARM64, config.Arch.X64, config.Arch.S390X, config.Arch.PPC64LE)
    ),
    help="Image architecture.",
    required=True,
)
@click.option(
    "-b",
    "--base-image",
    type=click.Choice(config.BASE_CHOICES),
    default="noble",
    help=("The Ubuntu base image to use as build base."),
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
@click.pass_context
# click doesn't yet support dataclasses, hence all arguments are required.
def run(  # pylint: disable=too-many-arguments, too-many-locals, too-many-positional-arguments
    ctx: click.Context,
    arch: config.Arch,
    image_name: str,
    base_image: str,
    keep_revisions: int,
    runner_version: str,
    flavor: str,
    network: str,
    prefix: str,
    proxy: str,
    script_url: urllib.parse.ParseResult | None,
    upload_clouds: str,
) -> None:
    """Build a cloud image using chroot and upload it to OpenStack.

    Args:
        ctx: click.Context object for passing shared state.
        arch: The architecture to run build for.
        image_name: The image name uploaded to Openstack.
        base_image: The Ubuntu base image to use as build base.
        keep_revisions: Number of past revisions to keep before deletion.
        runner_version: GitHub runner version to pin.
        flavor: The Openstack flavor to create server to build images.
        network: The Openstack network to assign to server to build images.
        prefix: The prefix to use for OpenStack resource names.
        proxy: Proxy to use for external build VMs.
        script_url: The external setup bash script URL.
        upload_clouds: The Openstack cloud to use to upload externally built image.
    """
    base = config.BaseImage.from_str(base_image)
    upload_cloud_names = (
        [cloud_name.strip() for cloud_name in upload_clouds.split(",")] if upload_clouds else None
    )
    state = cast(SharedState, ctx.obj)
    image_ids = openstack_builder.run(
        cloud_config=openstack_builder.CloudConfig(
            cloud_name=state.cloud,
            flavor=flavor,
            network=network,
            prefix=prefix,
            proxy=proxy,
            upload_cloud_names=upload_cloud_names,
        ),
        image_config=config.ImageConfig(
            arch=arch,
            base=base,
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
