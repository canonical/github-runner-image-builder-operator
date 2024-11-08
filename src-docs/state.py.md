<!-- markdownlint-disable -->

<a href="../src/state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `state.py`
Module for interacting with charm state and configurations. 

**Global Variables**
---------------
- **ARCHITECTURES_ARM64**
- **ARCHITECTURES_X86**
- **CLOUD_NAME**
- **LTS_IMAGE_VERSION_TAG_MAP**
- **ARCHITECTURE_CONFIG_NAME**
- **APP_CHANNEL_CONFIG_NAME**
- **BASE_IMAGE_CONFIG_NAME**
- **BUILD_INTERVAL_CONFIG_NAME**
- **DOCKERHUB_CACHE_CONFIG_NAME**
- **EXTERNAL_BUILD_CONFIG_NAME**
- **EXTERNAL_BUILD_FLAVOR_CONFIG_NAME**
- **EXTERNAL_BUILD_NETWORK_CONFIG_NAME**
- **JUJU_CHANNELS_CONFIG_NAME**
- **MICROK8S_CHANNELS_CONFIG_NAME**
- **OPENSTACK_AUTH_URL_CONFIG_NAME**
- **OPENSTACK_PASSWORD_CONFIG_NAME**
- **OPENSTACK_PROJECT_DOMAIN_CONFIG_NAME**
- **OPENSTACK_PROJECT_CONFIG_NAME**
- **OPENSTACK_USER_DOMAIN_CONFIG_NAME**
- **OPENSTACK_USER_CONFIG_NAME**
- **REVISION_HISTORY_LIMIT_CONFIG_NAME**
- **RUNNER_VERSION_CONFIG_NAME**
- **IMAGE_RELATION**


---

## <kbd>class</kbd> `Arch`
Supported system architectures. 



**Attributes:**
 
 - <b>`ARM64`</b>:  Represents an ARM64 system architecture. 
 - <b>`X64`</b>:  Represents an X64/AMD64 system architecture. 





---

## <kbd>class</kbd> `BaseImage`
The ubuntu OS base image to build and deploy runners on. 



**Attributes:**
 
 - <b>`JAMMY`</b>:  The jammy ubuntu LTS image. 
 - <b>`NOBLE`</b>:  The noble ubuntu LTS image. 





---

## <kbd>class</kbd> `BuildConfigInvalidError`
Raised when charm config related to image build config is invalid. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `BuildIntervalConfigError`
Represents an error with invalid interval configuration. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `BuilderAppChannel`
Image builder application channel. 

This is managed by the application's git tag and versioning tag in pyproject.toml. 



**Attributes:**
 
 - <b>`EDGE`</b>:  Edge application channel. 
 - <b>`STABLE`</b>:  Stable application channel. 





---

## <kbd>class</kbd> `BuilderAppChannelInvalidError`
Represents invalid builder app channel configuration. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `BuilderInitConfig`
The image builder setup config. 



**Attributes:**
 
 - <b>`app_name`</b>:  The current charm's application name. 
 - <b>`channel`</b>:  The application installation channel. 
 - <b>`external_build`</b>:  Whether the image builder should run in external build mode. 
 - <b>`interval`</b>:  The interval in hours between each scheduled image builds. 
 - <b>`run_config`</b>:  The configuration required to build the image. 
 - <b>`unit_name`</b>:  The charm unit name in which the builder is running on. 




---

<a href="../src/state.py#L853"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → BuilderInitConfig
```

Initialize charm state from current charm instance. 



**Args:**
 
 - <b>`charm`</b>:  The running charm instance. 



**Returns:**
 Current charm state. 


---

## <kbd>class</kbd> `BuilderRunConfig`
Configurations for running builder periodically. 



**Attributes:**
 
 - <b>`image_config`</b>:  Image configuration parameters. 
 - <b>`cloud_config`</b>:  Cloud configuration parameters. 
 - <b>`service_config`</b>:  The external dependent service configurations to build the image. 
 - <b>`parallel_build`</b>:  The number of images to build in parallel. 




---

<a href="../src/state.py#L516"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → BuilderRunConfig
```

Initialize build state from current charm instance. 



**Args:**
 
 - <b>`charm`</b>:  The running charm instance. 



**Returns:**
 Current charm state. 


---

## <kbd>class</kbd> `BuilderSetupConfigInvalidError`
Raised when charm config related to image build setup config is invalid. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `CharmConfigInvalidError`
Raised when charm config is invalid. 



**Attributes:**
 
 - <b>`msg`</b>:  Explanation of the error. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `CloudConfig`
Cloud configuration parameters. 



**Attributes:**
 
 - <b>`cloud_name`</b>:  The OpenStack cloud name to connect to from clouds.yaml. 
 - <b>`external_build_config`</b>:  The external builder configuration values. 
 - <b>`num_revisions`</b>:  Number of images to keep before deletion. 
 - <b>`openstack_clouds_config`</b>:  The OpenStack clouds.yaml passed as charm config. 
 - <b>`upload_cloud_ids`</b>:  The OpenStack cloud ids to connect to, where the image should be             made available. 


---

#### <kbd>property</kbd> cloud_name

The cloud name from cloud_config. 

---

#### <kbd>property</kbd> upload_cloud_ids

The cloud name from cloud_config. 



---

