import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import re
import time
import logging
from pathlib import Path
from feedgen.feed import FeedGenerator

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://mustafa-suleyman.ai"


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def ensure_feeds_directory():
    """Ensure the feeds directory exists."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def setup_selenium_driver():
    """Set up Selenium WebDriver with undetected-chromedriver."""
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return uc.Chrome(options=options)


def fetch_blog_content_selenium(url=BASE_URL):
    """Fetch the fully loaded HTML content using Selenium."""
    driver = None
    try:
        logger.info(f"Fetching content from URL: {url}")
        driver = setup_selenium_driver()
        driver.get(url)

        # Wait for the page to fully load
        wait_time = 10
        logger.info(f"Waiting {wait_time} seconds for the page to fully load...")
        time.sleep(wait_time)

        # Try to scroll to the writing section to trigger lazy loading
        try:
            driver.execute_script("document.querySelector('#writing')?.scrollIntoView()")
            time.sleep(3)
        except:
            pass

        # Wait for writing section content to load
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            # Wait for any article links to appear
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='writing'], a[href*='blog'], article a"))
            )
            logger.info("Writing section loaded successfully")
        except Exception as e:
            logger.warning(f"Could not confirm writing section loaded: {e}")

        html_content = driver.page_source
        logger.info("Successfully fetched HTML content")
        return html_content

    except Exception as e:
        logger.error(f"Error fetching content: {e}")
        raise
    finally:
        if driver:
            driver.quit()


def parse_date(date_text):
    """Parse date string."""
    date_formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%Y-%m-%d",
        "%d %B %Y",
        "%d %b %Y",
        "%m/%d/%Y",
    ]

    date_text = date_text.strip()
    for fmt in date_formats:
        try:
            date_obj = datetime.strptime(date_text, fmt)
            return date_obj.replace(tzinfo=pytz.UTC)
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_text}")
    return None


def parse_blog_html(html_content):
    """Parse the blog HTML content and extract post information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []
        seen_links = set()

        # Try multiple strategies to find blog posts

        # Strategy 1: Look for article elements
        articles = soup.find_all('article')
        for article in articles:
            link = article.find('a', href=True)
            if link:
                post = extract_post_from_element(article, link, seen_links)
                if post:
                    blog_posts.append(post)

        # Strategy 2: Look for links in the writing section
        writing_section = soup.find(id='writing') or soup.find(class_=re.compile(r'writing', re.I))
        if writing_section:
            links = writing_section.find_all('a', href=True)
            for link in links:
                post = extract_post_from_element(link.parent, link, seen_links)
                if post:
                    blog_posts.append(post)

        # Strategy 3: Look for any links that look like blog posts
        all_links = soup.find_all('a', href=re.compile(r'(blog|writing|post|article)', re.I))
        for link in all_links:
            post = extract_post_from_element(link.parent, link, seen_links)
            if post:
                blog_posts.append(post)

        # Strategy 4: Look for card-like structures with titles
        cards = soup.find_all(['div', 'li'], class_=re.compile(r'(card|post|article|item)', re.I))
        for card in cards:
            link = card.find('a', href=True)
            if link:
                post = extract_post_from_element(card, link, seen_links)
                if post:
                    blog_posts.append(post)

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def extract_post_from_element(container, link, seen_links):
    """Extract post information from a container element."""
    href = link.get('href', '')
    if not href or href in seen_links or href == '#' or href == '/':
        return None

    # Skip navigation links, social links, etc.
    skip_patterns = ['twitter', 'linkedin', 'facebook', 'instagram', 'youtube', 'mailto:', 'tel:', '#', 'javascript:']
    if any(pattern in href.lower() for pattern in skip_patterns):
        return None

    seen_links.add(href)

    # Construct full URL
    if href.startswith('http'):
        full_url = href
    elif href.startswith('/'):
        full_url = f"{BASE_URL}{href}"
    else:
        full_url = f"{BASE_URL}/{href}"

    # Extract title
    title = None
    for selector in ['h1', 'h2', 'h3', 'h4', 'strong', '.title', '[class*="title"]']:
        title_elem = container.select_one(selector) if hasattr(container, 'select_one') else None
        if title_elem:
            title = title_elem.get_text(strip=True)
            if title and len(title) > 3:
                break

    if not title:
        title = link.get_text(strip=True)

    if not title or len(title) < 3:
        return None

    # Skip if title looks like navigation
    nav_words = ['home', 'about', 'contact', 'menu', 'search', 'sign in', 'log in']
    if title.lower() in nav_words:
        return None

    # Extract date
    date = None
    date_patterns = [
        r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
        r'(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})',
        r'(\d{4}-\d{2}-\d{2})',
    ]

    container_text = container.get_text() if container else ''
    for pattern in date_patterns:
        match = re.search(pattern, container_text)
        if match:
            date = parse_date(match.group(1))
            if date:
                break

    # Extract description
    description = title
    desc_elem = container.find('p') if container else None
    if desc_elem:
        desc_text = desc_elem.get_text(strip=True)
        if desc_text and len(desc_text) > 10 and desc_text != title:
            description = desc_text[:300]

    return {
        "title": title,
        "date": date,
        "description": description,
        "link": full_url,
    }


def generate_rss_feed(blog_posts, feed_name="suleyman"):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Mustafa Suleyman - Writing")
        fg.description("Blog posts and opinion articles from Mustafa Suleyman")
        fg.link(href=f"{BASE_URL}/#writing")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Mustafa Suleyman"})
        fg.subtitle("Writings from the Microsoft AI CEO")
        fg.link(href=f"{BASE_URL}/#writing", rel="alternate")

        # Feedgen reverses entry order, so we reverse posts to get newest-first in output
        for post in reversed(blog_posts):
            fe = fg.add_entry()
            fe.title(post["title"])
            fe.description(post["description"])
            fe.link(href=post["link"])
            if post["date"]:
                fe.published(post["date"])
            fe.id(post["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def save_rss_feed(feed_generator, feed_name="suleyman"):
    """Save the RSS feed to a file in the feeds directory."""
    try:
        feeds_dir = ensure_feeds_directory()
        output_filename = feeds_dir / f"feed_{feed_name}.xml"
        feed_generator.rss_file(str(output_filename), pretty=True)
        logger.info(f"Successfully saved RSS feed to {output_filename}")
        return output_filename

    except Exception as e:
        logger.error(f"Error saving RSS feed: {str(e)}")
        raise


def main(blog_url=BASE_URL, feed_name="suleyman"):
    """Main function to generate RSS feed from Mustafa Suleyman's website."""
    try:
        # Fetch blog content using Selenium
        html_content = fetch_blog_content_selenium(blog_url)

        # Parse blog posts from HTML
        blog_posts = parse_blog_html(html_content)

        if not blog_posts:
            logger.warning("No posts found. The site structure may have changed.")
            # Create an empty feed anyway so the file exists
            blog_posts = []

        # Generate RSS feed
        feed = generate_rss_feed(blog_posts, feed_name)

        # Save feed to file
        save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(blog_posts)} posts")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
