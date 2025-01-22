<!-- markdownlint-disable -->

<a href="../src/github_runner_image_builder/errors.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `errors`
Module containing error definitions. 



---

<a href="../src/github_runner_image_builder/errors.py#L7"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ImageBuilderBaseError`
Represents an error with any builder related executions. 





---

<a href="../src/github_runner_image_builder/errors.py#L11"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `BuilderInitializeError`
Represents an error while setting up host machine as builder. 





---

<a href="../src/github_runner_image_builder/errors.py#L16"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `DependencyInstallError`
Represents an error while installing required dependencies. 





---

<a href="../src/github_runner_image_builder/errors.py#L20"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `NetworkBlockDeviceError`
Represents an error while enabling network block device. 





---

<a href="../src/github_runner_image_builder/errors.py#L24"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `UnsupportedArchitectureError`
Raised when given machine architecture is unsupported. 





---

<a href="../src/github_runner_image_builder/errors.py#L28"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `BuildImageError`
Represents an error while building the image. 





---

<a href="../src/github_runner_image_builder/errors.py#L32"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `UnmountBuildPathError`
Represents an error while unmounting build path. 





---

<a href="../src/github_runner_image_builder/errors.py#L36"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `BaseImageDownloadError`
Represents an error downloading base image. 





---

<a href="../src/github_runner_image_builder/errors.py#L40"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ImageResizeError`
Represents an error while resizing the image. 





---

<a href="../src/github_runner_image_builder/errors.py#L44"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ImageConnectError`
Represents an error while connecting the image to network block device. 





---

<a href="../src/github_runner_image_builder/errors.py#L48"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ResizePartitionError`
Represents an error while resizing network block device partitions. 





---

<a href="../src/github_runner_image_builder/errors.py#L52"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `UnattendedUpgradeDisableError`
Represents an error while disabling unattended-upgrade related services. 





---

<a href="../src/github_runner_image_builder/errors.py#L56"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SystemUserConfigurationError`
Represents an error while adding user to chroot env. 





---

<a href="../src/github_runner_image_builder/errors.py#L60"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `PermissionConfigurationError`
Represents an error while modifying dir permissions. 





---

<a href="../src/github_runner_image_builder/errors.py#L64"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `YQBuildError`
Represents an error while building yq binary from source. 





---

<a href="../src/github_runner_image_builder/errors.py#L68"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `YarnInstallError`
Represents an error installilng Yarn. 





---

<a href="../src/github_runner_image_builder/errors.py#L72"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerDownloadError`
Represents an error downloading GitHub runner tar archive. 





---

<a href="../src/github_runner_image_builder/errors.py#L76"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ImageCompressError`
Represents an error while compressing cloud-img. 





---

<a href="../src/github_runner_image_builder/errors.py#L80"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `HomeDirectoryChangeOwnershipError`
Represents an error while changing ubuntu home directory. 





---

<a href="../src/github_runner_image_builder/errors.py#L84"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackBaseError`
Represents an error while interacting with Openstack. 





---

<a href="../src/github_runner_image_builder/errors.py#L88"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `UnauthorizedError`
Represents an unauthorized connection to Openstack. 





---

<a href="../src/github_runner_image_builder/errors.py#L92"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `UploadImageError`
Represents an error when uploading image to Openstack. 





---

<a href="../src/github_runner_image_builder/errors.py#L96"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackError`
Represents an error while communicating with Openstack. 





---

<a href="../src/github_runner_image_builder/errors.py#L100"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CloudsYAMLError`
Represents an error with clouds.yaml for OpenStack connection. 





---

<a href="../src/github_runner_image_builder/errors.py#L104"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `NotFoundError`
Represents an error with not matching OpenStack object found. 





---

<a href="../src/github_runner_image_builder/errors.py#L108"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `FlavorNotFoundError`
Represents an error with given OpenStack flavor not found. 





---

<a href="../src/github_runner_image_builder/errors.py#L112"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `FlavorRequirementsNotMetError`
Represents an error with given OpenStack flavor not meeting the minimum requirements. 





---

<a href="../src/github_runner_image_builder/errors.py#L116"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `NetworkNotFoundError`
Represents an error with given OpenStack network not found. 





---

<a href="../src/github_runner_image_builder/errors.py#L120"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `AddressNotFoundError`
Represents an error with OpenStack instance not receiving an IP address. 





---

<a href="../src/github_runner_image_builder/errors.py#L124"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CloudInitFailError`
Represents an error with cloud-init. 





