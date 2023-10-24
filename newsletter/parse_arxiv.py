import arxiv
from datetime import datetime, timedelta


def iter_todays_papers(category: str):
    client = arxiv.Client()
    search = arxiv.Search(
        query=f"cat:{category}", sort_by=arxiv.SortCriterion.SubmittedDate
    )

    today = datetime.utcnow().date()

    for item in client.results(search):
        # only include papers from the last day
        if (today - item.published.date()) >= timedelta(days=2):
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
