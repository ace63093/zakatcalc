/**
 * Currency Autocomplete Component
 *
 * An ARIA-accessible combobox for selecting currencies from the ISO 4217 list.
 * Features:
 * - Auto-select on focus (typing replaces current value)
 * - Dropdown opens on focus with top currencies
 * - Keyboard navigation (ArrowUp/Down, Enter, Esc)
 * - Robust blur validation with revert behavior
 * - Works with dynamically added rows
 *
 * Usage:
 *   CurrencyAutocomplete.create(containerElement, {
 *     currencies: [...],  // Array of {code, name, priority}
 *     onSelect: (currency) => {},
 *     initialValue: 'CAD'
 *   });
 */

const CurrencyAutocomplete = (function() {
    'use strict';

    const MAX_SUGGESTIONS = 12;
    let instanceCounter = 0;

    /**
     * Normalize a string for matching: lowercase, trim, collapse spaces, strip punctuation
     */
    function normalizeQuery(str) {
        return (str || '')
            .toLowerCase()
            .trim()
            .replace(/\s+/g, ' ')
            .replace(/[^\w\s]/g, '');
    }

    /**
     * Get default suggestions (top currencies) when no query is entered.
     * Order: CAD first, then common currencies, then alphabetical remainder.
     */
    function getDefaultSuggestions(currencies) {
        return currencies.slice(0, MAX_SUGGESTIONS);
    }

    /**
     * Filter currencies based on query with match precedence:
     * 1. code startsWith query
     * 2. name startsWith query
     * 3. code contains query
     * 4. name contains query
     * Preserves original ordering within each tier.
     */
    function filterCurrencies(currencies, query) {
        const normalized = normalizeQuery(query);
        if (!normalized) {
            // No query: return top currencies (default suggestions)
            return getDefaultSuggestions(currencies);
        }

        const codeStartsWith = [];
        const nameStartsWith = [];
        const codeContains = [];
        const nameContains = [];

        for (const currency of currencies) {
            const code = normalizeQuery(currency.code);
            const name = normalizeQuery(currency.name);

            if (code.startsWith(normalized)) {
                codeStartsWith.push(currency);
            } else if (name.startsWith(normalized)) {
                nameStartsWith.push(currency);
            } else if (code.includes(normalized)) {
                codeContains.push(currency);
            } else if (name.includes(normalized)) {
                nameContains.push(currency);
            }
        }

        const results = [
            ...codeStartsWith,
            ...nameStartsWith,
            ...codeContains,
            ...nameContains
        ];

        return results.slice(0, MAX_SUGGESTIONS);
    }

    /**
     * Check if query exactly matches a currency code or name (unambiguous match)
     */
    function findExactMatch(currencies, query) {
        const normalized = normalizeQuery(query);
        if (!normalized) return null;

        for (const currency of currencies) {
            if (normalizeQuery(currency.code) === normalized) {
                return currency;
            }
            if (normalizeQuery(currency.name) === normalized) {
                return currency;
            }
        }
        return null;
    }

    /**
     * Create a currency autocomplete instance
     */
    function create(container, options = {}) {
        const currencies = options.currencies || [];
        const onSelect = options.onSelect || function() {};
        const initialValue = options.initialValue || '';
        const name = options.name || 'currency';

        const instanceId = ++instanceCounter;
        const inputId = `currency-input-${instanceId}`;
        const listboxId = `currency-listbox-${instanceId}`;

        // ==================== STATE ====================
        let filteredCurrencies = [];
        let activeIndex = -1;
        let isOpen = false;

        // Selection state
        let lastSelectedCode = '';      // Last confirmed valid selection code
        let lastSelectedLabel = '';     // Last confirmed valid selection display label
        let isQueryMode = false;        // True when user is typing (input != lastSelectedLabel)
        let shouldSelectAllOnFocus = false;  // Flag to select all text on focus

        // ==================== DOM SETUP ====================
        container.innerHTML = `
            <div class="autocomplete-wrapper">
                <input
                    type="text"
                    id="${inputId}"
                    class="autocomplete-input"
                    role="combobox"
                    aria-autocomplete="list"
                    aria-expanded="false"
                    aria-controls="${listboxId}"
                    aria-activedescendant=""
                    autocomplete="off"
                    placeholder="Type to search..."
                />
                <input type="hidden" name="${name}" value="" />
                <ul
                    id="${listboxId}"
                    class="autocomplete-listbox"
                    role="listbox"
                    hidden
                ></ul>
            </div>
        `;

        const input = container.querySelector(`#${inputId}`);
        const hiddenInput = container.querySelector('input[type="hidden"]');
        const listbox = container.querySelector(`#${listboxId}`);

        // Set initial value if provided
        if (initialValue) {
            const initial = currencies.find(c => c.code === initialValue);
            if (initial) {
                selectCurrency(initial, false);
            }
        }

        // ==================== EVENT HANDLERS ====================
        input.addEventListener('mousedown', handleMouseDown);
        input.addEventListener('input', handleInput);
        input.addEventListener('keydown', handleKeyDown);
        input.addEventListener('focus', handleFocus);
        input.addEventListener('blur', handleBlur);
        listbox.addEventListener('mousedown', handleListMouseDown);

        /**
         * Handle mousedown - prepare for select-all if clicking into finalized field
         */
        function handleMouseDown(event) {
            // If input is not focused and shows a finalized label, prepare to select all
            if (document.activeElement !== input && lastSelectedLabel && input.value === lastSelectedLabel) {
                shouldSelectAllOnFocus = true;
            }
        }

        /**
         * Handle input changes - user is typing
         */
        function handleInput() {
            const query = input.value;

            // Enter query mode - user is typing
            isQueryMode = true;

            // Clear hidden input during query mode (no valid selection yet)
            hiddenInput.value = '';

            // Filter currencies based on query
            filteredCurrencies = filterCurrencies(currencies, query);

            // Check for exact match - auto-finalize if found
            const exactMatch = findExactMatch(currencies, query);
            if (exactMatch) {
                selectCurrency(exactMatch, true);
                close();
                return;
            }

            // Render and open dropdown
            activeIndex = -1;
            render();
            open();
        }

        /**
         * Handle keyboard navigation
         */
        function handleKeyDown(event) {
            switch (event.key) {
                case 'ArrowDown':
                    event.preventDefault();
                    if (!isOpen) {
                        // Open dropdown with appropriate suggestions
                        if (isQueryMode) {
                            filteredCurrencies = filterCurrencies(currencies, input.value);
                        } else {
                            filteredCurrencies = getDefaultSuggestions(currencies);
                        }
                        render();
                        open();
                    } else {
                        moveActive(1);
                    }
                    break;

                case 'ArrowUp':
                    event.preventDefault();
                    if (isOpen) {
                        moveActive(-1);
                    }
                    break;

                case 'Enter':
                    event.preventDefault();
                    if (isOpen && activeIndex >= 0 && filteredCurrencies[activeIndex]) {
                        selectCurrency(filteredCurrencies[activeIndex], true);
                        close();
                    }
                    break;

                case 'Escape':
                    event.preventDefault();
                    close();
                    // Revert to last valid selection if in query mode
                    if (isQueryMode) {
                        revertToLastSelection();
                    }
                    break;

                case 'Tab':
                    // Let blur handler manage validation
                    close();
                    break;
            }
        }

        /**
         * Handle focus - select all text and open dropdown
         */
        function handleFocus() {
            // Auto-select text if showing finalized label
            if (shouldSelectAllOnFocus && lastSelectedLabel && input.value === lastSelectedLabel) {
                // Use requestAnimationFrame to avoid timing issues
                requestAnimationFrame(function() {
                    input.select();
                });
            }
            shouldSelectAllOnFocus = false;

            // Open dropdown with default suggestions (if not in query mode)
            if (!isQueryMode && lastSelectedLabel) {
                // Show default suggestions (top currencies)
                filteredCurrencies = getDefaultSuggestions(currencies);
            } else if (input.value) {
                // Filter based on current query
                filteredCurrencies = filterCurrencies(currencies, input.value);
            } else {
                // Empty input - show defaults
                filteredCurrencies = getDefaultSuggestions(currencies);
            }

            if (filteredCurrencies.length > 0) {
                render();
                open();
            }
        }

        /**
         * Handle blur - validate and finalize or revert
         */
        function handleBlur() {
            // Delay to allow click on listbox item
            setTimeout(function() {
                close();

                // If not in query mode, nothing to validate
                if (!isQueryMode) {
                    return;
                }

                // Try to find exact match for current input
                const exactMatch = findExactMatch(currencies, input.value);
                if (exactMatch) {
                    selectCurrency(exactMatch, true);
                } else {
                    // No valid match - revert to last selection
                    revertToLastSelection();
                }
            }, 150);
        }

        /**
         * Handle click on listbox option
         */
        function handleListMouseDown(event) {
            event.preventDefault(); // Prevent blur
            const option = event.target.closest('[role="option"]');
            if (option) {
                const code = option.dataset.code;
                const currency = currencies.find(c => c.code === code);
                if (currency) {
                    selectCurrency(currency, true);
                    close();
                    input.focus();
                }
            }
        }

        // ==================== HELPER FUNCTIONS ====================

        /**
         * Move active selection in dropdown
         */
        function moveActive(delta) {
            const len = filteredCurrencies.length;
            if (len === 0) return;

            if (activeIndex === -1) {
                activeIndex = delta > 0 ? 0 : len - 1;
            } else {
                activeIndex = (activeIndex + delta + len) % len;
            }
            updateActiveDescendant();
        }

        /**
         * Select a currency and finalize the selection
         */
        function selectCurrency(currency, notify) {
            // Update state
            lastSelectedCode = currency.code;
            lastSelectedLabel = formatDisplay(currency);
            isQueryMode = false;

            // Update DOM
            input.value = lastSelectedLabel;
            hiddenInput.value = currency.code;

            if (notify) {
                onSelect(currency);
                // Dispatch change event for live calculation
                hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        /**
         * Revert to last valid selection (or clear if none)
         */
        function revertToLastSelection() {
            if (lastSelectedCode && lastSelectedLabel) {
                input.value = lastSelectedLabel;
                hiddenInput.value = lastSelectedCode;
            } else {
                input.value = '';
                hiddenInput.value = '';
            }
            isQueryMode = false;
        }

        /**
         * Format currency for display: "CAD — Canadian Dollar"
         */
        function formatDisplay(currency) {
            return `${currency.code} \u2014 ${currency.name}`;
        }

        /**
         * Open dropdown
         */
        function open() {
            if (filteredCurrencies.length === 0) return;
            isOpen = true;
            listbox.hidden = false;
            input.setAttribute('aria-expanded', 'true');
        }

        /**
         * Close dropdown
         */
        function close() {
            isOpen = false;
            listbox.hidden = true;
            input.setAttribute('aria-expanded', 'false');
            input.setAttribute('aria-activedescendant', '');
            activeIndex = -1;
        }

        /**
         * Update aria-activedescendant and visual active state
         */
        function updateActiveDescendant() {
            const options = listbox.querySelectorAll('[role="option"]');
            options.forEach(function(opt, i) {
                const isActive = i === activeIndex;
                opt.classList.toggle('active', isActive);
                opt.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });

            if (activeIndex >= 0 && options[activeIndex]) {
                input.setAttribute('aria-activedescendant', options[activeIndex].id);
                options[activeIndex].scrollIntoView({ block: 'nearest' });
            }
        }

        /**
         * Render dropdown options
         */
        function render() {
            listbox.innerHTML = filteredCurrencies.map(function(c, i) {
                return `
                    <li
                        id="${listboxId}-option-${i}"
                        role="option"
                        aria-selected="false"
                        data-code="${c.code}"
                        class="autocomplete-option"
                    >
                        <span class="currency-code">${escapeHtml(c.code)}</span>
                        <span class="currency-name">${escapeHtml(c.name)}</span>
                    </li>
                `;
            }).join('');
        }

        /**
         * Escape HTML special characters
         */
        function escapeHtml(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        // ==================== PUBLIC API ====================
        const api = {
            getValue: function() {
                return hiddenInput.value;
            },
            setValue: function(code) {
                const currency = currencies.find(c => c.code === code);
                if (currency) {
                    selectCurrency(currency, false);
                }
            },
            destroy: function() {
                input.removeEventListener('mousedown', handleMouseDown);
                input.removeEventListener('input', handleInput);
                input.removeEventListener('keydown', handleKeyDown);
                input.removeEventListener('focus', handleFocus);
                input.removeEventListener('blur', handleBlur);
                listbox.removeEventListener('mousedown', handleListMouseDown);
            }
        };

        // Store reference on container for external access
        container._autocomplete = api;

        return api;
    }

    /**
     * Initialize all currency autocomplete containers on the page
     */
    function initAll(selector, currencies, options = {}) {
        const containers = document.querySelectorAll(selector);
        const instances = [];

        containers.forEach(function(container) {
            if (!container._currencyAutocomplete) {
                const instance = create(container, {
                    ...options,
                    currencies: currencies
                });
                container._currencyAutocomplete = instance;
                instances.push(instance);
            }
        });

        return instances;
    }

    /**
     * Set value on an existing autocomplete container
     * @param {Element} container - Container element with initialized autocomplete
     * @param {string} code - Currency code to set
     */
    function setValue(container, code) {
        if (container && container._currencyAutocomplete) {
            container._currencyAutocomplete.setValue(code);
        }
    }

    return {
        create: create,
        initAll: initAll,
        setValue: setValue,
        filterCurrencies: filterCurrencies,
        normalizeQuery: normalizeQuery
    };
})();

// Export for use as module if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CurrencyAutocomplete;
}
