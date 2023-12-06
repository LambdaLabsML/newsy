import json
from typing import Callable
import os
import ssl
import certifi
import requests
from slack_sdk.web import WebClient
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from newsletter import (
    lm,
    parse_arxiv,
    parse_hn,
    parse_reddit,
    parse_rss,
    parse_youtube,
    util,
    parse_pdf,
)
from newsletter.slack import EditableMessage

app = App(
    client=WebClient(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        ssl=ssl.create_default_context(cafile=certifi.where()),
    ),
)

ARTICLE_FILTER = """Articles related to Artificial intelligence (AI), Machine Learning (ML), foundation models, LLMs (large language models), GPT, generation models.
"""

PAPER_FILTER = """Papers related to:
1. Prompting techniques for language models
2. Techniques for increasing sequence length of transformers.
3. Techniques for optimizing size or efficiency of language models (like quantization or sparsification)
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

*`reddit <subreddit name> <description of posts to find>`*
> Crawls a specific subreddit for *top posts over the last day* that match the descrtiption you give.
> Example command: `reddit Programming Posts related to security breaches or cyber security.`

*`hackernews <description of posts to find>`*
> Crawls hackernews for current top stories that match the description you give.
> Example command: `hackernews Anything to do with world history, human history, ancient civilizations.`
"""


@app.event("message")
@app.event("app_mention")
def handle_app_mention(event):
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

    try:
        if parts[0]["type"] == "link":
            _do_summarize(
                parts[0]["url"],
                EditableMessage(
                    app.client,
                    event["channel"],
                    "_Working on it..._",
                    ts=event["event_ts"],
                ),
                printl,
            )
            return

        if parts[0]["type"] != "text":
            printl(f"Unrecognized command `{parts[0]}`. " + HELP)
            return

        command = parts[0]["text"].strip()

        if command == "news":
            _do_news(channel=event["channel"])
        elif (
            "summarize" in command or "summary" in command or "explain" in command
        ) and any(p["type"] == "link" for p in parts):
            if len(parts) != 2 or parts[1]["type"] != "link":
                printl("Missing a link to summarize. " + HELP)
                return
            _do_summarize(
                parts[1]["url"],
                EditableMessage(
                    app.client,
                    event["channel"],
                    "_Working on it..._",
                    ts=event["event_ts"],
                ),
                printl,
            )
        elif command.startswith("arxiv"):
            assert len(parts) == 1
            parts = command.split(" ")
            if len(parts) < 4:
                printl("Must include a arxiv category and description. " + HELP)
                return
            category = parts[1]
            sub_category = parts[2]
            description = " ".join(parts[3:])
            _arxiv_search(category, sub_category, description, channel=event["channel"])
        elif command.startswith("reddit"):
            assert len(parts) == 1
            parts = command.split(" ")
            if len(parts) < 3:
                printl("Must include a subreddit name and description. " + HELP)
                return
            subreddit_name = parts[1]
            description = " ".join(parts[2:])
            _reddit_search(subreddit_name, description, channel=event["channel"])
        elif command.startswith("hackernews"):
            assert len(parts) == 1
            parts = command.split(" ")
            if len(parts) < 2:
                printl("Must include a description. " + HELP)
                return
            description = " ".join(parts[1:])
            _hackernews_search(description, channel=event["channel"])
        else:
            if "thread_ts" in event:
                ts = event["thread_ts"]
            else:
                ts = event["event_ts"]
            # this is probably a question in a summary thread
            conversation = app.client.conversations_replies(
                channel=event["channel"], ts=ts
            )
            _do_interactive(
                conversation["messages"],
                EditableMessage(
                    app.client,
                    event["channel"],
                    "_Let me check..._",
                    ts=ts,
                ),
            )
    except Exception as err:
        printl(f"Sorry I encountered an error: {type(err)} {repr(err)}")


