"""Reusable configuration for SFG generators exposed by the editor."""

import inspect
from collections.abc import Callable, Mapping
from typing import Any, get_type_hints

from b_asic import sfg_generators
from b_asic.sfg import SFG


class SFGGenerator:
    """
    Describe and invoke an SFG generator using its annotated signature.

    Instantiate with a generator function, or subclass and set ``generator``
    to a staticmethod. ``defaults`` can override parameter defaults for the UI.
    Subclasses may override ``generate`` to customize graph construction.
    """

    generator: Callable[..., SFG] | None = None

    def __init__(
        self,
        generator: Callable[..., SFG] | None = None,
        *,
        name: str | None = None,
        defaults: Mapping[str, Any] | None = None,
    ) -> None:
        if generator is not None:
            self.generator = generator
        if self.generator is None:
            raise ValueError("An SFG generator function is required")
        self.name = name or self.generator.__name__.replace("_", " ")
        self.description = inspect.getdoc(self.generator) or ""
        signature = inspect.signature(self.generator)
        self._call_signature = signature
        hints = get_type_hints(self.generator)
        defaults = dict(defaults or {})
        unknown = defaults.keys() - signature.parameters.keys()
        if unknown:
            raise ValueError(
                f"Unknown generator parameters: {', '.join(sorted(unknown))}"
            )
        parameters = []
        for parameter in signature.parameters.values():
            if parameter.kind in (
                parameter.POSITIONAL_ONLY,
                parameter.VAR_POSITIONAL,
                parameter.VAR_KEYWORD,
            ):
                raise ValueError(
                    "Generator parameters must accept explicit keyword arguments"
                )
            parameters.append(
                parameter.replace(
                    kind=parameter.KEYWORD_ONLY,
                    annotation=hints.get(parameter.name, parameter.annotation),
                    default=defaults.get(parameter.name, parameter.default),
                )
            )
        self.signature = signature.replace(parameters=parameters)

    @property
    def parameters(self) -> Mapping[str, inspect.Parameter]:
        """All configurable parameters, including annotations and defaults."""
        return self.signature.parameters

    def generate(self, **configuration: Any) -> SFG:
        """Generate a graph, using configured defaults for omitted arguments."""
        arguments = self.signature.bind(**configuration)
        arguments.apply_defaults()
        call = self._call_signature.bind(**arguments.arguments)
        sfg = self.generator(*call.args, **call.kwargs)
        if not isinstance(sfg, SFG):
            raise TypeError("The generator must return an SFG")
        return sfg


def builtin_generators() -> tuple[SFGGenerator, ...]:
    """Return configurations for every public built-in SFG generator."""
    return tuple(
        SFGGenerator(getattr(sfg_generators, name)) for name in sfg_generators.__all__
    )
