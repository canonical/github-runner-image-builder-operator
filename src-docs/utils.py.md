<!-- markdownlint-disable -->

<a href="../src/utils.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `utils.py`
Utilities used by the charm. 


---

<a href="../src/utils.py#L23"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `retry`

```python
retry(
    exception: Type[Exception] = <class 'Exception'>,
    tries: int = 1,
    delay: float = 0,
    max_delay: Optional[float] = None,
    backoff: float = 1,
    local_logger: Logger = <Logger utils.py (WARNING)>
) → Callable[[Callable[~ParamT, ~ReturnT]], Callable[~ParamT, ~ReturnT]]
```

Parameterize the decorator for adding retry to functions. 



**Args:**
 
 - <b>`exception`</b>:  Exception type to be retried. 
 - <b>`tries`</b>:  Number of attempts at retry. 
 - <b>`delay`</b>:  Time in seconds to wait between retry. 
 - <b>`max_delay`</b>:  Max time in seconds to wait between retry. 
 - <b>`backoff`</b>:  Factor to increase the delay by each retry. 
 - <b>`local_logger`</b>:  Logger for logging. 



**Returns:**
 The function decorator for retry. 


