import openai


def summarize_post(post, model="gpt-3.5-turbo-16k"):
    result = openai.ChatCompletion.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": f"""{post['title']}

{post['content']}
---

Generate at most 3 bullet points summarizing the article. Do not mention the title of the article, or include filler words. The title will be included along with these bullet points.

Strictly adhere to the following rules:
- Do not generate more than 3 bullet points
- Each individual bullet point should be at most 5 words
- Each individual bullet point does not need to be a grammatically correct sentence.
- Prioritize bullet points that can be very quickly skimmed.
- Reduce mental strain while skimming the bullet points.

Here are the bullet points:
""",
            }
        ],
    )
    return result.choices[0].message["content"]


def summarize_comment(title, summary, comment, model="gpt-3.5-turbo-16k"):
    result = openai.ChatCompletion.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": f"""**Title**: {title}

**Article Summary**:
{summary}

**Comment**:
{comment}

Write an extremely short (less than 5 words; no need for grammatically correct) info bite summarizing the comment:
""",
            }
        ],
    )
    return result.choices[0].message["content"]


def matches_filter(summary, filter, model="gpt-3.5-turbo-16k"):
    result = openai.ChatCompletion.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": f"""**Article**: {summary}

We are looking for Articles that match the following **Filter**: {filter}

Does the above Article match the above Filter? The Answer should be Yes or No:
**Answer**:
""",
            }
        ],
    )
    content = result.choices[0].message["content"].strip().lower()
    return content == "yes" or content not in ["yes", "no"]
