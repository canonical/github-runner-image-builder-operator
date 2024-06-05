<!-- markdownlint-disable -->

<a href="../src/builder.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `builder.py`
Module for interacting with qemu image builder. 

**Global Variables**
---------------
- **UBUNTU_USER**
- **APT_DEPENDENCIES**
- **IMAGE_NAME_TMPL**

---

<a href="../src/builder.py#L68"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `setup_builder`

```python
setup_builder(
    build_config: BuildConfig,
    cloud_config: dict,
    interval: int
) → None
```

Configure the host machine to build images. 



**Args:**
 
 - <b>`build_config`</b>:  Configuration values to register cron to build images periodically. 
 - <b>`cloud_config`</b>:  The openstack clouds.yaml contents 
 - <b>`interval`</b>:  The frequency in which the image builder should be triggered. 



**Raises:**
 
 - <b>`BuilderSetupError`</b>:  If there was an error setting up the host device for building images. 


---

<a href="../src/builder.py#L129"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `install_clouds_yaml`

```python
install_clouds_yaml(cloud_config: dict) → None
```

Install clouds.yaml for Openstack used by the image builder. 



**Args:**
 
 - <b>`cloud_config`</b>:  The contents of clouds.yaml parsed as dict. 


---

<a href="../src/builder.py#L142"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `configure_cron`

```python
configure_cron(build_config: BuildConfig, interval: int) → bool
```

Configure cron to run builder. 



**Args:**
 
 - <b>`build_config`</b>:  The configuration required to run builder. 
 - <b>`interval`</b>:  Number of hours in between image build runs. 



**Returns:**
 True if cron is reconfigured. False otherwise. 


---

<a href="../src/builder.py#L221"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `build_immediate`

```python
build_immediate(config: BuildConfig) → None
```

Run a build immediately. 



**Args:**
 
 - <b>`config`</b>:  The configuration values for running image builder. 


---

<a href="../src/builder.py#L264"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_latest_image`

```python
get_latest_image(arch: Arch, base: BaseImage, cloud_name: str) → str
```

Fetch the latest image build ID. 



**Args:**
 
 - <b>`arch`</b>:  The machine architecture the image was built with. 
 - <b>`base`</b>:  Ubuntu OS image to build from. 
 - <b>`cloud_name`</b>:  The Openstack cloud name to connect to from clouds.yaml. 



**Raises:**
 
 - <b>`GetLatestImageError`</b>:  If there was an error fetching the latest image. 



**Returns:**
 The latest successful image build ID. 


---

## <kbd>class</kbd> `BuildConfig`
Configurations for running builder periodically. 



**Attributes:**
 
 - <b>`arch`</b>:  The machine architecture of the image to build with. 
 - <b>`base`</b>:  Ubuntu OS image to build from. 
 - <b>`cloud_name`</b>:  The Openstack cloud name to connect to from clouds.yaml. 
 - <b>`num_revisions`</b>:  Number of images to keep before deletion. 
 - <b>`callback_script`</b>:  Path to callback script. 





