import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://transformer-circuits.pub"


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


def parse_blog_html(html_content):
    """Parse the blog HTML content and extract post information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # Find the table of contents container
        toc = soup.select_one(".container .toc")
        if not toc:
            toc = soup.select_one(".container")

        if not toc:
            logger.error("Could not find content container")
            return []

        # Get all date divs and posts in document order
        all_elements = toc.find_all(['div', 'a'], recursive=False)

        current_date = None
        for element in all_elements:
            # Check if this is a date element
            if element.name == 'div' and 'date' in element.get('class', []):
                date_text = element.text.strip()
                current_date = parse_date(date_text)
                continue

            # Check if this is a post (paper or note)
            if element.name == 'a':
                classes = element.get('class', [])
                if 'paper' in classes or 'note' in classes:
                    post = extract_post(element, current_date)
                    if post:
                        blog_posts.append(post)

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def parse_date(date_text):
    """Parse date string like 'November 2025' or 'March 2020 - April 2021'."""
    try:
        # Handle date ranges like "March 2020 - April 2021"
        if " - " in date_text:
            # Use the end date for date ranges
            date_text = date_text.split(" - ")[-1].strip()

        # Parse "Month YYYY" format
        date_obj = datetime.strptime(date_text, "%B %Y")
        # Set to first of month
        return date_obj.replace(day=1, tzinfo=pytz.UTC)
    except ValueError:
        logger.warning(f"Could not parse date: {date_text}")
        return None


def extract_post(element, current_date):
    """Extract post information from a paper or note element."""
    try:
        # Get the link
        href = element.get('href', '')
        if not href:
            return None

        # Construct full URL
        if href.startswith('http'):
            link = href
        else:
            link = f"{BASE_URL}/{href}"

        # Extract title
        title_elem = element.select_one('h3')
        if not title_elem:
            return None
        title = title_elem.text.strip()

        # Extract description
        desc_elem = element.select_one('.description')
        description = desc_elem.text.strip() if desc_elem else title

        # Extract byline if present (for papers)
        byline_elem = element.select_one('.byline')
        byline = byline_elem.text.strip() if byline_elem else None

        # Determine post type
        classes = element.get('class', [])
        post_type = "Paper" if 'paper' in classes else "Note"

        # Build full description
        full_description = description
        if byline:
            full_description = f"{byline} - {description}"

        return {
            "title": title,
            "date": current_date,
            "description": full_description,
            "link": link,
            "type": post_type,
        }

    except Exception as e:
        logger.warning(f"Error extracting post: {str(e)}")
        return None


def generate_rss_feed(blog_posts, feed_name="transformer_circuits"):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Transformer Circuits Thread")
        fg.description("Anthropic's Interpretability Research - Can we reverse engineer transformer language models into human-understandable computer programs?")
        fg.link(href=BASE_URL)
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic Interpretability Team"})
        fg.logo("https://transformer-circuits.pub/interp.png")
        fg.subtitle("Latest interpretability research from Anthropic")
        fg.link(href=BASE_URL, rel="alternate")
        fg.link(href=f"{BASE_URL}/feed_{feed_name}.xml", rel="self")

        # Feedgen reverses entry order, so we reverse posts to get newest-first in output
        for post in reversed(blog_posts):
            fe = fg.add_entry()
            fe.title(post["title"])
            fe.description(post["description"])
            fe.link(href=post["link"])
            if post["date"]:
                fe.published(post["date"])
            fe.category(term=post["type"])
            fe.id(post["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def save_rss_feed(feed_generator, feed_name="transformer_circuits"):
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


def main(blog_url=BASE_URL, feed_name="transformer_circuits"):
    """Main function to generate RSS feed from Transformer Circuits."""
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
        output_file = save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(blog_posts)} posts")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
