<!-- markdownlint-disable -->

<a href="../src/builder.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `builder.py`
Module for interacting with qemu image builder. 

**Global Variables**
---------------
- **UBUNTU_USER**
- **APT_DEPENDENCIES**

---

<a href="../src/builder.py#L72"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `initialize`

```python
initialize(app_init_config: ApplicationInitializationConfig) → None
```

Configure the host machine to build images. 

The application pre-populate OpenStack resources required to build the image. 



**Args:**
 
 - <b>`app_init_config`</b>:  Configuration required to initialize the app. 



**Raises:**
 
 - <b>`BuilderSetupError`</b>:  If there was an error setting up the host device for building images. 


---

<a href="../src/builder.py#L187"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `install_clouds_yaml`

```python
install_clouds_yaml(cloud_config: OpenstackCloudsConfig) → None
```

Install clouds.yaml for Openstack used by the image builder. 

The application interfaces OpenStack credentials with the charm via the clouds.yaml since each of the parameters being passed on (i.e. --openstack-username --openstack-password     --upload-openstack-username --upload-openstack-password ...) is too verbose. 



**Args:**
 
 - <b>`cloud_config`</b>:  The contents of clouds.yaml parsed as dict. 


---

<a href="../src/builder.py#L205"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/builder.py#L407"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `run`

```python
run(
    config_matrix: ConfigMatrix,
    static_config: StaticConfigs
) → list[list[CloudImage]]
```

Run a build immediately. 



**Args:**
 
 - <b>`config_matrix`</b>:  The configurable values matrix for running image builder. 
 - <b>`static_config`</b>:  The static configurations values to run the image builder. 



**Raises:**
 
 - <b>`BuilderRunError`</b>:  if there was an error while launching the subprocess. 



**Returns:**
 The built image metadata. 


---

<a href="../src/builder.py#L727"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_latest_images`

```python
get_latest_images(
    config_matrix: ConfigMatrix,
    static_config: StaticConfigs
) → list[CloudImage]
```

Fetch the latest image build ID. 



**Args:**
 
 - <b>`config_matrix`</b>:  Matricized values of configurable image parameters. 
 - <b>`static_config`</b>:  Static configurations that are used to interact with the image repository. 



**Raises:**
 
 - <b>`GetLatestImageError`</b>:  If there was an error fetching the latest image. 



**Returns:**
 The latest successful image build information. 


---

<a href="../src/builder.py#L866"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `upgrade_app`

```python
upgrade_app() → None
```

Upgrade the application if newer version is available. 



**Raises:**
 
 - <b>`UpgradeApplicationError`</b>:  If there was an error upgrading the application. 


---

## <kbd>class</kbd> `ApplicationInitializationConfig`
Required application initialization configurations. 



**Attributes:**
 
 - <b>`cloud_config`</b>:  The OpenStack cloud config the application should interact with. 
 - <b>`channel`</b>:  The application channel. 
 - <b>`cron_interval`</b>:  The number of hours to retrigger build. 
 - <b>`image_arch`</b>:  The image architecture to initialize build resources for. 
 - <b>`resource_prefix`</b>:  The prefix of application resources. 
 - <b>`unit_name`</b>:  The Juju unit name to trigger the CRON with. 





---

## <kbd>class</kbd> `CloudConfig`
Builder run cloud related configuration parameters. 



**Attributes:**
 
 - <b>`build_cloud`</b>:  The cloud to build the images on. 
 - <b>`build_flavor`</b>:  The OpenStack builder flavor to use. 
 - <b>`build_network`</b>:  The OpenStack builder network to use. 
 - <b>`resource_prefix`</b>:  The OpenStack resources prefix to indicate the ownership. 
 - <b>`upload_clouds`</b>:  The clouds to upload the final image to. 
 - <b>`num_revisions`</b>:  The number of revisions to keep before deleting the image. 





---

## <kbd>class</kbd> `CloudImage`
The cloud ID to uploaded image ID pair. 



**Attributes:**
 
 - <b>`arch`</b>:  The image architecture. 
 - <b>`base`</b>:  The ubuntu base image of the build. 
 - <b>`cloud_id`</b>:  The cloud ID that the image was uploaded to. 
 - <b>`image_id`</b>:  The uploaded image ID. 
 - <b>`juju`</b>:  The juju snap channel. 
 - <b>`microk8s`</b>:  The microk8s snap channel. 





---

## <kbd>class</kbd> `ConfigMatrix`
Configurable image parameters matrix. 

This is just a wrapper DTO on parameterizable variables. 



**Attributes:**
 
 - <b>`bases`</b>:  The ubuntu OS bases. 
 - <b>`juju_channels`</b>:  The juju snap channels to iterate during parametrization. e.g.             {"3.1/stable", "2.9/stable"} 
 - <b>`microk8s_channels`</b>:  The microk8s snap channels to iterate during parametrization. e.g.             {"1.28-strict/stable", "1.29-strict/edge"} 





---

## <kbd>class</kbd> `ExternalServiceConfig`
Builder run external service dependencies. 



**Attributes:**
 
 - <b>`dockerhub_cache`</b>:  The DockerHub cache URL to use to apply to image building. 
 - <b>`proxy`</b>:  The proxy to use to build the image. 





---

## <kbd>class</kbd> `FetchConfig`
Fetch image configuration parameters. 



**Attributes:**
 
 - <b>`arch`</b>:  The architecture to build the image for. 
 - <b>`base`</b>:  The Ubuntu base OS image to build the image on. 
 - <b>`cloud_id`</b>:  The cloud ID to fetch the image from. 
 - <b>`juju`</b>:  The Juju channel to fetch the image for. 
 - <b>`microk8s`</b>:  The Microk8s channel to fetch the image for. 
 - <b>`prefix`</b>:  The image name prefix. 
 - <b>`image_name`</b>:  The image name derived from image configuration attributes. 


---

#### <kbd>property</kbd> image_name

The image name derived from the image configuration attributes. 



**Returns:**
  The image name. 




---

## <kbd>class</kbd> `ImageConfig`
Builder run image related configuration parameters. 



**Attributes:**
 
 - <b>`arch`</b>:  The architecture to build the image for. 
 - <b>`base`</b>:  The Ubuntu base OS image to build the image on. 
 - <b>`juju`</b>:  The Juju channel to install and bootstrap on the image. 
 - <b>`microk8s`</b>:  The Microk8s channel to install and bootstrap on the image. 
 - <b>`prefix`</b>:  The image prefix. 
 - <b>`runner_version`</b>:  The GitHub runner version to pin, defaults to latest. 
 - <b>`script_url`</b>:  The external script to run during cloud-init process. 
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
 - <b>`external_service`</b>:  The external service dependencies for building the image. 





---

## <kbd>class</kbd> `StaticConfigs`
Static configurations that are used to interact with the image repository. 



**Attributes:**
 
 - <b>`cloud_config`</b>:  The OpenStack cloud configuration. 
 - <b>`image_config`</b>:  The output image configuration. 
 - <b>`service_config`</b>:  The helper services to build the image. 





---

## <kbd>class</kbd> `StaticImageConfig`
Static image configuration values. 



**Attributes:**
 
 - <b>`arch`</b>:  The architecture to build the image for. 
 - <b>`prefix`</b>:  The image name prefix. 
 - <b>`script_url`</b>:  The external script to run at the end of the cloud-init. 
 - <b>`runner_version`</b>:  The GitHub runner version. 





