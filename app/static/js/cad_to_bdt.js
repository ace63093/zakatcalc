(function() {
    'use strict';

    var dateInput = document.getElementById('rateDateInput');
    var cadInput = document.getElementById('cadAmount');
    var bdtInput = document.getElementById('bdtAmount');
    var displayCad = document.getElementById('displayCad');
    var displayBdt = document.getElementById('displayBdt');
    var rateValue = document.getElementById('rateValue');
    var rateDate = document.getElementById('rateDate');
    var rateNote = document.getElementById('rateNote');
    var statusMessage = document.getElementById('statusMessage');

    var currentCadToBdt = null;
    var currentBdtToCad = null;
    var lastEdited = 'cad';
    var isUpdating = false;

    function getLocalDateString() {
        var now = new Date();
        var local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
        return local.toISOString().slice(0, 10);
    }

    function formatRate(value, maxFractionDigits) {
        if (!Number.isFinite(value)) return '—';
        var formatter = new Intl.NumberFormat('en-US', {
            maximumFractionDigits: maxFractionDigits,
            minimumFractionDigits: 0
        });
        return formatter.format(value);
    }

    function formatInputValue(value, decimals) {
        if (!Number.isFinite(value)) return '';
        var factor = Math.pow(10, decimals);
        var rounded = Math.round(value * factor) / factor;
        return rounded.toFixed(decimals);
    }

    function formatDisplayAmount(value) {
        if (!Number.isFinite(value)) return '—';
        return new Intl.NumberFormat('en-US', {
            maximumFractionDigits: 2,
            minimumFractionDigits: 0
        }).format(value);
    }

    function setStatus(message, status) {
        if (!statusMessage) return;
        statusMessage.textContent = message || '';
        if (status) {
            statusMessage.setAttribute('data-status', status);
        } else {
            statusMessage.removeAttribute('data-status');
        }
    }

    function updateHeaderAmounts(cadValue, bdtValue) {
        if (!displayCad || !displayBdt) return;
        displayCad.textContent = formatDisplayAmount(cadValue);
        displayBdt.textContent = formatDisplayAmount(bdtValue);
    }

    function updateRateDisplay(data) {
        if (!data) return;
        rateValue.textContent = formatRate(currentCadToBdt, 4);

        var requested = (data.request && data.request.date) || dateInput.value;
        var effective = data.effective_date || requested;

        rateDate.textContent = effective;

        if (effective !== requested) {
            rateNote.textContent = 'Using nearest available date ' + effective + ' for ' + requested + '.';
            rateNote.hidden = false;
        } else {
            rateNote.textContent = '';
            rateNote.hidden = true;
        }
    }

    function clearRateDisplay() {
        rateValue.textContent = '—';
        rateDate.textContent = '—';
        rateNote.textContent = '';
        rateNote.hidden = true;
        updateHeaderAmounts(NaN, NaN);
    }

    function handleCadInput() {
        if (isUpdating) return;
        lastEdited = 'cad';

        if (!currentCadToBdt) {
            bdtInput.value = '';
            updateHeaderAmounts(NaN, NaN);
            return;
        }

        var amount = parseFloat(cadInput.value);
        if (!Number.isFinite(amount)) {
            bdtInput.value = '';
            updateHeaderAmounts(NaN, NaN);
            return;
        }

        isUpdating = true;
        var bdtValue = amount * currentCadToBdt;
        bdtInput.value = formatInputValue(bdtValue, 2);
        isUpdating = false;
        updateHeaderAmounts(amount, bdtValue);
    }

    function handleBdtInput() {
        if (isUpdating) return;
        lastEdited = 'bdt';

        if (!currentBdtToCad) {
            cadInput.value = '';
            updateHeaderAmounts(NaN, NaN);
            return;
        }

        var amount = parseFloat(bdtInput.value);
        if (!Number.isFinite(amount)) {
            cadInput.value = '';
            updateHeaderAmounts(NaN, NaN);
            return;
        }

        isUpdating = true;
        var cadValue = amount * currentBdtToCad;
        cadInput.value = formatInputValue(cadValue, 2);
        isUpdating = false;
        updateHeaderAmounts(cadValue, amount);
    }

    function updateConversionFields() {
        if (lastEdited === 'bdt') {
            handleBdtInput();
        } else {
            handleCadInput();
        }
    }

    function ensureDefaultAmount() {
        if (!cadInput.value && !bdtInput.value) {
            cadInput.value = '1';
            lastEdited = 'cad';
        }
    }

    function loadPricing(dateStr) {
        setStatus('Loading pricing...', 'loading');
        clearRateDisplay();

        return fetch('/api/v1/pricing?date=' + dateStr + '&base=CAD')
            .then(function(response) {
                return response.json().then(function(data) {
                    if (!response.ok) {
                        throw new Error((data && data.error) || 'Failed to load pricing');
                    }
                    return data;
                });
            })
            .then(function(data) {
                var fxRates = data.fx_rates || {};
                var bdtRateToCad = fxRates.BDT;

                if (!bdtRateToCad) {
                    throw new Error('BDT rate not available for this date.');
                }

                currentBdtToCad = bdtRateToCad;
                currentCadToBdt = 1 / bdtRateToCad;

                updateRateDisplay(data);
                ensureDefaultAmount();
                updateConversionFields();
                setStatus('', null);
            })
            .catch(function(error) {
                currentBdtToCad = null;
                currentCadToBdt = null;
                setStatus(error.message, 'error');
            });
    }

    if (!dateInput || !cadInput || !bdtInput) {
        return;
    }

    dateInput.addEventListener('change', function() {
        if (!dateInput.value) return;
        loadPricing(dateInput.value);
    });

    cadInput.addEventListener('input', handleCadInput);
    bdtInput.addEventListener('input', handleBdtInput);

    var defaultDate = getLocalDateString();
    dateInput.value = defaultDate;
    loadPricing(defaultDate);
})();
