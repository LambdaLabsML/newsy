from .util import get_json_from_url, get_text_from_url

_BASE_URL = "https://hacker-news.firebaseio.com/v0"


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
            if "text" not in c:
                # deleted comment
                continue
            comments.append(
                {
                    "content": c["text"],
                    "url": f"https://news.ycombinator.com/item?id={comment_id}",
                    "score": 0,
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
