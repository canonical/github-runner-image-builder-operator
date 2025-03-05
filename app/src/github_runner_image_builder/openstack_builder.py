# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module for interacting with external openstack VM image builder."""

import base64
import dataclasses
import hashlib
import logging
import pathlib
import shutil
import time
import typing
from collections import namedtuple

import fabric
import invoke
import jinja2
import openstack
import openstack.compute.v2.flavor
import openstack.compute.v2.image
import openstack.compute.v2.keypair
import openstack.compute.v2.server
import openstack.connection
import openstack.exceptions
import openstack.image.v2.image
import openstack.key_manager
import openstack.key_manager.key_manager_service
import openstack.network.v2.network
import openstack.network.v2.security_group
import openstack.network.v2.subnet
import paramiko
import paramiko.ssh_exception
import tenacity
import yaml
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

import github_runner_image_builder.errors
from github_runner_image_builder import cloud_image, config, store
from github_runner_image_builder.config import IMAGE_DEFAULT_APT_PACKAGES, Arch, BaseImage

logger = logging.getLogger(__name__)

CLOUD_YAML_PATHS = (
    pathlib.Path("clouds.yaml"),
    pathlib.Path("~/clouds.yaml"),
    pathlib.Path("~/.config/openstack/clouds.yaml"),
    pathlib.Path("/etc/openstack/clouds.yaml"),
)

BUILDER_KEY_PATH = pathlib.Path("/home/ubuntu/.ssh/builder_key")
SHARED_SECURITY_GROUP_NAME = "github-runner-image-builder-v1"
EXTERNAL_SCRIPT_PATH = pathlib.Path("/root/external.sh")

CREATE_SERVER_TIMEOUT = 20 * 60  # seconds
DELETE_SERVER_TIMEOUT = 20 * 60  # seconds

MIN_CPU = 2
MIN_RAM = 1024  # M
MIN_DISK = 20  # G


def determine_cloud(cloud_name: str | None = None) -> str:
    """Automatically determine cloud to use from clouds.yaml by selecting the first cloud.

    Args:
        cloud_name: str

    Raises:
        CloudsYAMLError: if clouds.yaml was not found.

    Returns:
        The cloud name to use.
    """
    # The cloud credentials may be stored in environment variable, trust user input if given.
    if cloud_name:
        return cloud_name
    logger.info("Determning cloud to use.")
    try:
        clouds_yaml_path = next(path for path in CLOUD_YAML_PATHS if path.exists())
    except StopIteration as exc:
        logger.exception("Unable to determine cloud to use from clouds.yaml files.")
        raise github_runner_image_builder.errors.CloudsYAMLError(
            "Unable to determine cloud to use from clouds.yaml files. "
            "Please check that clouds.yaml exists."
        ) from exc
    try:
        clouds_yaml = yaml.safe_load(clouds_yaml_path.read_text(encoding="utf-8"))
        cloud: str = list(clouds_yaml["clouds"].keys())[0]
    except (TypeError, yaml.error.YAMLError, KeyError, IndexError) as exc:
        logger.exception("Invalid clouds.yaml contents.")
        raise github_runner_image_builder.errors.CloudsYAMLError("Invalid clouds.yaml.") from exc
    return cloud


