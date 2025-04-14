from traceback import format_exc

from qtpy.QtWidgets import QErrorMessage


def handle_error(fn):
    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except Exception:
            error_msg = f"Unexpected error: {format_exc()}"
            self._window._logger.error(error_msg)
            QErrorMessage(self._window).showMessage(error_msg)

    return wrapper


def decorate_class(decorator):
    def decorate(cls):
        for attr in cls.__dict__:
            if callable(getattr(cls, attr)):
                setattr(cls, attr, decorator(getattr(cls, attr)))
        return cls

    return decorate
