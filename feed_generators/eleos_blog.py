import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import re
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://eleosai.org"


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def ensure_feeds_directory():
    """Ensure the feeds directory exists."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def fetch_blog_content(url):
    """Fetch blog content from the given URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching blog content: {str(e)}")
        raise


def parse_date(date_text):
    """Parse date string like 'October 31, 2025' or 'Blog · October 31, 2025'."""
    try:
        # Remove "Blog · " or similar prefixes
        date_text = re.sub(r'^[A-Za-z]+\s*·\s*', '', date_text.strip())
        date_obj = datetime.strptime(date_text.strip(), "%B %d, %Y")
        return date_obj.replace(tzinfo=pytz.UTC)
    except ValueError:
        try:
            # Try alternate format
            date_obj = datetime.strptime(date_text.strip(), "%b %d, %Y")
            return date_obj.replace(tzinfo=pytz.UTC)
        except ValueError:
            logger.warning(f"Could not parse date: {date_text}")
            return None


def parse_blog_html(html_content):
    """Parse the blog HTML content and extract post information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # Find all links to posts
        post_links = soup.find_all('a', href=re.compile(r'^/post/'))

        seen_links = set()
        for link in post_links:
            href = link.get('href', '')
            if not href or href in seen_links:
                continue
            seen_links.add(href)

            # Get title from link text
            title = link.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            # Construct full URL
            full_url = f"{BASE_URL}{href}"

            # Try to find date - look for text containing date pattern before/near the link
            date = None
            parent = link.parent
            while parent and not date:
                text = parent.get_text()
                # Look for "Blog · Date" or just date patterns
                date_match = re.search(r'(?:Blog\s*·\s*)?([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})', text)
                if date_match:
                    date = parse_date(date_match.group(1))
                    break
                parent = parent.parent
                if parent and parent.name == 'body':
                    break

            # Get description - look for nearby paragraph text
            description = title
            next_elem = link.find_next(['p', 'div'])
            if next_elem and next_elem.get_text(strip=True):
                desc_text = next_elem.get_text(strip=True)
                if len(desc_text) > 10 and desc_text != title:
                    description = desc_text[:300]

            blog_posts.append({
                "title": title,
                "date": date,
                "description": description,
                "link": full_url,
            })

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(blog_posts, feed_name="eleos"):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Eleos AI Research")
        fg.description("Research and blog posts from Eleos AI")
        fg.link(href=f"{BASE_URL}/research/")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Eleos AI"})
        fg.subtitle("AI safety and welfare research from Eleos AI")
        fg.link(href=f"{BASE_URL}/research/", rel="alternate")

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


def save_rss_feed(feed_generator, feed_name="eleos"):
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


def main(blog_url=f"{BASE_URL}/research/", feed_name="eleos"):
    """Main function to generate RSS feed from Eleos AI research page."""
    try:
        # Fetch blog content
        html_content = fetch_blog_content(blog_url)

        # Parse blog posts from HTML
        blog_posts = parse_blog_html(html_content)

        if not blog_posts:
            logger.warning("No posts found. Please check the HTML structure.")
            return False

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
