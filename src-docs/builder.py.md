<!-- markdownlint-disable -->

<a href="../src/builder.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `builder.py`
Module for interacting with qemu image builder. 

**Global Variables**
---------------
- **APT_DEPENDENCIES**
- **CLOUD_IMAGE_URL_TMPL**
- **CLOUD_IMAGE_FILE_NAME**
- **APT_TIMER**
- **APT_SVC**
- **APT_UPGRADE_TIMER**
- **APT_UPGRAD_SVC**
- **UBUNTU_USER**
- **DOCKER_GROUP**
- **MICROK8S_GROUP**
- **YQ_DOWNLOAD_URL_TMPL**
- **YQ_BINARY_CHECKSUM_URL**
- **YQ_CHECKSUM_HASHES_ORDER_URL**
- **YQ_EXTRACT_CHECKSUM_SCRIPT_URL**
- **BIN_ARCH_MAP**
- **IMAGE_DEFAULT_APT_PACKAGES**

---

<a href="../src/builder.py#L70"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `setup_builder`

```python
setup_builder() → None
```

Configure the host machine to build images. 



**Raises:**
 
 - <b>`BuilderSetupError`</b>:  If there was an error setting up the host device for building images. 


---

<a href="../src/builder.py#L530"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `build_image`

```python
build_image(config: BuildImageConfig) → Path
```

Build and save the image locally. 



**Args:**
 
 - <b>`config`</b>:  The configuration values to build the image with. 



**Raises:**
 
 - <b>`BuildImageError`</b>:  If there was an error building the image. 



**Returns:**
 The saved image path. 


---

## <kbd>class</kbd> `BuildImageConfig`
Configuration for building the image. 



**Attributes:**
 
 - <b>`arch`</b>:  The CPU architecture to build the image for. 
 - <b>`base_image`</b>:  The ubuntu image to use as build base. 





---

## <kbd>class</kbd> `BuildImageError`
Represents an error while building the image. 





---

## <kbd>class</kbd> `BuilderSetupError`
Represents an error while setting up host machine as builder. 





---

## <kbd>class</kbd> `CloudImageDownloadError`
Represents an error downloading cloud image. 





---

## <kbd>class</kbd> `DependencyInstallError`
Represents an error while installing required dependencies. 





---

## <kbd>class</kbd> `ExternalPackageInstallError`
Represents an error installilng external packages. 





---

## <kbd>class</kbd> `ImageCompressError`
Represents an error while compressing cloud-img. 





---

## <kbd>class</kbd> `ImageMountError`
Represents an error while mounting the image to network block device. 





---

## <kbd>class</kbd> `ImageResizeError`
Represents an error while resizing the image. 





---

## <kbd>class</kbd> `NetworkBlockDeviceError`
Represents an error while enabling network block device. 





---

## <kbd>class</kbd> `ResizePartitionError`
Represents an error while resizing network block device partitions. 





---

## <kbd>class</kbd> `SystemUserConfigurationError`
Represents an error while adding user to chroot env. 





---

## <kbd>class</kbd> `UnattendedUpgradeDisableError`
Represents an error while disabling unattended-upgrade related services. 





---

## <kbd>class</kbd> `UnsupportedArchitectureError`
Raised when given machine charm architecture is unsupported. 



**Attributes:**
 
 - <b>`arch`</b>:  The current machine architecture. 

<a href="../src/builder.py#L90"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(arch: str) → None
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`arch`</b>:  The current machine architecture. 





