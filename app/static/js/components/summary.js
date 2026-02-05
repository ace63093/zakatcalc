/**
 * Summary Page Component
 *
 * Loads calculation state from URL fragment and renders a printable summary.
 * Data stays client-side (not sent to server) for privacy.
 */

var ZakatSummary = (function() {
    'use strict';

    var HASH_PREFIX = '#data=';
    var state = null;
    var baseCurrency = 'CAD';

    // Currency symbols for display
    var CURRENCY_SYMBOLS = {
        CAD: 'C$', USD: '$', EUR: '\u20AC', GBP: '\u00A3', JPY: '\u00A5',
        AUD: 'A$', CHF: 'CHF', CNY: '\u00A5', INR: '\u20B9', BDT: '\u09F3'
    };

    /**
     * Initialize the summary page
     */
    function init() {
        var result = parseStateFromUrl();

        if (!result) {
            showError('No calculation data found in URL.');
            return;
        }

        if (result.error) {
            showError(result.message);
            return;
        }

        state = result.data;
        baseCurrency = state.base_currency || 'CAD';

        renderSummary();
    }

    /**
     * Parse state from URL hash
     */
    function parseStateFromUrl() {
        var hash = window.location.hash;

        if (!hash || !hash.startsWith(HASH_PREFIX)) {
            return null;
        }

        if (typeof LZString === 'undefined') {
            return { error: true, message: 'Compression library not loaded.' };
        }

        var compressed = hash.substring(HASH_PREFIX.length);
        if (!compressed) {
            return null;
        }

        try {
            var json = LZString.decompressFromEncodedURIComponent(compressed);
            if (!json) {
                return { error: true, message: 'Invalid data in URL.' };
            }

            var payload = JSON.parse(json);

            if (!payload || !payload.data) {
                return { error: true, message: 'Invalid data format.' };
            }

            return { data: payload.data };
        } catch (e) {
            console.error('Failed to parse summary data:', e);
            return { error: true, message: 'Unable to decode calculation data.' };
        }
    }

    /**
     * Show error state
     */
    function showError(message) {
        document.getElementById('summaryLoading').style.display = 'none';
        document.getElementById('summaryContent').style.display = 'none';
        document.getElementById('summaryError').style.display = 'block';
        document.getElementById('summaryErrorMessage').textContent = message;
    }

    /**
     * Format currency value
     */
    function formatMoney(value, currency) {
        currency = currency || baseCurrency;
        var symbol = CURRENCY_SYMBOLS[currency] || currency + ' ';
        var num = parseFloat(value) || 0;
        return symbol + num.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHtml(text) {
        if (typeof ZakatUtils !== 'undefined' && ZakatUtils.escapeHtml) {
            return ZakatUtils.escapeHtml(text);
        }
        var div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    /**
     * Render the full summary
     */
    function renderSummary() {
        // Set metadata
        document.getElementById('summaryCalcDate').textContent = state.calculation_date || 'Today';
        document.getElementById('summaryBaseCurrency').textContent = baseCurrency;
        document.getElementById('generatedTime').textContent = new Date().toLocaleString();

        // Render asset sections
        renderGoldItems();
        renderMetalItems();
        renderCashItems();
        renderBankItems();
        renderCryptoItems();

        // Render advanced assets if present
        if (state.advanced_mode) {
            renderStockItems();
            renderRetirementItems();
            renderReceivableItems();
            renderBusinessInventory();
            renderPropertyItems();
        }

        // Render debts
        var hasDebts = renderCreditCardItems() || renderLoanItems();
        if (state.advanced_mode) {
            hasDebts = renderPayableItems() || hasDebts;
        }

        if (hasDebts) {
            document.getElementById('debtsSection').style.display = 'block';
        }

        // Calculate totals and render calculation section
        renderCalculationSummary();

        // Show content
        document.getElementById('summaryLoading').style.display = 'none';
        document.getElementById('summaryContent').style.display = 'block';
    }

    /**
     * Render gold items
     */
    function renderGoldItems() {
        var items = (state.gold_items || []).filter(function(i) {
            return i.weight_grams > 0 || i.weight > 0;
        });
        if (items.length === 0) return;

        var tbody = document.getElementById('goldItemsBody');
        var total = 0;

        items.forEach(function(item) {
            var weight = item.weight_grams || (item.weight * (ZakatUtils.WEIGHT_UNITS[item.weight_unit || 'g']?.gramsPerUnit || 1));
            var tr = document.createElement('tr');
            tr.innerHTML = [
                '<td>' + escapeHtml(item.name || 'Gold') + '</td>',
                '<td>' + weight.toFixed(2) + ' g</td>',
                '<td>' + (item.purity_karat || 22) + 'K</td>',
                '<td class="col-value">—</td>'
            ].join('');
            tbody.appendChild(tr);
        });

        document.getElementById('goldAssets').style.display = 'block';
    }

    /**
     * Render metal items
     */
    function renderMetalItems() {
        var items = (state.metal_items || []).filter(function(i) {
            return i.weight_grams > 0 || i.weight > 0;
        });
        if (items.length === 0) return;

        var tbody = document.getElementById('metalItemsBody');

        items.forEach(function(item) {
            var weight = item.weight_grams || (item.weight * (ZakatUtils.WEIGHT_UNITS[item.weight_unit || 'g']?.gramsPerUnit || 1));
            var tr = document.createElement('tr');
            tr.innerHTML = [
                '<td>' + escapeHtml(item.name || 'Metal') + '</td>',
                '<td>' + escapeHtml(item.metal || 'silver') + '</td>',
                '<td>' + weight.toFixed(2) + ' g</td>',
                '<td class="col-value">—</td>'
            ].join('');
            tbody.appendChild(tr);
        });

        document.getElementById('metalAssets').style.display = 'block';
    }

    /**
     * Render cash items
     */
    function renderCashItems() {
        var items = (state.cash_items || []).filter(function(i) {
            return i.amount > 0;
        });
        if (items.length === 0) return;

        var tbody = document.getElementById('cashItemsBody');

        items.forEach(function(item) {
            var tr = document.createElement('tr');
            tr.innerHTML = [
                '<td>' + escapeHtml(item.name || 'Cash') + '</td>',
                '<td>' + formatMoney(item.amount, item.currency) + '</td>',
                '<td class="col-value">—</td>'
            ].join('');
            tbody.appendChild(tr);
        });

        document.getElementById('cashAssets').style.display = 'block';
    }

    /**
     * Render bank items
     */
    function renderBankItems() {
        var items = (state.bank_items || []).filter(function(i) {
            return i.amount > 0;
        });
        if (items.length === 0) return;

        var tbody = document.getElementById('bankItemsBody');

        items.forEach(function(item) {
            var tr = document.createElement('tr');
            tr.innerHTML = [
                '<td>' + escapeHtml(item.name || 'Bank Account') + '</td>',
                '<td>' + formatMoney(item.amount, item.currency) + '</td>',
                '<td class="col-value">—</td>'
            ].join('');
            tbody.appendChild(tr);
        });

        document.getElementById('bankAssets').style.display = 'block';
    }

    /**
     * Render crypto items
     */
    function renderCryptoItems() {
        var items = (state.crypto_items || []).filter(function(i) {
            return i.amount > 0 && i.symbol;
        });
        if (items.length === 0) return;

        var tbody = document.getElementById('cryptoItemsBody');

        items.forEach(function(item) {
            var tr = document.createElement('tr');
            tr.innerHTML = [
                '<td>' + escapeHtml(item.name || item.symbol) + '</td>',
                '<td>' + escapeHtml(item.symbol) + '</td>',
                '<td>' + item.amount + '</td>',
                '<td class="col-value">—</td>'
            ].join('');
            tbody.appendChild(tr);
        });

        document.getElementById('cryptoAssets').style.display = 'block';
    }

    /**
     * Render stock items
     */
    function renderStockItems() {
        var items = (state.stock_items || []).filter(function(i) {
            return i.value > 0;
        });
        if (items.length === 0) return;

        var tbody = document.getElementById('stockItemsBody');

        items.forEach(function(item) {
            var methodLabel = item.method === 'zakatable_portion' ? '30% Only' : 'Full Value';
            var tr = document.createElement('tr');
            tr.innerHTML = [
                '<td>' + escapeHtml(item.name || 'Stock') + '</td>',
                '<td>' + methodLabel + '</td>',
                '<td class="col-value">' + formatMoney(item.value, item.currency) + '</td>'
            ].join('');
            tbody.appendChild(tr);
        });

        document.getElementById('stockAssets').style.display = 'block';
    }

    /**
     * Render retirement items
     */
    function renderRetirementItems() {
        var items = (state.retirement_items || []).filter(function(i) {
            return i.balance > 0;
        });
        if (items.length === 0) return;

        var tbody = document.getElementById('retirementItemsBody');

        var methodLabels = {
            'accessible_only': 'If Accessible',
            'full_balance': 'Full Balance',
            'penalty_adjusted': 'After 10% Penalty'
        };

        items.forEach(function(item) {
            var methodLabel = methodLabels[item.method] || item.method;
            var tr = document.createElement('tr');
            tr.innerHTML = [
                '<td>' + escapeHtml(item.name || 'Retirement') + '</td>',
                '<td>' + methodLabel + '</td>',
                '<td class="col-value">' + formatMoney(item.balance, item.currency) + '</td>'
            ].join('');
            tbody.appendChild(tr);
        });

        document.getElementById('retirementAssets').style.display = 'block';
    }

    /**
     * Render receivable items
     */
    function renderReceivableItems() {
        var items = (state.receivable_items || []).filter(function(i) {
            return i.amount > 0;
        });
        if (items.length === 0) return;

        var tbody = document.getElementById('receivableItemsBody');

        items.forEach(function(item) {
            var tr = document.createElement('tr');
            tr.innerHTML = [
                '<td>' + escapeHtml(item.name || 'Receivable') + '</td>',
                '<td>' + escapeHtml(item.likelihood || 'likely') + '</td>',
                '<td class="col-value">' + formatMoney(item.amount, item.currency) + '</td>'
            ].join('');
            tbody.appendChild(tr);
        });

        document.getElementById('receivableAssets').style.display = 'block';
    }

    /**
     * Render business inventory
     */
    function renderBusinessInventory() {
        var business = state.business_inventory;
        if (!business) return;

        var hasValue = (business.resale_value > 0 || business.business_cash > 0 ||
                       business.receivables > 0 || business.payables > 0);
        if (!hasValue) return;

        var tbody = document.getElementById('businessItemsBody');

        var rows = [
            ['Business Name', escapeHtml(business.name || 'Business')],
            ['Inventory Resale Value', formatMoney(business.resale_value, business.currency)],
            ['Business Cash', formatMoney(business.business_cash, business.currency)],
            ['Business Receivables', formatMoney(business.receivables, business.currency)],
            ['Business Payables', '−' + formatMoney(business.payables, business.currency)]
        ];

        rows.forEach(function(row) {
            var tr = document.createElement('tr');
            tr.innerHTML = '<td>' + row[0] + '</td><td class="col-value">' + row[1] + '</td>';
            tbody.appendChild(tr);
        });

        document.getElementById('businessAssets').style.display = 'block';
    }

    /**
     * Render property items
     */
    function renderPropertyItems() {
        var items = (state.investment_property || []).filter(function(i) {
            return i.market_value > 0 || i.rental_income > 0;
        });
        if (items.length === 0) return;

        var tbody = document.getElementById('propertyItemsBody');

        items.forEach(function(item) {
            var intentLabel = item.intent === 'resale' ? 'For Resale' : 'Rental Income';
            var value = item.intent === 'resale' ? item.market_value : item.rental_income;
            var tr = document.createElement('tr');
            tr.innerHTML = [
                '<td>' + escapeHtml(item.name || 'Property') + '</td>',
                '<td>' + intentLabel + '</td>',
                '<td class="col-value">' + formatMoney(value, item.currency) + '</td>'
            ].join('');
            tbody.appendChild(tr);
        });

        document.getElementById('propertyAssets').style.display = 'block';
    }

    /**
     * Render credit card items
     */
    function renderCreditCardItems() {
        var items = (state.credit_card_items || []).filter(function(i) {
            return i.amount > 0;
        });
        if (items.length === 0) return false;

        var tbody = document.getElementById('creditCardItemsBody');

        items.forEach(function(item) {
            var tr = document.createElement('tr');
            tr.innerHTML = [
                '<td>' + escapeHtml(item.name || 'Credit Card') + '</td>',
                '<td>' + formatMoney(item.amount, item.currency) + '</td>',
                '<td class="col-value">—</td>'
            ].join('');
            tbody.appendChild(tr);
        });

        document.getElementById('creditCardDebts').style.display = 'block';
        return true;
    }

    /**
     * Render loan items
     */
    function renderLoanItems() {
        var items = (state.loan_items || []).filter(function(i) {
            return i.payment_amount > 0;
        });
        if (items.length === 0) return false;

        var tbody = document.getElementById('loanItemsBody');
        var multipliers = ZakatUtils.LOAN_FREQUENCY_MULTIPLIERS || {
            weekly: 52, biweekly: 26, semi_monthly: 24, monthly: 12, quarterly: 4, yearly: 1
        };

        items.forEach(function(item) {
            var annual = item.payment_amount * (multipliers[item.frequency] || 12);
            var tr = document.createElement('tr');
            tr.innerHTML = [
                '<td>' + escapeHtml(item.name || 'Loan') + '</td>',
                '<td>' + formatMoney(item.payment_amount, item.currency) + '</td>',
                '<td>' + escapeHtml(item.frequency || 'monthly') + '</td>',
                '<td class="col-value">' + formatMoney(annual, item.currency) + '</td>'
            ].join('');
            tbody.appendChild(tr);
        });

        document.getElementById('loanDebts').style.display = 'block';
        return true;
    }

    /**
     * Render payable items
     */
    function renderPayableItems() {
        var items = (state.short_term_payables || []).filter(function(i) {
            return i.amount > 0;
        });
        if (items.length === 0) return false;

        var tbody = document.getElementById('payableItemsBody');

        items.forEach(function(item) {
            var tr = document.createElement('tr');
            tr.innerHTML = [
                '<td>' + escapeHtml(item.name || 'Payable') + '</td>',
                '<td>' + escapeHtml(item.type || 'other') + '</td>',
                '<td class="col-value">' + formatMoney(item.amount, item.currency) + '</td>'
            ].join('');
            tbody.appendChild(tr);
        });

        document.getElementById('payableDebts').style.display = 'block';
        return true;
    }

    /**
     * Render the calculation summary section
     * Note: Actual values require pricing data - show placeholders
     */
    function renderCalculationSummary() {
        // Set nisab basis label
        var nisabLabel = state.nisab_basis === 'silver' ? 'Silver' : 'Gold';
        document.getElementById('nisabBasisLabel').textContent = nisabLabel;

        // We don't have pricing data here, so we show a note
        var placeholder = '(Requires live pricing)';
        document.getElementById('assetsGrandTotal').textContent = placeholder;
        document.getElementById('debtsGrandTotal').textContent = placeholder;
        document.getElementById('calcAssetsTotal').textContent = placeholder;
        document.getElementById('calcDebtsTotal').textContent = placeholder;
        document.getElementById('calcNetTotal').textContent = placeholder;
        document.getElementById('calcNisabThreshold').textContent = placeholder;
        document.getElementById('calcAboveNisab').textContent = '—';
        document.getElementById('calcZakatDue').textContent = placeholder;
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    // Public API
    return {
        init: init
    };
})();
