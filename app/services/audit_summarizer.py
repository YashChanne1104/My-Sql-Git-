from langchain_core.prompts import ChatPromptTemplate
# pyrefly: ignore [missing-import]
from langchain_mistralai import ChatMistralAI

model = ChatMistralAI(model="mistral-large-latest", temperature=0)

QUERY_SUMMARY_PROMPT = ChatPromptTemplate.from_template(
    """
    Describe what this SQL script actually DOES, in one short plain-English
    sentence for someone non-technical reading an audit log. Focus on the
    business action -- e.g. "Deactivates a branch record" or "Retrieves
    invoice report data filtered by branch". Do not mention who wrote it,
    review status, or approval -- ONLY describe the SQL's purpose/effect.

    SQL Type: {sql_type}
    SQL:
    {sql_text}

    Write only the one-sentence description, nothing else.
    """
)


def generate_query_summary(sql_text: str, sql_type: str) -> str:
    """
    Generates a plain-English description of what a SQL script does.
    Called ONCE per submission, at creation time -- the result is cached
    on submission.query_summary and never regenerated, since what the
    SQL *does* never changes after it's written.
    """
    messages = QUERY_SUMMARY_PROMPT.format_messages(sql_type=sql_type, sql_text=sql_text[:800])
    response = model.invoke(messages)
    return response.content.strip()