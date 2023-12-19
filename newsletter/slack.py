from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.models.blocks import SectionBlock
import os
import certifi
import ssl


class SlackChannel:
    def __init__(self, name) -> None:
        self.name = name
        self.client = WebClient(
            token=os.environ.get("SLACK_BOT_TOKEN"),
            ssl=ssl.create_default_context(cafile=certifi.where()),
        )

        self.conversation_id = None
        # Call the conversations.list method using the WebClient
        for result in self.client.conversations_list():
            if self.conversation_id is not None:
                break
            for channel in result["channels"]:
                if channel["name"] == self.name:
                    self.conversation_id = channel["id"]
                    break

    def post(self, msg, thread_ts=None):
        return self.client.chat_postMessage(
            channel=self.conversation_id,
            text=msg,
            thread_ts=thread_ts,
            unfurl_links=False,
            unfurl_media=False,
        )

    def edit(self, src, new_content):
        return self.client.chat_update(
            channel=self.conversation_id,
            ts=src["ts"],
            text=new_content,
            unfurl_links=False,
            unfurl_media=False,
        )


class EditableMessage:
    def __init__(self, client: WebClient, channel: str, msg: str, ts=None):
        self.client = client
        self.channel = channel
        self.blocks = []
        self.lines = [msg]
        news = self.client.chat_postMessage(
            text="\n".join(self.lines), channel=self.channel, thread_ts=ts
        )
        self.thread = news.data["ts"]

    def start_new_section(self):
        self.blocks.append(SectionBlock(text="\n".join(self.lines)))
        self.lines.clear()

    def lazy_add_line(self, new_line):
        self.lines.append(new_line)

    def edit_line(self, new_line):
        self.lines[-1] = new_line
        self._update("\n".join(self.lines))

    def add_line(self, new_line):
        if len("\n".join(self.lines)) + 1 + len(new_line) >= 3000:
            self.start_new_section()
        self.lines.append(new_line)
        self._update("\n".join(self.lines))

    def set_progress_msg(self, msg):
        if len("\n".join(self.lines)) + 5 + len(msg) >= 3000:
            self.start_new_section()
        self._update("\n".join(self.lines) + "\n\n_" + msg + "_\n")

    def _update(self, content):
        if len(self.blocks) == 0:
            blocks = None
            text = content
        else:
            blocks = self.blocks + [SectionBlock(text=content)]
            text = "More news for you!"
        for _ in range(3):
            try:
                self.client.chat_update(
                    text=text,
                    blocks=blocks,
                    channel=self.channel,
                    unfurl_links=False,
                    unfurl_media=False,
                    ts=self.thread,
                )
                return
            except SlackApiError:
                ...

    def reply(self, msg):
        self.client.chat_postMessage(
            text=msg, channel=self.channel, thread_ts=self.thread
        )