def _do_summarize(
    url,
    slack_msg: EditableMessage,
    printl: Callable[[str], None],
    model="gpt-3.5-turbo-16k",
):
    sections = []

    content = (
        "Unable to access Article - no questions can be answered nor summary provided."
    )
    try:
        is_twitter_post = "twitter.com" in url
        is_reddit_comments = "reddit.com" in url and "comments" in url
        is_hn_comments = "news.ycombinator.com/item" in url
        if is_twitter_post:
            raise util.ScrapePreventedError()
        elif is_reddit_comments or is_hn_comments:
            slack_msg.edit_line(f"_Scraping <{url}>..._")
            if "reddit.com" in url:
                item = parse_reddit.get_item(url)
            else:
                item = parse_hn.get_item(url)

            content = (
                f"[begin Article]\n{item['title']}\n\n{item['content']}\n[end Article]"
            )

            slack_msg.edit_line(f"_Summarizing content..._")
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
                    slack_msg.edit_line(f"_Summarizing comment {i + 1}..._")
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
            slack_msg.edit_line(f"_Scraping <{url}>..._")
            item = parse_arxiv.get_item(url)
            content = (
                f"[begin Article]\n{item['title']}\n\n{item['abstract']}\n[end Article]"
            )
            slack_msg.edit_line(f"_Summarizing abstract..._")
            summary = lm.summarize_abstract(item["title"], item["abstract"])
            sections.append(
                f"The abstract for *<{url}|{item['title']}>* discusses:\n{summary}"
            )
        elif "youtube.com" in url:
            slack_msg.edit_line(f"_Scraping <{url}>..._")
            item = parse_youtube.get_item(url)
            content = (
                f"[begin Article]\n{item['title']}\n\n{item['content']}\n[end Article]"
            )
            slack_msg.edit_line(f"_Summarizing video..._")
            summary = lm.summarize_post(item["title"], item["content"])
            sections.append(f"*<{url}|{item['title']}>* discusses:\n{summary}")
        else:
            # generic web page
            slack_msg.edit_line(f"_Scraping <{url}>..._")
            item = util.get_details_from_url(url)
            content = (
                f"[begin Article]\n{item['title']}\n\n{item['text']}\n[end Article]"
            )
            slack_msg.edit_line(f"_Summarizing content..._")
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
        sections.append(f"Sorry I encountered an error: {type(err)} {repr(err)}")

    discussions = []
    if not is_hn_comments:
        slack_msg.edit_line("_Searching for hackernews posts..._")
        discussions.append(("HackerNews", parse_hn.search_for_url(url)))
    if not is_reddit_comments:
        slack_msg.edit_line("_Searching for reddit posts..._")
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
                slack_msg.edit_line(f"_Summarizing comment {i + 1} on {name}..._")
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

    summary = "\n\n".join(sections)
    slack_msg.edit_line(summary)

    from langchain.chat_models import ChatOpenAI
    from langchain.schema import HumanMessage, AIMessage, SystemMessage

    chat = ChatOpenAI(model=model, request_timeout=30)

    try:
        response = chat(
            [
                SystemMessage(content=content),
                AIMessage(content=summary),
                HumanMessage(
                    content="Suggest 5 follow up questions to learn more about this post. The questions should be answerable based on the content in the article."
                ),
            ]
        )
        printl(
            "Here are some follow up questions to help you dive deeper into this post (tag me and and I can answer them!):\n"
            + response.content
        )
    except Exception as err:
        printl(f"Sorry I encountered an error: {type(err)} {repr(err)}")


