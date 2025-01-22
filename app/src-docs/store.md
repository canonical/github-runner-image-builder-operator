<!-- markdownlint-disable -->

<a href="../src/github_runner_image_builder/store.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `store`
Module for uploading images to shareable storage. 


---

<a href="../src/github_runner_image_builder/store.py#L22"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_snapshot`

```python
create_snapshot(
    cloud_name: str,
    image_name: str,
    server: Server,
    keep_revisions: int
) → Image
```

Upload image to openstack glance. 



**Args:**
 
 - <b>`cloud_name`</b>:  The Openstack cloud to use from clouds.yaml. 
 - <b>`image_name`</b>:  The image name to upload as. 
 - <b>`server`</b>:  The running OpenStack server to snapshot. 
 - <b>`keep_revisions`</b>:  The number of revisions to keep for an image. 



**Raises:**
 
 - <b>`UploadImageError`</b>:  If there was an error uploading the image to Openstack Glance. 



**Returns:**
 The created image. 


---

<a href="../src/github_runner_image_builder/store.py#L56"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `upload_image`

```python
upload_image(
    arch: Arch,
    cloud_name: str,
    image_name: str,
    image_path: Path,
    keep_revisions: int
) → Image
```

Upload image to openstack glance. 



**Args:**
 
 - <b>`arch`</b>:  The image architecture. 
 - <b>`cloud_name`</b>:  The Openstack cloud to use from clouds.yaml. 
 - <b>`image_name`</b>:  The image name to upload as. 
 - <b>`image_path`</b>:  The path to image to upload. 
 - <b>`keep_revisions`</b>:  The number of revisions to keep for an image. 



**Raises:**
 
 - <b>`UploadImageError`</b>:  If there was an error uploading the image to Openstack Glance. 



**Returns:**
 The created image. 


---

<a href="../src/github_runner_image_builder/store.py#L123"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_latest_build_id`

```python
get_latest_build_id(cloud_name: str, image_name: str) → str
```

Fetch the latest image id. 



**Args:**
 
 - <b>`cloud_name`</b>:  The Openstack cloud to use from clouds.yaml. 
 - <b>`image_name`</b>:  The image name to search for. 



**Returns:**
 The image ID if exists, None otherwise. 


