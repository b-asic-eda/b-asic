from qtpy.QtWidgets import QErrorMessage
from traceback import format_exc

def handle_error(fn):
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception:
            self._window.logger.error(f"Unexpected error: {format_exc()}")
            QErrorMessage(self._window).showMessage(
                f"Unexpected error: {format_exc()}")

    return wrapper

def decorate_class(decorator):
    def decorate(cls):
        for attr in cls.__dict__:
            if callable(getattr(cls, attr)):
                setattr(cls, attr, decorator(getattr(cls, attr)))
        return cls
    return decorate
