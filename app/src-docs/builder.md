<!-- markdownlint-disable -->

<a href="../src/github_runner_image_builder/builder.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `builder`
Module for interacting with qemu image builder. 

**Global Variables**
---------------
- **APT_DEPENDENCIES**
- **APT_NONINTERACTIVE_ENV**
- **SNAP_GO**
- **RESIZE_AMOUNT**
- **APT_TIMER**
- **APT_SVC**
- **APT_UPGRADE_TIMER**
- **APT_UPGRAD_SVC**
- **UBUNTU_USER**
- **DOCKER_GROUP**
- **MICROK8S_GROUP**
- **LXD_GROUP**
- **SUDOERS_GROUP**
- **YQ_REPOSITORY_URL**
- **IMAGE_HWE_PKG_FORMAT**

---

<a href="../src/github_runner_image_builder/builder.py#L95"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `initialize`

```python
initialize() → None
```

Configure the host machine to build images. 


---

<a href="../src/github_runner_image_builder/builder.py#L159"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `run`

```python
run(cloud_name: str, image_config: ImageConfig, keep_revisions: int) → str
```

Build and save the image locally. 



**Args:**
 
 - <b>`cloud_name`</b>:  The OpenStack cloud to use from clouds.yaml. 
 - <b>`image_config`</b>:  The target image configuration values. 
 - <b>`keep_revisions`</b>:  The number of image to keep for snapshot before deletion. 



**Raises:**
 
 - <b>`BuildImageError`</b>:  If there was an error building the image. 



**Returns:**
 The built image ID. 