def _do_news(channel):
    news = EditableMessage(
        app.client, channel, "Here's the latest news from today for you!"
    )

    news.start_new_section()
    news.add_line("*HackerNews:*")
    news.set_progress_msg("Retrieving posts")
    num = 0
    total = 0
    for post in parse_hn.iter_top_posts(num_posts=25):
        news.set_progress_msg(f"Processing <{post['content_url']}|{post['title']}>")
        total += 1
        try:
            should_show = lm.matches_filter(
                post["title"] + "\n\n" + post["content"], ARTICLE_FILTER
            )

            msg = f"{num + 1}. [<{post['comments_url']}|Comments>] <{post['content_url']}|{post['title']}>"
            print(msg)
            if should_show:
                num += 1
                news.lazy_add_line(msg)
        except Exception as err:
            print(err)
    if num == 0:
        news.add_line("_No more relevant posts from today._")
    news.add_line(f"_Checked {total} posts._")

    news.start_new_section()
    news.add_line("*/r/MachineLearning:*")
    news.set_progress_msg("Retrieving posts")
    num = 0
    total = 0
    for post in parse_reddit.iter_top_posts("MachineLearning", num_posts=2):
        news.set_progress_msg(f"Processing <{post['content_url']}|{post['title']}>")
        total += 1
        try:
            msg = f"{num + 1}. [<{post['comments_url']}|Comments>] (+{post['score']}) <{post['content_url']}|{post['title']}>"
            print(msg)
            num += 1
            news.lazy_add_line(msg)
        except Exception as err:
            print(err)
    if num == 0:
        news.add_line("_No more relevant posts from today._")
    news.add_line(f"_Checked {total} posts._")

    for name, rss_feed in [
        ("OpenAI Blog", "https://openai.com/blog/rss.xml"),
        ("StabilityAI Blog", "https://stability.ai/news?format=rss"),
        ("Deepmind Blog", "https://deepmind.google/blog/rss.xml"),
    ]:
        news.start_new_section()
        news.add_line(f"*{name}:*")
        news.set_progress_msg("Retrieving rss feed items")
        try:
            num = 0
            for item in parse_rss.iter_items_from_today(rss_feed):
                try:
                    msg = f"{num + 1}. <{item['url']}|{item['title']}>"
                    print(msg)
                    num += 1
                    news.lazy_add_line(msg)
                except Exception as err:
                    print(err)
            if num == 0:
                news.add_line("_No posts from today._")
        except Exception as err:
            news.add_line(f"_Encountered error pulling from this rss feed: {err}_")

    news.start_new_section()
    news.add_line("*arxiv AI papers:*")
    news.set_progress_msg("Retrieving papers")
    num = 0
    total = 0
    for paper in parse_arxiv.iter_todays_papers(category="cs.AI"):
        news.set_progress_msg(f"Processing <{paper['url']}|{paper['title']}>")
        total += 1
        try:
            should_show = lm.matches_filter(
                "Abstract:\n" + paper["abstract"], PAPER_FILTER
            )

            msg = f"{num + 1}. <{paper['url']}|{paper['title']}>"
            print(msg)
            if should_show:
                num += 1
                news.lazy_add_line(msg)
        except Exception as err:
            print(err)
    if num == 0:
        news.add_line("_No more relevant papers from today._")
    news.add_line(f"_Checked {total} papers._")
    news.add_line("\n\nEnjoy reading 🎉")


def _arxiv_search(category, sub_category, description, channel):
    news = EditableMessage(
        app.client, channel, f"*arxiv {category}.{sub_category} papers:*"
    )

    news.set_progress_msg("Retrieving papers")
    num = 0
    total = 0
    for paper in parse_arxiv.iter_todays_papers(category=f"{category}.{sub_category}"):
        news.set_progress_msg(f"Processing <{paper['url']}|{paper['title']}>")
        total += 1
        try:
            should_show = lm.matches_filter(
                "Abstract:\n" + paper["abstract"], description
            )
            msg = f"{num + 1}. <{paper['url']}|{paper['title']}>"
            print(msg)
            if should_show:
                num += 1
                news.lazy_add_line(msg)
        except Exception as err:
            print(err)
    if num == 0:
        news.add_line("_No more relevant papers from today._")
    news.add_line(f"_Checked {total} papers._")
    news.add_line("\n\nEnjoy reading 🎉")


def _reddit_search(subreddit_name, description, channel):
    news = EditableMessage(app.client, channel, f"*/r/{subreddit_name} posts:*")

    news.set_progress_msg("Retrieving posts")
    num = 0
    total = 0
    for post in parse_reddit.iter_top_posts(subreddit_name, num_posts=25):
        news.set_progress_msg(f"Processing <{post['content_url']}|{post['title']}>")
        total += 1
        try:
            should_show = lm.matches_filter(
                post["title"] + "\n\n" + post["content"], description
            )
            msg = f"{num + 1}. [<{post['comments_url']}|Comments>] (+{post['score']}) <{post['content_url']}|{post['title']}>"
            print(msg)
            if should_show:
                num += 1
                news.lazy_add_line(msg)
        except Exception as err:
            print(err)
    if num == 0:
        news.add_line("_No more relevant posts from today._")
    news.add_line(f"_Checked {total} posts._")


