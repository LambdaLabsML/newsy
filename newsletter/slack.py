from slack_sdk import WebClient
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

    def post(self, msg):
        return self.client.chat_postMessage(
            channel=self.conversation_id,
            text=msg,
            unfurl_links=False,
            unfurl_media=False,
        )
