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

Generate a summary for the above article. Prioritize:
1. Reducing the mental burden of reading the summary.
2. Conciseness over grammatical correctness.
3. Ability for general audience to understand.
4. Write the summary as if a 5 year old was the reader.
Here is the summary:
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
