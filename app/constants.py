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

# ============================================================
# Advanced Assets Constants (v2)
# ============================================================

# Debt deduction policies
DEBT_POLICIES = {
    '12_months': 'Deduct next 12 months only',
    'total': 'Deduct total outstanding',
    'custom': 'Custom deduction',
}
DEFAULT_DEBT_POLICY = '12_months'

# Receivables likelihood and inclusion rules
RECEIVABLE_LIKELIHOODS = {
    'likely': {'label': 'Likely to be paid', 'include': True, 'rate': 1.0},
    'uncertain': {'label': 'Uncertain', 'include': False, 'rate': 0.5},
    'doubtful': {'label': 'Doubtful/Bad debt', 'include': False, 'rate': 0.0},
}
DEFAULT_RECEIVABLE_LIKELIHOOD = 'likely'

# Stock/ETF calculation methods
STOCK_METHODS = {
    'market_value': 'Full market value (recommended)',
    'zakatable_portion': 'Zakatable portion only (30%)',
}
DEFAULT_STOCK_METHOD = 'market_value'
ZAKATABLE_PORTION_RATE = 0.30  # 30% for zakatable portion method

# Retirement account calculation methods
RETIREMENT_METHODS = {
    'full_balance': 'Full balance (if accessible)',
    'accessible_only': 'Accessible portion only',
    'penalty_adjusted': 'After early withdrawal penalty (10%)',
}
DEFAULT_RETIREMENT_METHOD = 'accessible_only'
EARLY_WITHDRAWAL_PENALTY_RATE = 0.10  # 10% penalty

# Investment property intent
PROPERTY_INTENTS = {
    'resale': 'Held for resale (include market value)',
    'rental': 'Held for rental income (include saved rent only)',
}
DEFAULT_PROPERTY_INTENT = 'rental'

# Short-term payables types
PAYABLE_TYPES = {
    'taxes': 'Taxes owing',
    'rent': 'Rent due',
    'utilities': 'Utilities due',
    'other': 'Other payables',
}

# Metals that require fiqh clarification (not universally agreed as zakatable)
METALS_REQUIRING_DISCLAIMER = ['platinum', 'palladium']

# Share-link schema version
SHARE_LINK_SCHEMA_VERSION = 2
