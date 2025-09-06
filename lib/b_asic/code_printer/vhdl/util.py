"""Utility functions for VHDL Printer."""


def signed_type(bits) -> str:
    return f"signed({bits - 1} downto 0)"