def initialize(arch: Arch, cloud_name: str, prefix: str) -> None:
    """Initialize the OpenStack external image builder.

    Upload ubuntu base images to openstack to use as builder base. This is a separate method to
    mitigate race conditions from happening during parallel runs (multiprocess) of the image
    builder, by creating shared resources beforehand.

    Args:
        arch: The architecture of the image to seed.
        cloud_name: The cloud to use from the clouds.yaml file.
        prefix: The prefix to use for OpenStack resource names.
    """
    logger.info("Initializing external builder.")
    logger.info("Downloading Jammy image.")
    jammy_image_path = cloud_image.download_and_validate_image(
        arch=arch, base_image=BaseImage.JAMMY
    )
    logger.info("Downloading Noble image.")
    noble_image_path = cloud_image.download_and_validate_image(
        arch=arch, base_image=BaseImage.NOBLE
    )
    logger.info("Uploading Jammy image.")
    store.upload_image(
        arch=arch,
        cloud_name=cloud_name,
        image_name=_get_base_image_name(arch=arch, base=BaseImage.JAMMY, prefix=prefix),
        image_path=jammy_image_path,
        keep_revisions=1,
    )
    logger.info("Uploading Noble image.")
    store.upload_image(
        arch=arch,
        cloud_name=cloud_name,
        image_name=_get_base_image_name(arch=arch, base=BaseImage.NOBLE, prefix=prefix),
        image_path=noble_image_path,
        keep_revisions=1,
    )

    with openstack.connect(cloud=cloud_name) as conn:
        _create_keypair(conn=conn, prefix=prefix)
        logger.info("Creating security group %s.", SHARED_SECURITY_GROUP_NAME)
        _create_security_group(conn=conn)


def _get_base_image_name(arch: Arch, base: BaseImage, prefix: str) -> str:
    """Get formatted image name.

    Args:
        arch: The architecture of the image to use as build base.
        base: The ubuntu base image.
        prefix: The prefix to use for the image name.

    Returns:
        The ubuntu base image name uploaded to OpenStack.
    """
    return f"{prefix}-image-builder-base-{base.value}-{arch.value}"


def _create_keypair(conn: openstack.connection.Connection, prefix: str) -> None:
    """Create an SSH Keypair to ssh into builder instance.

    Args:
        conn: The Openstach connection instance.
        prefix: The prefix to use for OpenStack resource names.
    """
    key_name = _get_keypair_name(prefix=prefix)
    key = conn.get_keypair(name_or_id=key_name)
    if key and BUILDER_KEY_PATH.exists():
        return
    logger.info("Deleting existing keypair (to regenerate) %s.", key_name)
    conn.delete_keypair(name=key_name)
    logger.info("Creating keypair %s.", key_name)
    keypair = conn.create_keypair(name=key_name)
    # OpenStack library does not provide correct type hints for keys.
    BUILDER_KEY_PATH.write_text(keypair.private_key, encoding="utf-8")  # type: ignore
    shutil.chown(BUILDER_KEY_PATH, user="ubuntu", group="ubuntu")
    BUILDER_KEY_PATH.chmod(0o400)


def _get_keypair_name(prefix: str) -> str:
    """Get OpenStack key name.

    Args:
        prefix: The prefix to use for OpenStack resource names.

    Returns:
        The OpenStack key name.
    """
    return f"{prefix}-image-builder-ssh-key"


def _create_security_group(conn: openstack.connection.Connection) -> None:
    """Create a security group for builder instances.

    Args:
        conn: The Openstach connection instance.
    """
    if conn.get_security_group(name_or_id=SHARED_SECURITY_GROUP_NAME):
        return
    conn.create_security_group(
        name=SHARED_SECURITY_GROUP_NAME,
        description="For builders managed by the github-runner-image-builder.",
    )
    conn.create_security_group_rule(
        secgroup_name_or_id=SHARED_SECURITY_GROUP_NAME,
        protocol="icmp",
        direction="ingress",
        ethertype="IPv4",
    )
    conn.create_security_group_rule(
        secgroup_name_or_id=SHARED_SECURITY_GROUP_NAME,
        port_range_min="22",
        port_range_max="22",
        protocol="tcp",
        direction="ingress",
        ethertype="IPv4",
    )


@dataclasses.dataclass
class CloudConfig:
    """The OpenStack cloud configuration values.

    Attributes:
        cloud_name: The OpenStack cloud name to use.
        flavor: The OpenStack flavor to launch builder VMs on.
        network: The OpenStack network to launch the builder VMs on.
        prefix: The prefix to use for OpenStack resource names.
        proxy: The proxy to enable on builder VMs.
        upload_cloud_names: The OpenStack cloud names to upload the snapshot to. (Defaults to \
            the same cloud)
    """

    cloud_name: str
    flavor: str
    network: str
    prefix: str
    proxy: str
    upload_cloud_names: typing.Iterable[str] | None


