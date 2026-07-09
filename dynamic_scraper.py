import time
import random
from app.services.scraper.static_scraper import StaticScraper
from bs4 import BeautifulSoup

# Playwright might not be installed, wrap imports gracefully
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

class DynamicScraper(StaticScraper):
    """Dynamic Scraper using headless Playwright for JS-rendered pages."""

    def __init__(self, config=None):
        super().__init__(config)
        self.browser_type = self.config.get('browser_type', 'chromium')
        self.headless = self.config.get('headless', True)
        self.scroll_pages = self.config.get('scroll_pages', 2)  # number of times to scroll down
        self.wait_time = self.config.get('wait_time', 3.0)  # seconds to wait for page stability

    def scrape(self, url):
        """Scrapes target URL dynamically via headless browser."""
        # 1. Robots.txt check
        if not self.is_allowed_by_robots(url):
            return False, {}, f"Scraping forbidden by robots.txt policy for URL: {url}"

        if not PLAYWRIGHT_AVAILABLE:
            return False, {}, (
                "Playwright library is not installed or configured in this environment. "
                "Please run 'pip install playwright' and 'playwright install' to enable dynamic scraping."
            )

        try:
            # Enforce rate limit delay
            if self.rate_limit > 0:
                time.sleep(self.rate_limit)

            with sync_playwright() as p:
                # 2. Choose browser type
                if self.browser_type == 'firefox':
                    browser_launcher = p.firefox
                elif self.browser_type == 'webkit':
                    browser_launcher = p.webkit
                else:
                    browser_launcher = p.chromium

                # 3. Launch browser with anti-bot argument mitigations
                args = [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
                
                browser = browser_launcher.launch(
                    headless=self.headless, 
                    args=args
                )
                
                # Create context with custom user agent and window size
                user_agent = self.headers.get('User-Agent', self.get_random_user_agent())
                context = browser.new_context(
                    user_agent=user_agent,
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    timezone_id="America/New_York"
                )
                
                # Prevent navigator.webdriver indicator
                page = context.new_page()
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                # Set extra headers
                extra_headers = {k: v for k, v in self.headers.items() if k.lower() != 'user-agent'}
                if extra_headers:
                    page.set_extra_http_headers(extra_headers)

                # Set proxy if defined
                # Playwright supports proxies at context level. For simplicity, we assume proxies
                # config in playwright uses browser launch options, but context works as well.

                # 4. Navigate to URL
                response = page.goto(url, timeout=self.timeout * 1000, wait_until="load")
                
                # Check response status code
                status = response.status if response else 0
                if status != 200:
                    browser.close()
                    return False, {}, f"Failed to fetch dynamic page. HTTP status code: {status}"

                # 5. Emulate human interactions (scrolling down for lazy-loaded assets)
                if self.scroll_pages > 0:
                    self._emulate_scrolling(page)
                
                # Wait for network idle or a specific delay
                time.sleep(self.wait_time)
                
                # 6. Extract rendered HTML content
                html_content = page.content()
                final_url = page.url
                
                browser.close()

            # 7. Parse rendered HTML using BeautifulSoup to reuse parser pipelines
            soup = BeautifulSoup(html_content, 'html.parser')
            extracted_data = self._extract_content(soup, final_url)
            
            return True, extracted_data, None

        except Exception as e:
            return False, {}, f"Dynamic scraping failed: {str(e)}"

    def _emulate_scrolling(self, page):
        """Scrolls the page down incrementally to trigger lazy loaders and infinite scrolling."""
        viewport_height = page.viewport_size["height"] if page.viewport_size else 800
        
        for i in range(self.scroll_pages):
            # Calculate scroll target
            scroll_target = viewport_height * (i + 1)
            
            # Perform scroll with small randomized delays to mimic real human behavior
            page.evaluate(f"window.scrollTo(0, {scroll_target})")
            
            # Randomized human-like pause
            time.sleep(random.uniform(0.5, 1.5))
            
            # Scroll slightly back and down again to mimic a reader
            page.evaluate(f"window.scrollTo(0, {scroll_target - 50})")
            time.sleep(random.uniform(0.2, 0.4))
            page.evaluate(f"window.scrollTo(0, {scroll_target})")
            
            # Let new contents render
            time.sleep(random.uniform(0.5, 1.0))
            
        # Scroll back to the top of the page
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)
