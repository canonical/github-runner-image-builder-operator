<!-- markdownlint-disable -->

<a href="../src/chroot.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `chroot.py`
Context manager for chrooting. 

**Global Variables**
---------------
- **CHROOT_DEVICE_DIR**
- **CHROOT_SHARED_DIRS**
- **CHROOT_EXTENDED_SHARED_DIRS**


---

## <kbd>class</kbd> `ChrootBaseError`
Represents the errors with chroot. 





---

## <kbd>class</kbd> `ChrootContextManager`
A helper class for managing chroot environments. 

<a href="../src/chroot.py#L33"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(chroot_path: Path)
```

Initialize the chroot context manager. 



**Args:**
 
 - <b>`chroot_path`</b>:  The path to set as new root. 





---

## <kbd>class</kbd> `MountError`
Represents an error while (un)mounting shared dirs. 





---

## <kbd>class</kbd> `SyncError`
Represents an error while syncing chroot dir. 





