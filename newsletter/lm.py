from openai import OpenAI

_CLIENT = OpenAI()
_ARGS = dict(
    model="gpt-5-nano-2025-08-07",
    timeout=120,
    tools=[{"type": "web_search"}],
)

def summarize_post(title: str, content: str) -> str:
    response = _CLIENT.responses.create(
        **_ARGS,
        instructions="""Generate a bulleted list that summarizes the main points from the Article. Prioritize:
1. Reducing the mental burden of reading the summary.
2. Conciseness over grammatical correctness.
3. Ability for general audience to understand.
4. Write the summary as if a 5 year old was the reader.
Generate at most 3 bullet points.
""",
        input=f"""[begin Article]
{title}

{content}
[end Article]
"""
    )
    return response.output_text


def summarize_abstract(title: str, content: str) -> str:
    response = _CLIENT.responses.create(
        **_ARGS,
        instructions="""Generate a bulleted list that summarizes the given Abstract.
There should be exactly 3 bullets describing:
1. The motivation & why its important
2. The method & how it works
3. The results & how well it works

The format of the summary must look like the following:
- *Motivation*: <description of motivation>
- *Method*: <description of method>
- *Results*: <description of results>
""",
        input = f"""[begin Abstract]
{title}

{content}
[end Abstract]
"""
    )
    return response.output_text


def summarize_comment(title: str, summary: str, comment: str) -> str:
    response = _CLIENT.responses.create(
        **_ARGS,
        instructions="""Write an extremely short (less than 5 words; no need for grammatically correct) info bite summarizing the Comment""",
        input=f"""[begin Article]
{title}

{summary}
[end Article]

[begin Comment]
{comment}
[end Comment]
"""
    )
    return response.output_text


def matches_filter(content: str, filter: str) -> bool:
    response = _CLIENT.responses.create(
        **_ARGS,
        instructions=f"""We are looking for Articles that match the following Filter
[begin Filter]
{filter}
[end Filter]

Output exactly one of ["yes", "no"].
Your response will be turned into a boolean value using response.strip().lower() == 'yes'""",
        input=f"""[[begin Article]
{content}
[end Article]
"""
    )
    content = response.output_text.strip().lower()
    return content == "yes" or content not in ["yes", "no"]
