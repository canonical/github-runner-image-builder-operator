<!-- markdownlint-disable -->

<a href="../src/state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `state.py`
Module for interacting with charm state and configurations. 

**Global Variables**
---------------
- **BASE_IMAGE_CONFIG_NAME**
- **BUILD_INTERVAL_CONFIG_NAME**
- **OPENSTACK_CLOUDS_YAML_CONFIG_NAME**
- **REVISION_HISTORY_LIMIT_CONFIG_NAME**
- **ARCHITECTURES_ARM64**
- **ARCHITECTURES_X86**
- **LTS_IMAGE_VERSION_TAG_MAP**


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

## <kbd>class</kbd> `CharmConfigInvalidError`
Raised when charm config is invalid. 



**Attributes:**
 
 - <b>`msg`</b>:  Explanation of the error. 

<a href="../src/state.py#L268"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `CharmState`
The charm state. 



**Attributes:**
 
 - <b>`build_interval`</b>:  The interval in hours between each scheduled image builds. 
 - <b>`cloud_config`</b>:  The Openstack clouds.yaml passed as charm config. 
 - <b>`image_config`</b>:  The charm configuration values related to image. 
 - <b>`revision_history_limit`</b>:  The number of image revisions to keep. 




---

<a href="../src/state.py#L293"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → CharmState
```

Initialize charm state from current charm instance. 



**Args:**
 
 - <b>`charm`</b>:  The running charm instance. 



**Raises:**
 
 - <b>`CharmConfigInvalidError`</b>:  If there was an invalid configuration on the charm. 



**Returns:**
 Current charm state. 


---

## <kbd>class</kbd> `ImageConfig`
The charm configuration values related to image. 



**Attributes:**
 
 - <b>`arch`</b>:  The underlying compute architecture, i.e. x86_64, amd64, arm64/aarch64. 
 - <b>`base_image`</b>:  The ubuntu base image to run the runner virtual machines on. 




---

<a href="../src/state.py#L144"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → ImageConfig
```

Initialize image config from charm instance. 



**Args:**
 
 - <b>`charm`</b>:  The running charm instance. 



**Raises:**
 
 - <b>`InvalidImageConfigError`</b>:  If an invalid image configuration value has been set. 



**Returns:**
 Current charm image configuration state. 


---

## <kbd>class</kbd> `InvalidCloudConfigError`
Represents an error with openstack cloud config. 





---

## <kbd>class</kbd> `InvalidImageConfigError`
Represents an error with invalid image config. 





---

## <kbd>class</kbd> `UnsupportedArchitectureError`
Raised when given machine charm architecture is unsupported. 



**Attributes:**
 
 - <b>`arch`</b>:  The current machine architecture. 

<a href="../src/state.py#L58"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(arch: str) → None
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`arch`</b>:  The current machine architecture. 





