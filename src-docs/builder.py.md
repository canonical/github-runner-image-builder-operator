<!-- markdownlint-disable -->

<a href="../src/builder.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `builder.py`
Module for interacting with qemu image builder. 

**Global Variables**
---------------
- **UBUNTU_USER**
- **APT_DEPENDENCIES**

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

<a href="../src/builder.py#L140"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `install_clouds_yaml`

```python
install_clouds_yaml(cloud_config: OpenstackCloudsConfig) → None
```

Install clouds.yaml for Openstack used by the image builder. 



**Args:**
 
 - <b>`cloud_config`</b>:  The contents of clouds.yaml parsed as dict. 


---

<a href="../src/builder.py#L154"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/builder.py#L216"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `run`

```python
run(
    config: BuilderRunConfig,
    proxy: ProxyConfig | None
) → list[list[CloudImage]]
```

Run a build immediately. 



**Args:**
 
 - <b>`config`</b>:  The configuration values for running image builder. 
 - <b>`proxy`</b>:  The proxy configuration to apply on the builder. 



**Raises:**
 
 - <b>`BuilderRunError`</b>:  if there was an error while launching the subprocess. 



**Returns:**
 The built image id. 


---

<a href="../src/builder.py#L431"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_latest_images`

```python
get_latest_images(config: BuilderRunConfig, cloud_id: str) → list[CloudImage]
```

Fetch the latest image build ID. 



**Args:**
 
 - <b>`config`</b>:  The configuration values for fetching latest image id. 
 - <b>`cloud_id`</b>:  The cloud the fetch the images for. 



**Raises:**
 
 - <b>`GetLatestImageError`</b>:  If there was an error fetching the latest image. 



**Returns:**
 The latest successful image build information. 


---

<a href="../src/builder.py#L558"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `upgrade_app`

```python
upgrade_app() → None
```

Upgrade the application if newer version is available. 



**Raises:**
 
 - <b>`UpgradeApplicationError`</b>:  If there was an error upgrading the application. 


---

## <kbd>class</kbd> `CloudImage`
The cloud ID to uploaded image ID pair. 



**Attributes:**
 
 - <b>`arch`</b>:  The image architecture. 
 - <b>`base`</b>:  The ubuntu base image of the build. 
 - <b>`cloud_id`</b>:  The cloud ID that the image was uploaded to. 
 - <b>`image_id`</b>:  The uploaded image ID. 
 - <b>`juju`</b>:  The juju snap channel. 





---

## <kbd>class</kbd> `FetchConfig`
Fetch image configuration parameters. 



**Attributes:**
 
 - <b>`arch`</b>:  The architecture to build the image for. 
 - <b>`base`</b>:  The Ubuntu base OS image to build the image on. 
 - <b>`cloud_id`</b>:  The cloud ID to fetch the image from. 
 - <b>`juju`</b>:  The Juju channel to fetch the image for. 
 - <b>`prefix`</b>:  The image name prefix. 
 - <b>`image_name`</b>:  The image name derived from image configuration attributes. 


---

#### <kbd>property</kbd> image_name

The image name derived from the image configuration attributes. 



**Returns:**
  The image name. 




---

## <kbd>class</kbd> `RunConfig`
Builder run configuration parameters. 



**Attributes:**
 
 - <b>`image`</b>:  The image configuration parameters. 
 - <b>`cloud`</b>:  The cloud configuration parameters. 





