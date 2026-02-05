/**
 * Zakat Calculator - Shared Utilities
 *
 * Common utility functions and constants used across multiple components.
 * Must be loaded before other calculator components.
 */

var ZakatUtils = (function() {
    'use strict';

    // ========== Constants ==========

    /**
     * Weight unit conversion constants (all values are grams per unit)
     */
    var WEIGHT_UNITS = {
        g: { gramsPerUnit: 1, label: 'Grams (g)', short: 'g', decimals: 2 },
        ozt: { gramsPerUnit: 31.1034768, label: 'Troy ounces (oz t)', short: 'oz t', decimals: 4 },
        tola: { gramsPerUnit: 11.6638038, label: 'Tola', short: 'tola', decimals: 4 },
        vori: { gramsPerUnit: 11.6638038, label: 'Vori', short: 'vori', decimals: 4 },
        aana: { gramsPerUnit: 0.72898774, label: 'Aana', short: 'aana', decimals: 2 }
    };

    /**
     * Loan frequency multipliers for annualization
     */
    var LOAN_FREQUENCY_MULTIPLIERS = {
        weekly: 52,
        biweekly: 26,
        semi_monthly: 24,
        monthly: 12,
        quarterly: 4,
        yearly: 1
    };

    /**
     * Nisab thresholds
     */
    var NISAB_GOLD_GRAMS = 85;
    var NISAB_SILVER_GRAMS = 595;

    /**
     * Zakat rate (2.5%)
     */
    var ZAKAT_RATE = 0.025;

    // ========== Utility Functions ==========

    /**
     * Escape HTML special characters
     * @param {string} str - String to escape
     * @returns {string} Escaped string
     */
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Show notification toast
     * @param {string} message - Message to show
     * @param {string} type - 'success' or 'error'
     */
    function showNotification(message, type) {
        // Remove existing notifications
        var existing = document.querySelector('.tools-notification');
        if (existing) {
            existing.remove();
        }

        var notification = document.createElement('div');
        notification.className = 'tools-notification tools-notification-' + type;
        notification.textContent = message;
        document.body.appendChild(notification);

        // Trigger animation
        setTimeout(function() {
            notification.classList.add('visible');
        }, 10);

        // Auto-remove after 3 seconds
        setTimeout(function() {
            notification.classList.remove('visible');
            setTimeout(function() {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 300);
        }, 3000);
    }

    // ========== Weight Conversion Helpers ==========

    /**
     * Convert a value from display unit to grams (canonical storage)
     * @param {number} value - Value in display unit
     * @param {string} unit - Unit code (g, ozt, tola, vori, aana)
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
     * @param {string} unit - Unit code (g, ozt, tola, vori, aana)
     * @returns {number} Value in display unit
     */
    function fromGrams(grams, unit) {
        if (!grams || isNaN(grams)) return 0;
        var unitInfo = WEIGHT_UNITS[unit] || WEIGHT_UNITS.g;
        return grams / unitInfo.gramsPerUnit;
    }

    /**
     * Get weight unit info by code
     * @param {string} code - Weight unit code (g, ozt, tola, vori, aana)
     * @returns {Object} Weight unit info {gramsPerUnit, label, short, decimals}
     */
    function getWeightUnit(code) {
        return WEIGHT_UNITS[code] || WEIGHT_UNITS.g;
    }

    // ========== Public API ==========

    return {
        // Constants
        WEIGHT_UNITS: WEIGHT_UNITS,
        LOAN_FREQUENCY_MULTIPLIERS: LOAN_FREQUENCY_MULTIPLIERS,
        NISAB_GOLD_GRAMS: NISAB_GOLD_GRAMS,
        NISAB_SILVER_GRAMS: NISAB_SILVER_GRAMS,
        ZAKAT_RATE: ZAKAT_RATE,

        // Utility functions
        escapeHtml: escapeHtml,
        showNotification: showNotification,

        // Weight conversion helpers
        toGrams: toGrams,
        fromGrams: fromGrams,
        getWeightUnit: getWeightUnit
    };
})();
