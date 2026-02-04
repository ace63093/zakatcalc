/**
 * Nisab Indicator Component
 *
 * Displays the nisab threshold progress with gold/silver toggle.
 * Shows visual progress bar and status text indicating how close
 * the user's zakatable wealth is to the nisab threshold.
 */

var NisabIndicator = (function() {
    'use strict';

    // Constants
    var NISAB_GOLD_GRAMS = 85;
    var NISAB_SILVER_GRAMS = 595;

    // Private state
    var container = null;
    var nisabBasis = 'gold';
    var nisabData = null;
    var baseCurrency = 'CAD';
    var onBasisChange = null;
    var hasAnimated = false;  // Track if initial animation has played
    var ratesExpanded = false;  // Track rates section state
    var currentRates = null;  // Store current conversion rates

    // Currency symbols for fallback display
    var CURRENCY_SYMBOLS = {
        CAD: 'C$', USD: '$', EUR: '\u20AC', GBP: '\u00A3', JPY: '\u00A5',
        AUD: 'A$', CHF: 'CHF', CNY: '\u00A5', INR: '\u20B9', BDT: '\u09F3'
    };
    var MONEY_FORMATTERS = {};

    /**
     * Initialize the nisab indicator
     * @param {string} containerId - ID of the container element
     * @param {Object} options - Configuration options
     * @param {string} options.basis - Initial basis ('gold' or 'silver')
     * @param {string} options.baseCurrency - Currency code for formatting
     * @param {Function} options.onBasisChange - Callback when basis changes
     */
    function init(containerId, options) {
        container = document.getElementById(containerId);
        if (!container) {
            console.warn('NisabIndicator: Container not found:', containerId);
            return;
        }

        options = options || {};
        nisabBasis = options.basis || 'gold';
        baseCurrency = options.baseCurrency || 'CAD';
        onBasisChange = options.onBasisChange || null;
        hasAnimated = false;  // Reset animation flag on init

        render();
        bindEvents();
    }

    /**
     * Set the nisab basis (gold or silver)
     * @param {string} basis - 'gold' or 'silver'
     */
    function setBasis(basis) {
        if (basis !== 'gold' && basis !== 'silver') {
            basis = 'gold';
        }
        nisabBasis = basis;

        // Update toggle button states
        updateToggleButtons();

        // Trigger callback if provided
        if (onBasisChange) {
            onBasisChange(nisabBasis);
        }
    }

    /**
     * Get the current nisab basis
     * @returns {string} 'gold' or 'silver'
     */
    function getBasis() {
        return nisabBasis;
    }

    /**
     * Update the indicator with new nisab data from API response
     * @param {Object} data - Nisab data from API response
     * @param {string} currency - Base currency code
     */
    function update(data, currency) {
        if (!data) return;

        nisabData = data;
        if (currency) {
            baseCurrency = currency;
        }
        if (data.basis_used) {
            nisabBasis = data.basis_used;
        }

        updateDisplay();
    }

    /**
     * Set the base currency for formatting
     * @param {string} currency - Currency code
     */
    function setBaseCurrency(currency) {
        baseCurrency = currency;
        if (nisabData) {
            updateDisplay();
        }
    }

    /**
     * Render the component structure
     */
    function render() {
        if (!container) return;

        container.innerHTML = [
            '<div class="nisab-indicator">',
            '  <h3>',
            '    <span>Nisab Threshold</span>',
            '    <div class="nisab-toggle-group" role="group" aria-label="Nisab basis selection">',
            '      <button type="button" class="nisab-toggle-btn' + (nisabBasis === 'gold' ? ' active' : '') + '" ',
            '              data-basis="gold" aria-pressed="' + (nisabBasis === 'gold') + '">',
            '        Gold (' + NISAB_GOLD_GRAMS + 'g)',
            '      </button>',
            '      <button type="button" class="nisab-toggle-btn' + (nisabBasis === 'silver' ? ' active' : '') + '" ',
            '              data-basis="silver" aria-pressed="' + (nisabBasis === 'silver') + '">',
            '        Silver (' + NISAB_SILVER_GRAMS + 'g)',
            '      </button>',
            '    </div>',
            '  </h3>',
            '  <div class="nisab-progress-container">',
            '    <div class="nisab-progress-bar">',
            '      <div class="nisab-progress-fill status-below" style="width: 0%"></div>',
            '    </div>',
            '    <div class="nisab-progress-labels">',
            '      <span class="current-amount">--</span>',
            '      <span class="threshold-amount">--</span>',
            '    </div>',
            '  </div>',
            '  <div class="nisab-status status-below">',
            '    <span class="nisab-status-icon"></span>',
            '    <div class="nisab-status-text">',
            '      <span class="difference">--</span>',
            '      <span class="description">Enter your assets to calculate</span>',
            '    </div>',
            '  </div>',
            '  <div class="nisab-threshold-info">',
            '    <span>Threshold: </span>',
            '    <span class="threshold-value">--</span>',
            '    <span class="effective-date"></span>',
            '    <button type="button" class="nisab-rates-toggle" aria-expanded="false">',
            '      <span class="nisab-rates-toggle-icon">&#9654;</span>',
            '      <span>View conversion rates</span>',
            '    </button>',
            '    <div class="nisab-rates-content" aria-hidden="true">',
            '      <ul class="nisab-rates-list"></ul>',
            '    </div>',
            '  </div>',
            '</div>'
        ].join('\n');
    }

    /**
     * Bind event listeners
     */
    function bindEvents() {
        if (!container) return;

        container.addEventListener('click', function(event) {
            var btn = event.target.closest('.nisab-toggle-btn');
            if (btn) {
                var basis = btn.dataset.basis;
                setBasis(basis);
                return;
            }

            var ratesToggle = event.target.closest('.nisab-rates-toggle');
            if (ratesToggle) {
                toggleRatesSection();
            }
        });
    }

    /**
     * Toggle the rates section expanded/collapsed state
     */
    function toggleRatesSection() {
        if (!container) return;

        ratesExpanded = !ratesExpanded;

        var toggle = container.querySelector('.nisab-rates-toggle');
        var content = container.querySelector('.nisab-rates-content');

        if (toggle) {
            toggle.classList.toggle('expanded', ratesExpanded);
            toggle.setAttribute('aria-expanded', ratesExpanded);
        }

        if (content) {
            content.classList.toggle('show', ratesExpanded);
            content.setAttribute('aria-hidden', !ratesExpanded);
        }
    }

    /**
     * Update toggle button visual states
     */
    function updateToggleButtons() {
        if (!container) return;

        var buttons = container.querySelectorAll('.nisab-toggle-btn');
        buttons.forEach(function(btn) {
            var isActive = btn.dataset.basis === nisabBasis;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', isActive);
        });
    }

    /**
     * Update the display with current nisab data
     */
    function updateDisplay() {
        if (!container || !nisabData) return;

        var ratio = nisabData.ratio || 0;
        var status = nisabData.status || 'below';
        var difference = nisabData.difference || 0;
        var differenceText = nisabData.difference_text || '';
        var thresholdUsed = nisabData.threshold_used || 0;

        // Update progress bar
        var progressFill = container.querySelector('.nisab-progress-fill');
        if (progressFill) {
            var percentage = Math.min(ratio * 100, 100);
            progressFill.style.width = percentage + '%';
            progressFill.className = 'nisab-progress-fill status-' + status;

            // Only trigger fill animation on initial load, not on every update
            // Subsequent updates use CSS transition for smooth progress
            if (!hasAnimated) {
                hasAnimated = true;
                progressFill.classList.remove('animate');
                void progressFill.offsetWidth; // Force reflow
                progressFill.classList.add('animate');
            }
        }

        // Update progress labels
        var currentAmount = container.querySelector('.current-amount');
        var thresholdAmount = container.querySelector('.threshold-amount');
        if (currentAmount) {
            // Calculate current amount from ratio and threshold
            var current = thresholdUsed * ratio;
            currentAmount.textContent = formatCurrency(current);
        }
        if (thresholdAmount) {
            thresholdAmount.textContent = formatCurrency(thresholdUsed);
        }

        // Update status section
        var statusContainer = container.querySelector('.nisab-status');
        if (statusContainer) {
            statusContainer.className = 'nisab-status status-' + status;
        }

        var statusIcon = container.querySelector('.nisab-status-icon');
        if (statusIcon) {
            if (status === 'above') {
                statusIcon.textContent = '\u2713'; // checkmark
            } else if (status === 'near') {
                statusIcon.textContent = '!';
            } else {
                statusIcon.textContent = '-';
            }
        }

        var differenceElem = container.querySelector('.nisab-status-text .difference');
        if (differenceElem) {
            differenceElem.textContent = formatCurrency(difference);
        }

        var descriptionElem = container.querySelector('.nisab-status-text .description');
        if (descriptionElem) {
            if (status === 'above') {
                descriptionElem.textContent = 'above nisab - Zakat is due';
            } else if (status === 'near') {
                descriptionElem.textContent = 'more to reach nisab (almost there!)';
            } else {
                descriptionElem.textContent = 'more to reach nisab';
            }
        }

        // Update threshold info
        var thresholdValue = container.querySelector('.threshold-value');
        if (thresholdValue) {
            var basisLabel = nisabBasis === 'gold'
                ? NISAB_GOLD_GRAMS + 'g gold'
                : NISAB_SILVER_GRAMS + 'g silver';
            thresholdValue.textContent = formatCurrency(thresholdUsed) + ' (' + basisLabel + ')';
        }

        // Update toggle buttons to reflect current basis
        updateToggleButtons();
    }

    /**
     * Set the effective date display
     * @param {string} dateStr - ISO date string
     */
    function setEffectiveDate(dateStr) {
        if (!container) return;

        var effectiveDateElem = container.querySelector('.effective-date');
        if (effectiveDateElem && dateStr) {
            effectiveDateElem.textContent = 'Prices as of ' + dateStr;
        }
    }

    /**
     * Set conversion rates for display
     * @param {Object} rates - Rates data
     * @param {string} rates.baseCurrency - Base currency code
     * @param {Object} rates.metals - Metal prices { gold: { price_per_gram: 95 }, ... }
     * @param {Object} rates.fx - FX rates { USD: 1.35, EUR: 1.48 }
     * @param {Object} rates.crypto - Crypto prices { BTC: { price: 92000, name: 'Bitcoin' }, ... }
     */
    function setConversionRates(rates) {
        if (!container) return;

        currentRates = rates;
        renderRatesList();
    }

    /**
     * Render the rates list based on currentRates
     */
    function renderRatesList() {
        if (!container || !currentRates) return;

        var list = container.querySelector('.nisab-rates-list');
        if (!list) return;

        var items = [];
        var base = currentRates.baseCurrency || baseCurrency;

        // Add metal rates
        if (currentRates.metals) {
            Object.keys(currentRates.metals).forEach(function(metal) {
                var info = currentRates.metals[metal];
                if (info && info.price_per_gram > 0) {
                    var metalName = metal.charAt(0).toUpperCase() + metal.slice(1);
                    var priceStr = formatCurrency(info.price_per_gram) + '/g';
                    items.push({
                        label: metalName,
                        value: priceStr,
                        order: metal === 'gold' ? 0 : metal === 'silver' ? 1 : 2
                    });
                }
            });
        }

        // Add FX rates (flip if < 1 for readability)
        if (currentRates.fx) {
            Object.keys(currentRates.fx).forEach(function(currency) {
                var rate = currentRates.fx[currency];
                if (rate && rate > 0) {
                    var label, value;
                    if (rate >= 1) {
                        // 1 foreign = X base (e.g., 1 USD → 1.35 CAD)
                        label = '1 ' + currency;
                        value = formatRate(rate) + ' ' + base;
                    } else {
                        // Flip: 1 base = X foreign (e.g., 1 CAD = 0.74 USD becomes 1 USD → 1.35 CAD)
                        var flipped = 1 / rate;
                        label = '1 ' + base;
                        value = formatRate(flipped) + ' ' + currency;
                    }
                    items.push({
                        label: label,
                        value: value,
                        order: 10
                    });
                }
            });
        }

        // Add crypto rates
        if (currentRates.crypto) {
            Object.keys(currentRates.crypto).forEach(function(symbol) {
                var info = currentRates.crypto[symbol];
                if (info && info.price > 0) {
                    items.push({
                        label: symbol,
                        value: formatCurrency(info.price),
                        order: 20
                    });
                }
            });
        }

        // Sort by order then alphabetically
        items.sort(function(a, b) {
            if (a.order !== b.order) return a.order - b.order;
            return a.label.localeCompare(b.label);
        });

        // Render
        if (items.length === 0) {
            list.innerHTML = '<li class="nisab-rates-empty">No conversion rates to display.<br>Please input amounts in alternate currencies to display conversion rates.</li>';
        } else {
            list.innerHTML = items.map(function(item) {
                return '<li><span class="nisab-rate-label">' + item.label + '</span><span class="nisab-rate-value">' + item.value + '</span></li>';
            }).join('');
        }
    }

    /**
     * Format a rate number for display
     * @param {number} rate - The rate value
     * @returns {string} Formatted rate
     */
    function formatRate(rate) {
        if (rate >= 100) {
            return rate.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        } else if (rate >= 1) {
            return rate.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
        } else {
            return rate.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 });
        }
    }

    /**
     * Format a number as currency
     * @param {number} amount - Amount to format
     * @returns {string} Formatted currency string
     */
    function formatCurrency(amount) {
        if (amount === undefined || amount === null || isNaN(amount)) {
            return '--';
        }

        if (!MONEY_FORMATTERS[baseCurrency]) {
            try {
                MONEY_FORMATTERS[baseCurrency] = new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: baseCurrency,
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            } catch (error) {
                MONEY_FORMATTERS[baseCurrency] = null;
            }
        }

        if (MONEY_FORMATTERS[baseCurrency]) {
            return MONEY_FORMATTERS[baseCurrency].format(amount);
        }

        var symbol = CURRENCY_SYMBOLS[baseCurrency] || baseCurrency + ' ';
        return symbol + amount.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    // Public API
    return {
        init: init,
        setBasis: setBasis,
        getBasis: getBasis,
        update: update,
        setBaseCurrency: setBaseCurrency,
        setEffectiveDate: setEffectiveDate,
        setConversionRates: setConversionRates,
        render: render
    };
})();
