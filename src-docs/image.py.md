<!-- markdownlint-disable -->

<a href="../src/image.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `image.py`
The Github-runner-image-builder-operator image relation observer. 



---

## <kbd>class</kbd> `ImageRelationData`
Relation data for providing image ID. 

Other attributes map from image ID to comma separated tags. 



**Attributes:**
 
 - <b>`id`</b>:  The latest image ID to provide of the primary default image. 
 - <b>`tags`</b>:  The comma separated tags of the image, e.g. x64, jammy, of the primary default image. 





---

## <kbd>class</kbd> `Observer`
The image relation observer. 

<a href="../src/image.py#L35"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/image.py#L62"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `update_image_data`

```python
update_image_data(results: Iterable[BuildResult | GetLatestImageResult]) → None
```

Update the relation data if exists. 



**Args:**
 
 - <b>`results`</b>:  The build results from image builder. 


