from pathlib import Path

def run():
    root=Path(__file__).resolve().parent
    response=(root/'response.py').read_text(encoding='utf-8')
    agent=(root/'agent.py').read_text(encoding='utf-8')
    lab=(root/'lab_session.py').read_text(encoding='utf-8')
    checks={
        'deterministic_social_response':'social_turn_uses_deterministic_terminal_response' in response,
        'no_social_response_llm':'return AgentResponse("Estoy aquí para ayudarte.' in response,
        'neutral_social_boundary':'neutral_social_interruption' in agent,
        'social_terminal_event':'deterministic_social_terminal' in agent,
        'social_context_preserved':'preserved_previous_answer_context' in lab,
        'social_finalize_returns_before_capture':lab.index('if social_turn:') < lab.index('context = capture_answer_context'),
        'format_updated':'henkia_support_assist_4b1_2' in lab,
        'no_literal_social_word_routing':all(x not in response.casefold() for x in ['message.lower()','message.casefold()','muchas gracias','hasta luego']),
    }
    failed=[k for k,v in checks.items() if not v]
    return {'passed':len(checks)-len(failed),'failed':len(failed),'checks':checks}

if __name__=='__main__':
    import json
    result=run();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(1 if result['failed'] else 0)