<a href="../src/state.py#L422"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → CloudConfig
```

Initialize cloud config state from current charm instance. 



**Args:**
 
 - <b>`charm`</b>:  The running charm instance. 



**Returns:**
 Cloud configuration state. 


---

## <kbd>class</kbd> `CloudsAuthConfig`
Clouds.yaml authentication parameters. 



**Attributes:**
 
 - <b>`auth_url`</b>:  OpenStack authentication URL (keystone). 
 - <b>`password`</b>:  OpenStack project user password. 
 - <b>`project_domain_name`</b>:  OpenStack project domain name. 
 - <b>`project_name`</b>:  OpenStack project name. 
 - <b>`user_domain_name`</b>:  OpenStack user domain name. 
 - <b>`username`</b>:  The OpenStack user name for given project. 


---

#### <kbd>property</kbd> model_extra

Get extra fields set during validation. 



**Returns:**
  A dictionary of extra fields, or `None` if `config.extra` is not set to `"allow"`. 

---

#### <kbd>property</kbd> model_fields_set

Returns the set of fields that have been explicitly set on this model instance. 



**Returns:**
  A set of strings representing the fields that have been set,  i.e. that were not filled from defaults. 



---

<a href="../src/state.py#L288"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_unit_relation_data`

```python
from_unit_relation_data(data: RelationDataContent) → CloudsAuthConfig | None
```

Get auth data from unit relation data. 



**Args:**
 
 - <b>`data`</b>:  The unit relation data. 



**Returns:**
 CloudsAuthConfig if all required relation data are available, None otherwise. 

---

<a href="../src/state.py#L280"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_id`

```python
get_id() → str
```

Get unique cloud configuration ID. 



**Returns:**
  The unique cloud configuration ID. 


---

## <kbd>class</kbd> `ExternalBuildConfig`
Configurations for external builder VMs. 



**Attributes:**
 
 - <b>`flavor`</b>:  The OpenStack flavor to use for external builder VM. 
 - <b>`network`</b>:  The OpenStack network to launch the builder VM. 




---

<a href="../src/state.py#L228"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → ExternalBuildConfig
```

Initialize build configuration from current charm instance. 



**Args:**
 
 - <b>`charm`</b>:  The running charm instance. 



**Returns:**
 The external build configuration of the charm. 


---

## <kbd>class</kbd> `ImageConfig`
Image configuration parameters. 



**Attributes:**
 
 - <b>`arch`</b>:  The machine architecture of the image to build with. 
 - <b>`bases`</b>:  Ubuntu OS images to build from. 
 - <b>`juju_channels`</b>:  The Juju channels to install on the images. 
 - <b>`microk8s_channels`</b>:  The Microk8s channels to install on the images. 
 - <b>`prefix`</b>:  The image name prefix (application name). 
 - <b>`runner_version`</b>:  The GitHub runner version to embed in the image. Latest version if empty. 




---

<a href="../src/state.py#L365"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → ImageConfig
```

Initialize image config state from current charm instance. 



**Args:**
 
 - <b>`charm`</b>:  The running charm instance. 



**Returns:**
 Image configuration state. 


---

## <kbd>class</kbd> `InsufficientCoresError`
Represents an error with invalid charm resource configuration. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `InvalidBaseImageError`
Represents an error with invalid charm base image configuration. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `InvalidCloudConfigError`
Represents an error with openstack cloud config. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `InvalidDockerHubCacheURLError`
Represents an error with DockerHub cache URL. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `InvalidRevisionHistoryLimitError`
Represents an error with invalid revision history limit configuration value. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `JujuChannelInvalidError`
Represents invalid Juju channels configuration. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `Microk8sChannelInvalidError`
Represents invalid Microk8s channels configuration. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `OpenstackCloudsConfig`
The Openstack clouds.yaml configuration mapping. 



**Attributes:**
 
 - <b>`clouds`</b>:  The mapping of cloud to cloud configuration values. 


---

#### <kbd>property</kbd> model_extra

Get extra fields set during validation. 



**Returns:**
  A dictionary of extra fields, or `None` if `config.extra` is not set to `"allow"`. 

---

#### <kbd>property</kbd> model_fields_set

Returns the set of fields that have been explicitly set on this model instance. 



**Returns:**
  A set of strings representing the fields that have been set,  i.e. that were not filled from defaults. 




---

## <kbd>class</kbd> `ProxyConfig`
Proxy configuration. 



**Attributes:**
 
 - <b>`http`</b>:  HTTP proxy address. 
 - <b>`https`</b>:  HTTPS proxy address. 
 - <b>`no_proxy`</b>:  Comma-separated list of hosts that should not be proxied. 




---

<a href="../src/state.py#L199"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_env`

```python
from_env() → ProxyConfig | None
```

Initialize the proxy config from charm. 



**Returns:**
  Current proxy config of the charm. 


---

## <kbd>class</kbd> `ServiceConfig`
External service configuration values. 



**Attributes:**
 
 - <b>`dockerhub_cache`</b>:  The DockerHub cache to use for microk8s installation. 
 - <b>`proxy`</b>:  The Juju proxy in which the charm should use to build the image. 




---

<a href="../src/state.py#L460"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → ServiceConfig
```

Initialize the external service configurations from charm. 



**Args:**
 
 - <b>`charm`</b>:  The running charm instance. 



**Returns:**
 The external service configurations used to build images. 


---

## <kbd>class</kbd> `UnsupportedArchitectureError`
Raised when given machine charm architecture is unsupported. 

<a href="../src/state.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str | None = None)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





