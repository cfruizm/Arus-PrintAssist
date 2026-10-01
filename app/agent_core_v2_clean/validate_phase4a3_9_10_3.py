from src.models import ConversationMemory, TurnUnderstanding
from src.memory import apply_understanding
from src.escalation_coordinator import start

def run():
    m=ConversationMemory()
    u=TurnUnderstanding(
        "attempt_result","troubleshooting","same_topic","in_scope","Continue diagnosis",False,{},[
            {"type":"attempted_action","value":"inspect shared queue","result_text":"failure continues","outcome_text":"unchanged"},
            {"type":"attempted_action","value":"restart processing service","result_text":"failure continues","observed_outcome":"unchanged"},
        ],False,None,True,1.0,"fixture"
    )
    apply_understanding(m,u)
    assert m.support_case.attempts == [
        {"action":"inspect shared queue","result":"failure continues","outcome":"unchanged"},
        {"action":"restart processing service","result":"failure continues","outcome":"unchanged"},
    ]
    start(m.escalation,m,{},"request")
    summary=m.escalation.fields["troubleshooting_performed"]["value"]
    assert summary.count("Estado: sin cambios") == 2
    assert summary.count("Resultado: failure continues") == 2
    import pathlib
    root=pathlib.Path(__file__).parent
    memory=(root/"memory.py").read_text().casefold()
    assert '"outcome_text"' in memory and '"observed_outcome"' in memory
    for forbidden in ("papercut","find-me","print provider","cola del servidor","hp sds"):
        assert forbidden not in memory
    print({"passed":10,"failed":0,"phase":"4A.3.9.10.3"})

if __name__=="__main__":run()
