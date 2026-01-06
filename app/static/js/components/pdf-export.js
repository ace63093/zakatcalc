/**
 * PDF Export Component
 *
 * Generates and downloads PDF reports of Zakat calculations.
 * Uses jsPDF library loaded lazily from CDN when export is triggered.
 *
 * Features:
 * - Lazy loading of jsPDF (only loads when needed)
 * - Clean, organized PDF layout
 * - Includes all asset categories and nisab information
 * - Works offline after initial library load
 */

var PdfExport = (function() {
    'use strict';

    // Constants
    var JSPDF_CDN = 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js';
    var JSPDF_INTEGRITY = 'sha512-qZvrmS2ekKPF2mSznTQsxqPgnpkI4DNTlrdUmTzrDgektczlKNRRhy5X5AAOnx5S09ydFYWWNSfcEqDTTHLQfUg==';

    var NISAB_GOLD_GRAMS = 85;
    var NISAB_SILVER_GRAMS = 595;
    var ZAKAT_RATE = 0.025;

    // Currency symbols for display
    var CURRENCY_SYMBOLS = {
        CAD: 'C$', USD: '$', EUR: 'EUR', GBP: 'GBP', JPY: 'JPY',
        AUD: 'A$', CHF: 'CHF', CNY: 'CNY', INR: 'INR', BDT: 'BDT'
    };

    // State
    var jspdfLoaded = false;
    var isLoading = false;

    /**
     * Load jsPDF library dynamically
     * @param {Function} callback - Called when library is loaded
     */
    function loadJsPdf(callback) {
        if (jspdfLoaded && window.jspdf) {
            callback();
            return;
        }

        if (isLoading) {
            // Wait for existing load to complete
            var checkInterval = setInterval(function() {
                if (jspdfLoaded && window.jspdf) {
                    clearInterval(checkInterval);
                    callback();
                }
            }, 100);
            return;
        }

        isLoading = true;
        showLoadingState(true);

        var script = document.createElement('script');
        script.src = JSPDF_CDN;
        script.integrity = JSPDF_INTEGRITY;
        script.crossOrigin = 'anonymous';

        script.onload = function() {
            jspdfLoaded = true;
            isLoading = false;
            showLoadingState(false);
            callback();
        };

        script.onerror = function() {
            isLoading = false;
            showLoadingState(false);
            showError('Failed to load PDF library. Please check your internet connection and try again.');
        };

        document.head.appendChild(script);
    }

    /**
     * Format currency for display in PDF
     * @param {number} amount - Amount to format
     * @param {string} currency - Currency code
     * @returns {string} Formatted currency string
     */
    function formatCurrency(amount, currency) {
        var symbol = CURRENCY_SYMBOLS[currency] || currency + ' ';
        return symbol + formatNumber(amount);
    }

    /**
     * Format a number with commas and decimals
     * @param {number} num - Number to format
     * @returns {string} Formatted number
     */
    function formatNumber(num) {
        return num.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    /**
     * Truncate text to fit in PDF
     * @param {string} text - Text to truncate
     * @param {number} maxLength - Maximum length
     * @returns {string} Truncated text
     */
    function truncateText(text, maxLength) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength - 3) + '...';
    }

    /**
     * Generate the PDF document
     * @param {Object} result - Calculation result from ZakatCalculator
     * @param {Object} state - Current calculator state
     * @returns {Object} jsPDF document instance
     */
    function generatePdf(result, state) {
        var doc = new window.jspdf.jsPDF();
        var pageWidth = doc.internal.pageSize.getWidth();
        var margin = 20;
        var contentWidth = pageWidth - (margin * 2);
        var y = 20;

        // Helper functions for positioning
        function addLine(yPos) {
            doc.setDrawColor(200, 200, 200);
            doc.line(margin, yPos, pageWidth - margin, yPos);
        }

        function checkPageBreak(neededHeight) {
            var pageHeight = doc.internal.pageSize.getHeight();
            if (y + neededHeight > pageHeight - 20) {
                doc.addPage();
                y = 20;
                return true;
            }
            return false;
        }

        // Header
        doc.setFontSize(20);
        doc.setFont('helvetica', 'bold');
        doc.text('ZAKAT CALCULATION REPORT', pageWidth / 2, y, { align: 'center' });
        y += 10;

        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(100, 100, 100);
        doc.text('Generated: ' + new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC', pageWidth / 2, y, { align: 'center' });
        y += 15;

        addLine(y);
        y += 10;

        // Calculation info
        doc.setTextColor(0, 0, 0);
        doc.setFontSize(11);
        doc.text('Calculation Date: ' + (state.calculation_date || '-'), margin, y);
        y += 7;
        doc.text('Base Currency: ' + (state.base_currency || 'CAD'), margin, y);
        y += 12;

        addLine(y);
        y += 10;

        // Nisab Status Section
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('NISAB STATUS', margin, y);
        y += 8;

        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');

        var nisabBasis = state.nisab_basis || 'gold';
        var nisabGrams = nisabBasis === 'silver' ? NISAB_SILVER_GRAMS : NISAB_GOLD_GRAMS;
        var nisabLabel = nisabBasis === 'silver' ? 'Silver' : 'Gold';

        doc.text('Basis: ' + nisabLabel + ' (' + nisabGrams + 'g)', margin, y);
        y += 6;

        var nisabThreshold = result.nisabThreshold || 0;
        doc.text('Threshold: ' + formatCurrency(nisabThreshold, state.base_currency), margin, y);
        y += 6;

        var grandTotal = result.grandTotal || 0;
        doc.text('Your Total: ' + formatCurrency(grandTotal, state.base_currency), margin, y);
        y += 6;

        var aboveNisab = grandTotal >= nisabThreshold;
        var statusText = aboveNisab ? 'Above Nisab - Zakat is Due' : 'Below Nisab';
        var statusSymbol = aboveNisab ? ' [Yes]' : ' [No]';
        doc.text('Status: ' + statusText + statusSymbol, margin, y);
        y += 12;

        addLine(y);
        y += 10;

        // Asset sections
        var sections = [
            { title: 'GOLD ASSETS', items: state.gold_items || [], type: 'gold' },
            { title: 'OTHER METALS', items: state.metal_items || [], type: 'metal' },
            { title: 'CASH ON HAND', items: state.cash_items || [], type: 'cash' },
            { title: 'BANK ACCOUNTS', items: state.bank_items || [], type: 'bank' },
            { title: 'CRYPTOCURRENCY', items: state.crypto_items || [], type: 'crypto' }
        ];

        var subtotals = {
            gold: result.goldTotal || 0,
            metal: result.metalTotal || 0,
            cash: result.cashTotal || 0,
            bank: result.bankTotal || 0,
            crypto: result.cryptoTotal || 0
        };

        sections.forEach(function(section) {
            // Filter out empty items
            var validItems = section.items.filter(function(item) {
                if (section.type === 'gold' || section.type === 'metal') {
                    return item.weight_grams > 0;
                } else if (section.type === 'cash' || section.type === 'bank') {
                    return item.amount > 0;
                } else if (section.type === 'crypto') {
                    return item.amount > 0 && item.symbol;
                }
                return false;
            });

            // Skip empty sections but show subtotal
            checkPageBreak(50);

            doc.setFontSize(12);
            doc.setFont('helvetica', 'bold');
            doc.text(section.title, margin, y);
            y += 8;

            if (validItems.length === 0) {
                doc.setFontSize(10);
                doc.setFont('helvetica', 'italic');
                doc.setTextColor(120, 120, 120);
                doc.text('No items', margin, y);
                doc.setTextColor(0, 0, 0);
                y += 6;
            } else {
                doc.setFontSize(9);
                doc.setFont('helvetica', 'normal');

                // Table header
                doc.setFont('helvetica', 'bold');
                if (section.type === 'gold') {
                    doc.text('Name', margin, y);
                    doc.text('Weight (g)', margin + 60, y);
                    doc.text('Karat', margin + 100, y);
                } else if (section.type === 'metal') {
                    doc.text('Name', margin, y);
                    doc.text('Metal', margin + 60, y);
                    doc.text('Weight (g)', margin + 100, y);
                } else if (section.type === 'cash' || section.type === 'bank') {
                    doc.text('Name', margin, y);
                    doc.text('Currency', margin + 60, y);
                    doc.text('Amount', margin + 100, y);
                } else if (section.type === 'crypto') {
                    doc.text('Name', margin, y);
                    doc.text('Symbol', margin + 60, y);
                    doc.text('Amount', margin + 100, y);
                }
                y += 5;

                doc.setFont('helvetica', 'normal');

                validItems.forEach(function(item) {
                    checkPageBreak(10);

                    var name = truncateText(item.name || '-', 25);

                    if (section.type === 'gold') {
                        doc.text(name, margin, y);
                        doc.text(formatNumber(item.weight_grams), margin + 60, y);
                        doc.text((item.purity_karat || 22) + 'K', margin + 100, y);
                    } else if (section.type === 'metal') {
                        doc.text(name, margin, y);
                        doc.text(capitalizeFirst(item.metal || 'silver'), margin + 60, y);
                        doc.text(formatNumber(item.weight_grams), margin + 100, y);
                    } else if (section.type === 'cash' || section.type === 'bank') {
                        doc.text(name, margin, y);
                        doc.text(item.currency || state.base_currency, margin + 60, y);
                        doc.text(formatNumber(item.amount), margin + 100, y);
                    } else if (section.type === 'crypto') {
                        doc.text(name, margin, y);
                        doc.text(item.symbol || '-', margin + 60, y);
                        doc.text(item.amount.toString(), margin + 100, y);
                    }

                    y += 5;
                });
            }

            // Subtotal
            y += 2;
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(10);
            doc.text('Subtotal: ' + formatCurrency(subtotals[section.type], state.base_currency), pageWidth - margin, y, { align: 'right' });
            y += 10;

            addLine(y);
            y += 8;
        });

        // Summary section
        checkPageBreak(60);

        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('SUMMARY', margin, y);
        y += 10;

        doc.setFontSize(11);

        // Grand total
        doc.setFont('helvetica', 'bold');
        doc.text('Grand Total:', margin, y);
        doc.text(formatCurrency(grandTotal, state.base_currency), pageWidth - margin, y, { align: 'right' });
        y += 8;

        // Nisab threshold
        doc.setFont('helvetica', 'normal');
        doc.text('Nisab Threshold (' + nisabGrams + 'g ' + nisabLabel + '):', margin, y);
        doc.text(formatCurrency(nisabThreshold, state.base_currency), pageWidth - margin, y, { align: 'right' });
        y += 8;

        // Status
        doc.text('Above Nisab:', margin, y);
        doc.text(aboveNisab ? 'Yes' : 'No', pageWidth - margin, y, { align: 'right' });
        y += 12;

        // Zakat due (highlighted)
        if (aboveNisab) {
            doc.setFillColor(240, 253, 244);
            doc.rect(margin - 5, y - 5, contentWidth + 10, 15, 'F');
        }

        doc.setFontSize(13);
        doc.setFont('helvetica', 'bold');
        var zakatDue = aboveNisab ? grandTotal * ZAKAT_RATE : 0;
        doc.text('Zakat Due (2.5%):', margin, y);
        doc.text(formatCurrency(zakatDue, state.base_currency), pageWidth - margin, y, { align: 'right' });
        y += 20;

        // Footer
        addLine(y);
        y += 8;

        doc.setFontSize(8);
        doc.setFont('helvetica', 'italic');
        doc.setTextColor(120, 120, 120);
        doc.text('This report is for personal record-keeping purposes only.', pageWidth / 2, y, { align: 'center' });
        y += 5;
        doc.text('Please consult a qualified Islamic scholar for guidance on your specific situation.', pageWidth / 2, y, { align: 'center' });

        return doc;
    }

    /**
     * Capitalize first letter
     * @param {string} str - String to capitalize
     * @returns {string} Capitalized string
     */
    function capitalizeFirst(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    /**
     * Show/hide loading state on export button
     * @param {boolean} loading - Whether to show loading state
     */
    function showLoadingState(loading) {
        var btn = document.getElementById('export-pdf-btn');
        if (!btn) return;

        if (loading) {
            btn.disabled = true;
            btn.dataset.originalText = btn.textContent;
            btn.textContent = 'Loading...';
            btn.classList.add('loading');
        } else {
            btn.disabled = false;
            btn.textContent = btn.dataset.originalText || 'Export PDF';
            btn.classList.remove('loading');
        }
    }

    /**
     * Show success notification
     * @param {string} message - Success message
     */
    function showSuccess(message) {
        showNotification(message, 'success');
    }

    /**
     * Show error notification
     * @param {string} message - Error message
     */
    function showError(message) {
        showNotification(message, 'error');
    }

    /**
     * Show notification toast
     * @param {string} message - Message to display
     * @param {string} type - 'success' or 'error'
     */
    function showNotification(message, type) {
        // Remove existing notifications
        var existing = document.querySelector('.pdf-notification');
        if (existing) {
            existing.remove();
        }

        var notification = document.createElement('div');
        notification.className = 'pdf-notification pdf-notification-' + type;
        notification.textContent = message;
        document.body.appendChild(notification);

        // Trigger animation
        setTimeout(function() {
            notification.classList.add('visible');
        }, 10);

        // Auto-remove after 4 seconds
        setTimeout(function() {
            notification.classList.remove('visible');
            setTimeout(function() {
                notification.remove();
            }, 300);
        }, 4000);
    }

    /**
     * Initialize the PDF export component
     */
    function init() {
        // Bind click event to export button
        document.addEventListener('click', function(event) {
            var exportBtn = event.target.closest('#export-pdf-btn');
            if (exportBtn) {
                event.preventDefault();
                exportPdf();
            }
        });
    }

    /**
     * Export the current calculation as PDF
     */
    function exportPdf() {
        if (typeof ZakatCalculator === 'undefined') {
            showError('Calculator not available.');
            return;
        }

        var state = ZakatCalculator.getState();
        var result = ZakatCalculator.getLastResult();

        if (!result) {
            showError('No calculation results available. Please enter some assets first.');
            return;
        }

        loadJsPdf(function() {
            try {
                var doc = generatePdf(result, state);
                var filename = 'zakat-calculation-' + (state.calculation_date || new Date().toISOString().split('T')[0]) + '.pdf';
                doc.save(filename);
                showSuccess('PDF exported: ' + filename);
            } catch (error) {
                console.error('PDF generation failed:', error);
                showError('Failed to generate PDF. Please try again.');
            }
        });
    }

    // Public API
    return {
        init: init,
        export: exportPdf
    };
})();
