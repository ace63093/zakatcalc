"""
Selenium live tests for whatismyzakat.com

These tests run against the live production site to verify user-facing functionality.

Requirements:
    pip install selenium webdriver-manager

Run:
    pytest tests/test_selenium_live.py -v
    pytest tests/test_selenium_live.py -v -k test_calculator_loads

Environment:
    LIVE_TEST_URL: Override the default URL (default: https://whatismyzakat.com)
    HEADLESS: Set to '0' to see the browser (default: '1' = headless)
"""

import os
import pytest
from datetime import date

# Skip all tests if selenium not installed
pytest.importorskip("selenium")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

try:
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_WEBDRIVER_MANAGER = True
except ImportError:
    HAS_WEBDRIVER_MANAGER = False


BASE_URL = os.environ.get('LIVE_TEST_URL', 'https://whatismyzakat.com')
HEADLESS = os.environ.get('HEADLESS', '1') != '0'


@pytest.fixture(scope='module')
def driver():
    """Create a Chrome WebDriver instance."""
    options = Options()
    if HEADLESS:
        options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    if HAS_WEBDRIVER_MANAGER:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    driver.implicitly_wait(10)
    yield driver
    driver.quit()


class TestCalculatorPage:
    """Tests for the main calculator page."""

    def test_calculator_loads(self, driver):
        """Verify calculator page loads successfully."""
        driver.get(BASE_URL)
        assert 'Zakat' in driver.title

        # Check main sections exist
        assert driver.find_element(By.CSS_SELECTOR, '.calculator-layout')
        assert driver.find_element(By.CSS_SELECTOR, '.calculator-results')

    def test_base_currency_selector(self, driver):
        """Verify base currency selector works."""
        driver.get(BASE_URL)

        # Find the base currency input (inside the container)
        base_currency_container = driver.find_element(By.ID, 'baseCurrencyContainer')
        base_currency = base_currency_container.find_element(By.CSS_SELECTOR, 'input')
        # Value shows full display like "CAD — Canadian Dollar"
        assert 'CAD' in base_currency.get_attribute('value')

        # Click to open dropdown
        base_currency.click()

        # Wait for dropdown to appear (it's a ul.autocomplete-listbox that becomes visible)
        WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '.autocomplete-listbox'))
        )

    def test_date_picker_shows_today(self, driver):
        """Verify date picker defaults to today (or close to it due to timezone)."""
        driver.get(BASE_URL)

        date_input = driver.find_element(By.ID, 'calculationDate')
        selected_date = date_input.get_attribute('value')

        # Should be today or yesterday/tomorrow (due to timezone differences)
        today = date.today()
        acceptable_dates = [
            (today - __import__('datetime').timedelta(days=1)).isoformat(),
            today.isoformat(),
            (today + __import__('datetime').timedelta(days=1)).isoformat(),
        ]
        assert selected_date in acceptable_dates

    def test_add_gold_item(self, driver):
        """Test adding a gold item."""
        driver.get(BASE_URL)

        # Find and click "Add Gold" button (uses onclick="addGoldRow()")
        add_gold_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Add Gold')]")
        add_gold_btn.click()

        # Verify a gold row was added
        gold_rows = driver.find_elements(By.CSS_SELECTOR, '.asset-row[data-type="gold"]')
        assert len(gold_rows) >= 1

        # Fill in weight
        weight_input = gold_rows[-1].find_element(By.CSS_SELECTOR, '.input-weight')
        weight_input.clear()
        weight_input.send_keys('10')

        # Wait for recalculation
        WebDriverWait(driver, 5).until(
            lambda d: gold_rows[-1].find_element(
                By.CSS_SELECTOR, '.base-value-pill'
            ).text != '—'
        )

    def test_add_cash_item(self, driver):
        """Test adding a cash item."""
        driver.get(BASE_URL)

        # Find and click "Add Cash" button (uses onclick="addCashRow()")
        add_cash_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Add Cash')]")
        add_cash_btn.click()

        # Verify a cash row was added
        cash_rows = driver.find_elements(By.CSS_SELECTOR, '.asset-row[data-type="cash"]')
        assert len(cash_rows) >= 1

        # Fill in amount
        amount_input = cash_rows[-1].find_element(By.CSS_SELECTOR, '.input-amount')
        amount_input.clear()
        amount_input.send_keys('1000')

        # Wait for recalculation
        WebDriverWait(driver, 5).until(
            lambda d: cash_rows[-1].find_element(
                By.CSS_SELECTOR, '.base-value-pill'
            ).text != '—'
        )

    def test_results_panel_updates(self, driver):
        """Test that results panel updates with totals."""
        import re
        driver.get(BASE_URL)

        # Add a cash item with significant value (uses onclick="addCashRow()")
        add_cash_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Add Cash')]")
        add_cash_btn.click()

        cash_rows = driver.find_elements(By.CSS_SELECTOR, '.asset-row[data-type="cash"]')
        amount_input = cash_rows[-1].find_element(By.CSS_SELECTOR, '.input-amount')
        amount_input.clear()
        amount_input.send_keys('50000')

        # Wait for total to update (extract numeric value from formatted currency)
        total_element = driver.find_element(By.ID, 'grandTotal')

        def extract_numeric(text):
            """Extract numeric value from currency text like '$50,000.00' or 'CA$50,000.00'."""
            match = re.search(r'[\d,]+\.?\d*', text.replace(',', ''))
            return float(match.group()) if match else 0

        WebDriverWait(driver, 5).until(
            lambda d: extract_numeric(total_element.text) > 0
        )

        # Check zakat amount is calculated
        zakat_element = driver.find_element(By.ID, 'zakatDue')
        assert extract_numeric(zakat_element.text) > 0

    def test_nisab_indicator_visible(self, driver):
        """Test nisab indicator card is visible."""
        driver.get(BASE_URL)

        nisab_card = driver.find_element(By.CSS_SELECTOR, '.nisab-indicator')
        assert nisab_card.is_displayed()

        # Should show threshold value with gold/silver toggle buttons
        threshold_value = driver.find_element(By.CSS_SELECTOR, '.nisab-indicator .threshold-value')
        toggle_buttons = driver.find_elements(By.CSS_SELECTOR, '.nisab-toggle-btn')

        # Should have gold and silver toggle buttons
        assert len(toggle_buttons) == 2

        # Threshold value should be populated after pricing loads
        WebDriverWait(driver, 5).until(
            lambda d: threshold_value.text not in ('', '--')
        )


