import time
import re
import requests
from bs4 import BeautifulSoup
from app.services.scraper.base_scraper import BaseScraper

class StaticScraper(BaseScraper):
    """HTML Scraper using requests and BeautifulSoup for static pages."""

    def __init__(self, config=None):
        super().__init__(config)
        self.session = requests.Session()
        # Sync session headers
        self.session.headers.update(self.headers)
        
        # Configure retries
        self.max_retries = self.config.get('max_retries', 3)
        self.backoff_factor = 2.0  # multiplier for retry delays

    def _make_request(self, url):
        """Perform HTTP requests with retry logic, back-off, and rate limiting."""
        # Enforce rate limit delay
        if self.rate_limit > 0:
            time.sleep(self.rate_limit)

        retries = 0
        last_error = ""
        
        while retries <= self.max_retries:
            try:
                # Rotate user agent for every request if retry happens
                if retries > 0:
                    self.session.headers.update({'User-Agent': self.get_random_user_agent()})
                
                response = self.session.get(
                    url, 
                    timeout=self.timeout, 
                    proxies=self.proxies, 
                    allow_redirects=True
                )
                
                # Check status
                if response.status_code == 200:
                    return response
                
                # Handling temporary status errors (e.g. 500, 502, 503, 504, 429)
                if response.status_code in [429, 500, 502, 503, 504]:
                    retries += 1
                    sleep_time = self.backoff_factor ** retries
                    time.sleep(sleep_time)
                    last_error = f"HTTP {response.status_code}"
                    continue
                else:
                    response.raise_for_status()
                    
            except requests.RequestException as e:
                retries += 1
                sleep_time = self.backoff_factor ** retries
                time.sleep(sleep_time)
                last_error = str(e)
                
        raise Exception(f"Failed to fetch page after {self.max_retries} retries. Error: {last_error}")

    def scrape(self, url):
        """Scrapes the target URL and extracts data based on configuration."""
        # 1. Robots.txt Validation
        if not self.is_allowed_by_robots(url):
            return False, {}, f"Scraping forbidden by robots.txt policy for URL: {url}"
            
        try:
            # 2. Make Request
            response = self._make_request(url)
            html_content = response.text
            
            # 3. Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 4. Extract Data
            extracted_data = self._extract_content(soup, response.url)
            
            return True, extracted_data, None
            
        except Exception as e:
            return False, {}, str(e)

    def _extract_content(self, soup, page_url):
        """Processes the parsed page to extract both general and target elements."""
        results = {
            "url": page_url,
            "meta": self._extract_metadata(soup),
            "headings": self._extract_headings(soup),
            "paragraphs": self._extract_paragraphs(soup),
            "links": self._extract_links(soup, page_url),
            "contacts": self._extract_contacts(soup),
            "tables": self._extract_tables(soup),
            "media": self._extract_media(soup, page_url)
        }
        
        # Extract custom fields if selectors are defined in config
        custom_selectors = self.config.get('selectors', {})
        if custom_selectors:
            results['custom_fields'] = self._extract_custom_selectors(soup, custom_selectors)
            
        return results

    def _extract_metadata(self, soup):
        """Extracts webpage metadata (title, description, OpenGraph tags)."""
        meta_data = {}
        
        # Title
        meta_data['title'] = soup.title.string.strip() if soup.title else ""
        
        # Meta description
        desc_tag = soup.find('meta', attrs={'name': 'description'}) or \
                   soup.find('meta', attrs={'property': 'og:description'})
        meta_data['description'] = desc_tag['content'].strip() if desc_tag and desc_tag.has_attr('content') else ""
        
        # Meta keywords
        keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
        meta_data['keywords'] = keywords_tag['content'].strip() if keywords_tag and keywords_tag.has_attr('content') else ""
        
        # OpenGraph Title & Image
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        meta_data['og_title'] = og_title['content'].strip() if og_title and og_title.has_attr('content') else ""
        
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        meta_data['og_image'] = og_image['content'].strip() if og_image and og_image.has_attr('content') else ""
        
        return meta_data

    def _extract_headings(self, soup):
        """Extracts h1-h6 headings."""
        headings = {}
        for i in range(1, 7):
            tag_name = f"h{i}"
            headings[tag_name] = [t.get_text(strip=True) for t in soup.find_all(tag_name) if t.get_text(strip=True)]
        return headings

    def _extract_paragraphs(self, soup):
        """Extracts text paragraphs."""
        return [p.get_text(strip=True) for p in soup.find_all('p') if p.get_text(strip=True)]

    def _extract_links(self, soup, base_url):
        """Extracts hyperlink targets and anchor text."""
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            # Resolve relative URLs
            if href.startswith('/'):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            
            anchor_text = a.get_text(strip=True)
            if href.startswith('http'):
                links.append({
                    "url": href,
                    "text": anchor_text or "[No Anchor Text]"
                })
        return links

    def _extract_contacts(self, soup):
        """Extracts email addresses and phone numbers using regex."""
        page_text = soup.get_text()
        
        # Regex search
        email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        phone_regex = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        
        emails = list(set(re.findall(email_regex, page_text)))
        phones = list(set(re.findall(phone_regex, page_text)))
        
        # Filter phone numbers that might just be long digits
        phones = [p.strip() for p in phones if len(re.sub(r'\D', '', p)) >= 10]
        
        return {
            "emails": emails,
            "phones": phones
        }

    def _extract_tables(self, soup):
        """Extracts structured tables into arrays of rows and cell objects."""
        tables_data = []
        for table_idx, table in enumerate(soup.find_all('table')):
            table_rows = []
            
            # Find headers
            headers = [th.get_text(strip=True) for th in table.find_all('th')]
            
            # Find rows
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all('td')]
                if cells:
                    # Map to headers if sizes match, otherwise save list
                    if headers and len(cells) == len(headers):
                        row_dict = dict(zip(headers, cells))
                        table_rows.append(row_dict)
                    else:
                        table_rows.append(cells)
            
            if table_rows:
                tables_data.append({
                    "table_index": table_idx,
                    "headers": headers,
                    "rows": table_rows
                })
        return tables_data

    def _extract_custom_selectors(self, soup, selectors):
        """Extracts custom fields specified by CSS selectors in config."""
        custom_data = {}
        for field_name, selector in selectors.items():
            elements = soup.select(selector)
            if not elements:
                custom_data[field_name] = None
            elif len(elements) == 1:
                custom_data[field_name] = elements[0].get_text(strip=True)
            else:
                custom_data[field_name] = [el.get_text(strip=True) for el in elements]
        return custom_data

    def _extract_media(self, soup, base_url):
        """Extracts media resource URLs (images and videos)."""
        from urllib.parse import urljoin
        media = {
            "images": [],
            "videos": []
        }
        
        # Images
        for img in soup.find_all('img'):
            src = img.get('src')
            if src:
                media['images'].append({
                    "url": urljoin(base_url, src),
                    "alt": img.get('alt', '').strip()
                })
                
        # Videos / Audio / Source files
        for video in soup.find_all('video'):
            # Check src on video tag itself
            src = video.get('src')
            if src:
                media['videos'].append(urljoin(base_url, src))
            # Check source tags inside video
            for source in video.find_all('source'):
                src = source.get('src')
                if src:
                    media['videos'].append(urljoin(base_url, src))
                    
        # Make video lists unique
        media['videos'] = list(set(media['videos']))
        return media

