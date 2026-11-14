"""Configure generators and emit complete SFGs for insertion into the editor."""

import ast
import inspect
from collections.abc import Sequence
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from b_asic.sfg_gui.sfg_generator import SFGGenerator, builtin_generators


def _literal_choices(annotation: Any) -> tuple[Any, ...] | None:
    """Extract Literal choices, including nullable and union Literal types."""
    origin = get_origin(annotation)
    if origin is Literal:
        return get_args(annotation)
    if origin in (Union, UnionType):
        choices = []
        for option in get_args(annotation):
            if option is type(None):
                choices.append(None)
            else:
                values = _literal_choices(option)
                if values is None:
                    return None
                choices.extend(values)
        return tuple(choices)
    return None


def _matches_type(value: Any, annotation: Any) -> bool:
    """Validate the scalar and container annotations used by generators."""
    if annotation in (Any, inspect.Parameter.empty):
        return True
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (Union, UnionType):
        return any(_matches_type(value, option) for option in args)
    if origin is Literal:
        return any(type(value) is type(option) and value == option for option in args)
    if annotation is type(None):
        return value is None
    if annotation in (int, float, complex):
        numeric_types = {
            int: (int,),
            float: (int, float),
            complex: (int, float, complex),
        }
        return type(value) in numeric_types[annotation]
    if origin in (list, tuple, Sequence):
        if not isinstance(value, (list, tuple)):
            return False
        if origin is tuple and args and args[-1] is not Ellipsis:
            return len(value) == len(args) and all(
                _matches_type(item, item_type)
                for item, item_type in zip(value, args, strict=True)
            )
        return not args or all(_matches_type(item, args[0]) for item in value)
    if origin is dict:
        return isinstance(value, dict) and (
            not args
            or all(
                _matches_type(key, args[0]) and _matches_type(item, args[1])
                for key, item in value.items()
            )
        )
    return isinstance(value, annotation)


def _parse_value(text: str, annotation: Any) -> Any:
    if annotation is str:
        return text
    if set(get_args(annotation)) == {str, type(None)}:
        return None if not text.strip() or text.strip() == "None" else text
    if not text.strip() and type(None) in get_args(annotation):
        return None
    try:
        value = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        # Names may be entered without quotes, including str | Sequence[str].
        if str in get_args(annotation):
            value = text
        else:
            raise ValueError(
                "Enter a number, list, tuple, dictionary, or None"
            ) from None
    if not _matches_type(value, annotation):
        raise ValueError(f"Expected {annotation}")
    return value


class GeneratorWindow(QDialog):
    """Edit all parameters of a selected generator before generating an SFG."""

    generated = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        generators: Sequence[SFGGenerator] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generate SFG")
        self.resize(600, 520)
        self.generators = tuple(
            builtin_generators() if generators is None else generators
        )
        self._fields: dict[str, QWidget] = {}
        layout = QVBoxLayout(self)
        self._selector = QComboBox(self)
        for generator in self.generators:
            self._selector.addItem(generator.name)
        layout.addWidget(self._selector)
        self._description = QLabel(self)
        self._description.setWordWrap(True)
        layout.addWidget(self._description)
        instructions = QLabel(
            "Enter sequences as [1, 0.5, 2j] and properties as {'latency': 1}. "
            "Use None for optional values; optional text may be left blank.",
            self,
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        layout.addWidget(self._scroll)
        self._error = QLabel(self)
        self._error.setWordWrap(True)
        layout.addWidget(self._error)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self._buttons.button(QDialogButtonBox.Ok).setText("Generate")
        self._buttons.accepted.connect(self._generate)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self._selector.currentIndexChanged.connect(self._configure)
        self._configure()

    def _configure(self) -> None:
        self._fields.clear()
        self._error.clear()
        form_widget = QWidget(self)
        form = QFormLayout(form_widget)
        previous = self._scroll.takeWidget()
        if previous is not None:
            previous.deleteLater()
        self._scroll.setWidget(form_widget)
        index = self._selector.currentIndex()
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(index >= 0)
        if index < 0:
            return
        generator = self.generators[index]
        self._description.setText(generator.description.split("\n\n", 1)[0])
        for name, parameter in generator.parameters.items():
            default = parameter.default
            choices = _literal_choices(parameter.annotation)
            if choices is not None:
                field = QComboBox(form_widget)
                for choice in choices:
                    field.addItem(str(choice), choice)
                if default is not inspect.Parameter.empty:
                    field.setCurrentIndex(choices.index(default))
            elif parameter.annotation is bool:
                field = QCheckBox(form_widget)
                field.setChecked(default is True)
            else:
                field = QLineEdit(form_widget)
                if default is not inspect.Parameter.empty:
                    field.setText(
                        default if isinstance(default, str) else repr(default)
                    )
                else:
                    field.setPlaceholderText("Required")
            field.setObjectName(name)
            field.setToolTip(f"{name}: {parameter.annotation}")
            self._fields[name] = field
            form.addRow(name.replace("_", " ") + ":", field)

    def configuration(self) -> dict[str, Any]:
        """Read typed parameter values, reporting the field on invalid input."""
        generator = self.generators[self._selector.currentIndex()]
        values = {}
        for name, parameter in generator.parameters.items():
            field = self._fields[name]
            try:
                if isinstance(field, QComboBox):
                    value = field.currentData()
                elif isinstance(field, QCheckBox):
                    value = field.isChecked()
                else:
                    value = _parse_value(field.text(), parameter.annotation)
                values[name] = value
            except (ValueError, TypeError) as error:
                field.setFocus()
                raise ValueError(f"{name}: {error}") from error
        return values

    def _generate(self) -> None:
        try:
            generator = self.generators[self._selector.currentIndex()]
            sfg = generator.generate(**self.configuration())
        except Exception as error:
            self._error.setText(str(error))
            return
        if not sfg.name:
            sfg.name = generator.name
        self.generated.emit(sfg)
        self.accept()
