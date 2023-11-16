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

    # message_changed events happen when slack adds the preview for urls
    # app_mention's also get an identical message event, but we filter them out by checking for channel_type != im
    if event["type"] == "message" and (
        event["channel_type"] != "im" or event.get("subtype", "") == "message_changed"
    ):
        return

    assert len(event["blocks"]) == 1
    assert event["blocks"][0]["type"] == "rich_text"
    assert len(event["blocks"][0]["elements"]) == 1
    assert event["blocks"][0]["elements"][0]["type"] == "rich_text_section"
    parts = event["blocks"][0]["elements"][0]["elements"]

    # strip out the app mention part
    if event["type"] == "app_mention":
        parts = [p for p in parts if p["type"] != "user"]

    if parts[0]["type"] != "text":
        say(f"Unrecognized command `{parts[0]}`. " + HELP)
        return

    command = parts[0]["text"].strip()

    if command == "news":
        _do_news(channel=event["channel"])
    elif command == "summarize":
        if len(parts) != 2 or parts[1]["type"] != "link":
            say("Missing a link to summarize. " + HELP)
            return
        _do_summarize(parts[1]["url"], printl)
    elif command == "arxiv":
        assert len(parts) == 1
        parts = command.split(" ")
        if len(parts) < 4:
            say("Must include a arxiv category and description. " + HELP)
            return
        category = parts[1]
        sub_category = parts[2]
        description = " ".join(parts[3:])
        _arxiv_search(category, sub_category, description, channel=event["channel"])
    else:
        say(f"Unrecognized command `{command}`. " + HELP)
        return