def run(
    cloud_config: CloudConfig,
    image_config: config.ImageConfig,
    keep_revisions: int,
) -> str:
    """Run external OpenStack builder instance and create a snapshot.

    Args:
        cloud_config: The OpenStack cloud configuration values for builder VM.
        image_config: The target image configuration values.
        keep_revisions: The number of image to keep for snapshot before deletion.

    Returns:
        The Openstack snapshot image ID.
    """
    cloud_init_script = _generate_cloud_init_script(
        image_config=image_config,
        proxy=cloud_config.proxy,
    )
    builder_name = _get_builder_name(
        arch=image_config.arch, base=image_config.base, prefix=cloud_config.prefix
    )
    builder_key_name = _get_keypair_name(prefix=cloud_config.prefix)
    with openstack.connect(cloud=cloud_config.cloud_name) as conn:
        _prepare_openstack_resources(
            conn=conn,
            builder_name=builder_name,
            key_name=builder_key_name,
            prefix=cloud_config.prefix,
        )
        flavor = _determine_flavor(conn=conn, flavor_name=cloud_config.flavor)
        logger.info("Using flavor ID: %s.", flavor)
        network = _determine_network(conn=conn, network_name=cloud_config.network)
        logger.info("Using network ID: %s.", network)
        builder: openstack.compute.v2.server.Server = conn.create_server(
            name=builder_name,
            image=_get_base_image_name(
                arch=image_config.arch, base=image_config.base, prefix=cloud_config.prefix
            ),
            key_name=builder_key_name,
            flavor=flavor,
            network=network,
            security_groups=[SHARED_SECURITY_GROUP_NAME],
            userdata=cloud_init_script,
            auto_ip=False,
            timeout=CREATE_SERVER_TIMEOUT,
            wait=True,
        )
        logger.info("Launched builder, waiting for cloud-init to complete: %s.", builder.id)
        ssh_conn = _get_ssh_connection(conn=conn, server=builder, ssh_key=BUILDER_KEY_PATH)
        _wait_for_cloud_init_complete(conn=conn, server=builder, ssh_conn=ssh_conn)
        if script_url := image_config.script_config.script_url:
            _execute_external_script(
                script_url=script_url.geturl(),
                script_secrets=image_config.script_config.script_secrets,
                ssh_conn=ssh_conn,
            )
        conn.compute.stop_server(server=builder)
        log_output = conn.get_server_console(server=builder)
        logger.info("Build output: %s", log_output)
        image = store.create_snapshot(
            cloud_name=cloud_config.cloud_name,
            image_name=image_config.name,
            server=builder,
            keep_revisions=keep_revisions,
        )
        logger.info(
            "Requested snapshot, waiting for snapshot to complete: %s, %s.", builder.id, image.id
        )
        _wait_for_snapshot_complete(conn=conn, image=image)
        images = _upload_to_clouds(
            conn=conn,
            image=image,
            upload_cloud_names=cloud_config.upload_cloud_names,
            upload_cloud_config=_UploadCloudConfig(
                arch=image_config.arch,
                image_name=image_config.name,
                keep_revisions=keep_revisions,
            ),
        )
        logger.info("Deleting builder VM: %s (%s)", builder.name, builder.id)
        conn.delete_server(name_or_id=builder.id, wait=True, timeout=DELETE_SERVER_TIMEOUT)
        logger.info("Image builder run complete.")
    return ",".join(str(image.id) for image in images)


