from praw import Reddit
import os

from .util import get_text_from_url


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
                print(err)
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
            "title": item.title,
            "score": item.score,
            "content_url": item.url,
            "comments_url": "https://www.reddit.com" + item.permalink,
            "content": content,
            "comments": comments,
        }
