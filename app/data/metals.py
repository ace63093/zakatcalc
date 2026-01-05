"""Supported precious metals for zakat calculation."""

# Supported metals with their properties
SUPPORTED_METALS = {
    'gold': {
        'name': 'Gold',
        'symbol': 'Au',
        'nisab_grams': 85,
    },
    'silver': {
        'name': 'Silver',
        'symbol': 'Ag',
        'nisab_grams': 595,
    },
    'platinum': {
        'name': 'Platinum',
        'symbol': 'Pt',
        'nisab_grams': None,  # No traditional nisab
    },
    'palladium': {
        'name': 'Palladium',
        'symbol': 'Pd',
        'nisab_grams': None,  # No traditional nisab
    },
}

# Gold karats and their purity fractions
GOLD_KARATS = {
    24: 1.0,
    22: 22/24,
    21: 21/24,
    18: 18/24,
    14: 14/24,
    10: 10/24,
    9: 9/24,
}


def get_supported_metals() -> list[dict]:
    """Get list of supported metals for UI dropdowns."""
    return [
        {
            'id': metal_id,
            'name': info['name'],
            'symbol': info['symbol'],
        }
        for metal_id, info in SUPPORTED_METALS.items()
    ]


def get_other_metals() -> list[dict]:
    """Get metals other than gold (for the 'Other Metals' section)."""
    return [
        {
            'id': metal_id,
            'name': info['name'],
            'symbol': info['symbol'],
        }
        for metal_id, info in SUPPORTED_METALS.items()
        if metal_id != 'gold'
    ]


def is_valid_metal(metal_id: str) -> bool:
    """Check if a metal ID is valid."""
    return metal_id.lower() in SUPPORTED_METALS


def get_karat_fraction(karat: int) -> float:
    """Get purity fraction for a gold karat value."""
    return GOLD_KARATS.get(karat, karat / 24)


def get_valid_karats() -> list[int]:
    """Get list of valid karat values."""
    return sorted(GOLD_KARATS.keys(), reverse=True)
