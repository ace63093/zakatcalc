/**
 * Zakat Date Assistant Component
 *
 * Helps users track their zakat anniversary date with:
 * - Anniversary date selection and storage
 * - Approximate Hijri date display
 * - ICS calendar export for reminders
 */

var ZakatDateAssistant = (function() {
    'use strict';

    // State
    var container = null;
    var anniversaryDate = null;
    var expanded = false;

    // Hijri calendar constants (approximate)
    var HIJRI_EPOCH = 1948439.5; // Julian day of Hijri epoch (July 16, 622 CE)
    var HIJRI_YEAR_DAYS = 354.36667; // Average Hijri year length

    // Hijri month names
    var HIJRI_MONTHS = [
        'Muharram', 'Safar', 'Rabi\' al-Awwal', 'Rabi\' al-Thani',
        'Jumada al-Awwal', 'Jumada al-Thani', 'Rajab', 'Sha\'ban',
        'Ramadan', 'Shawwal', 'Dhu al-Qi\'dah', 'Dhu al-Hijjah'
    ];

    /**
     * Initialize the date assistant
     * @param {string} containerId - Container element ID
     */
    function init(containerId) {
        container = document.getElementById(containerId);
        if (!container) {
            console.warn('ZakatDateAssistant: Container not found');
            return;
        }

        // Load saved anniversary date
        loadSavedDate();

        // Render UI
        render();

        // Bind events
        bindEvents();
    }

    /**
     * Load saved anniversary date from localStorage
     */
    function loadSavedDate() {
        try {
            var saved = localStorage.getItem('zakatAnniversaryDate');
            if (saved) {
                anniversaryDate = new Date(saved);
                if (isNaN(anniversaryDate.getTime())) {
                    anniversaryDate = null;
                }
            }
        } catch (e) {
            console.warn('ZakatDateAssistant: Could not load saved date');
        }
    }

    /**
     * Save anniversary date to localStorage
     */
    function saveDate() {
        try {
            if (anniversaryDate) {
                localStorage.setItem('zakatAnniversaryDate', anniversaryDate.toISOString());
            } else {
                localStorage.removeItem('zakatAnniversaryDate');
            }
        } catch (e) {
            console.warn('ZakatDateAssistant: Could not save date');
        }
    }

    /**
     * Render the UI
     */
    function render() {
        var html = [
            '<div class="date-assistant">',
            '  <div class="date-assistant-header" role="button" tabindex="0" aria-expanded="' + expanded + '">',
            '    <span class="date-assistant-icon">📅</span>',
            '    <span class="date-assistant-title">Zakat Date Assistant</span>',
            '    <span class="date-assistant-toggle">' + (expanded ? '−' : '+') + '</span>',
            '  </div>',
            '  <div class="date-assistant-content" style="display: ' + (expanded ? 'block' : 'none') + ';">',
            renderContent(),
            '  </div>',
            '</div>'
        ].join('\n');

        container.innerHTML = html;
    }

    /**
     * Render the content section
     */
    function renderContent() {
        var today = new Date();
        var formattedDate = anniversaryDate ? formatDate(anniversaryDate) : '';
        var hijriDate = anniversaryDate ? gregorianToHijri(anniversaryDate) : null;
        var nextAnniversary = anniversaryDate ? getNextAnniversary(anniversaryDate) : null;
        var daysUntil = nextAnniversary ? daysBetween(today, nextAnniversary) : null;

        var lines = [
            '<div class="date-assistant-section">',
            '  <label for="zakatAnniversaryInput">Your Zakat Anniversary Date</label>',
            '  <p class="date-hint">The date when you first became obligated to pay zakat, or the date you chose to calculate from each year.</p>',
            '  <div class="date-input-row">',
            '    <input type="date" id="zakatAnniversaryInput" value="' + formattedDate + '" class="date-input">',
            '    <button type="button" id="saveDateBtn" class="date-btn-save">Save</button>',
            '  </div>',
            '</div>'
        ];

        if (anniversaryDate) {
            lines.push('<div class="date-assistant-section date-info">');

            // Hijri date
            if (hijriDate) {
                lines.push('<div class="date-info-row">');
                lines.push('  <span class="date-info-label">Approximate Hijri Date:</span>');
                lines.push('  <span class="date-info-value">' + formatHijri(hijriDate) + '</span>');
                lines.push('</div>');
            }

            // Next anniversary
            if (nextAnniversary && daysUntil !== null) {
                var urgencyClass = '';
                var message = '';

                if (daysUntil === 0) {
                    urgencyClass = 'date-today';
                    message = 'Today is your zakat anniversary!';
                } else if (daysUntil < 0) {
                    urgencyClass = 'date-overdue';
                    message = 'Your zakat anniversary was ' + Math.abs(daysUntil) + ' days ago';
                } else if (daysUntil <= 30) {
                    urgencyClass = 'date-soon';
                    message = daysUntil + ' days until your next zakat anniversary';
                } else {
                    message = daysUntil + ' days until ' + formatDate(nextAnniversary);
                }

                lines.push('<div class="date-info-row ' + urgencyClass + '">');
                lines.push('  <span class="date-info-label">Next Anniversary:</span>');
                lines.push('  <span class="date-info-value">' + message + '</span>');
                lines.push('</div>');
            }

            lines.push('</div>');

            // Calendar export
            lines.push('<div class="date-assistant-section date-actions">');
            lines.push('  <button type="button" id="exportIcsBtn" class="date-btn-export">');
            lines.push('    Add to Calendar (.ics)');
            lines.push('  </button>');
            lines.push('  <button type="button" id="clearDateBtn" class="date-btn-clear">');
            lines.push('    Clear Date');
            lines.push('  </button>');
            lines.push('</div>');
        }

        return lines.join('\n');
    }

    /**
     * Bind event listeners
     */
    function bindEvents() {
        container.addEventListener('click', function(e) {
            // Toggle header
            var header = e.target.closest('.date-assistant-header');
            if (header) {
                expanded = !expanded;
                render();
                bindEvents();
                return;
            }

            // Save button
            if (e.target.id === 'saveDateBtn') {
                var input = document.getElementById('zakatAnniversaryInput');
                if (input && input.value) {
                    anniversaryDate = new Date(input.value + 'T00:00:00');
                    saveDate();
                    render();
                    bindEvents();
                    showNotification('Zakat anniversary date saved!', 'success');
                }
                return;
            }

            // Export ICS
            if (e.target.id === 'exportIcsBtn') {
                exportICS();
                return;
            }

            // Clear date
            if (e.target.id === 'clearDateBtn') {
                anniversaryDate = null;
                saveDate();
                render();
                bindEvents();
                showNotification('Zakat anniversary date cleared.', 'info');
                return;
            }
        });

        // Keyboard support for header
        container.addEventListener('keydown', function(e) {
            var header = e.target.closest('.date-assistant-header');
            if (header && (e.key === 'Enter' || e.key === ' ')) {
                e.preventDefault();
                expanded = !expanded;
                render();
                bindEvents();
            }
        });
    }

    /**
     * Convert Gregorian date to approximate Hijri date
     * @param {Date} date - Gregorian date
     * @returns {Object} { year, month, day }
     */
    function gregorianToHijri(date) {
        // Convert to Julian day number
        var y = date.getFullYear();
        var m = date.getMonth() + 1;
        var d = date.getDate();

        var a = Math.floor((14 - m) / 12);
        var jy = y + 4800 - a;
        var jm = m + 12 * a - 3;

        var jd = d + Math.floor((153 * jm + 2) / 5) + 365 * jy +
                 Math.floor(jy / 4) - Math.floor(jy / 100) +
                 Math.floor(jy / 400) - 32045;

        // Days since Hijri epoch
        var daysSinceEpoch = jd - HIJRI_EPOCH;

        // Approximate Hijri year
        var hijriYear = Math.floor(daysSinceEpoch / HIJRI_YEAR_DAYS) + 1;

        // Calculate month and day (approximate)
        var daysInYear = daysSinceEpoch - Math.floor((hijriYear - 1) * HIJRI_YEAR_DAYS);
        var hijriMonth = Math.floor(daysInYear / 29.5) + 1;
        if (hijriMonth > 12) hijriMonth = 12;
        var hijriDay = Math.round(daysInYear - (hijriMonth - 1) * 29.5) + 1;
        if (hijriDay < 1) hijriDay = 1;
        if (hijriDay > 30) hijriDay = 30;

        return {
            year: hijriYear,
            month: hijriMonth,
            day: hijriDay
        };
    }

    /**
     * Format Hijri date for display
     */
    function formatHijri(hijri) {
        var monthName = HIJRI_MONTHS[hijri.month - 1] || 'Unknown';
        return hijri.day + ' ' + monthName + ' ' + hijri.year + ' AH';
    }

    /**
     * Format date as YYYY-MM-DD
     */
    function formatDate(date) {
        return date.toISOString().split('T')[0];
    }

    /**
     * Get next anniversary date
     */
    function getNextAnniversary(baseDate) {
        var today = new Date();
        today.setHours(0, 0, 0, 0);

        var thisYear = new Date(today.getFullYear(), baseDate.getMonth(), baseDate.getDate());
        var nextYear = new Date(today.getFullYear() + 1, baseDate.getMonth(), baseDate.getDate());

        // If this year's anniversary is today or in the future, use it
        if (thisYear >= today) {
            return thisYear;
        }
        return nextYear;
    }

    /**
     * Calculate days between two dates
     */
    function daysBetween(date1, date2) {
        var d1 = new Date(date1);
        var d2 = new Date(date2);
        d1.setHours(0, 0, 0, 0);
        d2.setHours(0, 0, 0, 0);
        var diff = d2 - d1;
        return Math.round(diff / (1000 * 60 * 60 * 24));
    }

    /**
     * Export ICS calendar file
     */
    function exportICS() {
        if (!anniversaryDate) return;

        var nextDate = getNextAnniversary(anniversaryDate);
        var dateStr = formatDate(nextDate).replace(/-/g, '');

        var icsContent = [
            'BEGIN:VCALENDAR',
            'VERSION:2.0',
            'PRODID:-//WhatIsMyZakat//Zakat Calculator//EN',
            'CALSCALE:GREGORIAN',
            'METHOD:PUBLISH',
            'BEGIN:VEVENT',
            'DTSTART;VALUE=DATE:' + dateStr,
            'DTEND;VALUE=DATE:' + dateStr,
            'SUMMARY:Zakat Anniversary - Calculate Your Zakat',
            'DESCRIPTION:Today marks your annual zakat calculation date. Visit whatismyzakat.com to calculate your zakat obligation.',
            'URL:https://whatismyzakat.com',
            'RRULE:FREQ=YEARLY',
            'BEGIN:VALARM',
            'TRIGGER:-P7D',
            'ACTION:DISPLAY',
            'DESCRIPTION:Zakat anniversary in 7 days',
            'END:VALARM',
            'END:VEVENT',
            'END:VCALENDAR'
        ].join('\r\n');

        // Create download
        var blob = new Blob([icsContent], { type: 'text/calendar;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = 'zakat-anniversary.ics';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);

        showNotification('Calendar file downloaded!', 'success');
    }

    /**
     * Show notification (uses ZakatUtils if available)
     */
    function showNotification(message, type) {
        if (typeof ZakatUtils !== 'undefined' && ZakatUtils.showNotification) {
            ZakatUtils.showNotification(message, type);
        } else {
            console.log('[' + type + '] ' + message);
        }
    }

    /**
     * Get the current anniversary date
     */
    function getAnniversaryDate() {
        return anniversaryDate;
    }

    /**
     * Set the anniversary date programmatically
     */
    function setAnniversaryDate(date) {
        if (date instanceof Date && !isNaN(date.getTime())) {
            anniversaryDate = date;
            saveDate();
            if (container) {
                render();
                bindEvents();
            }
        }
    }

    // Public API
    return {
        init: init,
        getAnniversaryDate: getAnniversaryDate,
        setAnniversaryDate: setAnniversaryDate,
        gregorianToHijri: gregorianToHijri,
        formatHijri: formatHijri
    };
})();
