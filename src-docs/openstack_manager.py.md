<!-- markdownlint-disable -->

<a href="../src/openstack_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_manager.py`
Module for interactions with Openstack. 

**Global Variables**
---------------
- **IMAGE_NAME_TMPL**


---

## <kbd>class</kbd> `GetImageError`
Represents an error when fetching images from Openstack. 





---

## <kbd>class</kbd> `OpenstackConnectionError`
Represents an error while communicating with Openstack. 





---

## <kbd>class</kbd> `OpenstackManager`
Class to manage interactions with Openstack. 

<a href="../src/openstack_manager.py#L65"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(cloud_config: dict[str, dict])
```

Initialize the openstack manager class. 



**Args:**
 
 - <b>`cloud_config`</b>:  The parsed cloud config yaml contents. 



**Raises:**
 
 - <b>`UnauthorizedError`</b>:  If an invalid openstack credentials was given. 




---

<a href="../src/openstack_manager.py#L166"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_latest_image_id`

```python
get_latest_image_id(
    image_base: BaseImage,
    app_name: str,
    arch: Arch
) → str | None
```

Fetch the latest image id. 



**Args:**
 
 - <b>`image_base`</b>:  The image OS base to search for. 
 - <b>`app_name`</b>:  The name of the application responsible for managing the image. 
 - <b>`arch`</b>:  The architecture used to build the image name. 



**Raises:**
 
 - <b>`GetImageError`</b>:  If there was an error fetching image from Openstack. 



**Returns:**
 The image ID if exists, None otherwise. 

---

<a href="../src/openstack_manager.py#L139"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `upload_image`

```python
upload_image(config: UploadImageConfig) → str
```

Upload image to openstack glance. 



**Args:**
 
 - <b>`config`</b>:  Configuration values for creating image. 



**Raises:**
 
 - <b>`UploadImageError`</b>:  If there was an error uploading the image to Openstack Glance. 



**Returns:**
 The created image ID. 


---

## <kbd>class</kbd> `UnauthorizedError`
Represents an unauthorized connection to Openstack. 





---

## <kbd>class</kbd> `UploadImageConfig`
Configuration values for creating image. 



**Attributes:**
 
 - <b>`arch`</b>:  The architecture the image was built for. 
 - <b>`app_name`</b>:  The application name as a part of image naming. 
 - <b>`base`</b>:  The ubuntu OS base the image was created with. 
 - <b>`num_revisions`</b>:  The number of revisions to keep for an image. 
 - <b>`src_path`</b>:  The path to image to upload. 





---

## <kbd>class</kbd> `UploadImageError`
Represents an error when uploading image to Openstack. 