class TestPricingAPI:
    """Tests for pricing API via browser."""

    def test_pricing_endpoint_returns_data(self, driver):
        """Verify pricing API returns valid data."""
        today = date.today().isoformat()
        driver.get(f'{BASE_URL}/api/v1/pricing?date={today}&base=CAD')

        # Page should contain JSON response
        body = driver.find_element(By.TAG_NAME, 'body').text
        assert 'effective_date' in body
        assert 'metals' in body
        assert 'fx_rates' in body

    def test_sync_status_endpoint(self, driver):
        """Verify sync status endpoint is accessible."""
        driver.get(f'{BASE_URL}/api/v1/pricing/sync-status')

        body = driver.find_element(By.TAG_NAME, 'body').text
        assert 'sync_enabled' in body
        assert 'data_coverage' in body


class TestNavigation:
    """Tests for site navigation."""

    def test_nav_links_work(self, driver):
        """Test that navigation links work."""
        driver.get(BASE_URL)

        # Test About Zakat link
        about_link = driver.find_element(By.LINK_TEXT, 'About Zakat')
        about_link.click()
        WebDriverWait(driver, 5).until(EC.url_contains('/about-zakat'))
        assert '/about-zakat' in driver.current_url

        # Test FAQ link
        driver.get(BASE_URL)
        faq_link = driver.find_element(By.LINK_TEXT, 'FAQ')
        faq_link.click()
        WebDriverWait(driver, 5).until(EC.url_contains('/faq'))
        assert '/faq' in driver.current_url

        # Test Contact link
        driver.get(BASE_URL)
        contact_link = driver.find_element(By.LINK_TEXT, 'Contact Us')
        contact_link.click()
        WebDriverWait(driver, 5).until(EC.url_contains('/contact'))
        assert '/contact' in driver.current_url

    def test_contribute_button_exists(self, driver):
        """Test that contribute button is present."""
        driver.get(BASE_URL)

        contribute_link = driver.find_element(By.LINK_TEXT, 'Contribute')
        assert contribute_link.is_displayed()
        assert 'buymeacoffee' in contribute_link.get_attribute('href')


