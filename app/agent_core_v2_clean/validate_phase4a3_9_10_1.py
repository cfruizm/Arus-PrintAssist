from src.models import ConversationMemory, TurnUnderstanding
from src.memory import apply_understanding
from src.escalation_coordinator import start

def run():
    m=ConversationMemory()
    u=TurnUnderstanding(
        "attempt_result","troubleshooting","same_topic","in_scope","Continue diagnosis",False,{},[
            {"type":"attempted_action","value":"inspect shared queue","result_observed":"no change","outcome_observed":"unchanged"},
            {"type":"attempted_action","value":"restart processing service","result_observed":"failure continues","outcome_observed":"unchanged"},
        ],False,None,True,1.0,"fixture"
    )
    apply_understanding(m,u)
    assert m.support_case.attempts == [
        {"action":"inspect shared queue","result":"no change","outcome":"unchanged"},
        {"action":"restart processing service","result":"failure continues","outcome":"unchanged"},
    ]
    start(m.escalation,m,{},"request")
    summary=m.escalation.fields["troubleshooting_performed"]["value"]
    assert "Resultado: no change" in summary and "Resultado: failure continues" in summary
    assert summary.count("Estado: sin cambios") == 2
    import pathlib
    root=pathlib.Path(__file__).parent
    memory=(root/"memory.py").read_text().casefold()
    assert '"result_observed"' in memory and '"outcome_observed"' in memory
    for forbidden in ("papercut","find-me","print provider","hp sds","hp access control"):
        assert forbidden not in memory
    print({"passed":9,"failed":0,"phase":"4A.3.9.10.1"})

if __name__=="__main__":run()
