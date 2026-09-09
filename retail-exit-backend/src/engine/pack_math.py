"""Packaging Mathematics Module

Transparent arithmetic calculations mapping sealed cases to individual item unit counts.
"""

from typing import Tuple, Dict, Any


def calculate_total_units(cases: int, pack_size: int, singles: int = 0) -> int:
    """Computes total units: (cases * pack_size) + singles."""
    if pack_size <= 0:
        raise ValueError(f"pack_size must be positive, got {pack_size}")
    return (cases * pack_size) + singles


def decompose_units_to_cases(total_units: int, pack_size: int) -> Tuple[int, int]:
    """Decomposes total units into (full_cases, remaining_singles)."""
    if pack_size <= 0:
        raise ValueError(f"pack_size must be positive, got {pack_size}")
    full_cases = total_units // pack_size
    singles = total_units % pack_size
    return full_cases, singles


def format_arithmetic_formula(
    product_name: str,
    pack_size: int,
    cases: int,
    singles: int = 0
) -> Dict[str, Any]:
    """Generates transparent, human-readable breakdown for the loss prevention UI."""
    case_units = cases * pack_size
    total_units = case_units + singles
    
    formula_text = (
        f"{cases} × FULL_CASE \"{product_name}\" (pack {pack_size}) = {case_units} units"
    )
    if singles > 0:
        formula_text += f" + {singles} singles = {total_units} units"
    else:
        formula_text += f" = {total_units} units"
        
    return {
        "product_name": product_name,
        "pack_size": pack_size,
        "cases": cases,
        "singles": singles,
        "case_units": case_units,
        "total_units": total_units,
        "formula_text": formula_text,
    }

