<!-- markdownlint-disable -->

<a href="../src/builder.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `builder.py`
Module for interacting with qemu image builder. 

**Global Variables**
---------------
- **UBUNTU_USER**
- **APT_DEPENDENCIES**
- **OPENSTACK_IMAGE_ID_ENV**
- **IMAGE_NAME_TMPL**

---

<a href="../src/builder.py#L91"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `setup_builder`

```python
setup_builder(
    callback_config: CallbackConfig,
    cron_config: CronConfig,
    cloud_config: dict
) → None
```

Configure the host machine to build images. 



**Args:**
 
 - <b>`callback_config`</b>:  Configuration values to create callbacks script. 
 - <b>`cron_config`</b>:  Configuration values to register cron to build images periodically. 
 - <b>`cloud_config`</b>:  The openstack clouds.yaml contents 



**Raises:**
 
 - <b>`BuilderSetupError`</b>:  If there was an error setting up the host device for building images. 


---

<a href="../src/builder.py#L177"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `install_clouds_yaml`

```python
install_clouds_yaml(cloud_config: dict) → None
```

Install clouds.yaml for Openstack used by the image builder. 



**Args:**
 
 - <b>`cloud_config`</b>:  The contents of clouds.yaml parsed as dict. 


---

<a href="../src/builder.py#L190"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `configure_cron`

```python
configure_cron(config: CronConfig) → bool
```

Configure cron to run builder. 



**Args:**
 
 - <b>`config`</b>:  The configuration required to setup cron job to run builder periodically. 



**Returns:**
 True if cron is reconfigured. False otherwise. 


---

<a href="../src/builder.py#L271"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `build_immediate`

```python
build_immediate(config: CronConfig) → None
```

Run a build immediately. 



**Args:**
 
 - <b>`config`</b>:  The configuration values for running image builder. 


---

<a href="../src/builder.py#L313"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_latest_image`

```python
get_latest_image(
    base: BaseImage,
    app_name: str,
    arch: Arch,
    cloud_name: str
) → str
```

Fetch the latest image build ID. 



**Args:**
 
 - <b>`app_name`</b>:  The current charm application name. 
 - <b>`arch`</b>:  The machine architecture the image was built with. 
 - <b>`base`</b>:  Ubuntu OS image to build from. 
 - <b>`cloud_name`</b>:  The Openstack cloud name to connect to from clouds.yaml. 



**Raises:**
 
 - <b>`GetLatestImageError`</b>:  If there was an error fetching the latest image. 



**Returns:**
 The latest successful image build ID. 


---

## <kbd>class</kbd> `CallbackConfig`
Configuration for callback scripts. 



**Attributes:**
 
 - <b>`model_name`</b>:  Juju model name. 
 - <b>`unit_name`</b>:  Current juju application unit name. 
 - <b>`charm_dir`</b>:  Charm directory to trigger the juju hooks. 
 - <b>`hook_name`</b>:  The Juju hook to call after building image. 





---

## <kbd>class</kbd> `CronConfig`
Configurations for running builder periodically. 



**Attributes:**
 
 - <b>`arch`</b>:  The machine architecture of the image to build with. 
 - <b>`app_name`</b>:  The charm application name, used to name Openstack image. 
 - <b>`base`</b>:  Ubuntu OS image to build from. 
 - <b>`cloud_name`</b>:  The Openstack cloud name to connect to from clouds.yaml. 
 - <b>`interval`</b>:  The frequency in which the image builder should be triggered. 
 - <b>`num_revisions`</b>:  Number of images to keep before deletion. 





