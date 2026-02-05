"""Shared constants for zakat calculation."""

# Nisab thresholds (minimum wealth for zakat obligation)
NISAB_GOLD_GRAMS = 85
NISAB_SILVER_GRAMS = 595

# Zakat rate (2.5%)
ZAKAT_RATE = 0.025

# Loan frequency multipliers for annualization
LOAN_FREQUENCY_MULTIPLIERS = {
    'weekly': 52,
    'biweekly': 26,
    'semi_monthly': 24,
    'monthly': 12,
    'quarterly': 4,
    'yearly': 1,
}

# Valid gold karats
VALID_KARATS = [24, 22, 21, 18, 14, 10, 9]
