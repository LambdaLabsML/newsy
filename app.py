import itertools
import json
import os
import ssl
import certifi
from slack_sdk.web import WebClient
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from newsletter import lm, parse_arxiv, parse_hn, parse_reddit

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


@app.command("/newsletter")
def command_newsletter(ack, respond, command):
    ack()

    if not os.path.exists(DB_FILENAME):
        with open(DB_FILENAME, "w") as fp:
            fp.write("[]")

    with open(DB_FILENAME) as fp:
        processed = set(json.load(fp))

    lines = ["Here's the latest news from today for you!"]

    def add_line(new_line):
        lines.append(new_line)
        app.client.chat_update(
            text="\n".join(lines),
            channel=command["channel_id"],
            unfurl_links=False,
            unfurl_media=False,
            ts=thread,
        )

    news = app.client.chat_postMessage(
        text="\n".join(lines), channel=command["channel_id"]
    )
    thread = news.data["ts"]

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


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
