from praw import Reddit
from praw.models import Submission
import os

from .util import get_text_from_url


def search_for_url(url: str, num_comments=3):
    reddit = Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        password=os.environ["REDDIT_PASSWORD"],
        username=os.environ["REDDIT_USERNAME"],
        user_agent="USERAGENT",
    )

    for item in reddit.subreddit("all").search(f"url:{url}", limit=25):
        if item.url != url:
            continue

        comments = []
        for i, comment in enumerate(item.comments):
            if i >= num_comments:
                break
            comments.append(
                {
                    "content": comment.body,
                    "url": "https://www.reddit.com" + comment.permalink,
                    "score": comment.score,
                }
            )

        return {
            "source": "/r/" + item.subreddit.display_name,
            "title": item.title,
            "score": item.score,
            "content_url": item.url,
            "comments_url": "https://www.reddit.com" + item.permalink,
            "comments": comments,
        }

    return None


def get_item(url: str, num_comments=3):
    reddit = Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        password=os.environ["REDDIT_PASSWORD"],
        username=os.environ["REDDIT_USERNAME"],
        user_agent="USERAGENT",
    )

    item = Submission(reddit, url=url)

    content = item.selftext
    if len(content) == 0:
        # this was not a selftext
        content = get_text_from_url(item.url)

    comments = []
    for i, comment in enumerate(item.comments):
        if i >= num_comments:
            break
        comments.append(
            {
                "content": comment.body,
                "url": "https://www.reddit.com" + comment.permalink,
                "score": comment.score,
            }
        )

    return {
        "source": "/r/" + item.subreddit.display_name,
        "title": item.title,
        "score": item.score,
        "content_url": item.url,
        "comments_url": "https://www.reddit.com" + item.permalink,
        "content": content,
        "comments": comments,
    }


def iter_top_posts(subreddit, num_posts=25, num_comments=3):
    reddit = Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        password=os.environ["REDDIT_PASSWORD"],
        username=os.environ["REDDIT_USERNAME"],
        user_agent="USERAGENT",
    )

    for item in reddit.subreddit(subreddit).top(time_filter="day", limit=num_posts):
        content = item.selftext
        if len(content) == 0:
            # this was not a selftext
            try:
                content = get_text_from_url(item.url)
            except Exception as err:
                yield {
                    "source": f"/r/{subreddit}",
                    "title": item.title,
                    "score": item.score,
                    "content_url": item.url,
                    "comments_url": "https://www.reddit.com" + item.permalink,
                    "error": err,
                }
                continue

        comments = []
        for i, comment in enumerate(item.comments):
            if i >= num_comments:
                break
            comments.append(
                {
                    "content": comment.body,
                    "url": "https://www.reddit.com" + comment.permalink,
                    "score": comment.score,
                }
            )

        yield {
            "source": f"/r/{subreddit}",
            "title": item.title,
            "score": item.score,
            "content_url": item.url,
            "comments_url": "https://www.reddit.com" + item.permalink,
            "content": content,
            "comments": comments,
        }
