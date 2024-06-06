<!-- markdownlint-disable -->

<a href="../src/charm.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm.py`
Entrypoint for GithubRunnerImageBuilder charm. 

**Global Variables**
---------------
- **BUILD_SUCCESS_EVENT_NAME**
- **BUILD_FAIL_EVENT_NAME**
- **OPENSTACK_IMAGE_ID_ENV**


---

## <kbd>class</kbd> `BuildEvents`
Represents events triggered by image builder callback. 



**Attributes:**
 
 - <b>`build_success`</b>:  Represents a successful image build event. 
 - <b>`build_failed`</b>:  Represents a failed image build event. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 




---

## <kbd>class</kbd> `BuildFailedEvent`
Represents a failed image build event. 





---

## <kbd>class</kbd> `BuildSuccessEvent`
Represents a successful image build event. 





---

## <kbd>class</kbd> `GithubRunnerImageBuilderCharm`
Charm GitHubRunner image builder application. 



**Attributes:**
 
 - <b>`on`</b>:  Represents custom events managed by cron. 

<a href="../src/charm.py#L57"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(*args: Any)
```

Initialize the charm. 



**Args:**
 
 - <b>`args`</b>:  The CharmBase initialization arguments. 


---

#### <kbd>property</kbd> app

Application that this unit is part of. 

---

#### <kbd>property</kbd> charm_dir

Root directory of the charm as it is running. 

---

#### <kbd>property</kbd> config

A mapping containing the charm's config and current values. 

---

#### <kbd>property</kbd> meta

Metadata of this charm. 

---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 

---

#### <kbd>property</kbd> unit

Unit that this execution is responsible for. 


---

#### <kbd>handler</kbd> on


---

<a href="../src/charm.py#L158"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `update_status`

```python
update_status(status: StatusBase) → None
```

Update the charm status. 



**Args:**
 
 - <b>`status`</b>:  The desired status instance. 


