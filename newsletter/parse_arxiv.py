import arxiv
from datetime import datetime, timedelta


def get_item(url: str):
    assert "arxiv.org" in url

    client = arxiv.Client()
    search = arxiv.Search(id_list=[url.split("/")[-1].replace(".pdf", "")])
    item = next(client.results(search))

    return {
        "source": "arxiv",
        "title": item.title,
        "url": item.entry_id,
        "authors": [str(a) for a in item.authors],
        "abstract": item.summary,
        "category": item.primary_category,
        "pdf_url": item.pdf_url,
    }


def iter_todays_papers(category: str):
    client = arxiv.Client()
    search = arxiv.Search(
        query=f"cat:{category}", sort_by=arxiv.SortCriterion.SubmittedDate
    )

    today = datetime.utcnow().date()

    if today.weekday() == 0:
        # its a monday! grab papers from the last friday
        delta = timedelta(days=4)
    else:
        delta = timedelta(days=2)

    for item in client.results(search):
        # only include papers from the last day
        if (today - item.published.date()) >= delta:
            break

        yield {
            "source": "arxiv",
            "title": item.title,
            "url": item.entry_id,
            "authors": [str(a) for a in item.authors],
            "abstract": item.summary,
            "category": item.primary_category,
            "pdf_url": item.pdf_url,
        }
