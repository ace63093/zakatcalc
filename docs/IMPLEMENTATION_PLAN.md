# Zakat Calculator Enhancement Implementation Plan

## Overview
This document outlines the implementation plan for recommendations #3-#9, including schema versioning for share-link backward compatibility.

---

## 1. Payload Schema Versioning Strategy

### Current Schema (v1)
```javascript
{
  v: 1,
  data: {
    base_currency: "CAD",
    calculation_date: "2026-01-15",
    nisab_basis: "gold",
    gold_items: [{name, weight, weight_unit, weight_grams, purity_karat}],
    cash_items: [{name, amount, currency}],
    bank_items: [{name, amount, currency}],
    metal_items: [{name, metal, weight, weight_unit, weight_grams}],
    crypto_items: [{name, symbol, amount}],
    credit_card_items: [{name, amount, currency}],
    loan_items: [{name, payment_amount, currency, frequency}]
  }
}
```

### Proposed Schema (v2)
```javascript
{
  v: 2,
  data: {
    // === EXISTING (v1 compatible) ===
    base_currency: "CAD",
    calculation_date: "2026-01-15",
    nisab_basis: "gold",
    gold_items: [{name, weight, weight_unit, weight_grams, purity_karat}],
    cash_items: [{name, amount, currency}],
    bank_items: [{name, amount, currency}],
    metal_items: [{name, metal, weight, weight_unit, weight_grams, treat_as_trade_goods}],
    crypto_items: [{name, symbol, amount}],
    credit_card_items: [{name, amount, currency}],
    loan_items: [{name, payment_amount, currency, frequency}],

    // === NEW in v2: Settings ===
    advanced_mode: false,
    debt_policy: "12_months",  // "12_months" | "total" | "custom"

    // === NEW in v2: Advanced Assets ===
    stock_items: [{name, value, currency, method}],  // method: "market_value" | "zakatable_portion"
    retirement_items: [{name, balance, currency, accessible_now, method}],
    receivable_items: [{name, amount, currency, likelihood}],  // likelihood: "likely" | "uncertain" | "doubtful"
    business_inventory: {resale_value, business_cash, receivables, payables, currency},
    investment_property: [{name, intent, market_value, rental_income, currency}],  // intent: "resale" | "rental"

    // === NEW in v2: Additional Debts ===
    short_term_payables: [{name, amount, currency, type}],  // type: "taxes" | "rent" | "utilities" | "other"

    // === NEW in v2: Date Assistant ===
    zakat_anniversary: "2026-03-15",

    // === NEW in v2: UI State ===
    expanded_sections: ["advanced", "debts"]  // Which accordion sections are expanded
  }
}
```

### Migration Strategy
1. **Backward Compatibility**: When loading v1 links, migrate to v2 structure with defaults
2. **Forward Compatibility**: v1 readers ignore unknown fields (already implemented)
3. **Version Detection**: Check `payload.v` and route to appropriate parser

```javascript
function parsePayload(payload) {
  switch(payload.v) {
    case 1: return migrateV1ToV2(payload);
    case 2: return payload.data;
    default: throw new Error('Unknown schema version');
  }
}

function migrateV1ToV2(v1Payload) {
  return {
    ...v1Payload.data,
    advanced_mode: false,
    debt_policy: "12_months",
    stock_items: [],
    retirement_items: [],
    receivable_items: [],
    business_inventory: null,
    investment_property: [],
    short_term_payables: [],
    zakat_anniversary: null,
    expanded_sections: []
  };
}
```

---

## 2. Implementation Order

### Phase 1: Foundation
1. **Feature flags** in `app/services/config.py`
2. **Schema v2** in share-link.js with migration
3. **Constants update** in `app/constants.py`

### Phase 2: Core Features (Order: 3 → 4 → 5)

#### Rec #3: Advanced Assets Mode
- **Backend**: Add calculation functions for stocks, retirement, receivables, business, property
- **Frontend**: Add Advanced toggle, accordion sections, new row templates
- **Share-link**: Include new asset types in serialization

#### Rec #4: Debts Enhancements
- **Backend**: Add debt policy parameter to calculation, short-term payables
- **Frontend**: Add policy selector, payables section, transparent annualization
- **Share-link**: Include debt_policy and short_term_payables

#### Rec #5: Precious Metals Clarification
- **Frontend**: Move platinum/palladium behind Advanced OR add disclaimer
- **Backend**: Add `treat_as_trade_goods` flag to metal calculation

### Phase 3: User Features (Order: 7 → 6 → 8)

#### Rec #7: Printable Summary
- **Backend**: Add `/summary` route
- **Frontend**: Add print CSS, share-link to summary integration

