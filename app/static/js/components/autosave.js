/**
 * Autosave Component - Persists calculator state to localStorage
 *
 * Saves calculator state automatically after input changes (debounced).
 * Restores state on page load unless a share-link is present.
 * Uses the same state format as ShareLink for consistency.
 */
const Autosave = (function() {
    'use strict';

    const STORAGE_KEY = 'zakatCalculator_autosave';
    const SCHEMA_VERSION = 2;
    const DEBOUNCE_MS = 2000;

    let enabled = false;
    let timer = null;
    let initialized = false;

    /**
     * Initialize autosave. Call after ZakatCalculator.init() completes.
     * @param {boolean} featureEnabled - Whether the autosave feature flag is on
     */
    function init(featureEnabled) {
        enabled = !!featureEnabled;
        if (!enabled) return;
        if (!storageAvailable()) {
            console.warn('Autosave: localStorage not available');
            enabled = false;
            return;
        }

        // Don't restore if a share-link is in the URL (share-link takes priority)
        if (window.location.hash && window.location.hash.startsWith('#data=')) {
            console.log('Autosave: share-link detected, skipping restore');
        } else {
            restore();
        }

        bindSaveEvents();
        initialized = true;
        console.log('Autosave: initialized');
    }

    /**
     * Check if localStorage is available and working
     */
    function storageAvailable() {
        try {
            var t = '__autosave_test__';
            localStorage.setItem(t, '1');
            localStorage.removeItem(t);
            return true;
        } catch (e) {
            return false;
        }
    }

    /**
     * Save current calculator state to localStorage (debounced)
     */
    function scheduleSave() {
        if (!enabled) return;
        clearTimeout(timer);
        timer = setTimeout(save, DEBOUNCE_MS);
    }

    /**
     * Immediately save current state
     */
    function save() {
        if (!enabled) return;
        try {
            var state = ZakatCalculator.getState();
            var payload = {
                v: SCHEMA_VERSION,
                ts: Date.now(),
                data: state
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
        } catch (e) {
            console.warn('Autosave: failed to save', e);
        }
    }

    /**
     * Restore state from localStorage
     */
    function restore() {
        try {
            var raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return;

            var payload = JSON.parse(raw);
            if (!payload || !payload.data) return;

            // Check if saved state has any actual content
            var d = payload.data;
            var hasContent = hasNonEmptyItems(d.gold_items) ||
                hasNonEmptyItems(d.cash_items) ||
                hasNonEmptyItems(d.bank_items) ||
                hasNonEmptyItems(d.metal_items) ||
                hasNonEmptyItems(d.crypto_items) ||
                hasNonEmptyItems(d.credit_card_items) ||
                hasNonEmptyItems(d.loan_items);

            if (!hasContent) return;

            ZakatCalculator.setState(payload.data);
            showRestoredNotice();
            console.log('Autosave: state restored');
        } catch (e) {
            console.warn('Autosave: failed to restore', e);
        }
    }

    /**
     * Check if an items array has any rows with non-default values
     */
    function hasNonEmptyItems(items) {
        if (!items || !Array.isArray(items) || items.length === 0) return false;
        return items.some(function(item) {
            if (item.weight_grams > 0) return true;
            if (item.weight > 0) return true;
            if (item.amount > 0) return true;
            if (item.name && item.name.length > 0) return true;
            return false;
        });
    }

    /**
     * Show a brief toast indicating state was restored
     */
    function showRestoredNotice() {
        var notice = document.createElement('div');
        notice.className = 'autosave-notice';
        notice.innerHTML = '<span>Previous session restored</span>' +
            '<button type="button" class="autosave-notice-clear" title="Clear saved data">Clear</button>' +
            '<button type="button" class="autosave-notice-dismiss" title="Dismiss">&times;</button>';
        document.body.appendChild(notice);

        // Trigger animation
        requestAnimationFrame(function() {
            notice.classList.add('autosave-notice-show');
        });

        // Clear button
        notice.querySelector('.autosave-notice-clear').addEventListener('click', function() {
            clearSaved();
            window.location.reload();
        });

        // Dismiss button
        notice.querySelector('.autosave-notice-dismiss').addEventListener('click', function() {
            dismissNotice(notice);
        });

        // Auto-dismiss after 6 seconds
        setTimeout(function() {
            dismissNotice(notice);
        }, 6000);
    }

    function dismissNotice(el) {
        if (!el || !el.parentNode) return;
        el.classList.remove('autosave-notice-show');
        setTimeout(function() {
            if (el.parentNode) el.parentNode.removeChild(el);
        }, 300);
    }

    /**
     * Clear saved state from localStorage
     */
    function clearSaved() {
        try {
            localStorage.removeItem(STORAGE_KEY);
            console.log('Autosave: cleared');
        } catch (e) {
            // Ignore
        }
    }

    /**
     * Bind to input events to trigger autosave
     */
    function bindSaveEvents() {
        document.addEventListener('input', function(event) {
            var t = event.target;
            if (t.matches('.asset-row input, .asset-row select, #calculationDate')) {
                scheduleSave();
            }
        });
        document.addEventListener('change', function(event) {
            var t = event.target;
            if (t.matches('.asset-row select, .asset-row input[type="hidden"], #baseCurrencyInput, #nisabBasisSelect')) {
                scheduleSave();
            }
        });
    }

    /**
     * Check if autosave has stored data
     */
    function hasSavedData() {
        try {
            return !!localStorage.getItem(STORAGE_KEY);
        } catch (e) {
            return false;
        }
    }

    return {
        init: init,
        save: save,
        clearSaved: clearSaved,
        hasSavedData: hasSavedData
    };
})();
