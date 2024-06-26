<!-- markdownlint-disable -->

<a href="../src/charm_utils.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm_utils.py`
Module for functions containing charm utilities. 


---

<a href="../src/charm_utils.py#L34"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `block_if_invalid_config`

```python
block_if_invalid_config(
    defer: bool = False
) → Callable[[Callable[[~C, ~E], NoneType]], Callable[[~C, ~E], NoneType]]
```

Create a decorator that puts the charm in blocked state if the config is wrong. 



**Args:**
 
 - <b>`defer`</b>:  whether to defer the event. 



**Returns:**
 the function decorator. 


---

## <kbd>class</kbd> `GithubRunnerImageBuilderCharmProtocol`
Protocol to use for the decorator to block if invalid. 




---

<a href="../src/charm_utils.py#L22"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `update_status`

```python
update_status(status: StatusBase) → None
```

Update the application and unit status. 



**Args:**
 
 - <b>`status`</b>:  the desired unit status. 


