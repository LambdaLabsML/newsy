from typing import Callable
import os
import ssl
import certifi
import requests
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from datetime import datetime, timedelta
import time

from newsletter import lm, parse_arxiv, parse_hn, parse_reddit, parse_rss, util

app = App(
    client=WebClient(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        ssl=ssl.create_default_context(cafile=certifi.where()),
    ),
)

ARTICLE_FILTER = """Articles related to Artificial intelligence (AI), Machine Learning (ML), foundation models, LLMs (large language models), GPT, generation models.
"""

PAPER_FILTER = """Papers related to:
1. evaluating GPT or large language models
2. prompting techniques for language models
3. techniques for optimizing size or efficiency of language models (like quantization or sparsification)
4. techniques for increasing sequence length of transformers.
"""

HELP = """Valid commands are:
*`news`*
> Pulls from a list of news sources related to AI/ML.

*`summarize <url>`*
> Given any url, summarizes the content, and searches for related discussions on hacker news.

*`arxiv <main category> <sub category> <description of papers to find>`*
> Crawls arxiv for papers in the category & sub category that are related to the description that you give.
> Main & sub categories can be found on this page <https://arxiv.org/category_taxonomy>.
> For example, given the category `cs.AI`, the main category is `cs` and the sub category is `AI`.
> Example command: `arxiv cs AI Papers related to Large language models, GPT, and prompting.`

*`subscribe <command>`*
> The command will be executed immediately, and then daily in your DMs. Command can be any of the above valid commands.
"""


