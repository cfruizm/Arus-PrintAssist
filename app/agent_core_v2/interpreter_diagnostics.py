from app.agent_core_v2.interpreter import ignored_interpreter_fields

def summarize_ignored_fields(raw_payload):
    return {"ignored_fields": ignored_interpreter_fields(raw_payload)}
