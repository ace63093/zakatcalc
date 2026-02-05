/**
 * Crypto Autocomplete Component
 *
 * An ARIA-accessible combobox for selecting cryptocurrencies from the top 100 list.
 * Similar to CurrencyAutocomplete but with rank display.
 *
 * Usage:
 *   CryptoAutocomplete.create(containerElement, {
 *     cryptos: [...],  // Array of {symbol, name, rank}
 *     onSelect: (crypto) => {},
 *     initialValue: 'BTC'
 *   });
 */

const CryptoAutocomplete = (function() {
    'use strict';

    const MAX_SUGGESTIONS = 12;
    let instanceCounter = 0;

    /**
     * Normalize a string for matching
     */
    function normalizeQuery(str) {
        return (str || '')
            .toLowerCase()
            .trim()
            .replace(/\s+/g, ' ')
            .replace(/[^\w\s]/g, '');
    }

    /**
     * Filter cryptos based on query with match precedence:
     * 1. symbol startsWith query
     * 2. name startsWith query
     * 3. symbol contains query
     * 4. name contains query
     * Preserves rank ordering within each tier.
     */
    function filterCryptos(cryptos, query) {
        const normalized = normalizeQuery(query);
        if (!normalized) {
            return cryptos.slice(0, MAX_SUGGESTIONS);
        }

        const symbolStartsWith = [];
        const nameStartsWith = [];
        const symbolContains = [];
        const nameContains = [];

        for (const crypto of cryptos) {
            const symbol = normalizeQuery(crypto.symbol);
            const name = normalizeQuery(crypto.name);

            if (symbol.startsWith(normalized)) {
                symbolStartsWith.push(crypto);
            } else if (name.startsWith(normalized)) {
                nameStartsWith.push(crypto);
            } else if (symbol.includes(normalized)) {
                symbolContains.push(crypto);
            } else if (name.includes(normalized)) {
                nameContains.push(crypto);
            }
        }

        const results = [
            ...symbolStartsWith,
            ...nameStartsWith,
            ...symbolContains,
            ...nameContains
        ];

        return results.slice(0, MAX_SUGGESTIONS);
    }

    /**
     * Check if query exactly matches a crypto symbol or name
     */
    function findExactMatch(cryptos, query) {
        const normalized = normalizeQuery(query);
        if (!normalized) return null;

        for (const crypto of cryptos) {
            if (normalizeQuery(crypto.symbol) === normalized) {
                return crypto;
            }
            if (normalizeQuery(crypto.name) === normalized) {
                return crypto;
            }
        }
        return null;
    }

    /**
     * Create a crypto autocomplete instance
     */
    function create(container, options = {}) {
        const cryptos = options.cryptos || [];
        const onSelect = options.onSelect || function() {};
        const initialValue = options.initialValue || '';
        const name = options.name || 'crypto';

        const instanceId = ++instanceCounter;
        const inputId = `crypto-input-${instanceId}`;
        const listboxId = `crypto-listbox-${instanceId}`;

        // State
        let filteredCryptos = [];
        let activeIndex = -1;
        let isOpen = false;
        let selectedCrypto = null;

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
                    placeholder="Type to search crypto..."
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
            const initial = cryptos.find(c => c.symbol === initialValue);
            if (initial) {
                selectCrypto(initial, false);
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
            filteredCryptos = filterCryptos(cryptos, query);

            // Auto-select if exact match or only one result
            const exactMatch = findExactMatch(cryptos, query);
            if (exactMatch) {
                selectCrypto(exactMatch, true);
                close();
                return;
            }

            if (filteredCryptos.length === 1) {
                selectCrypto(filteredCryptos[0], true);
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
                        filteredCryptos = filterCryptos(cryptos, input.value);
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
                        selectCrypto(filteredCryptos[activeIndex], true);
                        close();
                    }
                    break;

                case 'Escape':
                    event.preventDefault();
                    close();
                    if (selectedCrypto) {
                        input.value = formatDisplay(selectedCrypto);
                    }
                    break;

                case 'Tab':
                    close();
                    break;
            }
        }

        function handleFocus() {
            if (input.value && !isOpen) {
                filteredCryptos = filterCryptos(cryptos, input.value);
                if (filteredCryptos.length > 0) {
                    render();
                    open();
                }
            }
        }

        function handleBlur() {
            setTimeout(function() {
                close();
                if (selectedCrypto && input.value !== formatDisplay(selectedCrypto)) {
                    input.value = formatDisplay(selectedCrypto);
                }
            }, 150);
        }

        function handleListMouseDown(event) {
            event.preventDefault();
            const option = event.target.closest('[role="option"]');
            if (option) {
                const symbol = option.dataset.symbol;
                const crypto = cryptos.find(c => c.symbol === symbol);
                if (crypto) {
                    selectCrypto(crypto, true);
                    close();
                    input.focus();
                }
            }
        }

        function moveActive(delta) {
            const len = filteredCryptos.length;
            if (len === 0) return;

            if (activeIndex === -1) {
                activeIndex = delta > 0 ? 0 : len - 1;
            } else {
                activeIndex = (activeIndex + delta + len) % len;
            }
            updateActiveDescendant();
        }

        function selectCrypto(crypto, notify) {
            selectedCrypto = crypto;
            input.value = formatDisplay(crypto);
            hiddenInput.value = crypto.symbol;

            if (notify) {
                onSelect(crypto);
                hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        function formatDisplay(crypto) {
            return `${crypto.symbol} \u2014 ${crypto.name}`;
        }

        function open() {
            if (filteredCryptos.length === 0) return;
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
            listbox.innerHTML = filteredCryptos.map(function(c, i) {
                return `
                    <li
                        id="${listboxId}-option-${i}"
                        role="option"
                        aria-selected="false"
                        data-symbol="${c.symbol}"
                        class="autocomplete-option"
                    >
                        <span class="crypto-rank">#${c.rank}</span>
                        <span class="crypto-symbol">${escapeHtml(c.symbol)}</span>
                        <span class="crypto-name">${escapeHtml(c.name)}</span>
                    </li>
                `;
            }).join('');
        }

        // Use shared utility for HTML escaping
        var escapeHtml = ZakatUtils.escapeHtml;

        return {
            getValue: function() {
                return hiddenInput.value;
            },
            setValue: function(symbol) {
                const crypto = cryptos.find(c => c.symbol === symbol);
                if (crypto) {
                    selectCrypto(crypto, false);
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
     * Initialize all crypto autocomplete containers on the page
     */
    function initAll(selector, cryptos, options = {}) {
        const containers = document.querySelectorAll(selector);
        const instances = [];

        containers.forEach(function(container) {
            if (!container._cryptoAutocomplete) {
                const instance = create(container, {
                    ...options,
                    cryptos: cryptos
                });
                container._cryptoAutocomplete = instance;
                instances.push(instance);
            }
        });

        return instances;
    }

    return {
        create: create,
        initAll: initAll,
        filterCryptos: filterCryptos,
        normalizeQuery: normalizeQuery
    };
})();

if (typeof module !== 'undefined' && module.exports) {
    module.exports = CryptoAutocomplete;
}