def _hackernews_search(description, channel):
    news = EditableMessage(app.client, channel, f"*HackerNews posts:*")
    news.set_progress_msg("Retrieving posts")
    num = 0
    total = 0
    for post in parse_hn.iter_top_posts(num_posts=25):
        news.set_progress_msg(f"Processing <{post['content_url']}|{post['title']}>")
        total += 1
        try:
            should_show = lm.matches_filter(
                post["title"] + "\n\n" + post["content"], description
            )

            msg = f"{num + 1}. [<{post['comments_url']}|Comments>] <{post['content_url']}|{post['title']}>"
            print(msg)
            if should_show:
                num += 1
                news.lazy_add_line(msg)
        except Exception as err:
            print(err)
    if num == 0:
        news.add_line("_No more relevant posts from today._")
    news.add_line(f"_Checked {total} posts._")


def _do_interactive(
    conversation, slack_msg: EditableMessage, model="gpt-3.5-turbo-16k"
):
    from langchain.chat_models import ChatOpenAI
    from langchain.schema import HumanMessage, SystemMessage, AIMessage

    chat = ChatOpenAI(model=model, request_timeout=30)
    app_user_id = app.client.auth_test()["user_id"]

    arxiv_urls = {}
    messages = []
    for event in conversation:
        if event["user"] == app_user_id:
            messages.append(AIMessage(content=event["text"]))
        else:
            messages.append(HumanMessage(content=event["text"]))

            # check for any external links present in this message.
            for ele in event["blocks"][0]["elements"][0]["elements"]:
                if ele["type"] != "link":
                    continue
                url = ele["url"]

                slack_msg.edit_line(f"_Scraping <{url}>..._")

                if "twitter.com" in url:
                    # raise util.ScrapePreventedError()
                    ...
                elif "reddit.com" in url and "comments" in url:
                    item = parse_reddit.get_item(url)
                    msg = f"[begin Article]\n{item['title']}\n\n{item['content']}\n[end Article]"
                elif "news.ycombinator.com/item" in url:
                    item = parse_hn.get_item(url)
                    msg = f"[begin Article]\n{item['title']}\n\n{item['content']}\n[end Article]"
                elif "arxiv.org" in url:
                    item = parse_arxiv.get_item(url)
                    msg = f"[begin Article]\n{item['title']}\n\n{item['abstract']}\n[end Article]"
                    arxiv_urls[url] = len(messages)
                elif "youtube.com" in url:
                    item = parse_youtube.get_item(url)
                    msg = f"[begin Article]\n{item['title']}\n\n{item['content']}\n[end Article]"
                else:
                    item = util.get_details_from_url(url)
                    msg = f"[begin Article]\n{item['title']}\n\n{item['text']}\n[end Article]"
                messages.append(SystemMessage(content=msg))

    additional_content = {}
    for url in arxiv_urls:
        slack_msg.edit_line(f"_Downloading <{url}>..._")
        path = parse_arxiv.download_pdf(url)

        slack_msg.edit_line(f"_Parsing pdf..._")
        pdf = parse_pdf.ParsedPdf(path)

        new_content = []
        for section in pdf.section_names:
            slack_msg.edit_line(f"_Reading section '{section}'..._")
            messages.append(
                SystemMessage(
                    content=f"""[begin Section '{section}']
{pdf.get_section(section)}
[end Section '{section}']

[begin Question]
{conversation[-1]['text']}
[end Question]

Extract information from Section '{section}' that is relevant to the Question. The output should be a JSON dictionary with two keys. The first key should be the summary, and the second key should be a boolean value indicating whether there is useful information in the section. Here is an example output:
{{"summary": "<example summary text...>", "relevant": false}}
"""
                )
            )
            try:
                extraction = chat(messages).content
                extraction = json.loads(extraction)
                print(section, "|", extraction)
                if extraction["relevant"]:
                    new_content.append(
                        f"[begin Section '{section}']\n{extraction['summary']}\n[end Section '{section}']"
                    )
            except Exception as err:
                print(err)
            messages.pop()
        additional_content[url] = "\n\n".join(new_content)

    for url, i_msg in arxiv_urls.items():
        messages[i_msg].content += "\n" + additional_content[url]

    try:
        slack_msg.edit_line("_Thinking..._")
        response = chat(messages)
        slack_msg.edit_line(response.content)
    except Exception as err:
        slack_msg.edit_line(f"Sorry I encountered an error: {type(err)} {repr(err)}")


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