class TestShareAndExport:
    """Tests for share link and CSV export."""

    def test_share_link_button_exists(self, driver):
        """Test share link button is present."""
        driver.get(BASE_URL)

        share_btn = driver.find_element(By.ID, 'share-link-btn')
        assert share_btn.is_displayed()

    def test_csv_export_button_exists(self, driver):
        """Test CSV export button is present."""
        driver.get(BASE_URL)

        export_btn = driver.find_element(By.ID, 'export-csv-btn')
        assert export_btn.is_displayed()


class TestResponsive:
    """Tests for responsive layout."""

    def test_mobile_layout(self, driver):
        """Test calculator works on mobile viewport."""
        driver.set_window_size(375, 812)  # iPhone X size
        driver.get(BASE_URL)

        # Calculator should still be visible
        calc = driver.find_element(By.CSS_SELECTOR, '.calculator-layout')
        assert calc.is_displayed()

        # Results section should be visible
        results = driver.find_element(By.CSS_SELECTOR, '.calculator-results')
        assert results.is_displayed()

    def test_tablet_layout(self, driver):
        """Test calculator works on tablet viewport."""
        driver.set_window_size(768, 1024)  # iPad size
        driver.get(BASE_URL)

        calc = driver.find_element(By.CSS_SELECTOR, '.calculator-layout')
        assert calc.is_displayed()

    def test_desktop_layout(self, driver):
        """Test calculator works on desktop viewport."""
        driver.set_window_size(1920, 1080)
        driver.get(BASE_URL)

        calc = driver.find_element(By.CSS_SELECTOR, '.calculator-layout')
        assert calc.is_displayed()


class TestCadToBdtConverter:
    """Tests for the CAD to BDT converter page."""

    def test_page_loads(self, driver):
        """Verify CAD to BDT page loads successfully."""
        driver.get(f'{BASE_URL}/cad-to-bdt')
        assert 'CAD to BDT' in driver.title

        # Check main card exists
        card = driver.find_element(By.CSS_SELECTOR, '.cad-bdt-card')
        assert card.is_displayed()

    def test_date_picker_exists(self, driver):
        """Verify date picker is present and defaults to today."""
        driver.get(f'{BASE_URL}/cad-to-bdt')

        date_input = driver.find_element(By.ID, 'rateDateInput')
        assert date_input.is_displayed()

        # Should have a value (today's date)
        selected_date = date_input.get_attribute('value')
        assert selected_date  # Not empty

    def test_converter_inputs_exist(self, driver):
        """Verify CAD and BDT input fields are present."""
        driver.get(f'{BASE_URL}/cad-to-bdt')

        cad_input = driver.find_element(By.ID, 'cadAmount')
        bdt_input = driver.find_element(By.ID, 'bdtAmount')

        assert cad_input.is_displayed()
        assert bdt_input.is_displayed()

    def test_rate_displays_after_load(self, driver):
        """Verify exchange rate is displayed after page loads."""
        driver.get(f'{BASE_URL}/cad-to-bdt')

        # Wait for rate to load (displayBdt should show a number, not '—')
        display_bdt = driver.find_element(By.ID, 'displayBdt')
        WebDriverWait(driver, 10).until(
            lambda d: display_bdt.text != '—' and display_bdt.text != ''
        )

        # Rate should be a reasonable number (BDT is typically 80-120 per CAD)
        rate_text = display_bdt.text.replace(',', '')
        rate_value = float(rate_text)
        assert 50 < rate_value < 200  # Reasonable range for CAD to BDT

    def test_cad_input_updates_bdt(self, driver):
        """Test that entering CAD amount updates BDT amount."""
        driver.get(f'{BASE_URL}/cad-to-bdt')

        # Wait for rate to load first
        display_bdt = driver.find_element(By.ID, 'displayBdt')
        WebDriverWait(driver, 10).until(
            lambda d: display_bdt.text != '—'
        )

        # Enter CAD amount
        cad_input = driver.find_element(By.ID, 'cadAmount')
        cad_input.clear()
        cad_input.send_keys('100')

        # BDT input should update
        bdt_input = driver.find_element(By.ID, 'bdtAmount')
        WebDriverWait(driver, 5).until(
            lambda d: bdt_input.get_attribute('value') not in ('', '0')
        )

        bdt_value = float(bdt_input.get_attribute('value'))
        assert bdt_value > 0  # Should have a positive conversion


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
