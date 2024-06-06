<!-- markdownlint-disable -->

<a href="../src/state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `state.py`
Module for interacting with charm state and configurations. 

**Global Variables**
---------------
- **ARCHITECTURES_ARM64**
- **ARCHITECTURES_X86**
- **LTS_IMAGE_VERSION_TAG_MAP**
- **BASE_IMAGE_CONFIG_NAME**
- **BUILD_INTERVAL_CONFIG_NAME**
- **OPENSTACK_CLOUDS_YAML_CONFIG_NAME**
- **REVISION_HISTORY_LIMIT_CONFIG_NAME**


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

<a href="../src/state.py#L171"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `BuilderInitConfig`
The image builder setup config. 



**Attributes:**
 
 - <b>`run_config`</b>:  The configuration required to build the image. 
 - <b>`interval`</b>:  The interval in hours between each scheduled image builds. 




---

<a href="../src/state.py#L354"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → BuilderInitConfig
```

Initialize charm state from current charm instance. 



**Args:**
 
 - <b>`charm`</b>:  The running charm instance. 



**Raises:**
 
 - <b>`BuilderSetupConfigInvalidError`</b>:  If there was an invalid configuration on the charm. 



**Returns:**
 Current charm state. 


---

## <kbd>class</kbd> `BuilderRunConfig`
Configurations for running builder periodically. 



**Attributes:**
 
 - <b>`arch`</b>:  The machine architecture of the image to build with. 
 - <b>`base`</b>:  Ubuntu OS image to build from. 
 - <b>`cloud_config`</b>:  The Openstack clouds.yaml passed as charm config. 
 - <b>`cloud_name`</b>:  The Openstack cloud name to connect to from clouds.yaml. 
 - <b>`num_revisions`</b>:  Number of images to keep before deletion. 
 - <b>`callback_script`</b>:  Path to callback script. 


---

#### <kbd>property</kbd> cloud_name

The cloud name from cloud_config. 



---

<a href="../src/state.py#L208"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → BuilderRunConfig
```

Initialize build state from current charm instance. 



**Args:**
 
 - <b>`charm`</b>:  The running charm instance. 



**Raises:**
 
 - <b>`BuildConfigInvalidError`</b>:  If there was an invalid configuration on the charm. 



**Returns:**
 Current charm state. 


---

## <kbd>class</kbd> `BuilderSetupConfigInvalidError`
Raised when charm config related to image build setup config is invalid. 

<a href="../src/state.py#L171"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `CharmConfigInvalidError`
Raised when charm config is invalid. 



**Attributes:**
 
 - <b>`msg`</b>:  Explanation of the error. 

<a href="../src/state.py#L171"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `InvalidCloudConfigError`
Represents an error with openstack cloud config. 





---

## <kbd>class</kbd> `ProxyConfig`
Proxy configuration. 



**Attributes:**
 
 - <b>`http`</b>:  HTTP proxy address. 
 - <b>`https`</b>:  HTTPS proxy address. 
 - <b>`no_proxy`</b>:  Comma-separated list of hosts that should not be proxied. 




---

<a href="../src/state.py#L146"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_env`

```python
from_env() → Optional[ForwardRef('ProxyConfig')]
```

Initialize the proxy config from charm. 



**Returns:**
  Current proxy config of the charm. 


---

## <kbd>class</kbd> `UnsupportedArchitectureError`
Raised when given machine charm architecture is unsupported. 



**Attributes:**
 
 - <b>`arch`</b>:  The current machine architecture. 

<a href="../src/state.py#L69"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(arch: str) → None
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`arch`</b>:  The current machine architecture. 





