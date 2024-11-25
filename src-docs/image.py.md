<!-- markdownlint-disable -->

<a href="../src/image.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `image.py`
The Github-runner-image-builder-operator image relation observer. 



---

## <kbd>class</kbd> `ImageRelationData`
Relation data for providing image ID. 



**Attributes:**
 
 - <b>`id`</b>:  The latest image ID to provide. 
 - <b>`tags`</b>:  The comma separated tags of the image, e.g. x64, jammy. 
 - <b>`images`</b>:  JSON formatted list of image dictionary {id: str, tags: str}. 





---

## <kbd>class</kbd> `Observer`
The image relation observer. 

<a href="../src/image.py#L37"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBase)
```

Initialize the observer and register event handlers. 



**Args:**
 
 - <b>`charm`</b>:  The parent charm to attach the observer to. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 



---

<a href="../src/image.py#L105"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `update_image_data`

```python
update_image_data(cloud_images: list[list[CloudImage]]) → None
```

Update relation data for each cloud coming from image requires side of relation. 



**Args:**
 
 - <b>`cloud_images`</b>:  The cloud id and image ids to propagate via relation data. 


