"""German income-tax tariff (§32a EStG), Grundtarif.

Implements the statutory piecewise formula for a per-year constants table. zvE (taxable
income) and the resulting tax are floored to whole euros per §32a Abs. 1. These are
estimates for the freelance-profit overview — not a substitute for ELSTER / a tax advisor.
Only the Grundtarif (single assessment) is modelled; Splitting, Soli and church tax are out
of scope.
"""
from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal

# Per-year parameters. Thresholds g0..g3 are the upper bounds of zones 1..4 (in whole euros);
# the remaining coefficients are the statutory constants for each zone.
_PARAMS: dict[int, dict[str, Decimal]] = {
    2024: {
        "g0": Decimal(11604), "g1": Decimal(17005), "g2": Decimal(66760), "g3": Decimal(277825),
        "z2_a": Decimal("922.98"), "z2_b": Decimal(1400),
        "z3_a": Decimal("181.19"), "z3_b": Decimal(2397), "z3_c": Decimal("1025.38"),
        "z4_m": Decimal("0.42"), "z4_c": Decimal("10602.13"),
        "z5_m": Decimal("0.45"), "z5_c": Decimal("18936.88"),
    },
    2025: {
        "g0": Decimal(12096), "g1": Decimal(17443), "g2": Decimal(68480), "g3": Decimal(277825),
        "z2_a": Decimal("932.30"), "z2_b": Decimal(1400),
        "z3_a": Decimal("176.64"), "z3_b": Decimal(2397), "z3_c": Decimal("1015.13"),
        "z4_m": Decimal("0.42"), "z4_c": Decimal("10911.92"),
        "z5_m": Decimal("0.45"), "z5_c": Decimal("19246.67"),
    },
}


def tariff_year_used(year: int) -> int:
    """The year whose tariff table is applied for `year` (the newest available year ≤ it,
    falling back to the newest table overall)."""
    if year in _PARAMS:
        return year
    older = [y for y in _PARAMS if y <= year]
    return max(older) if older else max(_PARAMS)


def income_tax(zve: Decimal, year: int) -> Decimal:
    """Einkommensteuer (Grundtarif) on taxable income `zve` for `year`, in euros (floored)."""
    p = _PARAMS[tariff_year_used(year)]
    z = Decimal(zve).to_integral_value(rounding=ROUND_FLOOR)
    if z < 0:
        z = Decimal(0)

    if z <= p["g0"]:
        tax = Decimal(0)
    elif z <= p["g1"]:
        y = (z - p["g0"]) / Decimal(10000)
        tax = (p["z2_a"] * y + p["z2_b"]) * y
    elif z <= p["g2"]:
        w = (z - p["g1"]) / Decimal(10000)
        tax = (p["z3_a"] * w + p["z3_b"]) * w + p["z3_c"]
    elif z <= p["g3"]:
        tax = p["z4_m"] * z - p["z4_c"]
    else:
        tax = p["z5_m"] * z - p["z5_c"]

    tax = tax.to_integral_value(rounding=ROUND_FLOOR)
    return tax if tax > 0 else Decimal(0)
