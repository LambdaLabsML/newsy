import argparse
import time
import json
import os
import itertools

from newsletter import parse_hn, parse_reddit, lm, parse_arxiv
from newsletter.slack import SlackChannel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--filter",
        default="Articles related to Artificial intelligence (AI), Machine Learning (ML), foundation models, language models, GPT, generation models",
    )
    parser.add_argument(
        "-p",
        "--paper-filter",
        default="Papers related to:\n1. evaluating GPT or large language models\n2. prompting techniques for language models\n3. techniques for optimizing size or efficiency of language models (like quantization or sparsification)\n4. techniques for increasing sequence length of transformers",
    )
    parser.add_argument("-c", "--channel", default="hackernews")
    parser.add_argument("--db", default=".db")
    parser.add_argument("--dry-run", default=False, action="store_true")
    args = parser.parse_args()

    slack = SlackChannel(args.channel)

    if not os.path.exists(args.db):
        with open(args.db, "w") as fp:
            fp.write("[]")

    with open(args.db) as fp:
        processed = set(json.load(fp))

    posts = itertools.chain(
        parse_hn.iter_top_posts(num_posts=25),
        parse_reddit.iter_top_posts("MachineLearning", num_posts=2),
    )

    for post in posts:
        if not args.dry_run and post["comments_url"] in processed:
            continue

        processed.add(post["comments_url"])
        with open(args.db, "w") as fp:
            json.dump(list(processed), fp)

        try:
            summary = lm.summarize_post(post["title"], post["content"])
            should_show = lm.matches_filter(summary, args.filter)

            lines = [
                f"<{post['content_url']}|{post['title']}>",
                f"{post['source']} <{post['comments_url']}|Comments>:",
            ]
            for i, c in enumerate(post["comments"]):
                comment_summary = lm.summarize_comment(
                    post["title"], summary, c["content"]
                )
                if "score" in c:
                    lines.append(
                        f"{i + 1}. (+{c['score']}) <{c['url']}|{comment_summary}>"
                    )
                else:
                    lines.append(f"{i + 1}. <{c['url']}|{comment_summary}>")

            msg = "\n".join(lines)
            print(msg)

            if not args.dry_run and should_show:
                r = slack.post(msg)
                if r.data["ok"]:
                    slack.post(summary, thread_ts=r.data["ts"])
        except Exception as err:
            print(err)

    paper_msg = None
    lines = [
        "Here's a list of papers from today related to\n> {}".format(
            args.paper_filter.replace("\n", "\n> ")
        )
    ]
    for paper in parse_arxiv.iter_todays_papers(category="cs.AI"):
        if not args.dry_run and paper["url"] in processed:
            continue

        processed.add(paper["url"])
        with open(args.db, "w") as fp:
            json.dump(list(processed), fp)

        try:
            summary = lm.summarize_post(paper["title"], paper["abstract"])
            should_show = lm.matches_filter(
                "Abstract:\n" + paper["abstract"] + "\n\nSummary:\n" + summary,
                args.paper_filter,
            )

            msg = f"{len(lines)}. <{paper['url']}|{paper['title']}>"
            print(msg)
            if not args.dry_run and should_show:
                lines.append(msg)
                if paper_msg is None:
                    paper_msg = slack.post("\n".join(lines))
                else:
                    paper_msg = slack.edit(paper_msg.data, "\n".join(lines))
        except Exception as err:
            print(err)


if __name__ == "__main__":
    main()