def _prepare_openstack_resources(
    conn: openstack.connection.Connection, builder_name: str, key_name: str, prefix: str
) -> None:
    """Ensure that OpenStack resources are in expected state.

    1. Ensure the key that is installed matches what is expected by OpenStack.
    2. Ensure that only a single security group exists.
    3. Ensure that no VMs exist.

    Args:
        conn: The OpenStack connection instance.
        builder_name: The OpenStack builder VM name that is used to build the image.
        key_name: The OpenStack key name used to connect to the builder VM.
        prefix: The OpenStack resource prefix.
    """
    # OpenStack library does not provide good type hinting
    key: openstack.compute.v2.keypair.Keypair | None = conn.get_keypair(
        name_or_id=key_name
    )  # type: ignore
    # Check fingerprint since the key may have diverged due to unforeseen circumstances.
    if not key or key.fingerprint != _get_key_fingerprint():
        _create_keypair(conn=conn, prefix=prefix)

    security_groups: list[openstack.network.v2.security_group.SecurityGroup] = (
        conn.search_security_groups(name_or_id=SHARED_SECURITY_GROUP_NAME)
    )
    if len(security_groups) != 1:
        for security_group in security_groups:
            conn.delete_security_group(name_or_id=security_group.id)
        _create_security_group(conn=conn)

    servers: list[openstack.compute.v2.server.Server] = conn.search_servers(
        name_or_id=builder_name
    )
    if len(servers) > 0:
        for server in servers:
            conn.delete_server(name_or_id=server.id)


def _get_key_fingerprint() -> str:
    """Get the MD5 fingerprint of the ssh key.

    1. Read the private PEM file.
    2. Get the public key from the private key.
    3. Extract the base64 part of the public key.
    4. Generate MD5 hash.

    Returns:
        The MD5 fingerprint hash of the ssh public key.
    """
    key_data = BUILDER_KEY_PATH.read_bytes()
    private_key = serialization.load_pem_private_key(
        key_data, password=None, backend=default_backend()
    )
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH, format=serialization.PublicFormat.OpenSSH
    )
    key_base64 = public_bytes.split()[1]
    key_data = base64.b64decode(key_base64)
    # ignore B324:hashlib use of weak MD5 - OpenStack generates keys with this algo.
    md5_hash = hashlib.md5(key_data).hexdigest()  # nosec: B324
    return ":".join(md5_hash[i : i + 2] for i in range(0, len(md5_hash), 2))


def _determine_flavor(conn: openstack.connection.Connection, flavor_name: str | None) -> str:
    """Determine the flavor to use for the image builder.

    Args:
        conn: The OpenStack connection instance.
        flavor_name: Flavor name to use if given.

    Raises:
        FlavorNotFoundError: If no suitable flavor was found.
        FlavorRequirementsNotMetError: If the provided flavor does not meet minimum requirements.

    Returns:
        The flavor ID to use for launching builder VM.
    """
    if flavor_name:
        if not (flavor := conn.get_flavor(name_or_id=flavor_name)):
            logger.error("Given flavor %s not found.", flavor_name)
            raise github_runner_image_builder.errors.FlavorNotFoundError(
                f"Given flavor {flavor_name} not found."
            )
        logger.info("Flavor found, %s", flavor.name)
        # OpenStack library does not provide correct type hints for flavors.
        if not (
            flavor.vcpus >= MIN_CPU  # type: ignore
            and flavor.ram >= MIN_RAM  # type: ignore
            and flavor.disk >= MIN_DISK  # type: ignore
        ):
            logger.error("Given flavor %s does not meet the minimum requirements.", flavor_name)
            raise github_runner_image_builder.errors.FlavorRequirementsNotMetError(
                f"Provided flavor {flavor_name} does not meet the minimum requirements."
                f"Required: CPU: {MIN_CPU} MEM: {MIN_RAM}M DISK: {MIN_DISK}G. "
                f"Got: CPU: {flavor.vcpus} MEM: {flavor.ram}M DISK: {flavor.disk}G."
            )
        # OpenStack library does not provide correct type hints for flavors.
        return flavor.id  # type: ignore
    flavors: list[openstack.compute.v2.flavor.Flavor] = conn.list_flavors()
    flavors = sorted(flavors, key=lambda flavor: (flavor.vcpus, flavor.ram, flavor.disk))
    for flavor in flavors:
        # OpenStack library does not provide correct type hints for flavors.
        if (
            flavor.vcpus >= MIN_CPU  # type: ignore
            and flavor.ram >= MIN_RAM  # type: ignore
            and flavor.disk >= MIN_DISK  # type: ignore
        ):
            logger.info("Flavor found, %s", flavor.name)
            # OpenStack library does not provide correct type hints for flavors.
            return flavor.id  # type: ignore
    raise github_runner_image_builder.errors.FlavorNotFoundError("No suitable flavor found.")


