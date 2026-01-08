"""Utility functions for VHDL Printer."""


def signed_type(bits: int) -> str:
    return f"signed({bits - 1} downto 0)"


def schedule_time_type(time: int) -> str:
    if time <= 0:
        raise ValueError("Schedule time must be positive.")
    if time == 1:
        return unsigned_type(1)
    return unsigned_type((time - 1).bit_length())


def unsigned_type(bits: int) -> str:
    return f"unsigned({bits - 1} downto 0)"
