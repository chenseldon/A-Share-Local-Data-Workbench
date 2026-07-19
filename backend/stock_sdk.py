from free_stockdb_sdk_shim import load_real_sdk_module


_real_module = load_real_sdk_module("stock_sdk")
globals().update({name: value for name, value in vars(_real_module).items() if not name.startswith("__")})
__file__ = _real_module.__file__
__all__ = [name for name in globals() if not name.startswith("_")]