def _determine_network(conn: openstack.connection.Connection, network_name: str | None) -> str:
    """Determine the network to use for the image builder.

    Args:
        conn: The OpenStack connection instance.
        network_name: Network name to use if given.

    Raises:
        NetworkNotFoundError: If no suitable network was found.

    Returns:
        The network to use for launching builder VM.
    """
    if network_name:
        if not (network := conn.get_network(name_or_id=network_name)):
            logger.error("Given network %s not found.", network_name)
            raise github_runner_image_builder.errors.NetworkNotFoundError(
                f"Given network {network_name} not found."
            )
        logger.info("Network found, %s", network.name)
        # OpenStack library does not provide correct type hints for networks.
        return network.id  # type: ignore
    networks: list[openstack.network.v2.network.Network] = conn.list_networks()
    # Only a single valid subnet should exist per environment.
    subnets: list[openstack.network.v2.subnet.Subnet] = conn.list_subnets()
    if not subnets:
        logger.error("No valid subnets found.")
        raise github_runner_image_builder.errors.NetworkNotFoundError("No valid subnets found.")
    subnet = subnets[0]
    for network in networks:
        # OpenStack library does not provide correct type hints for networks.
        if subnet.id in network.subnet_ids:  # type: ignore
            logger.info("Network found, %s", network.name)
            # OpenStack library does not provide correct type hints for networks.
            return network.id  # type: ignore
    raise github_runner_image_builder.errors.NetworkNotFoundError("No suitable network found.")


def _generate_cloud_init_script(
    image_config: config.ImageConfig,
    proxy: str,
) -> str:
    """Generate userdata for installing GitHub runner image components.

    Args:
        image_config: The target image configuration values.
        proxy: The proxy to enable while setting up the VM.

    Returns:
        The cloud-init script to create snapshot image.
    """
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("github_runner_image_builder", "templates"),
        autoescape=jinja2.select_autoescape(),
    )
    template = env.get_template("cloud-init.sh.j2")
    return template.render(
        PROXY_URL=proxy,
        APT_PACKAGES=" ".join(IMAGE_DEFAULT_APT_PACKAGES),
        HWE_VERSION=BaseImage.get_version(image_config.base),
        RUNNER_VERSION=image_config.runner_version,
        RUNNER_ARCH=image_config.arch.value,
    )


def _get_builder_name(arch: Arch, base: BaseImage, prefix: str) -> str:
    """Get builder VM name.

    Args:
        arch: The architecture of the image to seed.
        base: The ubuntu base image.
        prefix: The prefix to use for OpenStack resource names.

    Returns:
        The builder VM name launched on OpenStack.
    """
    return f"{prefix}-image-builder-{base.value}-{arch.value}"


@tenacity.retry(
    wait=tenacity.wait_exponential(multiplier=2, max=30),
    # retry if False is returned
    retry=tenacity.retry_if_result(lambda result: not result),
    reraise=True,
)
def _wait_for_cloud_init_complete(
    conn: openstack.connection.Connection,
    server: openstack.compute.v2.server.Server,
    ssh_conn: fabric.Connection,
) -> bool:
    """Wait until the userdata has finished installing expected components.

    Args:
        conn: The Openstach connection instance.
        server: The OpenStack server instance to check if cloud_init is complete.
        ssh_conn: The SSH connection instance to the OpenStack server instance.

    Raises:
        CloudInitFailError: if there was an error running cloud-init status command.

    Returns:
        Whether the cloud init is complete. Used for tenacity retry to pick up return value.
    """
    try:
        result: fabric.Result | None = ssh_conn.run("cloud-init status --wait", timeout=60 * 30)
    except invoke.exceptions.UnexpectedExit as exc:
        log_out = conn.get_server_console(server=server)
        logger.error("Cloud init output: %s", log_out)
        raise github_runner_image_builder.errors.CloudInitFailError(
            f"Unexpected exit code, reason: {exc.reason}, result: {exc.result}"
        ) from exc
    if not result or not result.ok:
        logger.error("cloud-init status command failure, result: %s.", result)
        raise github_runner_image_builder.errors.CloudInitFailError("Invalid cloud-init status")
    return "status: done" in result.stdout


