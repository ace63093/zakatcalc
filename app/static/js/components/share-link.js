/**
 * Share Link Component
 *
 * Generates shareable links with compressed calculator state.
 * Uses LZ-string for compression and URL fragment (#data=...) for privacy.
 *
 * Features:
 * - Privacy-conscious: data stays in fragment (not sent to server)
 * - Compressed with LZ-string for compact URLs
 * - Schema versioning for forward compatibility
 * - URL length warnings with PDF fallback suggestion
 */

var ShareLink = (function() {
    'use strict';

    // Constants
    var MAX_URL_LENGTH = 2000;
    var SCHEMA_VERSION = 2;  // v2 adds advanced assets, debt_policy, date_assistant
    var HASH_PREFIX = '#data=';

    // State
    var shareModal = null;
    var loadModal = null;
    var pendingState = null;

    /**
     * Initialize the share link component
     * Checks for share payload in URL on page load
     */
    function init() {
        createModals();
        checkForSharePayload();
    }

    /**
     * Create modal elements
     */
    function createModals() {
        // Share modal
        if (!document.getElementById('share-modal')) {
            var shareModalHtml = [
                '<div id="share-modal" class="share-modal" role="dialog" aria-modal="true" aria-labelledby="share-modal-title">',
                '  <div class="share-modal-backdrop"></div>',
                '  <div class="share-modal-content">',
                '    <div class="share-modal-header">',
                '      <h3 id="share-modal-title">Share Calculation</h3>',
                '      <button type="button" class="share-modal-close" aria-label="Close">&times;</button>',
                '    </div>',
                '    <div class="share-modal-body">',
                '      <div class="share-privacy-warning">',
                '        <span class="share-warning-icon">!</span>',
                '        <div class="share-warning-text">',
                '          <strong>Privacy Notice:</strong> This link contains your calculation data.',
                '          Anyone with this link can view your entered values.',
                '        </div>',
                '      </div>',
                '      <div class="share-url-container">',
                '        <label for="share-url-input">Shareable Link:</label>',
                '        <div class="share-url-row">',
                '          <input type="text" id="share-url-input" class="share-url-input" readonly>',
                '          <button type="button" id="share-copy-btn" class="share-copy-btn">Copy</button>',
                '        </div>',
                '      </div>',
                '      <div id="share-length-warning" class="share-length-warning" style="display: none;">',
                '        <span class="share-length-icon">!</span>',
                '        <div class="share-length-text">',
                '          <strong>Long URL Warning:</strong> This link is <span id="share-url-length"></span> characters.',
                '          Some platforms may truncate it. Consider using <strong>PDF export</strong> for reliable sharing.',
                '        </div>',
                '      </div>',
                '    </div>',
                '    <div class="share-modal-footer">',
                '      <button type="button" class="share-btn-secondary share-modal-cancel">Close</button>',
                '    </div>',
                '  </div>',
                '</div>'
            ].join('\n');

            var div = document.createElement('div');
            div.innerHTML = shareModalHtml;
            document.body.appendChild(div.firstElementChild);
        }

        // Load confirmation modal
        if (!document.getElementById('load-share-modal')) {
            var loadModalHtml = [
                '<div id="load-share-modal" class="share-modal" role="dialog" aria-modal="true" aria-labelledby="load-share-modal-title">',
                '  <div class="share-modal-backdrop"></div>',
                '  <div class="share-modal-content">',
                '    <div class="share-modal-header">',
                '      <h3 id="load-share-modal-title">Load Shared Calculation</h3>',
                '      <button type="button" class="share-modal-close" aria-label="Close">&times;</button>',
                '    </div>',
                '    <div class="share-modal-body">',
                '      <p class="share-load-message">A shared calculation was found in the link. Would you like to load it?</p>',
                '      <div id="share-load-preview" class="share-load-preview"></div>',
                '    </div>',
                '    <div class="share-modal-footer">',
                '      <button type="button" class="share-btn-secondary share-load-cancel">No, Keep Current</button>',
                '      <button type="button" class="share-btn-primary share-load-confirm">Yes, Load It</button>',
                '    </div>',
                '  </div>',
                '</div>'
            ].join('\n');

            var div = document.createElement('div');
            div.innerHTML = loadModalHtml;
            document.body.appendChild(div.firstElementChild);
        }

        shareModal = document.getElementById('share-modal');
        loadModal = document.getElementById('load-share-modal');

        bindModalEvents();
    }

    /**
     * Bind modal event listeners
     */
    function bindModalEvents() {
        // Share modal events
        if (shareModal) {
            shareModal.querySelector('.share-modal-backdrop').addEventListener('click', hideShareModal);
            shareModal.querySelector('.share-modal-close').addEventListener('click', hideShareModal);
            shareModal.querySelector('.share-modal-cancel').addEventListener('click', hideShareModal);
            shareModal.querySelector('#share-copy-btn').addEventListener('click', function() {
                var input = document.getElementById('share-url-input');
                copyToClipboard(input.value);
            });
        }

        // Load modal events
        if (loadModal) {
            loadModal.querySelector('.share-modal-backdrop').addEventListener('click', hideLoadModal);
            loadModal.querySelector('.share-modal-close').addEventListener('click', hideLoadModal);
            loadModal.querySelector('.share-load-cancel').addEventListener('click', function() {
                clearHash();
                hideLoadModal();
            });
            loadModal.querySelector('.share-load-confirm').addEventListener('click', function() {
                if (pendingState && typeof ZakatCalculator !== 'undefined') {
                    ZakatCalculator.setState(pendingState);
                    showNotification('Shared calculation loaded successfully.', 'success');
                }
                clearHash();
                hideLoadModal();
                pendingState = null;
            });
        }

        // Share button in tools section
        document.addEventListener('click', function(event) {
            var shareBtn = event.target.closest('#share-link-btn');
            if (shareBtn) {
                event.preventDefault();
                showShareModal();
            }

            // Print Summary button
            var printBtn = event.target.closest('#print-summary-btn');
            if (printBtn) {
                event.preventDefault();
                openPrintSummary();
            }
        });

        // Escape key to close modals
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                if (shareModal && shareModal.classList.contains('visible')) {
                    hideShareModal();
                }
                if (loadModal && loadModal.classList.contains('visible')) {
                    hideLoadModal();
                }
            }
        });
    }

    /**
     * Generate a shareable link from current calculator state
     * @returns {string} Complete URL with compressed data in fragment
     */
    function generateLink() {
        if (typeof ZakatCalculator === 'undefined') {
            console.error('ShareLink: ZakatCalculator not available');
            return null;
        }

        if (typeof LZString === 'undefined') {
            console.error('ShareLink: LZString not available');
            return null;
        }

        var state = ZakatCalculator.getState();
        var payload = {
            v: SCHEMA_VERSION,
            data: state
        };

        var json = JSON.stringify(payload);
        var compressed = LZString.compressToEncodedURIComponent(json);

        var baseUrl = window.location.origin + window.location.pathname;
        return baseUrl + HASH_PREFIX + compressed;
    }

    /**
     * Migrate v1 state to v2 format
     * v2 adds: stock_items, retirement_items, receivable_items, business_inventory,
     * investment_property, short_term_payables, debt_policy, include_uncertain_receivables,
     * advanced_mode
     * @param {Object} state - v1 state object
     * @returns {Object} v2 state object
     */
    function migrateV1toV2(state) {
        var hasCryptoData = (state.crypto_items || []).some(function(item) {
            var amount = parseFloat(item.amount) || 0;
            return amount > 0 && !!item.symbol;
        });

        return Object.assign({}, state, {
            // Advanced assets (all empty arrays/null by default)
            stock_items: state.stock_items || [],
            retirement_items: state.retirement_items || [],
            receivable_items: state.receivable_items || [],
            business_inventory: state.business_inventory || null,
            investment_property: state.investment_property || [],
            short_term_payables: state.short_term_payables || [],
            // Advanced mode settings
            debt_policy: state.debt_policy || '12_months',
            include_uncertain_receivables: state.include_uncertain_receivables || false,
            // In v1, crypto was always active. Preserve that behavior if crypto data exists.
            advanced_mode: state.advanced_mode || hasCryptoData
        });
    }

    /**
     * Parse share payload from URL hash
     * @returns {Object|null} Parsed state or null if invalid
     */
    function parseLink() {
        var hash = window.location.hash;

        if (!hash || !hash.startsWith(HASH_PREFIX)) {
            return null;
        }

        if (typeof LZString === 'undefined') {
            console.error('ShareLink: LZString not available');
            return null;
        }

        var compressed = hash.substring(HASH_PREFIX.length);
        if (!compressed) {
            return null;
        }

        try {
            var json = LZString.decompressFromEncodedURIComponent(compressed);
            if (!json) {
                return { error: 'invalid', message: 'Invalid share link data.' };
            }

            var payload = JSON.parse(json);

            // Validate schema version
            if (!payload || typeof payload.v !== 'number') {
                return { error: 'invalid', message: 'Invalid share link format.' };
            }

            // Handle version migration
            var data = payload.data;
            if (!data) {
                return { error: 'invalid', message: 'No calculation data found in link.' };
            }

            if (payload.v === 1) {
                // Migrate v1 to v2
                data = migrateV1toV2(data);
            } else if (payload.v > SCHEMA_VERSION) {
                return {
                    error: 'version',
                    message: 'This link was created with a newer version (v' + payload.v + '). Please update your calculator.'
                };
            }

            return { success: true, data: data };
        } catch (e) {
            console.error('ShareLink: Failed to parse share link', e);
            return { error: 'corrupt', message: 'The share link data is corrupted.' };
        }
    }

    /**
     * Copy text to clipboard
     * @param {string} text - Text to copy
     * @returns {boolean} Success status
     */
    function copyToClipboard(text) {
        // Try modern clipboard API first
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function() {
                showNotification('Link copied to clipboard!', 'success');
            }).catch(function() {
                fallbackCopy(text);
            });
            return true;
        }

        // Fallback for older browsers
        return fallbackCopy(text);
    }

    /**
     * Fallback copy method for older browsers
     * @param {string} text - Text to copy
     * @returns {boolean} Success status
     */
    function fallbackCopy(text) {
        var textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();

        try {
            var success = document.execCommand('copy');
            if (success) {
                showNotification('Link copied to clipboard!', 'success');
            } else {
                showNotification('Failed to copy. Please copy manually.', 'error');
            }
            return success;
        } catch (e) {
            showNotification('Failed to copy. Please copy manually.', 'error');
            return false;
        } finally {
            document.body.removeChild(textarea);
        }
    }

    /**
     * Check URL length and return status
     * @param {string} url - URL to check
     * @returns {Object} { ok: boolean, length: number }
     */
    function checkUrlLength(url) {
        var length = url ? url.length : 0;
        return {
            ok: length <= MAX_URL_LENGTH,
            length: length
        };
    }

    /**
     * Show the share modal with generated link
     */
    function showShareModal() {
        if (!shareModal) {
            createModals();
        }

        var url = generateLink();
        if (!url) {
            showNotification('Failed to generate share link.', 'error');
            return;
        }

        var urlInput = document.getElementById('share-url-input');
        var lengthWarning = document.getElementById('share-length-warning');
        var lengthSpan = document.getElementById('share-url-length');

        if (urlInput) {
            urlInput.value = url;
        }

        // Check URL length
        var check = checkUrlLength(url);
        if (lengthWarning && lengthSpan) {
            if (!check.ok) {
                lengthSpan.textContent = check.length;
                lengthWarning.style.display = 'flex';
            } else {
                lengthWarning.style.display = 'none';
            }
        }

        shareModal.classList.add('visible');
        shareModal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';

        // Focus the copy button
        var copyBtn = document.getElementById('share-copy-btn');
        if (copyBtn) {
            setTimeout(function() { copyBtn.focus(); }, 100);
        }
    }

    /**
     * Hide the share modal
     */
    function hideShareModal() {
        if (shareModal) {
            shareModal.classList.remove('visible');
            shareModal.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = '';
        }
    }

    /**
     * Show the load confirmation modal
     * @param {Object} state - Parsed state to load
     */
    function showLoadConfirmation(state) {
        if (!loadModal) {
            createModals();
        }

        pendingState = state;

        // Build preview of what will be loaded
        var preview = buildPreview(state);
        var previewContainer = document.getElementById('share-load-preview');
        if (previewContainer) {
            previewContainer.innerHTML = preview;
        }

        loadModal.classList.add('visible');
        loadModal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';

        // Focus the confirm button
        var confirmBtn = loadModal.querySelector('.share-load-confirm');
        if (confirmBtn) {
            setTimeout(function() { confirmBtn.focus(); }, 100);
        }
    }

    /**
     * Hide the load confirmation modal
     */
    function hideLoadModal() {
        if (loadModal) {
            loadModal.classList.remove('visible');
            loadModal.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = '';
        }
    }

    /**
     * Build a preview of the state to be loaded
     * @param {Object} state - State object
     * @returns {string} HTML preview
     */
    function buildPreview(state) {
        if (!state) return '<p>No preview available.</p>';

        var items = [];

        items.push('<div class="share-preview-item"><strong>Base Currency:</strong> ' + escapeHtml(state.base_currency || 'N/A') + '</div>');
        items.push('<div class="share-preview-item"><strong>Date:</strong> ' + escapeHtml(state.calculation_date || 'Today') + '</div>');

        // Count basic assets
        var goldCount = (state.gold_items || []).filter(function(i) { return i.weight_grams > 0; }).length;
        var cashCount = (state.cash_items || []).filter(function(i) { return i.amount > 0; }).length;
        var bankCount = (state.bank_items || []).filter(function(i) { return i.amount > 0; }).length;
        var metalCount = (state.metal_items || []).filter(function(i) { return i.weight_grams > 0; }).length;
        var cryptoCount = (state.crypto_items || []).filter(function(i) { return i.amount > 0; }).length;

        var assetSummary = [];
        if (goldCount > 0) assetSummary.push(goldCount + ' gold item' + (goldCount > 1 ? 's' : ''));
        if (cashCount > 0) assetSummary.push(cashCount + ' cash item' + (cashCount > 1 ? 's' : ''));
        if (bankCount > 0) assetSummary.push(bankCount + ' bank account' + (bankCount > 1 ? 's' : ''));
        if (metalCount > 0) assetSummary.push(metalCount + ' metal item' + (metalCount > 1 ? 's' : ''));
        if (cryptoCount > 0) assetSummary.push(cryptoCount + ' crypto asset' + (cryptoCount > 1 ? 's' : ''));

        if (assetSummary.length > 0) {
            items.push('<div class="share-preview-item"><strong>Assets:</strong> ' + assetSummary.join(', ') + '</div>');
        } else {
            items.push('<div class="share-preview-item"><strong>Assets:</strong> None</div>');
        }

        // Count advanced assets (v2)
        var stockCount = (state.stock_items || []).filter(function(i) { return i.value > 0; }).length;
        var retirementCount = (state.retirement_items || []).filter(function(i) { return i.balance > 0; }).length;
        var receivableCount = (state.receivable_items || []).filter(function(i) { return i.amount > 0; }).length;
        var propertyCount = (state.investment_property || []).filter(function(i) { return i.market_value > 0 || i.rental_income > 0; }).length;
        var hasBusiness = state.business_inventory && (
            state.business_inventory.resale_value > 0 ||
            state.business_inventory.business_cash > 0 ||
            state.business_inventory.receivables > 0
        );

        var advancedSummary = [];
        if (stockCount > 0) advancedSummary.push(stockCount + ' stock' + (stockCount > 1 ? 's' : ''));
        if (retirementCount > 0) advancedSummary.push(retirementCount + ' retirement account' + (retirementCount > 1 ? 's' : ''));
        if (receivableCount > 0) advancedSummary.push(receivableCount + ' receivable' + (receivableCount > 1 ? 's' : ''));
        if (propertyCount > 0) advancedSummary.push(propertyCount + ' propert' + (propertyCount > 1 ? 'ies' : 'y'));
        if (hasBusiness) advancedSummary.push('business inventory');

        if (advancedSummary.length > 0) {
            items.push('<div class="share-preview-item"><strong>Advanced Assets:</strong> ' + advancedSummary.join(', ') + '</div>');
        }

        // Count debts
        var creditCardCount = (state.credit_card_items || []).filter(function(i) { return i.amount > 0; }).length;
        var loanCount = (state.loan_items || []).filter(function(i) { return i.payment_amount > 0; }).length;
        var payablesCount = (state.short_term_payables || []).filter(function(i) { return i.amount > 0; }).length;

        var debtSummary = [];
        if (creditCardCount > 0) debtSummary.push(creditCardCount + ' credit card' + (creditCardCount > 1 ? 's' : ''));
        if (loanCount > 0) debtSummary.push(loanCount + ' loan' + (loanCount > 1 ? 's' : ''));
        if (payablesCount > 0) debtSummary.push(payablesCount + ' payable' + (payablesCount > 1 ? 's' : ''));

        if (debtSummary.length > 0) {
            items.push('<div class="share-preview-item"><strong>Debts:</strong> ' + debtSummary.join(', ') + '</div>');
        }

        // Show advanced mode indicator
        if (state.advanced_mode) {
            items.push('<div class="share-preview-item"><strong>Mode:</strong> Advanced Assets</div>');
        }

        return items.join('');
    }

    /**
     * Check for share payload on page load
     */
    function checkForSharePayload() {
        var result = parseLink();

        if (!result) {
            return; // No share data in URL
        }

        if (result.error) {
            showNotification(result.message, 'error');
            clearHash();
            return;
        }

        if (result.success && result.data) {
            // Wait for calculator to initialize, then show confirmation
            waitForCalculator(function() {
                showLoadConfirmation(result.data);
            });
        }
    }

    /**
     * Wait for ZakatCalculator to be available
     * @param {Function} callback - Function to call when ready
     */
    function waitForCalculator(callback) {
        var attempts = 0;
        var maxAttempts = 50; // 5 seconds max

        function check() {
            attempts++;
            if (typeof ZakatCalculator !== 'undefined') {
                callback();
            } else if (attempts < maxAttempts) {
                setTimeout(check, 100);
            } else {
                console.warn('ShareLink: ZakatCalculator not available after waiting');
            }
        }

        check();
    }

    /**
     * Clear the URL hash
     */
    function clearHash() {
        if (window.history && window.history.replaceState) {
            window.history.replaceState(null, '', window.location.pathname + window.location.search);
        } else {
            window.location.hash = '';
        }
    }

    /**
     * Open printable summary in new window
     */
    function openPrintSummary() {
        if (typeof ZakatCalculator === 'undefined') {
            showNotification('Calculator not available.', 'error');
            return;
        }

        if (typeof LZString === 'undefined') {
            showNotification('Compression library not available.', 'error');
            return;
        }

        var state = ZakatCalculator.getState();
        var payload = {
            v: SCHEMA_VERSION,
            data: state
        };

        var json = JSON.stringify(payload);
        var compressed = LZString.compressToEncodedURIComponent(json);

        var summaryUrl = window.location.origin + '/summary' + HASH_PREFIX + compressed;

        // Open in new tab
        window.open(summaryUrl, '_blank');
    }

    // Use shared utilities
    var showNotification = ZakatUtils.showNotification;
    var escapeHtml = ZakatUtils.escapeHtml;

    // Public API
    return {
        init: init,
        generateLink: generateLink,
        parseLink: parseLink,
        copyToClipboard: copyToClipboard,
        checkUrlLength: checkUrlLength,
        showShareModal: showShareModal,
        showLoadConfirmation: showLoadConfirmation,
        openPrintSummary: openPrintSummary
    };
})();
