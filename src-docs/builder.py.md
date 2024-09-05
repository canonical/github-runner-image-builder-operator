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

<a href="../src/builder.py#L51"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `initialize`

```python
initialize(init_config: BuilderInitConfig) → None
```

Configure the host machine to build images. 



**Args:**
 
 - <b>`init_config`</b>:  Configuration values required to initialize the builder. 



**Raises:**
 
 - <b>`BuilderSetupError`</b>:  If there was an error setting up the host device for building images. 


---

<a href="../src/builder.py#L122"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `install_clouds_yaml`

```python
install_clouds_yaml(cloud_config: dict) → None
```

Install clouds.yaml for Openstack used by the image builder. 



**Args:**
 
 - <b>`cloud_config`</b>:  The contents of clouds.yaml parsed as dict. 


---

<a href="../src/builder.py#L135"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `configure_cron`

```python
configure_cron(unit_name: str, interval: int) → bool
```

Configure cron to run builder. 



**Args:**
 
 - <b>`unit_name`</b>:  The charm unit name to run cronjob dispatch hook. 
 - <b>`interval`</b>:  Number of hours in between image build runs. 



**Returns:**
 True if cron is reconfigured. False otherwise. 


---

<a href="../src/builder.py#L223"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `run`

```python
run(config: BuilderRunConfig) → list[BuildResult]
```

Run a build immediately. 



**Args:**
 
 - <b>`config`</b>:  The configuration values for running image builder. 



**Raises:**
 
 - <b>`BuilderRunError`</b>:  if there was an error while launching the subprocess. 



**Returns:**
 The built image results. 


---

<a href="../src/builder.py#L368"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_latest_image`

```python
get_latest_image(
    arch: Arch,
    bases: Iterable[BaseImage],
    cloud_name: str
) → list[GetLatestImageResult]
```

Fetch the latest image build ID. 



**Args:**
 
 - <b>`arch`</b>:  The machine architecture the image was built with. 
 - <b>`bases`</b>:  Ubuntu OS images the image was built on. 
 - <b>`cloud_name`</b>:  The Openstack cloud name to connect to from clouds.yaml. 



**Raises:**
 
 - <b>`GetLatestImageError`</b>:  If there was an error fetching the latest image. 



**Returns:**
 The latest successful image build ID. 


---

<a href="../src/builder.py#L444"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `upgrade_app`

```python
upgrade_app() → None
```

Upgrade the application if newer version is available. 



**Raises:**
 
 - <b>`UpgradeApplicationError`</b>:  If there was an error upgrading the application. 


---

## <kbd>class</kbd> `BuildConfig`
The image build configuration. 



**Attributes:**
 
 - <b>`base`</b>:  The ubuntu OS base to build. 





---

## <kbd>class</kbd> `BuildResult`
Build result wrapper. 



**Attributes:**
 
 - <b>`config`</b>:  The configuration values used to run build. 
 - <b>`id`</b>:  The output image id. 





---

## <kbd>class</kbd> `GetLatestImageConfig`
Configurations for fetching latest built images. 



**Attributes:**
 
 - <b>`arch`</b>:  The architecture of the image to fetch. 
 - <b>`base`</b>:  The Ubuntu OS base image. 
 - <b>`cloud_name`</b>:  The cloud to fetch the image from. 





---

## <kbd>class</kbd> `GetLatestImageResult`
Get latest image wrapper. 



**Attributes:**
 
 - <b>`id`</b>:  The image ID. 
 - <b>`config`</b>:  Configuration used to fetch the image. 





