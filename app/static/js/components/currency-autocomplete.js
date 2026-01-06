/**
 * Currency Autocomplete Component
 *
 * An ARIA-accessible combobox for selecting currencies from the ISO 4217 list.
 * Supports keyboard navigation, drill-down filtering, and works with dynamically added rows.
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
            return currencies.slice(0, MAX_SUGGESTIONS);
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
     * Check if query exactly matches a currency code or name
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

        // State
        let filteredCurrencies = [];
        let activeIndex = -1;
        let isOpen = false;
        let selectedCurrency = null;

        // Create DOM structure
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

        // Set initial value
        if (initialValue) {
            const initial = currencies.find(c => c.code === initialValue);
            if (initial) {
                selectCurrency(initial, false);
            }
        }

        // Event handlers
        input.addEventListener('input', handleInput);
        input.addEventListener('keydown', handleKeyDown);
        input.addEventListener('focus', handleFocus);
        input.addEventListener('blur', handleBlur);
        listbox.addEventListener('mousedown', handleListMouseDown);

        function handleInput() {
            const query = input.value;
            filteredCurrencies = filterCurrencies(currencies, query);

            // Auto-select if exact match or only one result
            const exactMatch = findExactMatch(currencies, query);
            if (exactMatch) {
                selectCurrency(exactMatch, true);
                close();
                return;
            }

            if (filteredCurrencies.length === 1) {
                selectCurrency(filteredCurrencies[0], true);
                close();
                return;
            }

            activeIndex = -1;
            render();
            open();
        }

        function handleKeyDown(event) {
            switch (event.key) {
                case 'ArrowDown':
                    event.preventDefault();
                    if (!isOpen) {
                        filteredCurrencies = filterCurrencies(currencies, input.value);
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
                    if (isOpen && activeIndex >= 0) {
                        selectCurrency(filteredCurrencies[activeIndex], true);
                        close();
                    }
                    break;

                case 'Escape':
                    event.preventDefault();
                    close();
                    // Restore previous selection if any
                    if (selectedCurrency) {
                        input.value = formatDisplay(selectedCurrency);
                    }
                    break;

                case 'Tab':
                    close();
                    break;
            }
        }

        function handleFocus() {
            if (input.value && !isOpen) {
                filteredCurrencies = filterCurrencies(currencies, input.value);
                if (filteredCurrencies.length > 0) {
                    render();
                    open();
                }
            }
        }

        function handleBlur() {
            // Delay to allow click on listbox item
            setTimeout(function() {
                close();
                // Restore previous selection if input doesn't match
                if (selectedCurrency && input.value !== formatDisplay(selectedCurrency)) {
                    input.value = formatDisplay(selectedCurrency);
                }
            }, 150);
        }

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

        function selectCurrency(currency, notify) {
            selectedCurrency = currency;
            input.value = formatDisplay(currency);
            hiddenInput.value = currency.code;

            if (notify) {
                onSelect(currency);
                // Dispatch change event for live calculation
                hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        function formatDisplay(currency) {
            return `${currency.code} \u2014 ${currency.name}`;
        }

        function open() {
            if (filteredCurrencies.length === 0) return;
            isOpen = true;
            listbox.hidden = false;
            input.setAttribute('aria-expanded', 'true');
        }

        function close() {
            isOpen = false;
            listbox.hidden = true;
            input.setAttribute('aria-expanded', 'false');
            input.setAttribute('aria-activedescendant', '');
            activeIndex = -1;
        }

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

        function escapeHtml(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        // Public API
        return {
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
                input.removeEventListener('input', handleInput);
                input.removeEventListener('keydown', handleKeyDown);
                input.removeEventListener('focus', handleFocus);
                input.removeEventListener('blur', handleBlur);
                listbox.removeEventListener('mousedown', handleListMouseDown);
            }
        };
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
