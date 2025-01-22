<!-- markdownlint-disable -->

<a href="../src/github_runner_image_builder/chroot.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `chroot`
Context manager for chrooting. 

**Global Variables**
---------------
- **CHROOT_DEVICE_DIR**
- **CHROOT_SHARED_DIRS**


---

<a href="../src/github_runner_image_builder/chroot.py#L17"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ChrootBaseError`
Represents the errors with chroot. 





---

<a href="../src/github_runner_image_builder/chroot.py#L21"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `MountError`
Represents an error while (un)mounting shared dirs. 





---

<a href="../src/github_runner_image_builder/chroot.py#L25"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SyncError`
Represents an error while syncing chroot dir. 





---

<a href="../src/github_runner_image_builder/chroot.py#L29"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ChrootContextManager`
A helper class for managing chroot environments. 

<a href="../src/github_runner_image_builder/chroot.py#L32"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(chroot_path: Path)
```

Initialize the chroot context manager. 



**Args:**
 
 - <b>`chroot_path`</b>:  The path to set as new root. 





