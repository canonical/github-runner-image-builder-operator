<!-- markdownlint-disable -->

<a href="../src/github_runner_image_builder/cloud_image.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `cloud_image`
Module for downloading images from cloud-images.ubuntu.com. 

**Global Variables**
---------------
- **CHECKSUM_BUF_SIZE**

---

<a href="../src/github_runner_image_builder/cloud_image.py#L27"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `download_and_validate_image`

```python
download_and_validate_image(arch: Arch, base_image: BaseImage) → Path
```

Download and verify the base image from cloud-images.ubuntu.com. 



**Args:**
 
 - <b>`arch`</b>:  The base image architecture to download. 
 - <b>`base_image`</b>:  The ubuntu base image OS to download. 



**Returns:**
 The downloaded image path. 



**Raises:**
 
 - <b>`BaseImageDownloadError`</b>:  If there was an error with downloading/verifying the image. 


