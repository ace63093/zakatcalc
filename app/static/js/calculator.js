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

    // State
    let currencies = [];
    let cryptos = [];
    let pricingSnapshot = null;
    let baseCurrency = 'CAD';
    let calculationDate = new Date().toISOString().split('T')[0];
    let nisabBasis = 'gold';
    let debounceTimer = null;

    // Currency symbols for display
    const CURRENCY_SYMBOLS = {
        CAD: 'C$', USD: '$', EUR: '\u20AC', GBP: '\u00A3', JPY: '\u00A5',
        AUD: 'A$', CHF: 'CHF', CNY: '\u00A5', INR: '\u20B9', BDT: '\u09F3'
    };

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
                baseCurrency = currency.code;
                // Update NisabIndicator's base currency
                if (typeof NisabIndicator !== 'undefined') {
                    NisabIndicator.setBaseCurrency(baseCurrency);
                }
                loadPricing().then(recalculate);
            }
        });
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
            CurrencyAutocomplete.create(container, {
                currencies: currencies,
                initialValue: baseCurrency,
                name: container.dataset.name || 'currency',
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
    }

    /**
     * Collect gold items from form
     */
    function collectGoldItems() {
        const items = [];
        document.querySelectorAll('#goldItems .asset-row').forEach(function(row) {
            const weight = parseFloat(row.querySelector('[name="gold_weight"]')?.value) || 0;
            const karat = parseInt(row.querySelector('[name="gold_karat"]')?.value) || 22;
            if (weight > 0) {
                items.push({
                    name: row.querySelector('[name="gold_name"]')?.value || 'Gold',
                    weight_grams: weight,
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
     */
    function collectMetalItems() {
        const items = [];
        document.querySelectorAll('#metalItems .asset-row').forEach(function(row) {
            const weight = parseFloat(row.querySelector('[name="metal_weight"]')?.value) || 0;
            const metal = row.querySelector('[name="metal_type"]')?.value || 'silver';
            if (weight > 0) {
                items.push({
                    name: row.querySelector('[name="metal_name"]')?.value || metal,
                    metal: metal,
                    weight_grams: weight
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

        for (const item of items) {
            total += convertToBase(item.amount, item.currency);
        }

        return total;
    }

    /**
     * Calculate bank total in base currency
     */
    function calculateBankTotal(items) {
        let total = 0;

        for (const item of items) {
            total += convertToBase(item.amount, item.currency);
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
    function convertToBase(amount, fromCurrency) {
        if (fromCurrency === baseCurrency) return amount;

        const fxRates = pricingSnapshot?.fx_rates || {};
        const rate = fxRates[fromCurrency] || 1;

        // fx_rates[X] is the conversion factor from X to base
        return amount * rate;
    }

    /**
     * Get metal price in base currency
     */
    function getMetalPrice(metal) {
        const metals = pricingSnapshot?.metals || {};
        const metalInfo = metals[metal] || {};
        return metalInfo.price_per_gram || 0;
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
        const symbol = CURRENCY_SYMBOLS[baseCurrency] || baseCurrency + ' ';

        setElementText('goldTotal', formatCurrency(results.goldTotal, symbol));
        setElementText('cashTotal', formatCurrency(results.cashTotal, symbol));
        setElementText('bankTotal', formatCurrency(results.bankTotal, symbol));
        setElementText('metalTotal', formatCurrency(results.metalTotal, symbol));
        setElementText('cryptoTotal', formatCurrency(results.cryptoTotal, symbol));
        setElementText('grandTotal', formatCurrency(results.grandTotal, symbol));
        setElementText('nisabThreshold', formatCurrency(results.nisabThreshold, symbol));
        setElementText('aboveNisab', results.aboveNisab ? 'Yes' : 'No');
        setElementText('zakatDue', formatCurrency(results.zakatDue, symbol));

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
    function formatCurrency(amount, symbol) {
        return symbol + amount.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
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
            <input type="text" name="gold_name" placeholder="Name (e.g., Ring)" class="input-name">
            <input type="number" name="gold_weight" step="0.01" min="0" placeholder="Weight (g)" class="input-weight">
            <select name="gold_karat" class="input-karat">
                <option value="24">24K</option>
                <option value="22" selected>22K</option>
                <option value="21">21K</option>
                <option value="18">18K</option>
                <option value="14">14K</option>
                <option value="10">10K</option>
                <option value="9">9K</option>
            </select>
            <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">X</button>
        `;
        container.appendChild(row);
    }

    function addCashRow() {
        const container = document.getElementById('cashItems');
        if (!container) return;

        const rowId = 'cash-row-' + Date.now();
        const row = document.createElement('div');
        row.className = 'asset-row';
        row.dataset.type = 'cash';
        row.innerHTML = `
            <input type="text" name="cash_name" placeholder="Name (e.g., Wallet)" class="input-name">
            <input type="number" name="cash_amount" step="0.01" min="0" placeholder="Amount" class="input-amount">
            <div class="currency-autocomplete" data-name="cash_currency"></div>
            <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">X</button>
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
            <input type="text" name="bank_name" placeholder="Name (e.g., Savings)" class="input-name">
            <input type="number" name="bank_amount" step="0.01" min="0" placeholder="Amount" class="input-amount">
            <div class="currency-autocomplete" data-name="bank_currency"></div>
            <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">X</button>
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
            <input type="text" name="metal_name" placeholder="Name (e.g., Silver coins)" class="input-name">
            <input type="number" name="metal_weight" step="0.01" min="0" placeholder="Weight (g)" class="input-weight">
            <select name="metal_type" class="input-metal">
                <option value="silver">Silver</option>
                <option value="platinum">Platinum</option>
                <option value="palladium">Palladium</option>
            </select>
            <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">X</button>
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
            <input type="text" name="crypto_name" placeholder="Name (e.g., Holdings)" class="input-name">
            <div class="crypto-autocomplete" data-name="crypto_symbol"></div>
            <input type="number" name="crypto_amount" step="0.00000001" min="0" placeholder="Amount" class="input-amount">
            <button type="button" class="btn-remove" onclick="ZakatCalculator.removeRow(this)">X</button>
        `;
        container.appendChild(row);
        initCryptoAutocompletes();
    }

    function removeRow(button) {
        const row = button.closest('.asset-row');
        const container = row.parentElement;

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
        }

        recalculate();
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
        removeRow: removeRow
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
