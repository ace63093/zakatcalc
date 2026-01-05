// Zakat Calculator JavaScript

// Currency symbols
const CURRENCY_SYMBOLS = {
    CAD: '$',
    USD: '$',
    BDT: '\u09F3'
};

// Format currency with appropriate symbol
function formatCurrency(amount, currency) {
    const symbol = CURRENCY_SYMBOLS[currency] || '$';
    return symbol + amount.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Get master currency
function getMasterCurrency() {
    return document.getElementById('masterCurrency').value;
}

// Create gold row HTML
function createGoldRow() {
    const div = document.createElement('div');
    div.className = 'asset-row';
    div.setAttribute('data-type', 'gold');
    div.innerHTML = '<input type="text" name="gold_name" placeholder="Name (e.g., Ring)" class="input-name">' +
        '<input type="number" name="gold_weight" step="0.01" min="0" placeholder="Weight (g)" class="input-weight">' +
        '<select name="gold_karat" class="input-karat">' +
        '<option value="24">24K</option>' +
        '<option value="22" selected>22K</option>' +
        '<option value="21">21K</option>' +
        '<option value="18">18K</option>' +
        '<option value="14">14K</option>' +
        '<option value="10">10K</option>' +
        '<option value="9">9K</option>' +
        '</select>' +
        '<button type="button" class="btn-remove" onclick="removeRow(this)">X</button>';
    return div;
}

// Create cash row HTML
function createCashRow() {
    const currency = getMasterCurrency();
    const div = document.createElement('div');
    div.className = 'asset-row';
    div.setAttribute('data-type', 'cash');
    div.innerHTML = '<input type="text" name="cash_name" placeholder="Name (e.g., Wallet)" class="input-name">' +
        '<input type="number" name="cash_amount" step="0.01" min="0" placeholder="Amount" class="input-amount">' +
        '<select name="cash_currency" class="input-currency">' +
        '<option value="CAD"' + (currency === 'CAD' ? ' selected' : '') + '>CAD</option>' +
        '<option value="USD"' + (currency === 'USD' ? ' selected' : '') + '>USD</option>' +
        '<option value="BDT"' + (currency === 'BDT' ? ' selected' : '') + '>BDT</option>' +
        '</select>' +
        '<button type="button" class="btn-remove" onclick="removeRow(this)">X</button>';
    return div;
}

// Create bank row HTML
function createBankRow() {
    const currency = getMasterCurrency();
    const div = document.createElement('div');
    div.className = 'asset-row';
    div.setAttribute('data-type', 'bank');
    div.innerHTML = '<input type="text" name="bank_name" placeholder="Name (e.g., Savings)" class="input-name">' +
        '<input type="number" name="bank_amount" step="0.01" min="0" placeholder="Amount" class="input-amount">' +
        '<select name="bank_currency" class="input-currency">' +
        '<option value="CAD"' + (currency === 'CAD' ? ' selected' : '') + '>CAD</option>' +
        '<option value="USD"' + (currency === 'USD' ? ' selected' : '') + '>USD</option>' +
        '<option value="BDT"' + (currency === 'BDT' ? ' selected' : '') + '>BDT</option>' +
        '</select>' +
        '<button type="button" class="btn-remove" onclick="removeRow(this)">X</button>';
    return div;
}

// Add row functions
function addGoldRow() {
    document.getElementById('goldItems').appendChild(createGoldRow());
}

function addCashRow() {
    document.getElementById('cashItems').appendChild(createCashRow());
}

function addBankRow() {
    document.getElementById('bankItems').appendChild(createBankRow());
}

// Remove row
function removeRow(button) {
    const row = button.closest('.asset-row');
    const container = row.parentElement;
    // Keep at least one row
    if (container.querySelectorAll('.asset-row').length > 1) {
        row.remove();
    } else {
        // Clear the row instead
        row.querySelectorAll('input').forEach(function(input) { input.value = ''; });
    }
}

// Collect gold items from form
function collectGoldItems() {
    const items = [];
    document.querySelectorAll('#goldItems .asset-row').forEach(function(row) {
        const weight = parseFloat(row.querySelector('[name="gold_weight"]').value) || 0;
        if (weight > 0) {
            items.push({
                name: row.querySelector('[name="gold_name"]').value || 'Gold',
                weight_grams: weight,
                purity_karat: parseInt(row.querySelector('[name="gold_karat"]').value)
            });
        }
    });
    return items;
}

// Collect cash items from form
function collectCashItems() {
    const items = [];
    document.querySelectorAll('#cashItems .asset-row').forEach(function(row) {
        const amount = parseFloat(row.querySelector('[name="cash_amount"]').value) || 0;
        if (amount > 0) {
            items.push({
                name: row.querySelector('[name="cash_name"]').value || 'Cash',
                amount: amount,
                currency: row.querySelector('[name="cash_currency"]').value
            });
        }
    });
    return items;
}

// Collect bank items from form
function collectBankItems() {
    const items = [];
    document.querySelectorAll('#bankItems .asset-row').forEach(function(row) {
        const amount = parseFloat(row.querySelector('[name="bank_amount"]').value) || 0;
        if (amount > 0) {
            items.push({
                name: row.querySelector('[name="bank_name"]').value || 'Bank',
                amount: amount,
                currency: row.querySelector('[name="bank_currency"]').value
            });
        }
    });
    return items;
}

// Display error message
function showError(message) {
    // Remove existing error
    const existing = document.querySelector('.error-message');
    if (existing) existing.remove();

    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    document.getElementById('zakatForm').appendChild(errorDiv);
}

// Calculate zakat via API
async function calculateZakat(event) {
    event.preventDefault();

    // Remove existing error
    const existing = document.querySelector('.error-message');
    if (existing) existing.remove();

    const masterCurrency = getMasterCurrency();
    const gold = collectGoldItems();
    const cash = collectCashItems();
    const bank = collectBankItems();

    // Check if there is anything to calculate
    if (gold.length === 0 && cash.length === 0 && bank.length === 0) {
        showError('Please enter at least one asset.');
        return;
    }

    try {
        const response = await fetch('/api/v1/calculate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                master_currency: masterCurrency,
                gold: gold,
                cash: cash,
                bank: bank
            })
        });

        const data = await response.json();

        if (!response.ok) {
            showError(data.error || 'Calculation failed');
            return;
        }

        // Display results
        document.getElementById('goldTotal').textContent = formatCurrency(data.subtotals.gold.total, masterCurrency);
        document.getElementById('cashTotal').textContent = formatCurrency(data.subtotals.cash.total, masterCurrency);
        document.getElementById('bankTotal').textContent = formatCurrency(data.subtotals.bank.total, masterCurrency);
        document.getElementById('grandTotal').textContent = formatCurrency(data.grand_total, masterCurrency);
        document.getElementById('nisabThreshold').textContent = formatCurrency(data.nisab_threshold, masterCurrency);
        document.getElementById('aboveNisab').textContent = data.above_nisab ? 'Yes' : 'No';
        document.getElementById('zakatDue').textContent = formatCurrency(data.zakat_due, masterCurrency);

        document.getElementById('result').classList.add('show');

    } catch (error) {
        console.error('Calculation error:', error);
        showError('Failed to calculate. Please try again.');
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('zakatForm').addEventListener('submit', calculateZakat);
});