@app.event("message")
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

    if event["type"] == "message":
        if event["channel_type"] != "im":
            return
        parts = event["text"].split(" ")
    else:
        assert event["type"] == "app_mention"
        parts = event["text"].split(" ")
        assert parts[0].startswith("<@")  # the mention
        parts = parts[1:]

    if parts[0] == "subscribe":
        do_subscribe = True
        parts = parts[1:]
    else:
        do_subscribe = False

    if parts[0] == "news":
        _do_news(channel=event["channel"])
    elif parts[0] == "summarize":
        if len(parts) != 2:
            say("Missing a link to summarize. " + HELP)
            return
        url = parts[1][1:-1]  # strip off the < and >
        try:
            _do_summarize(url, printl)
        except requests.exceptions.HTTPError as err:
            say(
                f"I'm unable to access this link for some reason (I get a {err.response.status_code} status code when I request access). Sorry!"
            )
    elif parts[0] == "arxiv":
        if len(parts) < 4:
            say("Must include a arxiv category and description. " + HELP)
            return
        category = parts[1]
        sub_category = parts[2]
        description = " ".join(parts[3:])
        _arxiv_search(category, sub_category, description, channel=event["channel"])
    else:
        say(f"Unrecognized command `{parts[0]}`. " + HELP)
        return

    if do_subscribe:
        app.client.chat_scheduleMessage(
            channel=event["user"],
            text="@ai-news-bot subscribe " + " ".join(parts),
            post_at=int((datetime.now() + timedelta(days=1)).timestamp()),
            as_user=True,
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
        printl(f"Here's the summary for <{url}|{item['title']}>:\n> {summary}")
        printl(f"For reference, here is the *Abstract*:\n{item['abstract']}")
    else:
        # generic web page
        item = util.get_details_from_url(url)
        summary = lm.summarize_post(item["title"], item["text"])
        printl(f"Here's the summary for <{url}|{item['title']}>:\n> {summary}")

        hn_discussion = parse_hn.search_for_url(url)
        if hn_discussion is not None:
            if len(hn_discussion["comments"]) == 0:
                printl(
                    f"I also found a +{hn_discussion['score']} discussion on <{hn_discussion['comments_url']}|{hn_discussion['source']}>. There aren't any comments yet though."
                )
            else:
                lines = [
                    f"I also found a +{hn_discussion['score']} discussion on <{hn_discussion['comments_url']}|{hn_discussion['source']}>. It's centered around:"
                ]
                for i, c in enumerate(hn_discussion["comments"]):
                    comment_summary = lm.summarize_comment(
                        hn_discussion["title"], summary, c["content"]
                    )
                    if "score" in c:
                        lines.append(
                            f"{i + 1}. (+{c['score']}) <{c['url']}|{comment_summary}>"
                        )
                    else:
                        lines.append(f"{i + 1}. <{c['url']}|{comment_summary}>")
                printl("\n".join(lines))


def _do_news(channel):
    lines = ["Here's the latest news from today for you!"]

    news = app.client.chat_postMessage(text="\n".join(lines), channel=channel)
    thread = news.data["ts"]

    def add_line(new_line):
        lines.append(new_line)
        for _ in range(3):
            try:
                app.client.chat_update(
                    text="\n".join(lines),
                    channel=channel,
                    unfurl_links=False,
                    unfurl_media=False,
                    ts=thread,
                )
                return
            except SlackApiError:
                ...

    def set_progress_msg(msg):
        for _ in range(3):
            try:
                app.client.chat_update(
                    text="\n".join(lines) + "\n\n_" + msg + "_\n",
                    channel=channel,
                    unfurl_links=False,
                    unfurl_media=False,
                    ts=thread,
                )
                return
            except SlackApiError:
                ...

    add_line("\n*HackerNews:*")
    set_progress_msg("Retrieving posts")
    num = 0
    for post in parse_hn.iter_top_posts(num_posts=25):
        set_progress_msg(f"Processing <{post['content_url']}|{post['title']}>")
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
    set_progress_msg("Retrieving posts")
    num = 0
    for post in parse_reddit.iter_top_posts("MachineLearning", num_posts=2):
        set_progress_msg(f"Processing <{post['content_url']}|{post['title']}>")
        try:
            summary = lm.summarize_post(post["title"], post["content"])
            should_show = lm.matches_filter(summary, ARTICLE_FILTER)

            msg = f"{num + 1}. [<{post['comments_url']}|Comments>] (+{post['score']}) <{post['content_url']}|{post['title']}>"
            print(msg)
            if should_show:
                num += 1
                add_line(msg)
        except Exception as err:
            print(err)
    if num == 0:
        add_line("_No more relevant posts from today._")

    for name, rss_feed in [
        ("OpenAI Blog", "https://openai.com/blog/rss.xml"),
        ("StabilityAI Blog", "https://stability.ai/blog?format=rss"),
        ("Deepmind Blog", "https://deepmind.google/blog/rss.xml"),
    ]:
        add_line(f"\n*{name}:*")
        set_progress_msg("Retrieving rss feed items")
        num = 0
        for item in parse_rss.iter_items_from_today(rss_feed):
            try:
                msg = f"{num + 1}. <{item['url']}|{item['title']}>"
                print(msg)
                num += 1
                add_line(msg)
            except Exception as err:
                print(err)
        if num == 0:
            add_line("_No posts from today._")

    add_line("\n*arxiv AI papers:*")
    set_progress_msg("Retrieving papers")
    num = 0
    for paper in parse_arxiv.iter_todays_papers(category="cs.AI"):
        set_progress_msg(f"Processing <{paper['url']}|{paper['title']}>")
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

    add_line("\n\nEnjoy reading 🎉")


def _arxiv_search(category, sub_category, description, channel):
    print(category, sub_category, description)
    lines = [f"*arxiv {category}.{sub_category} papers:*"]

    news = app.client.chat_postMessage(text="\n".join(lines), channel=channel)
    thread = news.data["ts"]

    def add_line(new_line):
        lines.append(new_line)
        for _ in range(3):
            try:
                app.client.chat_update(
                    text="\n".join(lines),
                    channel=channel,
                    unfurl_links=False,
                    unfurl_media=False,
                    ts=thread,
                )
                return
            except SlackApiError:
                ...

    def set_progress_msg(msg):
        for _ in range(3):
            try:
                app.client.chat_update(
                    text="\n".join(lines) + "\n\n_" + msg + "_\n",
                    channel=channel,
                    unfurl_links=False,
                    unfurl_media=False,
                    ts=thread,
                )
                return
            except SlackApiError:
                ...

    set_progress_msg("Retrieving papers")
    num = 0
    for paper in parse_arxiv.iter_todays_papers(category=f"{category}.{sub_category}"):
        set_progress_msg(f"Processing <{paper['url']}|{paper['title']}>")
        try:
            summary = lm.summarize_post(paper["title"], paper["abstract"])
            should_show = lm.matches_filter(
                "Abstract:\n" + paper["abstract"] + "\n\nSummary:\n" + summary,
                description,
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

    add_line("\n\nEnjoy reading 🎉")


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
