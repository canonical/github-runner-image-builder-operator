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

<a href="../src/builder.py#L48"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/builder.py#L118"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `install_clouds_yaml`

```python
install_clouds_yaml(cloud_config: dict) → None
```

Install clouds.yaml for Openstack used by the image builder. 



**Args:**
 
 - <b>`cloud_config`</b>:  The contents of clouds.yaml parsed as dict. 


---

<a href="../src/builder.py#L131"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/builder.py#L174"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `run`

```python
run(config: BuilderRunConfig) → str
```

Run a build immediately. 



**Args:**
 
 - <b>`config`</b>:  The configuration values for running image builder. 



**Raises:**
 
 - <b>`BuilderRunError`</b>:  if there was an error while launching the subprocess. 



**Returns:**
 The built image id. 


---

<a href="../src/builder.py#L235"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/builder.py#L271"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `upgrade_app`

```python
upgrade_app() → None
```

Upgrade the application if newer version is available. 



**Raises:**
 
 - <b>`UpgradeApplicationError`</b>:  If there was an error upgrading the application. 


