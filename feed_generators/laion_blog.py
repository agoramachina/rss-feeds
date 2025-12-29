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

BASE_URL = "https://laion.ai"


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
        "%b %d, %Y",
        "%B %d, %Y",
        "%b %d %Y",      # Aug 4 2025
        "%B %d %Y",      # August 4 2025
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d %B %Y",
        "%d %b %Y",
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
    """Parse the blog HTML content and extract post information from Next.js JSON data."""
    import json

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # Find Next.js data script
        script_tag = soup.find('script', id='__NEXT_DATA__')
        if not script_tag:
            logger.error("Could not find __NEXT_DATA__ script tag")
            return []

        # Parse JSON data
        try:
            data = json.loads(script_tag.string)
            posts_data = data.get('props', {}).get('pageProps', {}).get('posts', [])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return []

        for post in posts_data:
            slug = post.get('slug', '')
            if not slug:
                continue

            frontmatter = post.get('frontmatter', {})
            title = frontmatter.get('title', '')
            if not title:
                continue

            # Parse date from frontmatter or timestamp
            date = None
            date_str = frontmatter.get('date', '')
            if date_str:
                date = parse_date(date_str)

            if not date and post.get('date'):
                # Unix timestamp in milliseconds
                try:
                    timestamp = post['date'] / 1000
                    date = datetime.fromtimestamp(timestamp, tz=pytz.UTC)
                except (ValueError, TypeError):
                    pass

            # Get author for description
            author = frontmatter.get('author', '')
            description = f"By {author}" if author else title

            blog_posts.append({
                "title": title,
                "date": date,
                "description": description,
                "link": f"{BASE_URL}/blog/{slug}",
            })

        # Sort by date (newest first)
        blog_posts.sort(key=lambda x: x['date'] or datetime.min.replace(tzinfo=pytz.UTC), reverse=True)

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(blog_posts, feed_name="laion"):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("LAION Blog")
        fg.description("Blog posts from LAION - Large-scale Artificial Intelligence Open Network")
        fg.link(href=f"{BASE_URL}/blog/")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "LAION"})
        fg.subtitle("Open source AI research and datasets")
        fg.link(href=f"{BASE_URL}/blog/", rel="alternate")

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


def save_rss_feed(feed_generator, feed_name="laion"):
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


def main(blog_url=f"{BASE_URL}/blog/", feed_name="laion"):
    """Main function to generate RSS feed from LAION blog."""
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