#### Rec #6: Zakat Date Assistant
- **Backend**: Hijri date approximation utility
- **Frontend**: Date picker, ICS download generation

#### Rec #8: UX Polish
- **Frontend**: Tooltips, quick-add, sticky mobile, validation, localStorage autosave

### Phase 4: SEO (Order: 9)

#### Rec #9: SEO Upgrades
- **Backend**: Add `/methodology` route
- **Templates**: FAQ JSON-LD, canonical tags, internal linking

---

## 3. File Changes Summary

### New Files
```
app/services/advanced_calc.py       # Advanced asset calculations
app/services/hijri.py               # Hijri date utilities
app/routes/summary.py               # Summary/print route
app/templates/summary.html          # Print-friendly summary
app/templates/methodology.html      # Methodology page
app/static/js/components/date-assistant.js
app/static/js/components/autosave.js
app/static/css/print.css
app/static/css/advanced.css
```

### Modified Files
```
app/constants.py                    # Add DEBT_POLICIES, RECEIVABLE_LIKELIHOODS
app/services/config.py              # Add feature flags
app/services/calc.py                # Add v3 calculation with advanced assets
app/routes/main.py                  # Add new routes
app/routes/api.py                   # Add v3 calculate endpoint
app/templates/base.html             # Add canonical tag logic
app/templates/calculator.html       # Add advanced sections
app/templates/faq.html              # Add JSON-LD schema
app/static/js/calculator.js         # Add advanced mode, localStorage
app/static/js/components/share-link.js  # Schema v2
app/static/js/utils/shared.js       # Add new constants
```

### Test Files
```
tests/test_services/test_advanced_calc.py
tests/test_share_link_v2.py
tests/test_summary_route.py
tests/test_methodology_route.py
```

---

## 4. Feature Flags

```python
# app/services/config.py additions

ENABLE_ADVANCED_ASSETS = os.environ.get('ENABLE_ADVANCED_ASSETS', '1') == '1'
ENABLE_DATE_ASSISTANT = os.environ.get('ENABLE_DATE_ASSISTANT', '1') == '1'
ENABLE_AUTOSAVE = os.environ.get('ENABLE_AUTOSAVE', '1') == '1'
ENABLE_PRINT_SUMMARY = os.environ.get('ENABLE_PRINT_SUMMARY', '1') == '1'
```

---

## 5. Calculation Engine Changes

### New Subtotal Functions
```python
def calculate_stock_subtotal(stock_items, pricing, base_currency):
    """Calculate zakatable value of stocks based on method."""

def calculate_retirement_subtotal(retirement_items, pricing, base_currency):
    """Calculate zakatable value of retirement accounts."""

def calculate_receivables_subtotal(receivable_items, pricing, base_currency):
    """Calculate zakatable receivables (likely only by default)."""

def calculate_business_subtotal(business_inventory, pricing, base_currency):
    """Calculate zakatable business assets (inventory + cash + receivables - payables)."""

def calculate_property_subtotal(investment_property, pricing, base_currency):
    """Calculate zakatable property value based on intent."""

def calculate_short_term_payables_subtotal(payables, pricing, base_currency):
    """Calculate deductible short-term payables."""
```

### Updated Main Function
```python
def calculate_zakat_v3(
    # Existing params...
    # New params:
    stock_items=None,
    retirement_items=None,
    receivable_items=None,
    business_inventory=None,
    investment_property=None,
    short_term_payables=None,
    debt_policy="12_months",
):
    """Enhanced zakat calculation with advanced assets and debt policies."""
```

---

## 6. Testing Strategy

### Unit Tests
- [ ] Schema migration v1 → v2
- [ ] Advanced asset calculations
- [ ] Debt policy application
- [ ] Receivables likelihood filtering
- [ ] Business inventory net calculation
- [ ] Property intent-based inclusion

### Integration Tests
- [ ] `/api/v1/calculate` with v3 payload
- [ ] Share-link encode/decode with v2 schema
- [ ] Summary route rendering

### E2E Smoke Tests (Manual Checklist)
- [ ] Basic calculator still works
- [ ] Advanced toggle reveals/hides sections
- [ ] Share link loads correctly (v1 and v2)
- [ ] Print summary displays correctly
- [ ] Mobile sticky card works
- [ ] localStorage autosave persists

---

## 7. Rollout Plan

1. **Development**: All features on `refactored` branch
2. **Testing**: Run full test suite + manual smoke tests
3. **Staging**: Deploy to staging environment
4. **Production**: Gradual rollout with feature flags
