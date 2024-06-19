<!-- markdownlint-disable -->

<a href="../src/image.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `image.py`
The Github-runner-image-builder-operator image relation observer. 

**Global Variables**
---------------
- **IMAGE_RELATION**


---

## <kbd>class</kbd> `ImageRelationData`
Relation data for providing image ID. 



**Attributes:**
 
 - <b>`id`</b>:  The latest image ID to provide. 





---

## <kbd>class</kbd> `Observer`
The image relation observer. 

<a href="../src/image.py#L33"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/image.py#L60"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `update_image_id`

```python
update_image_id(image_id: str) → None
```

Update the relation data if exists. 



**Args:**
 
 - <b>`image_id`</b>:  The latest image ID to propagate. 


