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

BASE_URL = "https://www.neuronpedia.org"


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
    """Parse date string."""
    date_formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d %B %Y",
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

        # Find all links to blog posts
        post_links = soup.find_all('a', href=re.compile(r'^/blog/[^/]+$'))

        seen_links = set()
        for link in post_links:
            href = link.get('href', '')
            if not href or href in seen_links or href == '/blog/':
                continue
            seen_links.add(href)

            # Construct full URL
            full_url = f"{BASE_URL}{href}"

            # Find title - look for bold text or first significant text
            title = None
            title_elem = link.find('p', class_=re.compile(r'font-bold'))
            if title_elem:
                title = title_elem.get_text(strip=True)

            if not title:
                # Try to get any text content
                title = link.get_text(strip=True)
                if title:
                    # Take first line if multiple lines
                    title = title.split('\n')[0].strip()

            if not title or len(title) < 3:
                continue

            # Find description
            description = title
            desc_elem = link.find('p', class_=re.compile(r'text-slate-600'))
            if desc_elem:
                description = desc_elem.get_text(strip=True)

            # Find date
            date = None
            date_elem = link.find('p', class_=re.compile(r'text-slate-400'))
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                # Filter out author names - dates usually have numbers
                if re.search(r'\d', date_text):
                    date = parse_date(date_text)

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


def generate_rss_feed(blog_posts, feed_name="neuronpedia"):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Neuronpedia Blog")
        fg.description("Blog posts from Neuronpedia - exploring neural network interpretability")
        fg.link(href=f"{BASE_URL}/blog")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Neuronpedia"})
        fg.subtitle("Neural network interpretability research and updates")
        fg.link(href=f"{BASE_URL}/blog", rel="alternate")

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


def save_rss_feed(feed_generator, feed_name="neuronpedia"):
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


def main(blog_url=f"{BASE_URL}/blog", feed_name="neuronpedia"):
    """Main function to generate RSS feed from Neuronpedia blog."""
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
