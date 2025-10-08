"""Utility functions for VHDL Printer."""


def signed_type(bits: int) -> str:
    return f"signed({bits - 1} downto 0)"


def schedule_time_type(time: int) -> str:
    return unsigned_type(time.bit_length())


def unsigned_type(bits: int) -> str:
    return f"unsigned({bits - 1} downto 0)"
