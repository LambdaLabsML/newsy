import argparse
import time
import json
import os
import itertools

from newsletter import hn, reddit, lm
from newsletter.slack import SlackChannel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--filter",
        default="Articles related to Artificial intelligence (AI), Machine Learning (ML), foundation models, language models",
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
        hn.iter_top_posts(num_posts=25),
        reddit.iter_top_posts("MachineLearning", num_posts=5),
    )

    for post in posts:
        if not args.dry_run and post["comments_url"] in processed:
            continue

        processed.add(post["comments_url"])
        with open(args.db, "w") as fp:
            json.dump(list(processed), fp)

        try:
            summary = lm.summarize_post(post)
            should_show = lm.matches_filter(summary, args.filter)

            lines = [
                f"<{post['content_url']}|{post['title']}>",
                f"{post['source']} <{post['comments_url']}|Comments>:",
            ]
            for i, c in enumerate(post["comments"]):
                comment_summary = lm.summarize_comment(
                    post["title"], summary, c["content"]
                )
                lines.append(f"{i + 1}. (+{c['score']}) <{c['url']}|{comment_summary}>")

            msg = "\n".join(lines)
            print(msg)

            if not args.dry_run and should_show:
                r = slack.post(msg)
                if r.data["ok"]:
                    slack.post(summary, thread_ts=r.data["ts"])
        except Exception as err:
            print(err)


if __name__ == "__main__":
    main()
