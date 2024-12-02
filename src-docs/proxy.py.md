<!-- markdownlint-disable -->

<a href="../src/proxy.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `proxy.py`
Module for interacting with proxy. 

**Global Variables**
---------------
- **UBUNTU_USER**

---

<a href="../src/proxy.py#L15"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `setup`

```python
setup(proxy: ProxyConfig | None) → None
```

Install and configure aproxy. 



**Args:**
 
 - <b>`proxy`</b>:  The charm proxy configuration. 



**Raises:**
 
 - <b>`ProxyInstallError`</b>:  If there was an error setting up proxy. 


---

<a href="../src/proxy.py#L38"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `configure_aproxy`

```python
configure_aproxy(proxy: ProxyConfig | None) → None
```

Configure aproxy. 



**Args:**
 
 - <b>`proxy`</b>:  The charm proxy configuration. 



**Raises:**
 
 - <b>`ProxyInstallError`</b>:  If there was an error configuring aproxy. 


