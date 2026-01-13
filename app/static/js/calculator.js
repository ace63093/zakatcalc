/**
 * Zakat Calculator - Main JavaScript
 *
 * Features:
 * - Live totals that update on every input event
 * - Pricing snapshot cached from server
 * - Client-side calculation for instant feedback
 * - Integration with currency/crypto autocomplete components
 */

const ZakatCalculator = (function() {
    'use strict';

    // Constants
    const NISAB_GOLD_GRAMS = 85;
    const NISAB_SILVER_GRAMS = 595;
    const ZAKAT_RATE = 0.025;
    const DEBOUNCE_DELAY = 100;

    // Weight unit conversion constants (all values are grams per unit)
    const WEIGHT_UNITS = {
        g: { gramsPerUnit: 1, label: 'Grams (g)', short: 'g', decimals: 2 },
        ozt: { gramsPerUnit: 31.1034768, label: 'Troy ounces (oz t)', short: 'oz t', decimals: 4 },
        tola: { gramsPerUnit: 11.6638038, label: 'Tola', short: 'tola', decimals: 4 },
        vori: { gramsPerUnit: 11.6638038, label: 'Vori', short: 'vori', decimals: 4 },
        aana: { gramsPerUnit: 0.72898774, label: 'Aana', short: 'aana', decimals: 2 }
    };

    // State
    let currencies = [];
    let cryptos = [];
    let pricingSnapshot = null;
    let baseCurrency = 'CAD';
    let calculationDate = new Date().toISOString().split('T')[0];
    let nisabBasis = 'gold';
    let debounceTimer = null;
    let lastCalculationResult = null;

    // Currency symbols for display (expanded set)
    const CURRENCY_SYMBOLS = {
        CAD: 'C$', USD: '$', EUR: '\u20AC', GBP: '\u00A3', JPY: '\u00A5',
        AUD: 'A$', CHF: 'CHF', CNY: '\u00A5', INR: '\u20B9', BDT: '\u09F3',
        // Additional common currencies
        AED: 'د.إ', AFN: '؋', ALL: 'L', ARS: '$', BAM: 'KM',
        BGN: 'лв', BHD: '.د.ب', BRL: 'R$', BSD: '$', BWP: 'P',
        BYN: 'Br', CLP: '$', COP: '$', CRC: '₡', CZK: 'Kč',
        DKK: 'kr', DOP: 'RD$', EGP: 'E£', ETB: 'Br', FJD: '$',
        GEL: '₾', GHS: '₵', GTQ: 'Q', HKD: 'HK$', HNL: 'L',
        HRK: 'kn', HUF: 'Ft', IDR: 'Rp', ILS: '₪', IQD: 'ع.د',
        IRR: '﷼', ISK: 'kr', JMD: 'J$', JOD: 'د.ا', KES: 'KSh',
        KGS: 'лв', KHR: '៛', KRW: '₩', KWD: 'د.ك', KYD: '$',
        KZT: '₸', LAK: '₭', LBP: 'ل.ل', LKR: '₨', MAD: 'د.م.',
        MDL: 'L', MKD: 'ден', MMK: 'K', MNT: '₮', MOP: 'MOP$',
        MUR: '₨', MVR: 'Rf', MWK: 'MK', MXN: '$', MYR: 'RM',
        MZN: 'MT', NAD: '$', NGN: '₦', NIO: 'C$', NOK: 'kr',
        NPR: '₨', NZD: 'NZ$', OMR: '﷼', PAB: 'B/.', PEN: 'S/',
        PGK: 'K', PHP: '₱', PKR: '₨', PLN: 'zł', PYG: '₲',
        QAR: '﷼', RON: 'lei', RSD: 'Дин.', RUB: '₽', RWF: 'FRw',
        SAR: '﷼', SCR: '₨', SDG: 'ج.س.', SEK: 'kr', SGD: 'S$',
        SOS: 'S', SRD: '$', SSP: '£', SYP: '£', THB: '฿',
        TJS: 'SM', TMT: 'T', TND: 'د.ت', TOP: 'T$', TRY: '₺',
        TTD: 'TT$', TWD: 'NT$', TZS: 'TSh', UAH: '₴', UGX: 'USh',
        UYU: '$U', UZS: 'лв', VES: 'Bs', VND: '₫', VUV: 'VT',
        WST: 'WS$', XAF: 'FCFA', XCD: '$', XOF: 'CFA', XPF: '₣',
        YER: '﷼', ZAR: 'R', ZMW: 'ZK', ZWL: '$'
    };
    const MONEY_FORMATTERS = {};

    // ========== Weight Unit Conversion Helpers ==========

    /**
     * Convert a value from display unit to grams (canonical storage)
     * @param {number} value - Value in display unit
     * @param {string} unit - Unit code (g, ozt, tola, vori)
     * @returns {number} Value in grams
     */
    function toGrams(value, unit) {
        if (!value || isNaN(value)) return 0;
        var unitInfo = WEIGHT_UNITS[unit] || WEIGHT_UNITS.g;
        return value * unitInfo.gramsPerUnit;
    }

    /**
     * Convert grams to display unit
     * @param {number} grams - Value in grams
     * @param {string} unit - Unit code (g, ozt, tola, vori)
     * @returns {number} Value in display unit
     */
    function fromGrams(grams, unit) {
        if (!grams || isNaN(grams)) return 0;
        var unitInfo = WEIGHT_UNITS[unit] || WEIGHT_UNITS.g;
        return grams / unitInfo.gramsPerUnit;
    }

    /**
     * Format a weight value for display
     * @param {number} grams - Value in grams
     * @param {string} unit - Unit code
     * @returns {string} Formatted string
     */
    function formatWeight(grams, unit) {
        var unitInfo = WEIGHT_UNITS[unit] || WEIGHT_UNITS.g;
        var displayValue = fromGrams(grams, unit);
        return displayValue.toFixed(unitInfo.decimals);
    }

    /**
     * Initialize the calculator
     */
    async function init() {
        try {
            // Load currencies and initial pricing in parallel
            await Promise.all([
                loadCurrencies(),
                loadCryptos(),
            ]);

            await loadPricing();

            // Initialize UI components
            initBaseCurrencySelector();
            initDatePicker();
            initNisabIndicator();
            initAssetRows();
            bindEvents();

            // Initial calculation
            recalculate();

            console.log('Zakat Calculator initialized');
        } catch (error) {
            console.error('Failed to initialize calculator:', error);
            showError('Failed to load pricing data. Please refresh the page.');
        }
    }

    /**
     * Initialize the Nisab Indicator component
     */
    function initNisabIndicator() {
        if (typeof NisabIndicator === 'undefined') {
            console.warn('NisabIndicator component not available');
            return;
        }

        NisabIndicator.init('nisabIndicatorContainer', {
            basis: nisabBasis,
            baseCurrency: baseCurrency,
            onBasisChange: function(newBasis) {
                nisabBasis = newBasis;
                recalculate();
            }
        });
    }

    /**
     * Load currencies from API
     */
    async function loadCurrencies() {
        const response = await fetch('/api/v1/currencies');
        if (!response.ok) throw new Error('Failed to load currencies');

        const data = await response.json();
        currencies = data.currencies;
        baseCurrency = data.default;
    }

    /**
     * Load crypto list from pricing snapshot
     */
    async function loadCryptos() {
        // Cryptos come from the pricing endpoint
        // We'll populate this after loadPricing
    }

    /**
     * Load pricing snapshot from API
     */
    async function loadPricing() {
        const url = `/api/v1/pricing?date=${calculationDate}&base=${baseCurrency}`;
        const response = await fetch(url);

        if (!response.ok) {
            if (response.status === 404) {
                const data = await response.json();
                showWarning(`No pricing data for ${calculationDate}. Using ${data.latest_available || 'available data'}.`);
                return;
            }
            throw new Error('Failed to load pricing');
        }

        pricingSnapshot = await response.json();

        // Extract crypto list from snapshot
        if (pricingSnapshot.crypto) {
            cryptos = Object.entries(pricingSnapshot.crypto).map(([symbol, info]) => ({
                symbol: symbol,
                name: info.name,
                rank: info.rank,
                price: info.price
            })).sort((a, b) => a.rank - b.rank);
        }

        // Update effective date display
        updateEffectiveDateDisplay();

        // Update cadence banner
        updateCadenceBanner();
    }

    /**
     * Initialize base currency selector with autocomplete
     */
    function initBaseCurrencySelector() {
        const container = document.getElementById('baseCurrencyContainer');
        if (!container || typeof CurrencyAutocomplete === 'undefined') return;

        CurrencyAutocomplete.create(container, {
            currencies: currencies,
            initialValue: baseCurrency,
            name: 'baseCurrency',
            onSelect: function(currency) {
                handleBaseCurrencyChange(currency.code);
            }
        });
        container.dataset.initialized = 'true';
    }

    /**
     * Initialize date picker
     */
    function initDatePicker() {
        const datePicker = document.getElementById('calculationDate');
        if (!datePicker) return;

        datePicker.value = calculationDate;
        datePicker.addEventListener('change', function() {
            calculationDate = this.value;
            loadPricing().then(recalculate);
        });
    }

    /**
     * Initialize asset row event listeners
     */
    function initAssetRows() {
        // Initialize currency autocompletes for existing rows
        initCurrencyAutocompletes();
        initCryptoAutocompletes();
    }

    /**
     * Initialize currency autocompletes for cash/bank rows
     */
    function initCurrencyAutocompletes() {
        if (typeof CurrencyAutocomplete === 'undefined') return;

        document.querySelectorAll('.currency-autocomplete:not([data-initialized])').forEach(function(container) {
            if (container.id === 'baseCurrencyContainer') return;
            // Use compact mode for row-level selectors (inside .asset-row)
            var isRowLevel = container.closest('.asset-row') !== null;
            CurrencyAutocomplete.create(container, {
                currencies: currencies,
                initialValue: baseCurrency,
                name: container.dataset.name || 'currency',
                compact: isRowLevel,
                symbols: isRowLevel ? CURRENCY_SYMBOLS : {},
                onSelect: function() {
                    recalculate();
                }
            });
            container.dataset.initialized = 'true';
        });
    }

    /**
     * Initialize crypto autocompletes
     */
    function initCryptoAutocompletes() {
        if (typeof CryptoAutocomplete === 'undefined') return;

        document.querySelectorAll('.crypto-autocomplete:not([data-initialized])').forEach(function(container) {
            CryptoAutocomplete.create(container, {
                cryptos: cryptos,
                name: container.dataset.name || 'crypto',
                onSelect: function() {
                    recalculate();
                }
            });
            container.dataset.initialized = 'true';
        });
    }

    /**
     * Bind event listeners
     */
    function bindEvents() {
        // Use event delegation for dynamic rows
        document.addEventListener('input', function(event) {
            const target = event.target;
            if (target.matches('.asset-row input[type="number"], .asset-row input[type="text"], .asset-row select')) {
                debouncedRecalculate();
            }
        });

        document.addEventListener('change', function(event) {
            const target = event.target;
            if (target.matches('.asset-row select, .asset-row input[type="hidden"]')) {
                recalculate();
            }
        });

        // Form submission (optional server validation)
        const form = document.getElementById('zakatForm');
        if (form) {
            form.addEventListener('submit', function(event) {
                event.preventDefault();
                // Results already shown via live calculation
            });
        }
    }

    /**
     * Debounced recalculate
     */
    function debouncedRecalculate() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(recalculate, DEBOUNCE_DELAY);
    }

    /**
     * Main calculation function - runs client-side
     */
    function recalculate() {
        if (!pricingSnapshot) {
            console.warn('No pricing snapshot available');
            return;
        }

        // Collect all items
        const goldItems = collectGoldItems();
        const cashItems = collectCashItems();
        const bankItems = collectBankItems();
        const metalItems = collectMetalItems();
        const cryptoItems = collectCryptoItems();

        // Calculate subtotals
        const goldTotal = calculateGoldTotal(goldItems);
        const cashTotal = calculateCashTotal(cashItems);
        const bankTotal = calculateBankTotal(bankItems);
        const metalTotal = calculateMetalTotal(metalItems);
        const cryptoTotal = calculateCryptoTotal(cryptoItems);

        const grandTotal = goldTotal + cashTotal + bankTotal + metalTotal + cryptoTotal;

        // Calculate nisab thresholds
        const goldPrice = getMetalPrice('gold');
        const silverPrice = getMetalPrice('silver');
        const nisabGoldValue = NISAB_GOLD_GRAMS * goldPrice;
        const nisabSilverValue = NISAB_SILVER_GRAMS * silverPrice;

        // Use threshold based on selected basis
        const nisabThreshold = nisabBasis === 'silver' ? nisabSilverValue : nisabGoldValue;

        // Calculate ratio and status for nisab indicator
        let ratio = 0;
        let status = 'below';
        if (nisabThreshold > 0) {
            const rawRatio = grandTotal / nisabThreshold;
            ratio = Math.min(Math.max(rawRatio, 0), 1);
            if (rawRatio >= 1.0) {
                status = 'above';
            } else if (rawRatio >= 0.90) {
                status = 'near';
            }
        }

        const difference = Math.abs(grandTotal - nisabThreshold);
        const differenceText = grandTotal >= nisabThreshold
            ? difference.toFixed(2) + ' above nisab'
            : difference.toFixed(2) + ' more to reach nisab';

        const aboveNisab = grandTotal >= nisabThreshold;
        const zakatDue = aboveNisab ? grandTotal * ZAKAT_RATE : 0;

        // Update NisabIndicator with calculated data
        if (typeof NisabIndicator !== 'undefined') {
            NisabIndicator.update({
                basis_used: nisabBasis,
                gold_grams: NISAB_GOLD_GRAMS,
                gold_threshold: nisabGoldValue,
                silver_grams: NISAB_SILVER_GRAMS,
                silver_threshold: nisabSilverValue,
                threshold_used: nisabThreshold,
                ratio: ratio,
                status: status,
                difference: difference,
                difference_text: differenceText
            }, baseCurrency);

            // Set effective date if available
            if (pricingSnapshot.effective_date) {
                NisabIndicator.setEffectiveDate(pricingSnapshot.effective_date);
            }
        }

        // Update display
        updateDisplay({
            goldTotal,
            cashTotal,
            bankTotal,
            metalTotal,
            cryptoTotal,
            grandTotal,
            nisabThreshold,
            nisabBasis,
            aboveNisab,
            zakatDue
        });

        // Update per-row base value pills
        updateRowBaseValues();
    }

    /**
     * Handle base currency changes by reloading pricing and recalculating
     */
    function handleBaseCurrencyChange(currencyCode) {
        baseCurrency = currencyCode;
        if (typeof NisabIndicator !== 'undefined') {
            NisabIndicator.setBaseCurrency(baseCurrency);
        }

        loadPricing()
            .then(function() {
                recalculate();
                updateRowBaseValues();
            })
            .catch(function(error) {
                console.error('Failed to reload pricing for base currency change:', error);
            });
    }

    /**
     * Collect gold items from form
     * Weight is entered in row's display unit, converted to grams for storage
     */
    function collectGoldItems() {
        const items = [];
        document.querySelectorAll('#goldItems .asset-row').forEach(function(row) {
            const displayWeight = parseFloat(row.querySelector('[name="gold_weight"]')?.value) || 0;
            const rowUnit = row.querySelector('[name="gold_weight_unit"]')?.value || 'g';
            const karat = parseInt(row.querySelector('[name="gold_karat"]')?.value) || 22;
            if (displayWeight > 0) {
                items.push({
                    name: row.querySelector('[name="gold_name"]')?.value || 'Gold',
                    weight_grams: toGrams(displayWeight, rowUnit),
                    purity_karat: karat
                });
            }
        });
        return items;
    }

    /**
     * Collect cash items from form
     */
    function collectCashItems() {
        const items = [];
        document.querySelectorAll('#cashItems .asset-row').forEach(function(row) {
            const amount = parseFloat(row.querySelector('[name="cash_amount"]')?.value) || 0;
            const currency = row.querySelector('[name="cash_currency"]')?.value || baseCurrency;
            if (amount > 0) {
                items.push({
                    name: row.querySelector('[name="cash_name"]')?.value || 'Cash',
                    amount: amount,
                    currency: currency
                });
            }
        });
        return items;
    }

    /**
     * Collect bank items from form
     */
    function collectBankItems() {
        const items = [];
        document.querySelectorAll('#bankItems .asset-row').forEach(function(row) {
            const amount = parseFloat(row.querySelector('[name="bank_amount"]')?.value) || 0;
            const currency = row.querySelector('[name="bank_currency"]')?.value || baseCurrency;
            if (amount > 0) {
                items.push({
                    name: row.querySelector('[name="bank_name"]')?.value || 'Bank',
                    amount: amount,
                    currency: currency
                });
            }
        });
        return items;
    }

    /**
     * Collect metal items from form (silver, platinum, palladium)
     * Weight is entered in row's display unit, converted to grams for storage
     */
    function collectMetalItems() {
        const items = [];
        document.querySelectorAll('#metalItems .asset-row').forEach(function(row) {
            const displayWeight = parseFloat(row.querySelector('[name="metal_weight"]')?.value) || 0;
            const rowUnit = row.querySelector('[name="metal_weight_unit"]')?.value || 'g';
            const metal = row.querySelector('[name="metal_type"]')?.value || 'silver';
            if (displayWeight > 0) {
                items.push({
                    name: row.querySelector('[name="metal_name"]')?.value || metal,
                    metal: metal,
                    weight_grams: toGrams(displayWeight, rowUnit)
                });
            }
        });
        return items;
    }

    /**
     * Collect crypto items from form
     */
    function collectCryptoItems() {
        const items = [];
        document.querySelectorAll('#cryptoItems .asset-row').forEach(function(row) {
            const amount = parseFloat(row.querySelector('[name="crypto_amount"]')?.value) || 0;
            const symbol = row.querySelector('[name="crypto_symbol"]')?.value || '';
            if (amount > 0 && symbol) {
                items.push({
                    name: row.querySelector('[name="crypto_name"]')?.value || symbol,
                    symbol: symbol,
                    amount: amount
                });
            }
        });
        return items;
    }

    /**
     * Calculate gold total in base currency
     */
    function calculateGoldTotal(items) {
        const goldPrice = getMetalPrice('gold');
        let total = 0;

        for (const item of items) {
            const pureGrams = item.weight_grams * (item.purity_karat / 24);
            total += pureGrams * goldPrice;
        }

        return total;
    }

    /**
     * Calculate cash total in base currency
     */
    function calculateCashTotal(items) {
        let total = 0;
        const fxRates = pricingSnapshot?.fx_rates || {};

        for (const item of items) {
            total += convertCurrency(item.amount, item.currency, baseCurrency, fxRates);
        }

        return total;
    }

    /**
     * Calculate bank total in base currency
     */
    function calculateBankTotal(items) {
        let total = 0;
        const fxRates = pricingSnapshot?.fx_rates || {};

        for (const item of items) {
            total += convertCurrency(item.amount, item.currency, baseCurrency, fxRates);
        }

        return total;
    }

    /**
     * Calculate metal total in base currency
     */
    function calculateMetalTotal(items) {
        let total = 0;

        for (const item of items) {
            const price = getMetalPrice(item.metal);
            total += item.weight_grams * price;
        }

        return total;
    }

    /**
     * Calculate crypto total in base currency
     */
    function calculateCryptoTotal(items) {
        let total = 0;

        for (const item of items) {
            const price = getCryptoPrice(item.symbol);
            total += item.amount * price;
        }

        return total;
    }

    /**
     * Convert amount from one currency to base currency
     */
    function convertCurrency(amount, fromCurrency, toCurrency, fxRates) {
        if (!fromCurrency || !toCurrency || fromCurrency === toCurrency) return amount;
        if (!fxRates) return amount;

        const fromRate = fxRates[fromCurrency];
        const toRate = fxRates[toCurrency];

        if (!fromRate || !toRate) return amount;

        // fx_rates[X] is the conversion factor from X to base
        return amount * (fromRate / toRate);
    }

    /**
     * Get metal price in base currency
     * Falls back to approximate USD prices if unavailable
     */
    function getMetalPrice(metal) {
        // Fallback prices in USD per gram (approximate)
        const FALLBACK_PRICES = {
            gold: 85,      // ~$2,650/oz
            silver: 1.05,  // ~$33/oz
            platinum: 32,  // ~$1,000/oz
            palladium: 32  // ~$1,000/oz
        };

        const metals = pricingSnapshot?.metals || {};
        const metalInfo = metals[metal] || {};
        const price = metalInfo.price_per_gram || 0;
        const legacyPriceUsd = metalInfo.price_per_gram_usd || 0;
        const fxRates = pricingSnapshot?.fx_rates || {};

        // Use fallback if price is 0 or unavailable
        if (price === 0) {
            if (legacyPriceUsd) {
                return convertCurrency(legacyPriceUsd, 'USD', baseCurrency, fxRates);
            }
            if (FALLBACK_PRICES[metal]) {
                return convertCurrency(FALLBACK_PRICES[metal], 'USD', baseCurrency, fxRates);
            }
        }

        return price;
    }

    /**
     * Get crypto price in base currency
     */
    function getCryptoPrice(symbol) {
        const crypto = pricingSnapshot?.crypto || {};
        const cryptoInfo = crypto[symbol] || {};
        return cryptoInfo.price || 0;
    }

    /**
     * Update the display with calculated values
     */
    function updateDisplay(results) {
        // Store the last calculation result for PDF export
        lastCalculationResult = results;

        setElementText('goldTotal', formatMoney(baseCurrency, results.goldTotal));
        setElementText('cashTotal', formatMoney(baseCurrency, results.cashTotal));
        setElementText('bankTotal', formatMoney(baseCurrency, results.bankTotal));
        setElementText('metalTotal', formatMoney(baseCurrency, results.metalTotal));
        setElementText('cryptoTotal', formatMoney(baseCurrency, results.cryptoTotal));
        setElementText('grandTotal', formatMoney(baseCurrency, results.grandTotal));
        setElementText('nisabThreshold', formatMoney(baseCurrency, results.nisabThreshold));
        setElementText('aboveNisab', results.aboveNisab ? 'Yes' : 'No');
        setElementText('zakatDue', formatMoney(baseCurrency, results.zakatDue));
        setZakatDueGold(results.zakatDue >= 0.01);

        // Update nisab threshold label based on current basis
        const nisabLabel = results.nisabBasis === 'silver'
            ? 'Nisab Threshold (' + NISAB_SILVER_GRAMS + 'g Silver)'
            : 'Nisab Threshold (' + NISAB_GOLD_GRAMS + 'g Gold)';
        setElementText('nisabThresholdLabel', nisabLabel);

        // Show result section
        const resultSection = document.getElementById('result');
        if (resultSection) {
            resultSection.classList.add('show');
        }
    }

    /**
     * Toggle gold styling for zakat due when amount is at least one cent.
     */
    function setZakatDueGold(isGold) {
        const valueElem = document.getElementById('zakatDue');
        const labelElem = document.querySelector('.zakat-due-label');
        if (valueElem) {
            valueElem.classList.toggle('zakat-due-gold', isGold);
        }
        if (labelElem) {
            labelElem.classList.toggle('zakat-due-gold', isGold);
        }
    }

    /**
     * Update effective date display
     */
    function updateEffectiveDateDisplay() {
        const elem = document.getElementById('effectiveDate');
        if (elem && pricingSnapshot) {
            const requested = pricingSnapshot.request?.date || calculationDate;
            const effective = pricingSnapshot.effective_date || requested;

            if (requested !== effective) {
                elem.textContent = `Using prices from ${effective} (requested: ${requested})`;
                elem.style.display = 'block';
            } else {
                elem.textContent = `Prices as of ${effective}`;
                elem.style.display = 'block';
            }
        }
    }

    /**
     * Update cadence banner to show effective snapshot date and cadence type
     */
    function updateCadenceBanner() {
        const banner = document.getElementById('cadenceBanner');
        if (!banner || !pricingSnapshot) return;

        const requested = pricingSnapshot.request?.date || calculationDate;
        const effective = pricingSnapshot.effective_date || requested;
        const cadence = pricingSnapshot.cadence || 'weekly';
        const autoSync = pricingSnapshot.auto_sync || {};

        // Update banner content
        const cadenceType = document.getElementById('cadenceType');
        const effectiveDate = document.getElementById('cadenceEffectiveDate');
        const cadenceNote = document.getElementById('cadenceNote');

        if (cadenceType) cadenceType.textContent = cadence;
        if (effectiveDate) effectiveDate.textContent = effective;

        // Add note based on cadence (3-tier: daily/weekly/monthly)
        if (cadenceNote) {
            if (cadence === 'daily') {
                cadenceNote.textContent = 'Recent dates (last 30 days) use daily snapshots.';
            } else if (cadence === 'weekly') {
                cadenceNote.textContent = 'Dates 30-90 days ago use weekly Monday snapshots.';
            } else if (cadence === 'monthly') {
                cadenceNote.textContent = 'Historical dates (90+ days) use monthly 1st-of-month snapshots.';
            }

            // Add JIT sync note if applicable
            if (autoSync.jit_synced) {
                cadenceNote.textContent += ' (freshly synced)';
            }
        }

        // Show banner when date differs from requested, or to show cadence info
        if (requested !== effective || cadence !== 'daily') {
            banner.style.display = 'block';
        } else {
            banner.style.display = 'none';
        }
    }

    /**
     * Format currency for display
     */
    /**
     * Format money with currency symbol for base value pills
     * @param {string} currencyCode - The currency code (e.g., 'CAD')
     * @param {number|undefined} value - The value to format
     * @returns {string} Formatted string like "$1,234.56" or "—"
     */
    function formatMoney(currencyCode, value) {
        if (value === undefined || value === null || isNaN(value)) {
            return '—';
        }
        if (!currencyCode) {
            return value.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }

        if (!MONEY_FORMATTERS[currencyCode]) {
            try {
                MONEY_FORMATTERS[currencyCode] = new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: currencyCode,
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            } catch (error) {
                MONEY_FORMATTERS[currencyCode] = null;
            }
        }

        if (MONEY_FORMATTERS[currencyCode]) {
            return MONEY_FORMATTERS[currencyCode].format(value);
        }

        const symbol = CURRENCY_SYMBOLS[currencyCode] || currencyCode + ' ';
        return symbol + value.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    /**
     * Compute the base currency value for a single asset row
     * @param {HTMLElement} row - The asset row element
     * @returns {number|undefined} The value in base currency, or undefined if missing data
     */
    function computeRowBaseValue(row) {
        if (!pricingSnapshot) return undefined;

        const type = row.dataset.type;

        switch (type) {
            case 'gold': {
                const displayWeight = parseFloat(row.querySelector('[name="gold_weight"]')?.value);
                const rowUnit = row.querySelector('[name="gold_weight_unit"]')?.value || 'g';
                const karat = parseInt(row.querySelector('[name="gold_karat"]')?.value) || 22;
                if (!displayWeight || displayWeight === 0) return undefined;
                if (isNaN(displayWeight)) return undefined;
                // Convert display weight to grams, then to pure gold grams
                const weightGrams = toGrams(displayWeight, rowUnit);
                const pureGrams = weightGrams * (karat / 24);
                const goldPrice = getMetalPrice('gold');
                return pureGrams * goldPrice;
            }
            case 'metal': {
                const displayWeight = parseFloat(row.querySelector('[name="metal_weight"]')?.value);
                const rowUnit = row.querySelector('[name="metal_weight_unit"]')?.value || 'g';
                const metal = row.querySelector('[name="metal_type"]')?.value || 'silver';
                if (!displayWeight || displayWeight === 0) return undefined;
                if (isNaN(displayWeight)) return undefined;
                // Convert display weight to grams
                const weightGrams = toGrams(displayWeight, rowUnit);
                const metalPrice = getMetalPrice(metal);
                return weightGrams * metalPrice;
            }
            case 'cash': {
                const amount = parseFloat(row.querySelector('[name="cash_amount"]')?.value);
                const currency = row.querySelector('[name="cash_currency"]')?.value || baseCurrency;
                if (!amount || amount === 0) return undefined;
                if (isNaN(amount)) return undefined;
                return convertCurrency(amount, currency, baseCurrency, pricingSnapshot?.fx_rates || {});
            }
            case 'bank': {
                const amount = parseFloat(row.querySelector('[name="bank_amount"]')?.value);
                const currency = row.querySelector('[name="bank_currency"]')?.value || baseCurrency;
                if (!amount || amount === 0) return undefined;
                if (isNaN(amount)) return undefined;
                return convertCurrency(amount, currency, baseCurrency, pricingSnapshot?.fx_rates || {});
            }
            case 'crypto': {
                const amount = parseFloat(row.querySelector('[name="crypto_amount"]')?.value);
                const symbol = row.querySelector('[name="crypto_symbol"]')?.value || '';
                if (!amount || amount === 0) return undefined;
                if (isNaN(amount)) return undefined;
                if (!symbol) return undefined;
                const cryptoPrice = getCryptoPrice(symbol);
                if (!cryptoPrice) return undefined;
                return amount * cryptoPrice;
            }
            default:
                return undefined;
        }
    }

    /**
     * Update base value pills for all asset rows
     */
    function updateRowBaseValues() {
        document.querySelectorAll('.asset-row').forEach(function(row) {
            const pill = row.querySelector('.base-value-pill');
            if (!pill) return;

            const value = computeRowBaseValue(row);

            // Show explicit 0 if value is 0 and there's input, else show dash for blank
            const type = row.dataset.type;
            let hasInput = false;

            if (type === 'gold' || type === 'metal') {
                const weightInput = row.querySelector('[name$="_weight"]');
                hasInput = weightInput && weightInput.value !== '';
            } else if (type === 'cash' || type === 'bank') {
                const amountInput = row.querySelector('[name$="_amount"]');
                hasInput = amountInput && amountInput.value !== '';
            } else if (type === 'crypto') {
                const amountInput = row.querySelector('[name="crypto_amount"]');
                const symbolInput = row.querySelector('[name="crypto_symbol"]');
                hasInput = amountInput && amountInput.value !== '' && symbolInput && symbolInput.value !== '';
            }

            if (value === 0 && hasInput) {
                pill.textContent = formatMoney(baseCurrency, 0);
            } else if (value !== undefined && !isNaN(value)) {
                pill.textContent = formatMoney(baseCurrency, value);
            } else {
                pill.textContent = '—';
            }

            // Update grams pill for gold/metal rows
            if (type === 'gold' || type === 'metal') {
                updateRowGramsPill(row);
            }
        });
    }

    /**
     * Update the grams pill for a gold or metal row
     * @param {HTMLElement} row - The asset row element
     */
    function updateRowGramsPill(row) {
        const gramsPill = row.querySelector('.weight-grams-pill');
        if (!gramsPill) return;

        const type = row.dataset.type;
        const weightInput = row.querySelector('[name="' + type + '_weight"]');
        const unitSelect = row.querySelector('[name="' + type + '_weight_unit"]');

        if (!weightInput || !unitSelect) return;

        const displayWeight = parseFloat(weightInput.value);
        const rowUnit = unitSelect.value || 'g';

        if (!displayWeight || isNaN(displayWeight) || displayWeight === 0) {
            gramsPill.textContent = '—';
            return;
        }

        const weightGrams = toGrams(displayWeight, rowUnit);
        // Format with 2 decimal places and add 'g' suffix
        gramsPill.textContent = weightGrams.toFixed(2) + 'g';
    }

    /**
     * Set text content of an element
     */
    function setElementText(id, text) {
        const elem = document.getElementById(id);
        if (elem) {
            elem.textContent = text;
        }
    }

    /**
     * Show error message
     */
    function showError(message) {
        const container = document.querySelector('.error-message') || createMessageElement('error');
        container.textContent = message;
        container.style.display = 'block';
    }

    /**
     * Show warning message
     */
    function showWarning(message) {
        const container = document.querySelector('.warning-message') || createMessageElement('warning');
        container.textContent = message;
        container.style.display = 'block';
    }

    /**
     * Create a message element
     */
    function createMessageElement(type) {
        const elem = document.createElement('div');
        elem.className = type + '-message';
        const form = document.getElementById('zakatForm');
        if (form) {
            form.insertBefore(elem, form.firstChild);
        }
        return elem;
    }

    // Row management functions
    function addGoldRow() {
        const container = document.getElementById('goldItems');
        if (!container) return;

        const row = document.createElement('div');
        row.className = 'asset-row';
        row.dataset.type = 'gold';
        row.innerHTML = `
            <div class="group-name">
                <input type="text" name="gold_name" placeholder="Name (e.g., Ring)" class="input-name">
            </div>
            <div class="group-middle">
                <input type="number" name="gold_weight" step="0.0001" min="0" placeholder="Weight" class="input-weight">
            </div>
            <div class="group-middle-secondary">
                <select name="gold_weight_unit" class="input-weight-unit">
                    <option value="g" selected>g</option>
                    <option value="ozt">oz t</option>
                    <option value="tola">tola</option>
                    <option value="vori">vori</option>
                    <option value="aana">aana</option>
                </select>
                <select name="gold_karat" class="input-karat">
                    <option value="24">24K</option>
                    <option value="22" selected>22K</option>
                    <option value="21">21K</option>
                    <option value="18">18K</option>
                    <option value="14">14K</option>
                    <option value="10">10K</option>
                    <option value="9">9K</option>
                </select>
                <span class="weight-grams-pill" data-field="weight_grams">—</span>
            </div>
            <div class="group-value">
                <span class="base-value-pill" data-field="base_value">—</span>
            </div>
            <div class="group-remove">
                <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">−</button>
            </div>
        `;
        container.appendChild(row);
    }

    function addCashRow() {
        const container = document.getElementById('cashItems');
        if (!container) return;

        const row = document.createElement('div');
        row.className = 'asset-row';
        row.dataset.type = 'cash';
        row.innerHTML = `
            <div class="group-name">
                <input type="text" name="cash_name" placeholder="Name (e.g., Wallet)" class="input-name">
            </div>
            <div class="group-middle">
                <input type="number" name="cash_amount" step="0.01" min="0" placeholder="Amount" class="input-amount">
            </div>
            <div class="group-value">
                <div class="currency-autocomplete" data-name="cash_currency"></div>
                <span class="base-value-pill" data-field="base_value">—</span>
            </div>
            <div class="group-remove">
                <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">−</button>
            </div>
        `;
        container.appendChild(row);
        initCurrencyAutocompletes();
    }

    function addBankRow() {
        const container = document.getElementById('bankItems');
        if (!container) return;

        const row = document.createElement('div');
        row.className = 'asset-row';
        row.dataset.type = 'bank';
        row.innerHTML = `
            <div class="group-name">
                <input type="text" name="bank_name" placeholder="Name (e.g., Savings)" class="input-name">
            </div>
            <div class="group-middle">
                <input type="number" name="bank_amount" step="0.01" min="0" placeholder="Amount" class="input-amount">
            </div>
            <div class="group-value">
                <div class="currency-autocomplete" data-name="bank_currency"></div>
                <span class="base-value-pill" data-field="base_value">—</span>
            </div>
            <div class="group-remove">
                <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">−</button>
            </div>
        `;
        container.appendChild(row);
        initCurrencyAutocompletes();
    }

    function addMetalRow() {
        const container = document.getElementById('metalItems');
        if (!container) return;

        const row = document.createElement('div');
        row.className = 'asset-row';
        row.dataset.type = 'metal';
        row.innerHTML = `
            <div class="group-name">
                <input type="text" name="metal_name" placeholder="Name (e.g., Silver coins)" class="input-name">
            </div>
            <div class="group-middle">
                <input type="number" name="metal_weight" step="0.0001" min="0" placeholder="Weight" class="input-weight">
            </div>
            <div class="group-middle-secondary">
                <select name="metal_weight_unit" class="input-weight-unit">
                    <option value="g" selected>g</option>
                    <option value="ozt">oz t</option>
                    <option value="tola">tola</option>
                    <option value="vori">vori</option>
                    <option value="aana">aana</option>
                </select>
                <select name="metal_type" class="input-metal">
                    <option value="silver">Silver</option>
                    <option value="platinum">Platinum</option>
                    <option value="palladium">Palladium</option>
                </select>
                <span class="weight-grams-pill" data-field="weight_grams">—</span>
            </div>
            <div class="group-value">
                <span class="base-value-pill" data-field="base_value">—</span>
            </div>
            <div class="group-remove">
                <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">−</button>
            </div>
        `;
        container.appendChild(row);
    }

    function addCryptoRow() {
        const container = document.getElementById('cryptoItems');
        if (!container) return;

        const row = document.createElement('div');
        row.className = 'asset-row';
        row.dataset.type = 'crypto';
        row.innerHTML = `
            <div class="group-name">
                <input type="text" name="crypto_name" placeholder="Name (e.g., Holdings)" class="input-name">
            </div>
            <div class="group-middle">
                <div class="crypto-autocomplete" data-name="crypto_symbol"></div>
                <input type="number" name="crypto_amount" step="0.00000001" min="0" placeholder="Amount" class="input-amount">
            </div>
            <div class="group-value">
                <span class="base-value-pill" data-field="base_value">—</span>
            </div>
            <div class="group-remove">
                <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">−</button>
            </div>
        `;
        container.appendChild(row);
        initCryptoAutocompletes();
    }

    function removeRow(button) {
        const row = button.closest('.asset-row');
        const container = row.parentElement;

        // Check if row has any data entered
        const hasData = Array.from(row.querySelectorAll('input')).some(function(input) {
            return input.type !== 'hidden' && input.value.trim() !== '';
        });

        // Ask for confirmation if row has data
        if (hasData && !confirm('Remove this item?')) {
            return;
        }

        // Keep at least one row
        if (container.querySelectorAll('.asset-row').length > 1) {
            row.remove();
        } else {
            // Clear the row instead
            row.querySelectorAll('input').forEach(function(input) {
                if (input.type !== 'hidden') {
                    input.value = '';
                }
            });
            // Reset the pill
            const pill = row.querySelector('.base-value-pill');
            if (pill) pill.textContent = '—';
        }

        recalculate();
    }

    /**
     * Get the current state of the calculator form
     * @returns {Object} Current form state
     */
    function getState() {
        return {
            base_currency: baseCurrency,
            calculation_date: calculationDate,
            nisab_basis: typeof NisabIndicator !== 'undefined' ? NisabIndicator.getBasis() : nisabBasis,
            gold_items: collectGoldItemsFull(),
            cash_items: collectCashItemsFull(),
            bank_items: collectBankItemsFull(),
            metal_items: collectMetalItemsFull(),
            crypto_items: collectCryptoItemsFull()
        };
    }

    /**
     * Collect gold items with all fields (including empty)
     * Stores display weight, unit, and calculated grams
     */
    function collectGoldItemsFull() {
        var items = [];
        document.querySelectorAll('#goldItems .asset-row').forEach(function(row) {
            var displayWeight = parseFloat(row.querySelector('[name="gold_weight"]')?.value) || 0;
            var rowUnit = row.querySelector('[name="gold_weight_unit"]')?.value || 'g';
            items.push({
                name: row.querySelector('[name="gold_name"]')?.value || '',
                weight: displayWeight,
                weight_unit: rowUnit,
                weight_grams: toGrams(displayWeight, rowUnit),
                purity_karat: parseInt(row.querySelector('[name="gold_karat"]')?.value) || 22
            });
        });
        return items;
    }

    /**
     * Collect cash items with all fields (including empty)
     */
    function collectCashItemsFull() {
        var items = [];
        document.querySelectorAll('#cashItems .asset-row').forEach(function(row) {
            items.push({
                name: row.querySelector('[name="cash_name"]')?.value || '',
                amount: parseFloat(row.querySelector('[name="cash_amount"]')?.value) || 0,
                currency: row.querySelector('[name="cash_currency"]')?.value || baseCurrency
            });
        });
        return items;
    }

    /**
     * Collect bank items with all fields (including empty)
     */
    function collectBankItemsFull() {
        var items = [];
        document.querySelectorAll('#bankItems .asset-row').forEach(function(row) {
            items.push({
                name: row.querySelector('[name="bank_name"]')?.value || '',
                amount: parseFloat(row.querySelector('[name="bank_amount"]')?.value) || 0,
                currency: row.querySelector('[name="bank_currency"]')?.value || baseCurrency
            });
        });
        return items;
    }

    /**
     * Collect metal items with all fields (including empty)
     * Stores display weight, unit, and calculated grams
     */
    function collectMetalItemsFull() {
        var items = [];
        document.querySelectorAll('#metalItems .asset-row').forEach(function(row) {
            var displayWeight = parseFloat(row.querySelector('[name="metal_weight"]')?.value) || 0;
            var rowUnit = row.querySelector('[name="metal_weight_unit"]')?.value || 'g';
            items.push({
                name: row.querySelector('[name="metal_name"]')?.value || '',
                metal: row.querySelector('[name="metal_type"]')?.value || 'silver',
                weight: displayWeight,
                weight_unit: rowUnit,
                weight_grams: toGrams(displayWeight, rowUnit)
            });
        });
        return items;
    }

    /**
     * Collect crypto items with all fields (including empty)
     */
    function collectCryptoItemsFull() {
        var items = [];
        document.querySelectorAll('#cryptoItems .asset-row').forEach(function(row) {
            items.push({
                name: row.querySelector('[name="crypto_name"]')?.value || '',
                symbol: row.querySelector('[name="crypto_symbol"]')?.value || '',
                amount: parseFloat(row.querySelector('[name="crypto_amount"]')?.value) || 0
            });
        });
        return items;
    }

    /**
     * Set the calculator state from a state object
     * @param {Object} state - State object to restore
     */
    function setState(state) {
        if (!state) return;

        // Set base currency
        if (state.base_currency) {
            baseCurrency = state.base_currency;
            var baseCurrencyContainer = document.getElementById('baseCurrencyContainer');
            if (baseCurrencyContainer && typeof CurrencyAutocomplete !== 'undefined') {
                CurrencyAutocomplete.setValue(baseCurrencyContainer, state.base_currency);
            }
            if (typeof NisabIndicator !== 'undefined') {
                NisabIndicator.setBaseCurrency(state.base_currency);
            }
        }

        // Set calculation date
        if (state.calculation_date) {
            calculationDate = state.calculation_date;
            var datePicker = document.getElementById('calculationDate');
            if (datePicker) {
                datePicker.value = state.calculation_date;
            }
        }

        // Set nisab basis
        if (state.nisab_basis && typeof NisabIndicator !== 'undefined') {
            NisabIndicator.setBasis(state.nisab_basis);
            nisabBasis = state.nisab_basis;
        }

        // Restore gold items
        if (state.gold_items) {
            restoreGoldItems(state.gold_items);
        }

        // Restore cash items
        if (state.cash_items) {
            restoreCashItems(state.cash_items);
        }

        // Restore bank items
        if (state.bank_items) {
            restoreBankItems(state.bank_items);
        }

        // Restore metal items
        if (state.metal_items) {
            restoreMetalItems(state.metal_items);
        }

        // Restore crypto items
        if (state.crypto_items) {
            restoreCryptoItems(state.crypto_items);
        }

        // Reload pricing for the new date/currency and recalculate
        loadPricing().then(function() {
            recalculate();
        });
    }

    /**
     * Restore gold items from state
     * Weights are stored in grams but displayed in current unit
     */
    function restoreGoldItems(items) {
        var container = document.getElementById('goldItems');
        if (!container) return;

        // Clear existing rows
        container.innerHTML = '';

        // Add rows for each item (or at least one empty row)
        var itemsToRestore = items.length > 0 ? items : [{ name: '', weight: 0, weight_unit: 'g', purity_karat: 22 }];
        itemsToRestore.forEach(function(item) {
            // Use stored display weight and unit, or fall back to grams if only weight_grams exists (backward compat)
            var rowUnit = item.weight_unit || 'g';
            var displayWeight = '';
            if (item.weight && item.weight > 0) {
                displayWeight = item.weight;
            } else if (item.weight_grams && item.weight_grams > 0) {
                // Backward compatibility: convert grams to display unit
                var unitInfo = WEIGHT_UNITS[rowUnit] || WEIGHT_UNITS.g;
                displayWeight = fromGrams(item.weight_grams, rowUnit).toFixed(unitInfo.decimals);
            }

            var row = document.createElement('div');
            row.className = 'asset-row';
            row.dataset.type = 'gold';
            row.innerHTML = [
                '<div class="group-name">',
                '    <input type="text" name="gold_name" placeholder="Name (e.g., Ring)" class="input-name" value="' + escapeHtml(item.name || '') + '">',
                '</div>',
                '<div class="group-middle">',
                '    <input type="number" name="gold_weight" step="0.0001" min="0" placeholder="Weight" class="input-weight" value="' + displayWeight + '">',
                '</div>',
                '<div class="group-middle-secondary">',
                '    <select name="gold_weight_unit" class="input-weight-unit">',
                '        <option value="g"' + (rowUnit === 'g' ? ' selected' : '') + '>g</option>',
                '        <option value="ozt"' + (rowUnit === 'ozt' ? ' selected' : '') + '>oz t</option>',
                '        <option value="tola"' + (rowUnit === 'tola' ? ' selected' : '') + '>tola</option>',
                '        <option value="vori"' + (rowUnit === 'vori' ? ' selected' : '') + '>vori</option>',
                '        <option value="aana"' + (rowUnit === 'aana' ? ' selected' : '') + '>aana</option>',
                '    </select>',
                '    <select name="gold_karat" class="input-karat">',
                '        <option value="24"' + (item.purity_karat === 24 ? ' selected' : '') + '>24K</option>',
                '        <option value="22"' + (item.purity_karat === 22 || !item.purity_karat ? ' selected' : '') + '>22K</option>',
                '        <option value="21"' + (item.purity_karat === 21 ? ' selected' : '') + '>21K</option>',
                '        <option value="18"' + (item.purity_karat === 18 ? ' selected' : '') + '>18K</option>',
                '        <option value="14"' + (item.purity_karat === 14 ? ' selected' : '') + '>14K</option>',
                '        <option value="10"' + (item.purity_karat === 10 ? ' selected' : '') + '>10K</option>',
                '        <option value="9"' + (item.purity_karat === 9 ? ' selected' : '') + '>9K</option>',
                '    </select>',
                '    <span class="weight-grams-pill" data-field="weight_grams">—</span>',
                '</div>',
                '<div class="group-value">',
                '    <span class="base-value-pill" data-field="base_value">—</span>',
                '</div>',
                '<div class="group-remove">',
                '    <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">−</button>',
                '</div>'
            ].join('\n');
            container.appendChild(row);
        });
    }

    /**
     * Restore cash items from state
     */
    function restoreCashItems(items) {
        var container = document.getElementById('cashItems');
        if (!container) return;

        // Clear existing rows
        container.innerHTML = '';

        // Add rows for each item
        var itemsToRestore = items.length > 0 ? items : [{ name: '', amount: 0, currency: baseCurrency }];
        itemsToRestore.forEach(function(item) {
            var row = document.createElement('div');
            row.className = 'asset-row';
            row.dataset.type = 'cash';
            row.innerHTML = [
                '<div class="group-name">',
                '    <input type="text" name="cash_name" placeholder="Name (e.g., Wallet)" class="input-name" value="' + escapeHtml(item.name || '') + '">',
                '</div>',
                '<div class="group-middle">',
                '    <input type="number" name="cash_amount" step="0.01" min="0" placeholder="Amount" class="input-amount" value="' + (item.amount || '') + '">',
                '</div>',
                '<div class="group-value">',
                '    <div class="currency-autocomplete" data-name="cash_currency" data-initial="' + (item.currency || baseCurrency) + '"></div>',
                '    <span class="base-value-pill" data-field="base_value">—</span>',
                '</div>',
                '<div class="group-remove">',
                '    <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">−</button>',
                '</div>'
            ].join('\n');
            container.appendChild(row);
        });

        // Initialize currency autocompletes for the new rows
        initCurrencyAutocompletesWithValue();
    }

    /**
     * Restore bank items from state
     */
    function restoreBankItems(items) {
        var container = document.getElementById('bankItems');
        if (!container) return;

        // Clear existing rows
        container.innerHTML = '';

        // Add rows for each item
        var itemsToRestore = items.length > 0 ? items : [{ name: '', amount: 0, currency: baseCurrency }];
        itemsToRestore.forEach(function(item) {
            var row = document.createElement('div');
            row.className = 'asset-row';
            row.dataset.type = 'bank';
            row.innerHTML = [
                '<div class="group-name">',
                '    <input type="text" name="bank_name" placeholder="Name (e.g., Savings)" class="input-name" value="' + escapeHtml(item.name || '') + '">',
                '</div>',
                '<div class="group-middle">',
                '    <input type="number" name="bank_amount" step="0.01" min="0" placeholder="Amount" class="input-amount" value="' + (item.amount || '') + '">',
                '</div>',
                '<div class="group-value">',
                '    <div class="currency-autocomplete" data-name="bank_currency" data-initial="' + (item.currency || baseCurrency) + '"></div>',
                '    <span class="base-value-pill" data-field="base_value">—</span>',
                '</div>',
                '<div class="group-remove">',
                '    <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">−</button>',
                '</div>'
            ].join('\n');
            container.appendChild(row);
        });

        // Initialize currency autocompletes for the new rows
        initCurrencyAutocompletesWithValue();
    }

    /**
     * Restore metal items from state
     * Weights are stored in grams but displayed in current unit
     */
    function restoreMetalItems(items) {
        var container = document.getElementById('metalItems');
        if (!container) return;

        // Clear existing rows
        container.innerHTML = '';

        // Add rows for each item
        var itemsToRestore = items.length > 0 ? items : [{ name: '', metal: 'silver', weight: 0, weight_unit: 'g' }];
        itemsToRestore.forEach(function(item) {
            // Use stored display weight and unit, or fall back to grams if only weight_grams exists (backward compat)
            var rowUnit = item.weight_unit || 'g';
            var displayWeight = '';
            if (item.weight && item.weight > 0) {
                displayWeight = item.weight;
            } else if (item.weight_grams && item.weight_grams > 0) {
                // Backward compatibility: convert grams to display unit
                var unitInfo = WEIGHT_UNITS[rowUnit] || WEIGHT_UNITS.g;
                displayWeight = fromGrams(item.weight_grams, rowUnit).toFixed(unitInfo.decimals);
            }

            var row = document.createElement('div');
            row.className = 'asset-row';
            row.dataset.type = 'metal';
            row.innerHTML = [
                '<div class="group-name">',
                '    <input type="text" name="metal_name" placeholder="Name (e.g., Silver coins)" class="input-name" value="' + escapeHtml(item.name || '') + '">',
                '</div>',
                '<div class="group-middle">',
                '    <input type="number" name="metal_weight" step="0.0001" min="0" placeholder="Weight" class="input-weight" value="' + displayWeight + '">',
                '</div>',
                '<div class="group-middle-secondary">',
                '    <select name="metal_weight_unit" class="input-weight-unit">',
                '        <option value="g"' + (rowUnit === 'g' ? ' selected' : '') + '>g</option>',
                '        <option value="ozt"' + (rowUnit === 'ozt' ? ' selected' : '') + '>oz t</option>',
                '        <option value="tola"' + (rowUnit === 'tola' ? ' selected' : '') + '>tola</option>',
                '        <option value="vori"' + (rowUnit === 'vori' ? ' selected' : '') + '>vori</option>',
                '        <option value="aana"' + (rowUnit === 'aana' ? ' selected' : '') + '>aana</option>',
                '    </select>',
                '    <select name="metal_type" class="input-metal">',
                '        <option value="silver"' + (item.metal === 'silver' || !item.metal ? ' selected' : '') + '>Silver</option>',
                '        <option value="platinum"' + (item.metal === 'platinum' ? ' selected' : '') + '>Platinum</option>',
                '        <option value="palladium"' + (item.metal === 'palladium' ? ' selected' : '') + '>Palladium</option>',
                '    </select>',
                '    <span class="weight-grams-pill" data-field="weight_grams">—</span>',
                '</div>',
                '<div class="group-value">',
                '    <span class="base-value-pill" data-field="base_value">—</span>',
                '</div>',
                '<div class="group-remove">',
                '    <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">−</button>',
                '</div>'
            ].join('\n');
            container.appendChild(row);
        });
    }

    /**
     * Restore crypto items from state
     */
    function restoreCryptoItems(items) {
        var container = document.getElementById('cryptoItems');
        if (!container) return;

        // Clear existing rows
        container.innerHTML = '';

        // Add rows for each item
        var itemsToRestore = items.length > 0 ? items : [{ name: '', symbol: '', amount: 0 }];
        itemsToRestore.forEach(function(item) {
            var row = document.createElement('div');
            row.className = 'asset-row';
            row.dataset.type = 'crypto';
            row.innerHTML = [
                '<div class="group-name">',
                '    <input type="text" name="crypto_name" placeholder="Name (e.g., Holdings)" class="input-name" value="' + escapeHtml(item.name || '') + '">',
                '</div>',
                '<div class="group-middle">',
                '    <div class="crypto-autocomplete" data-name="crypto_symbol" data-initial="' + (item.symbol || '') + '"></div>',
                '    <input type="number" name="crypto_amount" step="0.00000001" min="0" placeholder="Amount" class="input-amount" value="' + (item.amount || '') + '">',
                '</div>',
                '<div class="group-value">',
                '    <span class="base-value-pill" data-field="base_value">—</span>',
                '</div>',
                '<div class="group-remove">',
                '    <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">−</button>',
                '</div>'
            ].join('\n');
            container.appendChild(row);
        });

        // Initialize crypto autocompletes for the new rows
        initCryptoAutocompletesWithValue();
    }

    /**
     * Initialize currency autocompletes with initial values from data attributes
     */
    function initCurrencyAutocompletesWithValue() {
        if (typeof CurrencyAutocomplete === 'undefined') return;

        document.querySelectorAll('.currency-autocomplete:not([data-initialized])').forEach(function(container) {
            if (container.id === 'baseCurrencyContainer') return;
            var initialValue = container.dataset.initial || baseCurrency;
            // Use compact mode for row-level selectors (inside .asset-row)
            var isRowLevel = container.closest('.asset-row') !== null;
            CurrencyAutocomplete.create(container, {
                currencies: currencies,
                initialValue: initialValue,
                name: container.dataset.name || 'currency',
                compact: isRowLevel,
                symbols: isRowLevel ? CURRENCY_SYMBOLS : {},
                onSelect: function() {
                    recalculate();
                }
            });
            container.dataset.initialized = 'true';
        });
    }

    /**
     * Initialize crypto autocompletes with initial values from data attributes
     */
    function initCryptoAutocompletesWithValue() {
        if (typeof CryptoAutocomplete === 'undefined') return;

        document.querySelectorAll('.crypto-autocomplete:not([data-initialized])').forEach(function(container) {
            var initialValue = container.dataset.initial || '';
            CryptoAutocomplete.create(container, {
                cryptos: cryptos,
                initialValue: initialValue,
                name: container.dataset.name || 'crypto',
                onSelect: function() {
                    recalculate();
                }
            });
            container.dataset.initialized = 'true';
        });
    }

    /**
     * Escape HTML special characters
     */
    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;')
                  .replace(/</g, '&lt;')
                  .replace(/>/g, '&gt;')
                  .replace(/"/g, '&quot;')
                  .replace(/'/g, '&#039;');
    }

    /**
     * Get the last calculation result
     * @returns {Object|null} Last calculation result or null if none
     */
    function getLastResult() {
        return lastCalculationResult;
    }

    // Public API
    return {
        init: init,
        recalculate: recalculate,
        addGoldRow: addGoldRow,
        addCashRow: addCashRow,
        addBankRow: addBankRow,
        addMetalRow: addMetalRow,
        addCryptoRow: addCryptoRow,
        removeRow: removeRow,
        getState: getState,
        setState: setState,
        getLastResult: getLastResult
    };
})();

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    ZakatCalculator.init();
});

// Legacy function support
function addGoldRow() { ZakatCalculator.addGoldRow(); }
function addCashRow() { ZakatCalculator.addCashRow(); }
function addBankRow() { ZakatCalculator.addBankRow(); }
function addMetalRow() { ZakatCalculator.addMetalRow(); }
function addCryptoRow() { ZakatCalculator.addCryptoRow(); }
function removeRow(btn) { ZakatCalculator.removeRow(btn); }
