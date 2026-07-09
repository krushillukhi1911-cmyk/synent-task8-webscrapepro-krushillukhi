from abc import ABC, abstractmethod
import random
import urllib.robotparser
from urllib.parse import urlparse

class BaseScraper(ABC):
    """Abstract Base Class defining the scraper engine interface."""
    
    # Common list of user agents for rotation
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36"
    ]

    def __init__(self, config=None):
        """
        Initialize the scraper with a configuration dictionary.
        Supported keys:
          - headers: custom dict of headers
          - timeout: int, request timeout in seconds
          - proxies: dict of proxy server URLs
          - rate_limit: float, delay between requests in seconds
          - ignore_robots_txt: bool
        """
        self.config = config or {}
        self.timeout = self.config.get('timeout', 15)
        self.proxies = self.config.get('proxies', {})
        self.rate_limit = self.config.get('rate_limit', 1.0)
        self.ignore_robots_txt = self.config.get('ignore_robots_txt', False)
        
        # Prepare headers
        self.headers = self.config.get('headers', {})
        if 'User-Agent' not in self.headers:
            self.headers['User-Agent'] = self.get_random_user_agent()

    def get_random_user_agent(self):
        """Returns a random user-agent string."""
        return random.choice(self.USER_AGENTS)

    def is_allowed_by_robots(self, url):
        """Checks if scraping is permitted by the site's robots.txt."""
        if self.ignore_robots_txt:
            return True
            
        parsed_url = urlparse(url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        
        rp = urllib.robotparser.RobotFileParser()
        try:
            rp.set_url(robots_url)
            # Fetch robots.txt with custom user agent to avoid blockage
            rp.read()
            user_agent = self.headers.get('User-Agent', '*')
            return rp.can_fetch(user_agent, url)
        except Exception as e:
            # If robots.txt cannot be fetched or read, default to allowing
            # to prevent blocking requests on sites without a robots.txt
            return True

    @abstractmethod
    def scrape(self, url):
        """
        Executes the scraping of the URL.
        Must return a tuple: (success: bool, data: dict/list, error_message: str)
        """
        pass
