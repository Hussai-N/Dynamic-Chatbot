import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import re
import sys
import time
from urllib.parse import urljoin, urlparse
from collections import deque

def get_page_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    soup = None
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        # Remove scripts and styles for text extraction
        for script in soup(["script", "style"]):
            script.decompose()
        static_text = soup.get_text(separator=" ", strip=True)
        
        # Detect if JavaScript is required
        js_required_patterns = [
            r"enable javascript",
            r"javascript to run this app",
            r"you need to enable javascript",
            r"javascript is disabled"
        ]
        if any(re.search(pattern, static_text.lower()) for pattern in js_required_patterns):
            # Fallback to Playwright for JS rendering
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=[
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-accelerated-2d-canvas',
                            '--no-first-run',
                            '--no-zygote',
                            '--disable-gpu',
                            '--disable-blink-features=AutomationControlled'
                        ]
                    )
                    context = browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        extra_http_headers={
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Connection': 'keep-alive',
                        },
                        permissions=['geolocation']
                    )
                    page = context.new_page()
                    page.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined,
                        });
                        delete navigator.__proto__.webdriver;
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5],
                        });
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['en-US', 'en'],
                        });
                        window.chrome = {
                            runtime: {},
                        };
                    """)
                    page.goto(url, wait_until='load', timeout=60000)
                    page.wait_for_load_state('networkidle', timeout=30000)
                    time.sleep(2)  # Reduced sleep for efficiency
                    html = page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    # Remove scripts and styles
                    for script in soup(["script", "style"]):
                        script.decompose()
                    text = soup.get_text(separator=" ", strip=True).strip()
                    browser.close()
                return text, soup
            except Exception as e:
                print(f"Warning: Could not render JavaScript ({e}). Falling back to static content.")
                text = static_text
                return text, soup
        else:
            text = static_text
            return text, soup
    except Exception as e:
        # Fallback to Playwright if requests fails
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--disable-gpu',
                        '--disable-blink-features=AutomationControlled'
                    ]
                )
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    extra_http_headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                    },
                    permissions=['geolocation']
                )
                page = context.new_page()
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                    delete navigator.__proto__.webdriver;
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en'],
                    });
                    window.chrome = {
                        runtime: {},
                    };
                """)
                page.goto(url, wait_until='load', timeout=60000)
                page.wait_for_load_state('networkidle', timeout=30000)
                time.sleep(2)  # Reduced sleep
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                # Remove scripts and styles
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text(separator=" ", strip=True).strip()
                browser.close()
            return text, soup
        except Exception as pw_e:
            error_msg = f"Error fetching the website with both methods: {e} (requests), {pw_e} (Playwright)"
            print(error_msg)
            return error_msg, None


def scrape_website(start_url, max_depth=1, delay=1.0):
    """
    Scrapes the starting URL and follows internal links up to max_depth.
    Returns combined text from all visited pages.
    """
    domain = urlparse(start_url).netloc
    visited = set()
    to_visit = deque([(start_url, 0)])  # (url, depth)
    all_text = []

    while to_visit:
        url, depth = to_visit.popleft()
        if url in visited or depth > max_depth:
            continue
        visited.add(url)

        text, soup = get_page_content(url)
        if isinstance(text, str) and not text.startswith("Error"):
            all_text.append(text)
        else:
            print(f"Skipping {url} due to error.")

        if depth >= max_depth or soup is None:
            time.sleep(delay)
            continue

        # Extract internal links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('#') or href.startswith('javascript:'):
                continue
            full_url = urljoin(url, href)
            parsed_url = urlparse(full_url)
            if (parsed_url.scheme in ('http', 'https') and
                parsed_url.netloc == domain and
                full_url not in visited):
                to_visit.append((full_url, depth + 1))

        time.sleep(delay)

    return '\n\n---\n\n'.join(all_text)