def _execute_external_script(
    script_url: str, script_secrets: dict[str, str], ssh_conn: fabric.Connection
) -> None:
    """Execute the external script on the OpenStack instance.

    Args:
        script_url: The external script URL to download and execute.
        script_secrets: The secrets to pass as environment variables to the script.
        ssh_conn: The SSH connection instance to the OpenStack server instance.

    Raises:
        ExternalScriptError: If the external script (or setup/cleanup of it) failed to execute.
    """
    general_timeout_in_minutes = 2
    script_run_timeout_in_minutes = 60
    Command = namedtuple("Command", ["name", "command", "timeout", "env"])
    script_setup_cmd = Command(
        name="Download the external script and set permissions",
        command=f'sudo curl "{script_url}" -o {EXTERNAL_SCRIPT_PATH} '
        f"&& sudo chmod +x {EXTERNAL_SCRIPT_PATH}",
        timeout=general_timeout_in_minutes,
        env={},
    )
    script_run_cmd = Command(
        name="Run the external script using the secrets provided as environment variables",
        command=f"sudo --preserve-env={','.join(script_secrets.keys())} {EXTERNAL_SCRIPT_PATH}",
        timeout=script_run_timeout_in_minutes,
        env=script_secrets,
    )
    script_rm_cmd = Command(
        name="Remove the external script",
        command=f"sudo rm {EXTERNAL_SCRIPT_PATH}",
        timeout=general_timeout_in_minutes,
        env={},
    )
    clear_journal_cmd = Command(
        name="Clear the journal to remove script traces",
        command="sudo journalctl --flush && sudo journalctl --rotate && "
        "sudo journalctl --merge --vacuum-size=1",
        timeout=general_timeout_in_minutes,
        env={},
    )
    clear_auth_logs_cmd = Command(
        name="Clear the auth logs to remove script traces",
        command="cat /dev/null | sudo tee /var/log/auth.log",
        timeout=general_timeout_in_minutes,
        env={},
    )

    try:
        for cmd in (
            script_setup_cmd,
            script_run_cmd,
            script_rm_cmd,
            clear_journal_cmd,
            clear_auth_logs_cmd,
        ):
            logger.info("Running command via ssh: %s", cmd.name)
            ssh_conn.run(cmd.command, timeout=cmd.timeout * 60, warn=False, env=cmd.env)
    except invoke.exceptions.UnexpectedExit as exc:
        raise github_runner_image_builder.errors.ExternalScriptError(
            f"Unexpected exit code, reason: {exc.reason}, result: {exc.result}"
        ) from exc


