"""
Selenium tests for multi-domain hosting (.com, .ca, .net, .org).

Verifies all domains serve content without redirects and canonical tags
always point to whatismyzakat.com.

Run:
    python3 -m pytest tests/test_selenium_multihost.py -v --noconftest
    HEADLESS=0 python3 -m pytest tests/test_selenium_multihost.py -v --noconftest
"""

import os
import pytest

pytest.importorskip("selenium")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

try:
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_WEBDRIVER_MANAGER = True
except ImportError:
    HAS_WEBDRIVER_MANAGER = False


CANONICAL_HOST = 'whatismyzakat.com'
DOMAINS = [
    'whatismyzakat.com',
    'whatismyzakat.ca',
    'whatismyzakat.net',
    'whatismyzakat.org',
]
HEADLESS = os.environ.get('HEADLESS', '1') != '0'


@pytest.fixture(scope='module')
def driver():
    """Create a Chrome WebDriver instance."""
    options = Options()
    if HEADLESS:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    if HAS_WEBDRIVER_MANAGER:
        service = Service(ChromeDriverManager().install())
        d = webdriver.Chrome(service=service, options=options)
    else:
        d = webdriver.Chrome(options=options)

    d.implicitly_wait(10)
    yield d
    d.quit()


class TestMultiDomainServing:
    """All domains serve the site without redirecting."""

    @pytest.mark.parametrize('domain', DOMAINS)
    def test_homepage_loads_200(self, driver, domain):
        """Each domain should serve the homepage (no redirect)."""
        driver.get(f'https://{domain}/')
        assert 'Zakat' in driver.title
        # URL should stay on the same domain (not redirected)
        assert domain in driver.current_url

    @pytest.mark.parametrize('domain', DOMAINS)
    def test_canonical_points_to_com(self, driver, domain):
        """Canonical tag should always reference .com regardless of domain."""
        driver.get(f'https://{domain}/')
        canonical = driver.find_element(By.CSS_SELECTOR, 'link[rel="canonical"]')
        href = canonical.get_attribute('href')
        assert href == f'https://{CANONICAL_HOST}/'

    @pytest.mark.parametrize('domain', DOMAINS)
    def test_og_url_points_to_com(self, driver, domain):
        """og:url meta should always reference .com."""
        driver.get(f'https://{domain}/')
        og = driver.find_element(By.CSS_SELECTOR, 'meta[property="og:url"]')
        assert og.get_attribute('content') == f'https://{CANONICAL_HOST}/'

    @pytest.mark.parametrize('domain', DOMAINS)
    def test_subpage_stays_on_domain(self, driver, domain):
        """Subpages should serve without redirect."""
        driver.get(f'https://{domain}/about-zakat')
        assert domain in driver.current_url
        assert 'About Zakat' in driver.page_source

    @pytest.mark.parametrize('domain', DOMAINS)
    def test_subpage_canonical_points_to_com(self, driver, domain):
        """Subpage canonical should reference .com with correct path."""
        driver.get(f'https://{domain}/about-zakat')
        canonical = driver.find_element(By.CSS_SELECTOR, 'link[rel="canonical"]')
        assert canonical.get_attribute('href') == f'https://{CANONICAL_HOST}/about-zakat'


class TestMultiDomainFunctionality:
    """Calculator works correctly on all domains."""

    @pytest.mark.parametrize('domain', DOMAINS)
    def test_calculator_sections_present(self, driver, domain):
        """Calculator layout and results should render on all domains."""
        driver.get(f'https://{domain}/')
        assert driver.find_element(By.CSS_SELECTOR, '.calculator-layout').is_displayed()
        assert driver.find_element(By.CSS_SELECTOR, '.calculator-results').is_displayed()

    @pytest.mark.parametrize('domain', DOMAINS)
    def test_pricing_api_works(self, driver, domain):
        """Pricing API should respond on all domains."""
        from datetime import date
        today = date.today().isoformat()
        driver.get(f'https://{domain}/api/v1/pricing?date={today}&base=CAD')
        body = driver.find_element(By.TAG_NAME, 'body').text
        assert 'effective_date' in body
        assert 'metals' in body

    @pytest.mark.parametrize('domain', DOMAINS)
    def test_healthz_works(self, driver, domain):
        """Health check should respond on all domains."""
        driver.get(f'https://{domain}/healthz')
        body = driver.find_element(By.TAG_NAME, 'body').text
        assert 'ok' in body.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
