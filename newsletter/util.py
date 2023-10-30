import requests
import bs4


def get_json_from_url(url):
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.json()


def get_text_from_url(url):
    return get_details_from_url(url)["text"]


def get_details_from_url(url):
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.content, "html.parser")
    ele = soup.find(attrs={"role": "main"})
    if ele is None:
        ele = soup.find("main")
    if ele is None:
        ele = soup.body

    title = soup.title.string

    if ele is not None:
        text = ele.get_text().strip()
    else:
        text = " ".join(t.strip() for t in soup.findAll(text=True))

    return {"title": title, "text": text}