@tenacity.retry(wait=tenacity.wait_exponential(multiplier=2, max=30), reraise=True)
def _get_ssh_connection(
    conn: openstack.connection.Connection,
    server: openstack.compute.v2.server.Server,
    ssh_key: pathlib.Path,
) -> fabric.Connection:
    """Get a valid SSH connection to OpenStack instance.

    Args:
        conn: The Openstach connection instance.
        server: The OpenStack server instance to check if cloud_init is complete.
        ssh_key: The key to SSH RSA key to connect to the OpenStack server instance.

    Raises:
        AddressNotFoundError: If there was no valid address to get SSH connection.

    Returns:
        The SSH Connection instance.
    """
    # OpenStack library does not provide correct type hints for it.
    server = conn.get_server(name_or_id=server.id)  # type: ignore
    network_address_list = server.addresses.values()  # type: ignore
    if not network_address_list:
        logger.error("Server address not found, %s.", server.name)
        raise github_runner_image_builder.errors.AddressNotFoundError(
            f"No addresses found for OpenStack server {server.name}"
        )

    server_addresses: list[str] = [
        address["addr"]
        for network_addresses in network_address_list
        for address in network_addresses
    ]
    for ip in server_addresses:
        try:
            connection = fabric.Connection(
                host=ip,
                user="ubuntu",
                connect_kwargs={"key_filename": str(ssh_key)},
                connect_timeout=30,
            )
            result: fabric.Result | None = connection.run(
                "echo hello world", warn=True, timeout=30
            )
            if not result or not result.ok:
                logger.warning(
                    "SSH test connection failed, server: %s, address: %s", server.name, ip
                )
                continue
            if "hello world" in result.stdout:
                return connection
        except (
            paramiko.ssh_exception.NoValidConnectionsError,
            TimeoutError,
            paramiko.ssh_exception.SSHException,
        ):
            logger.warning(
                "Unable to SSH into %s with address %s",
                server.name,
                connection.host,
                exc_info=True,
            )
            continue
    logger.error("Server SSH address not found, %s.", server.name)
    raise github_runner_image_builder.errors.AddressNotFoundError(
        f"No connectable SSH addresses found, server: {server.name}, "
        f"addresses: {server_addresses}"
    )


def _wait_for_snapshot_complete(
    conn: openstack.connection.Connection, image: openstack.image.v2.image.Image
) -> None:
    """Wait until snapshot has been completed and is ready to be used.

    Args:
        conn: The Openstach connection instance.
        image: The OpenStack server snapshot image to check is complete.

    Raises:
        TimeoutError: if the image snapshot took too long to complete.
    """
    for _ in range(10):
        # OpenStack library does not provide correct type hints for it.
        image = conn.get_image(name_or_id=image.id)  # type: ignore
        if image.status == "active":
            return
        logger.info(
            "Image snapshot not yet active, waiting..., name: %s, id: %s", image.name, image.id
        )
        time.sleep(60)
    # OpenStack library does not provide correct type hints for it.
    image = conn.get_image(name_or_id=image.id)  # type: ignore
    if not image or not image.status == "active":
        logger.error("Timed out waiting for snapshot to be active, %s.", image.name)
        raise TimeoutError(f"Timed out waiting for snapshot to be active, {image.id}.")


@dataclasses.dataclass
class _UploadCloudConfig:
    """The upload clouds arguments wrapper.

    Attributes:
        arch: The architecture of the image to use as build base.
        image_name: The name to upload the image as.
        keep_revisions: Number of revisions to keep before deletion.
    """

    arch: Arch
    image_name: str
    keep_revisions: int


def _upload_to_clouds(
    conn: openstack.connection.Connection,
    image: openstack.image.v2.image.Image,
    upload_cloud_names: typing.Iterable[str] | None,
    upload_cloud_config: _UploadCloudConfig,
) -> tuple[openstack.image.v2.image.Image, ...]:
    """Upload the snapshot image to different clouds.

    Args:
        conn: The OpenStack connection instance.
        image: The snapshot image to upload.
        upload_cloud_names: The clouds to upload the image to.
        upload_cloud_config: The upload image configuration.

    Returns:
        The uploaded cloud images.
    """
    if not upload_cloud_names:
        return (image,)
    file_path = pathlib.Path(f"{image.name}.snapshot")
    logger.info("Downloading snapshot to %s.", file_path)
    conn.download_image(name_or_id=image.id, output_file=file_path, stream=True)
    images: list[openstack.image.v2.image.Image] = []
    for cloud_name in upload_cloud_names:
        logger.info("Uploading downloaded snapshot to %s.", cloud_name)
        image = store.upload_image(
            arch=upload_cloud_config.arch,
            cloud_name=cloud_name,
            image_name=upload_cloud_config.image_name,
            image_path=file_path,
            keep_revisions=upload_cloud_config.keep_revisions,
        )
        images.append(image)
        logger.info(
            "Uploaded snapshot on cloud %s, id: %s, name: %s",
            cloud_name,
            image.id,
            image.name,
        )
    return tuple(images)
