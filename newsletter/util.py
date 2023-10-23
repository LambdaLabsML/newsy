import requests
import bs4


def get_json_from_url(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def get_text_from_url(url):
    response = requests.get(url)
    response.raise_for_status()
    soup = bs4.BeautifulSoup(response.content, "html.parser")
    ele = soup.find(attrs={"role": "main"})
    if ele is None:
        ele = soup.find("main")
    if ele is None:
        ele = soup.body

    if ele is not None:
        return ele.get_text().strip()
    else:
        return " ".join(t.strip() for t in soup.findAll(text=True))
