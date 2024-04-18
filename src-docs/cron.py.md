<!-- markdownlint-disable -->

<a href="../src/cron.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `cron.py`
Module for managing build intervals. 


---

<a href="../src/cron.py#L49"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `setup`

```python
setup(interval: int, model_name: str, unit_name: str) → None
```

Configure cron job to periodically build image. 



**Args:**
 
 - <b>`interval`</b>:  The number of hours between periodic builds. 
 - <b>`model_name`</b>:  THe model in which the unit belongs to. 
 - <b>`unit_name`</b>:  The unit name to setup the cron job for. 


---

## <kbd>class</kbd> `CronEvent`
Represents a cron triggered event. 





---

## <kbd>class</kbd> `CronEvents`
Represents events triggered by cron. 



**Attributes:**
 
 - <b>`trigger`</b>:  Represents a cron trigger event. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 




