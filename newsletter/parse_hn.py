from .util import get_json_from_url, get_text_from_url

_BASE_URL = "https://hacker-news.firebaseio.com/v0"


def search_for_url(url: str, num_comments=3):
    response = get_json_from_url(
        f"http://hn.algolia.com/api/v1/search?query={url}&restrictSearchableAttributes=url"
    )
    hits = sorted(response["hits"], key=lambda h: h["points"], reverse=True)
    if len(hits) == 0:
        return None
    item_id = hits[0]["story_id"]
    item = get_json_from_url(f"{_BASE_URL}/item/{item_id}.json")

    comments_url = f"https://news.ycombinator.com/item?id={item_id}"
    if "url" in item:
        content = get_text_from_url(item["url"])
    else:
        content = item["text"]

    comments = []
    for comment_id in item["kids"][:num_comments]:
        c = get_json_from_url(f"{_BASE_URL}/item/{comment_id}.json")
        if c is None or "text" not in c:
            # deleted comment
            continue
        comments.append(
            {
                "content": c["text"],
                "url": f"https://news.ycombinator.com/item?id={comment_id}",
            }
        )
    return {
        "source": "HackerNews",
        "title": item["title"],
        "score": item["score"],
        "content_url": item.get("url", comments_url),
        "comments_url": comments_url,
        "content": content,
        "comments": comments,
    }


def get_item(url: str, num_comments=3):
    """
    Parses a url like https://news.ycombinator.com/item?id=38064287
    """
    assert "news.ycombinator.com" in url
    query_params = dict(map(lambda p: p.split("="), url.split("?")[1].split("&")))
    item_id = query_params["id"]
    item = get_json_from_url(f"{_BASE_URL}/item/{item_id}.json")

    comments_url = f"https://news.ycombinator.com/item?id={item_id}"
    if "url" in item:
        content = get_text_from_url(item["url"])
    else:
        content = item["text"]

    comments = []
    for comment_id in item["kids"][:num_comments]:
        c = get_json_from_url(f"{_BASE_URL}/item/{comment_id}.json")
        if c is None or "text" not in c:
            # deleted comment
            continue
        comments.append(
            {
                "content": c["text"],
                "url": f"https://news.ycombinator.com/item?id={comment_id}",
            }
        )
    return {
        "source": "HackerNews",
        "title": item["title"],
        "score": item["score"],
        "content_url": item.get("url", comments_url),
        "comments_url": comments_url,
        "content": content,
        "comments": comments,
    }


def iter_top_posts(num_posts=25, num_comments=3):
    top_ids = get_json_from_url(f"{_BASE_URL}/topstories.json")
    for item_id in top_ids[:num_posts]:
        item = get_json_from_url(f"{_BASE_URL}/item/{item_id}.json")
        if item["type"] != "story" or "kids" not in item:
            continue

        comments_url = f"https://news.ycombinator.com/item?id={item_id}"
        try:
            if "url" in item:
                content = get_text_from_url(item["url"])
            else:
                content = item["text"]
        except Exception as err:
            print(err)
            continue

        comments = []
        for comment_id in item["kids"][:num_comments]:
            c = get_json_from_url(f"{_BASE_URL}/item/{comment_id}.json")
            if c is None or "text" not in c:
                # deleted comment
                continue
            comments.append(
                {
                    "content": c["text"],
                    "url": f"https://news.ycombinator.com/item?id={comment_id}",
                }
            )
        yield {
            "source": "HackerNews",
            "title": item["title"],
            "score": item["score"],
            "content_url": item.get("url", comments_url),
            "comments_url": comments_url,
            "content": content,
            "comments": comments,
        }
