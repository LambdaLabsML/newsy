import bs4
import requests
from datetime import datetime, timedelta

from .util import get_text_from_url


def iter_items_from_today(rss_feed: str):
    response = requests.get(rss_feed, timeout=5)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.content, "xml")
    now = datetime.utcnow()
    for item in soup.findAll("item"):
        try:
            pub_date = datetime.strptime(
                item.pubDate.string, "%a, %d %b %Y %H:%M:%S %z"
            )
        except ValueError:
            pub_date = datetime.strptime(
                item.pubDate.string, "%a, %d %b %Y %H:%M:%S %Z"
            )
        if pub_date.tzinfo is None:
            delta = now - pub_date
        else:
            delta = now.astimezone(pub_date.tzinfo) - pub_date
        if delta > timedelta(days=2):
            continue

        content = get_text_from_url(item.link.string)
        yield {
            "source": rss_feed,
            "url": item.link.string,
            "title": item.title.string,
            "content": content,
        }