def _do_summarize(url, printl: Callable[[str], None]):
    sections = []

    try:
        is_twitter_post = "twitter.com" in url
        is_reddit_comments = "reddit.com" in url and "comments" in url
        is_hn_comments = "news.ycombinator.com/item" in url
        if is_twitter_post:
            raise util.ScrapePreventedError()
        elif is_reddit_comments or is_hn_comments:
            # reddit post comments or hackernews comments
            if "reddit.com" in url:
                item = parse_reddit.get_item(url)
            else:
                item = parse_hn.get_item(url)

            summary = lm.summarize_post(item["title"], item["content"])

            lines = [
                f"*<{item['content_url']}|{item['title']}>* discusses:",
                summary,
                "",
                f"*<{item['comments_url']}|{item['source']}>* has a +{item['score']} discussion",
            ]
            if len(item["comments"]) == 0:
                lines[-1] += ", but there aren't any comments."
            else:
                lines[-1] += " centered around:"
                for i, c in enumerate(item["comments"]):
                    comment_summary = lm.summarize_comment(
                        item["title"], summary, c["content"]
                    )
                    if "score" in c:
                        lines.append(
                            f"{i + 1}. (+{c['score']}) <{c['url']}|{comment_summary}>"
                        )
                    else:
                        lines.append(f"{i + 1}. <{c['url']}|{comment_summary}>")
            sections.append("\n".join(lines))
        elif "arxiv.org" in url:
            # arxiv abstract
            item = parse_arxiv.get_item(url)
            summary = lm.summarize_abstract(item["title"], item["abstract"])
            sections.append(
                f"The abstract for *<{url}|{item['title']}>* discusses:\n{summary}"
            )
        else:
            # generic web page
            item = util.get_details_from_url(url)
            summary = lm.summarize_post(item["title"], item["text"])
            sections.append(f"*<{url}|{item['title']}>* discusses:\n{summary}")
    except requests.exceptions.HTTPError as err:
        sections.append(
            f"I'm unable to access this link for some reason (I get a {err.response.status_code} status code when I request access). Sorry!"
        )
    except util.ScrapePreventedError as err:
        sections.append(f"This website prevented me accessing its content, sorry!")
    except requests.exceptions.ReadTimeout as err:
        sections.append(f"My request to {err.request.url} timed out, sorry!")
    except Exception as err:
        sections.append(f"Sorry I encountered an error: {err}")

    discussions = []
    if not is_hn_comments:
        discussions.append(("HackerNews", parse_hn.search_for_url(url)))
    if not is_reddit_comments:
        discussions.append(("reddit", parse_reddit.search_for_url(url)))

    for name, discussion in discussions:
        if discussion is None:
            sections.append(f"*{name}* doesn't have a discussion for this url yet.")
            continue
        lines = [
            f"*<{discussion['comments_url']}|{discussion['source']}>* has a +{discussion['score']} discussion"
        ]
        if len(discussion["comments"]) == 0:
            lines[0] += ", but there aren't any comments."
        else:
            lines[0] += " centered around:"
            for i, c in enumerate(discussion["comments"]):
                comment_summary = lm.summarize_comment(
                    discussion["title"], summary, c["content"]
                )
                if "score" in c:
                    lines.append(
                        f"{i + 1}. (+{c['score']}) <{c['url']}|{comment_summary}>"
                    )
                else:
                    lines.append(f"{i + 1}. <{c['url']}|{comment_summary}>")
        sections.append("\n".join(lines))
    if not is_twitter_post:
        sections.append(
            f"You can search for tweets discussing this url on *<https://twitter.com/search?q=url:{url}&src=typed_query|Twitter>*"
        )

    printl("\n\n".join(sections))


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
    total = 0
    for post in parse_hn.iter_top_posts(num_posts=25):
        set_progress_msg(f"Processing <{post['content_url']}|{post['title']}>")
        total += 1
        try:
            should_show = lm.matches_filter(
                post["title"] + "\n\n" + post["content"], ARTICLE_FILTER
            )

            msg = f"{num + 1}. [<{post['comments_url']}|Comments>] <{post['content_url']}|{post['title']}>"
            print(msg)
            if should_show:
                num += 1
                add_line(msg)
        except Exception as err:
            print(err)
    if num == 0:
        add_line("_No more relevant posts from today._")
    add_line(f"_Checked {total} posts._")

    add_line("\n*/r/MachineLearning:*")
    set_progress_msg("Retrieving posts")
    num = 0
    total = 0
    for post in parse_reddit.iter_top_posts("MachineLearning", num_posts=2):
        set_progress_msg(f"Processing <{post['content_url']}|{post['title']}>")
        total += 1
        try:
            msg = f"{num + 1}. [<{post['comments_url']}|Comments>] (+{post['score']}) <{post['content_url']}|{post['title']}>"
            print(msg)
            num += 1
            add_line(msg)
        except Exception as err:
            print(err)
    if num == 0:
        add_line("_No more relevant posts from today._")
    add_line(f"_Checked {total} posts._")

    for name, rss_feed in [
        ("OpenAI Blog", "https://openai.com/blog/rss.xml"),
        ("StabilityAI Blog", "https://stability.ai/news?format=rss"),
        ("Deepmind Blog", "https://deepmind.google/blog/rss.xml"),
    ]:
        add_line(f"\n*{name}:*")
        set_progress_msg("Retrieving rss feed items")
        try:
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
        except Exception as err:
            add_line(f"_Encountered error pulling from this rss feed: {err}_")

    add_line("\n*arxiv AI papers:*")
    set_progress_msg("Retrieving papers")
    num = 0
    total = 0
    for paper in parse_arxiv.iter_todays_papers(category="cs.AI"):
        set_progress_msg(f"Processing <{paper['url']}|{paper['title']}>")
        total += 1
        try:
            should_show = lm.matches_filter(
                "Abstract:\n" + paper["abstract"], PAPER_FILTER
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
    add_line(f"_Checked {total} papers._")

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
    total = 0
    for paper in parse_arxiv.iter_todays_papers(category=f"{category}.{sub_category}"):
        set_progress_msg(f"Processing <{paper['url']}|{paper['title']}>")
        total += 1
        try:
            should_show = lm.matches_filter(
                "Abstract:\n" + paper["abstract"], description
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
    add_line(f"_Checked {total} papers._")

    add_line("\n\nEnjoy reading 🎉")


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
