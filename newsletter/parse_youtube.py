import requests
from youtube_transcript_api import YouTubeTranscriptApi, RequestBlocked
from .util import ScrapePreventedError

_CLIENT = YouTubeTranscriptApi()


def get_item(url: str):
    assert "youtube.com" in url
    assert "v=" in url
    video_id = url.split("v=")[1]

    try:
        params = {"format": "json", "url": url}
        meta = requests.get("https://www.youtube.com/oembed", params=params).json()

        parts = _CLIENT.fetch(video_id=video_id)
        content = " ".join(p["text"] for p in parts)

        return {
            "source": "YouTube",
            "title": meta["title"],
            "authors": [meta["author_name"]],
            "content_url": url,
            "content": content,
        }
    except RequestBlocked as e:
        raise ScrapePreventedError() from e
