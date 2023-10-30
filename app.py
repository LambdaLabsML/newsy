import itertools
from typing import Callable
import json
import os
import ssl
import certifi
from slack_sdk.web import WebClient
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from newsletter import lm, parse_arxiv, parse_hn, parse_reddit, util

app = App(
    client=WebClient(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        ssl=ssl.create_default_context(cafile=certifi.where()),
    ),
)

ARTICLE_FILTER = """Articles related to Artificial intelligence (AI), Machine Learning (ML), foundation models, language models, GPT, generation models.
"""

PAPER_FILTER = """Papers related to:
1. evaluating GPT or large language models
2. prompting techniques for language models
3. techniques for optimizing size or efficiency of language models (like quantization or sparsification)
4. techniques for increasing sequence length of transformers.
"""

DB_FILENAME = ".db"


@app.event("app_mention")
def handle_app_mention(event, say):
    def printl(msg):
        app.client.chat_postMessage(
            text=msg,
            channel=event["channel"],
            thread_ts=event["ts"],
            unfurl_links=False,
            unfurl_media=False,
        )

    parts = event["text"].split(" ")
    assert parts[0].startswith("<@")  # the mention

    if parts[1] == "newsletter":
        _do_newsletter(channel=event["channel"])
    elif parts[1] == "summarize":
        assert len(parts) == 3
        url = parts[2][1:-1]  # strip off the < and >
        _do_summarize(url, printl)
    else:
        say(
            f"""Unrecognized command `{parts[1]}`. Valid commands are:
1. `@<bot name> newsletter`
2. `@<bot name> summarize <url>`
"""
        )


def _do_summarize(url, printl: Callable[[str], None]):
    is_reddit_comments = "reddit.com" in url and "comments" in url
    is_hn_comments = "news.ycombinator.com/item" in url
    if is_reddit_comments or is_hn_comments:
        # reddit post comments or hackernews comments
        if "reddit.com" in url:
            item = parse_reddit.get_item(url)
        else:
            item = parse_hn.get_item(url)

        summary = lm.summarize_post(item["title"], item["content"])

        lines = [
            f"The discussion on <{item['content_url']}|{item['title']}> at <{item['comments_url']}|{item['source']}> is centered around:"
        ]
        for i, c in enumerate(item["comments"]):
            comment_summary = lm.summarize_comment(item["title"], summary, c["content"])
            if "score" in c:
                lines.append(f"{i + 1}. (+{c['score']}) <{c['url']}|{comment_summary}>")
            else:
                lines.append(f"{i + 1}. <{c['url']}|{comment_summary}>")
        printl("\n".join(lines))
        printl(f"And here's the summary for you:\n> {summary}")
    elif "arxiv.org" in url:
        # arxiv abstract
        item = parse_arxiv.get_item(url)
        summary = lm.summarize_post(item["title"], item["abstract"])
        printl(f"Here's the summary for <{url}|{item['title']}>:\n{summary}")
        printl(f"For reference, here is the *Abstract*:\n{item['abstract']}")
    else:
        # generic web page
        printl(f"Here's the summary for {url}:")
        printl(lm.summarize_post("", util.get_text_from_url(url)))


def _do_newsletter(channel):
    if not os.path.exists(DB_FILENAME):
        with open(DB_FILENAME, "w") as fp:
            fp.write("[]")

    with open(DB_FILENAME) as fp:
        processed = set(json.load(fp))

    lines = ["Here's the latest news from today for you!"]

    news = app.client.chat_postMessage(text="\n".join(lines), channel=channel)
    thread = news.data["ts"]

    def add_line(new_line):
        lines.append(new_line)
        app.client.chat_update(
            text="\n".join(lines),
            channel=channel,
            unfurl_links=False,
            unfurl_media=False,
            ts=thread,
        )

    add_line("\n*HackerNews:*")
    num = 0
    for post in parse_hn.iter_top_posts(num_posts=25):
        if post["comments_url"] in processed:
            continue

        processed.add(post["comments_url"])
        with open(DB_FILENAME, "w") as fp:
            json.dump(list(processed), fp)

        try:
            summary = lm.summarize_post(post["title"], post["content"])
            should_show = lm.matches_filter(summary, ARTICLE_FILTER)

            msg = f"{num + 1}. [<{post['comments_url']}|Comments>] <{post['content_url']}|{post['title']}>"
            print(msg)
            if should_show:
                num += 1
                add_line(msg)
        except Exception as err:
            print(err)
    if num == 0:
        add_line("_No more relevant posts from today._")

    add_line("\n*/r/MachineLearning:*")
    num = 0
    for post in parse_reddit.iter_top_posts("MachineLearning", num_posts=2):
        if post["comments_url"] in processed:
            continue

        processed.add(post["comments_url"])
        with open(DB_FILENAME, "w") as fp:
            json.dump(list(processed), fp)

        try:
            summary = lm.summarize_post(post["title"], post["content"])
            should_show = lm.matches_filter(summary, ARTICLE_FILTER)

            msg = f"{num + 1}. [<{post['comments_url']}|Comments>] <{post['content_url']}|{post['title']}>"
            print(msg)
            if should_show:
                num += 1
                add_line(msg)
        except Exception as err:
            print(err)
    if num == 0:
        add_line("_No more relevant posts from today._")

    add_line("\n*arxiv AI papers:*")
    num = 0
    for paper in parse_arxiv.iter_todays_papers(category="cs.AI"):
        if paper["url"] in processed:
            continue

        processed.add(paper["url"])
        with open(DB_FILENAME, "w") as fp:
            json.dump(list(processed), fp)

        try:
            summary = lm.summarize_post(paper["title"], paper["abstract"])
            should_show = lm.matches_filter(
                "Abstract:\n" + paper["abstract"] + "\n\nSummary:\n" + summary,
                PAPER_FILTER,
            )

            msg = f"{num + 1}. <{paper['url']}|{paper['title']}>"
            print(msg)
            if should_show:
                num += 1
                add_line(msg)
        except Exception as err:
            print(err)
    if num == 0:
        add_line("_No more relevant papers from today._")

    add_line("Enjoy reading 🎉")


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
