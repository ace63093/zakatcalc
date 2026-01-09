/**
 * CSV Export Component
 * Exports zakat calculation data to CSV format
 */
const CsvExport = (function() {
    'use strict';

    let exportBtn = null;

    /**
     * Initialize the CSV export component
     */
    function init() {
        exportBtn = document.getElementById('export-csv-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', handleExport);
        }
    }

    /**
     * Handle export button click
     */
    function handleExport() {
        const csvContent = generateCsv();
        downloadCsv(csvContent);
        showNotification('CSV exported successfully!', 'success');
    }

    /**
     * Generate CSV content from current calculator state
     * @returns {string} CSV formatted string
     */
    function generateCsv() {
        const rows = [];
        const baseCurrency = getBaseCurrency();
        const calculationDate = getCalculationDate();
        const effectiveDate = getEffectivePricingDate();
        const nisabInfo = getNisabInfo();
        const totals = getTotals();

        // Metadata section
        rows.push(['=== ZAKAT CALCULATION EXPORT ===']);
        rows.push([]);
        rows.push(['Metadata']);
        rows.push(['ExportedAt', new Date().toISOString()]);
        rows.push(['CalculationDate', calculationDate || 'Today']);
        rows.push(['EffectivePricingDate', effectiveDate || 'N/A']);
        rows.push(['BaseCurrency', baseCurrency]);
        rows.push(['NisabBasis', nisabInfo.basis]);
        rows.push(['NisabThreshold', nisabInfo.threshold]);
        rows.push(['ZakatableTotal', totals.grandTotal]);
        rows.push(['ZakatDue', totals.zakatDue]);
        rows.push([]);

        // Asset breakdown header
        rows.push(['=== ASSET BREAKDOWN ===']);
        rows.push([]);
        rows.push([
            'Category',
            'Item Name',
            'Input Currency/Unit',
            'Input Amount',
            'Pricing Symbol/Metal',
            'Price Per Unit (Base)',
            'Value (Base)',
            'Notes'
        ]);

        // Gold assets
        const goldAssets = collectGoldAssets(baseCurrency);
        goldAssets.forEach(asset => rows.push(asset));

        // Other metals
        const metalAssets = collectMetalAssets(baseCurrency);
        metalAssets.forEach(asset => rows.push(asset));

        // Cash
        const cashAssets = collectCashAssets(baseCurrency);
        cashAssets.forEach(asset => rows.push(asset));

        // Bank accounts
        const bankAssets = collectBankAssets(baseCurrency);
        bankAssets.forEach(asset => rows.push(asset));

        // Crypto
        const cryptoAssets = collectCryptoAssets(baseCurrency);
        cryptoAssets.forEach(asset => rows.push(asset));

        // Summary section
        rows.push([]);
        rows.push(['=== SUMMARY ===']);
        rows.push([]);
        rows.push(['Category', 'Total (' + baseCurrency + ')']);
        rows.push(['Gold', totals.gold]);
        rows.push(['Other Metals', totals.metals]);
        rows.push(['Cash', totals.cash]);
        rows.push(['Bank Accounts', totals.bank]);
        rows.push(['Cryptocurrency', totals.crypto]);
        rows.push([]);
        rows.push(['Grand Total', totals.grandTotal]);
        rows.push(['Nisab Threshold', nisabInfo.threshold]);
        rows.push(['Above Nisab', totals.grandTotal >= parseFloat(nisabInfo.threshold.replace(/[^0-9.-]/g, '')) ? 'Yes' : 'No']);
        rows.push(['Zakat Due (2.5%)', totals.zakatDue]);

        return rows.map(row => row.map(escapeCsvField).join(',')).join('\n');
    }

    /**
     * Escape a field for CSV format
     * @param {*} field - Field value to escape
     * @returns {string} Escaped field
     */
    function escapeCsvField(field) {
        if (field === null || field === undefined) {
            return '';
        }
        const str = String(field);
        // If field contains comma, quote, or newline, wrap in quotes
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
            return '"' + str.replace(/"/g, '""') + '"';
        }
        return str;
    }

    /**
     * Get base currency from the form
     * @returns {string} Base currency code
     */
    function getBaseCurrency() {
        const container = document.getElementById('baseCurrencyContainer');
        if (container && container._autocomplete) {
            return container._autocomplete.getValue() || 'USD';
        }
        return 'USD';
    }

    /**
     * Get calculation date from the form
     * @returns {string} Calculation date
     */
    function getCalculationDate() {
        const dateInput = document.getElementById('calculationDate');
        return dateInput ? dateInput.value : '';
    }

    /**
     * Get effective pricing date from the cadence banner
     * @returns {string} Effective pricing date
     */
    function getEffectivePricingDate() {
        const effectiveDateEl = document.getElementById('cadenceEffectiveDate');
        return effectiveDateEl ? effectiveDateEl.textContent : '';
    }

    /**
     * Weight unit definitions (must match calculator.js)
     */
    const WEIGHT_UNITS = {
        g: { gramsPerUnit: 1, label: 'Grams (g)', short: 'g' },
        ozt: { gramsPerUnit: 31.1034768, label: 'Troy ounces (oz t)', short: 'oz t' },
        tola: { gramsPerUnit: 11.6638038, label: 'Tola', short: 'tola' },
        vori: { gramsPerUnit: 11.6638038, label: 'Vori', short: 'vori' },
        aana: { gramsPerUnit: 0.72898774, label: 'Aana', short: 'aana' }
    };

    /**
     * Get weight unit info by code
     * @param {string} code - Weight unit code (g, ozt, tola, vori, aana)
     * @returns {Object} Weight unit info {code, label, short, gramsPerUnit}
     */
    function getRowWeightUnit(code) {
        const unitInfo = WEIGHT_UNITS[code] || WEIGHT_UNITS.g;
        return {
            code: code,
            label: unitInfo.label,
            short: unitInfo.short,
            gramsPerUnit: unitInfo.gramsPerUnit
        };
    }

    /**
     * Convert display weight to grams
     * @param {number} displayWeight - Weight in current display unit
     * @param {Object} weightUnit - Weight unit info
     * @returns {number} Weight in grams
     */
    function toGrams(displayWeight, weightUnit) {
        if (!displayWeight || isNaN(displayWeight)) return 0;
        return displayWeight * weightUnit.gramsPerUnit;
    }

    /**
     * Get nisab information from the results panel
     * @returns {Object} Nisab basis and threshold
     */
    function getNisabInfo() {
        const thresholdLabel = document.getElementById('nisabThresholdLabel');
        const thresholdValue = document.getElementById('nisabThreshold');

        let basis = 'Gold (85g)';
        if (thresholdLabel && thresholdLabel.textContent.toLowerCase().includes('silver')) {
            basis = 'Silver (595g)';
        }

        return {
            basis: basis,
            threshold: thresholdValue ? thresholdValue.textContent : '$0.00'
        };
    }

    /**
     * Get totals from the results panel
     * @returns {Object} All totals
     */
    function getTotals() {
        return {
            gold: getElementText('goldTotal'),
            metals: getElementText('metalTotal'),
            cash: getElementText('cashTotal'),
            bank: getElementText('bankTotal'),
            crypto: getElementText('cryptoTotal'),
            grandTotal: getElementText('grandTotal'),
            zakatDue: getElementText('zakatDue')
        };
    }

    /**
     * Get text content of an element by ID
     * @param {string} id - Element ID
     * @returns {string} Text content
     */
    function getElementText(id) {
        const el = document.getElementById(id);
        return el ? el.textContent : '$0.00';
    }

    /**
     * Collect gold assets from the form
     * @param {string} baseCurrency - Base currency code
     * @returns {Array} Array of asset rows
     */
    function collectGoldAssets(baseCurrency) {
        const rows = [];
        const goldItems = document.querySelectorAll('#goldItems .asset-row');

        goldItems.forEach(row => {
            const name = row.querySelector('[name="gold_name"]')?.value || '';
            const displayWeight = row.querySelector('[name="gold_weight"]')?.value || '';
            const rowUnitCode = row.querySelector('[name="gold_weight_unit"]')?.value || 'g';
            const rowUnit = getRowWeightUnit(rowUnitCode);
            const karat = row.querySelector('[name="gold_karat"]')?.value || '22';

            if (displayWeight && parseFloat(displayWeight) > 0) {
                const purity = parseInt(karat) / 24;
                const goldPrice = getMetalPriceFromSnapshot('gold');
                // Convert display weight to grams for calculation
                const weightGrams = toGrams(parseFloat(displayWeight), rowUnit);
                const value = weightGrams * purity * goldPrice;

                // Show weight in current unit with grams in notes
                const gramsNote = rowUnit.code !== 'g'
                    ? '(' + formatNumber(weightGrams) + 'g), Purity: ' + (purity * 100).toFixed(1) + '%'
                    : 'Purity: ' + (purity * 100).toFixed(1) + '%';

                rows.push([
                    'Gold',
                    name || 'Gold Item',
                    rowUnit.short,
                    displayWeight,
                    karat + 'K Gold',
                    formatNumber(goldPrice * purity),
                    formatNumber(value),
                    gramsNote
                ]);
            }
        });

        return rows;
    }

    /**
     * Collect other metal assets from the form
     * @param {string} baseCurrency - Base currency code
     * @returns {Array} Array of asset rows
     */
    function collectMetalAssets(baseCurrency) {
        const rows = [];
        const metalItems = document.querySelectorAll('#metalItems .asset-row');

        metalItems.forEach(row => {
            const name = row.querySelector('[name="metal_name"]')?.value || '';
            const displayWeight = row.querySelector('[name="metal_weight"]')?.value || '';
            const rowUnitCode = row.querySelector('[name="metal_weight_unit"]')?.value || 'g';
            const rowUnit = getRowWeightUnit(rowUnitCode);
            const metalType = row.querySelector('[name="metal_type"]')?.value || 'silver';

            if (displayWeight && parseFloat(displayWeight) > 0) {
                const metalPrice = getMetalPriceFromSnapshot(metalType);
                // Convert display weight to grams for calculation
                const weightGrams = toGrams(parseFloat(displayWeight), rowUnit);
                const value = weightGrams * metalPrice;

                // Show grams in notes if not using grams
                const gramsNote = rowUnit.code !== 'g'
                    ? '(' + formatNumber(weightGrams) + 'g)'
                    : '';

                rows.push([
                    'Other Metals',
                    name || metalType.charAt(0).toUpperCase() + metalType.slice(1),
                    rowUnit.short,
                    displayWeight,
                    metalType.charAt(0).toUpperCase() + metalType.slice(1),
                    formatNumber(metalPrice),
                    formatNumber(value),
                    gramsNote
                ]);
            }
        });

        return rows;
    }

    /**
     * Collect cash assets from the form
     * @param {string} baseCurrency - Base currency code
     * @returns {Array} Array of asset rows
     */
    function collectCashAssets(baseCurrency) {
        const rows = [];
        const cashItems = document.querySelectorAll('#cashItems .asset-row');

        cashItems.forEach(row => {
            const name = row.querySelector('[name="cash_name"]')?.value || '';
            const amount = row.querySelector('[name="cash_amount"]')?.value || '';
            const currencyContainer = row.querySelector('.currency-autocomplete');
            let currency = 'USD';
            if (currencyContainer && currencyContainer._autocomplete) {
                currency = currencyContainer._autocomplete.getValue() || 'USD';
            }

            if (amount && parseFloat(amount) > 0) {
                const rate = getCurrencyRate(currency, baseCurrency);
                const value = parseFloat(amount) * rate;

                rows.push([
                    'Cash',
                    name || 'Cash',
                    currency,
                    amount,
                    currency + '/' + baseCurrency,
                    formatNumber(rate),
                    formatNumber(value),
                    currency === baseCurrency ? 'Base currency' : ''
                ]);
            }
        });

        return rows;
    }

    /**
     * Collect bank assets from the form
     * @param {string} baseCurrency - Base currency code
     * @returns {Array} Array of asset rows
     */
    function collectBankAssets(baseCurrency) {
        const rows = [];
        const bankItems = document.querySelectorAll('#bankItems .asset-row');

        bankItems.forEach(row => {
            const name = row.querySelector('[name="bank_name"]')?.value || '';
            const amount = row.querySelector('[name="bank_amount"]')?.value || '';
            const currencyContainer = row.querySelector('.currency-autocomplete');
            let currency = 'USD';
            if (currencyContainer && currencyContainer._autocomplete) {
                currency = currencyContainer._autocomplete.getValue() || 'USD';
            }

            if (amount && parseFloat(amount) > 0) {
                const rate = getCurrencyRate(currency, baseCurrency);
                const value = parseFloat(amount) * rate;

                rows.push([
                    'Bank Account',
                    name || 'Bank Account',
                    currency,
                    amount,
                    currency + '/' + baseCurrency,
                    formatNumber(rate),
                    formatNumber(value),
                    currency === baseCurrency ? 'Base currency' : ''
                ]);
            }
        });

        return rows;
    }

    /**
     * Collect crypto assets from the form
     * @param {string} baseCurrency - Base currency code
     * @returns {Array} Array of asset rows
     */
    function collectCryptoAssets(baseCurrency) {
        const rows = [];
        const cryptoItems = document.querySelectorAll('#cryptoItems .asset-row');

        cryptoItems.forEach(row => {
            const name = row.querySelector('[name="crypto_name"]')?.value || '';
            const amount = row.querySelector('[name="crypto_amount"]')?.value || '';
            const symbolContainer = row.querySelector('.crypto-autocomplete');
            let symbol = 'BTC';
            if (symbolContainer && symbolContainer._autocomplete) {
                symbol = symbolContainer._autocomplete.getValue() || 'BTC';
            }

            if (amount && parseFloat(amount) > 0) {
                const price = getCryptoPrice(symbol);
                const value = parseFloat(amount) * price;

                rows.push([
                    'Cryptocurrency',
                    name || symbol,
                    symbol,
                    amount,
                    symbol + '/' + baseCurrency,
                    formatNumber(price),
                    formatNumber(value),
                    ''
                ]);
            }
        });

        return rows;
    }

    /**
     * Get metal price from global pricing snapshot
     * @param {string} metal - Metal type
     * @returns {number} Price per gram
     */
    function getMetalPriceFromSnapshot(metal) {
        // Access global pricingSnapshot from calculator.js
        if (typeof pricingSnapshot !== 'undefined' && pricingSnapshot?.metals) {
            const metalInfo = pricingSnapshot.metals[metal];
            if (metalInfo && metalInfo.price_per_gram) {
                return metalInfo.price_per_gram;
            }
        }
        // Fallback prices
        const fallbacks = { gold: 85, silver: 1.05, platinum: 32, palladium: 32 };
        return fallbacks[metal] || 0;
    }

    /**
     * Get currency exchange rate
     * @param {string} from - Source currency
     * @param {string} to - Target currency
     * @returns {number} Exchange rate
     */
    function getCurrencyRate(from, to) {
        if (from === to) return 1;

        if (typeof pricingSnapshot !== 'undefined' && pricingSnapshot?.currencies) {
            // Rates are relative to base currency (USD typically)
            const fromRate = pricingSnapshot.currencies[from]?.rate || 1;
            const toRate = pricingSnapshot.currencies[to]?.rate || 1;
            // Convert: from -> USD -> to
            return (1 / fromRate) * toRate;
        }
        return 1;
    }

    /**
     * Get crypto price from global pricing snapshot
     * @param {string} symbol - Crypto symbol
     * @returns {number} Price in base currency
     */
    function getCryptoPrice(symbol) {
        if (typeof pricingSnapshot !== 'undefined' && pricingSnapshot?.crypto) {
            const cryptoInfo = pricingSnapshot.crypto[symbol];
            if (cryptoInfo && cryptoInfo.price) {
                return cryptoInfo.price;
            }
        }
        return 0;
    }

    /**
     * Format a number for display
     * @param {number} value - Value to format
     * @returns {string} Formatted number
     */
    function formatNumber(value) {
        if (typeof value !== 'number' || isNaN(value)) {
            return '0.00';
        }
        return value.toFixed(2);
    }

    function getLocalDateISO() {
        const now = new Date();
        const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
        return local.toISOString().slice(0, 10);
    }

    /**
     * Download CSV content as a file
     * @param {string} csvContent - CSV string
     */
    function downloadCsv(csvContent) {
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');

        const date = getLocalDateISO();
        link.setAttribute('href', url);
        link.setAttribute('download', 'zakat-calculation-' + date + '.csv');
        link.style.visibility = 'hidden';

        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        URL.revokeObjectURL(url);
    }

    /**
     * Show a notification toast
     * @param {string} message - Message to display
     * @param {string} type - 'success' or 'error'
     */
    function showNotification(message, type) {
        // Remove any existing notification
        const existing = document.querySelector('.tools-notification');
        if (existing) {
            existing.remove();
        }

        const notification = document.createElement('div');
        notification.className = 'tools-notification tools-notification-' + type;
        notification.textContent = message;
        document.body.appendChild(notification);

        // Trigger animation
        requestAnimationFrame(() => {
            notification.classList.add('visible');
        });

        // Auto-hide after 3 seconds
        setTimeout(() => {
            notification.classList.remove('visible');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // Public API
    return {
        init: init
    };
})();
