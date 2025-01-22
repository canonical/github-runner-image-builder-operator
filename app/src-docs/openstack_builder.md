<!-- markdownlint-disable -->

<a href="../src/github_runner_image_builder/openstack_builder.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_builder`
Module for interacting with external openstack VM image builder. 

**Global Variables**
---------------
- **IMAGE_DEFAULT_APT_PACKAGES**
- **CLOUD_YAML_PATHS**
- **SHARED_SECURITY_GROUP_NAME**
- **CREATE_SERVER_TIMEOUT**
- **MIN_CPU**
- **MIN_RAM**
- **MIN_DISK**

---

<a href="../src/github_runner_image_builder/openstack_builder.py#L63"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `determine_cloud`

```python
determine_cloud(cloud_name: str | None = None) → str
```

Automatically determine cloud to use from clouds.yaml by selecting the first cloud. 



**Args:**
 
 - <b>`cloud_name`</b>:  str 



**Raises:**
 
 - <b>`CloudsYAMLError`</b>:  if clouds.yaml was not found. 



**Returns:**
 The cloud name to use. 


---

<a href="../src/github_runner_image_builder/openstack_builder.py#L96"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `initialize`

```python
initialize(arch: Arch, cloud_name: str, prefix: str) → None
```

Initialize the OpenStack external image builder. 

Upload ubuntu base images to openstack to use as builder base. This is a separate method to mitigate race conditions from happening during parallel runs (multiprocess) of the image builder, by creating shared resources beforehand. 



**Args:**
 
 - <b>`arch`</b>:  The architecture of the image to seed. 
 - <b>`cloud_name`</b>:  The cloud to use from the clouds.yaml file. 
 - <b>`prefix`</b>:  The prefix to use for OpenStack resource names. 


---

<a href="../src/github_runner_image_builder/openstack_builder.py#L238"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `run`

```python
run(
    cloud_config: CloudConfig,
    image_config: ImageConfig,
    keep_revisions: int
) → str
```

Run external OpenStack builder instance and create a snapshot. 



**Args:**
 
 - <b>`cloud_config`</b>:  The OpenStack cloud configuration values for builder VM. 
 - <b>`image_config`</b>:  The target image configuration values. 
 - <b>`keep_revisions`</b>:  The number of image to keep for snapshot before deletion. 



**Returns:**
 The Openstack snapshot image ID. 


---

<a href="../src/github_runner_image_builder/openstack_builder.py#L214"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CloudConfig`
The OpenStack cloud configuration values. 



**Attributes:**
 
 - <b>`cloud_name`</b>:  The OpenStack cloud name to use. 
 - <b>`dockerhub_cache`</b>:  The DockerHub cache to use for using cached images. 
 - <b>`flavor`</b>:  The OpenStack flavor to launch builder VMs on. 
 - <b>`network`</b>:  The OpenStack network to launch the builder VMs on. 
 - <b>`prefix`</b>:  The prefix to use for OpenStack resource names. 
 - <b>`proxy`</b>:  The proxy to enable on builder VMs. 
 - <b>`upload_cloud_names`</b>:  The OpenStack cloud names to upload the snapshot to. (Defaults to             the same cloud) 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    cloud_name: str,
    dockerhub_cache: ParseResult | None,
    flavor: str,
    network: str,
    prefix: str,
    proxy: str,
    upload_cloud_names: Optional[Iterable[str]]
) → None
```









