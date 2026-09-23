import json

from langchain_core.messages import AIMessage


def test_call_llm_json_includes_schema_and_strips_fences():
    from app.agents._llm_json import call_llm_json
    from app.agents.prompts.resume_prompt import OUTPUT_SCHEMA

    class FakeLLM:
        def __init__(self):
            self.messages = []

        def invoke(self, messages):
            self.messages.append(messages)
            return AIMessage(content='```json\n{"resume_markdown":"resume","summary":"summary","ats_score":1,"keywords_matched":[],"keywords_missing":[],"changes_made":[],"warnings":[]}\n```')

    llm = FakeLLM()
    result = call_llm_json(llm, "system", "human", OUTPUT_SCHEMA)

    assert result.summary == "summary"
    assert json.dumps(OUTPUT_SCHEMA.model_json_schema(), separators=(",", ":")) in llm.messages[0][0].content


def test_call_llm_json_retry_keeps_schema():
    from app.agents._llm_json import call_llm_json
    from app.agents.prompts.resume_prompt import OUTPUT_SCHEMA

    class FakeLLM:
        def __init__(self):
            self.messages = []

        def invoke(self, messages):
            self.messages.append(messages)
            if len(self.messages) == 1:
                return AIMessage(content="not json")
            return AIMessage(content='{"resume_markdown":"resume","summary":"summary","ats_score":1,"keywords_matched":[],"keywords_missing":[],"changes_made":[],"warnings":[]}')

    llm = FakeLLM()
    call_llm_json(llm, "system", "human", OUTPUT_SCHEMA)

    schema_text = json.dumps(OUTPUT_SCHEMA.model_json_schema(), separators=(",", ":"))
    assert schema_text in llm.messages[0][0].content
    assert schema_text in llm.messages[1][-1].content
    # The retry shows the model its own invalid output so it repairs it.
    assert isinstance(llm.messages[1][-2], AIMessage)
    assert llm.messages[1][-2].content == "not json"
