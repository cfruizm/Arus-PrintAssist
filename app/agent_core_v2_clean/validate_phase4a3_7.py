from src.source_footer import compact_sources
from src.diagnostic_language import soften_diagnostic_certainty
from src.escalation_coordinator import OUTCOME_LABELS
from src.workflow_understanding import WorkflowInterpreter

def run():
 evidence=[{"id":"R1","title":"Guide","source":"doc-a","page":"24"},{"id":"R2","title":"Guide","source":"doc-a","page":"29"},{"id":"R3","title":"Notes","source":"doc-b","page":"8"}]
 one=compact_sources(evidence,["R1","R2"]);assert one=="**Fuente documental:** Guide, págs. 24 y 29."
 many=compact_sources(evidence,["R1","R2","R3"]);assert many.count("Guide")==1 and many.count("Notes")==1 and many.startswith("**Fuentes documentales**")
 text,changed=soften_diagnostic_certainty("El problema no reside en la autenticación, sino en la red.","troubleshooting");assert changed and "reduce la probabilidad" in text and "ampliar el diagnóstico" in text
 assert OUTCOME_LABELS["unchanged"]=="sin cambios"
 class G:pass
 wi=WorkflowInterpreter(G(),96);assert wi.max_tokens==96
 import pathlib
 root=pathlib.Path(__file__).parent;code=(root/"workflow_understanding.py").read_text();lab=(root/"lab_session.py").read_text()
 assert 'role!="workflow_action" and action!="none"' in code and "phase4a3_7_presentation_and_semantic_polish" in lab
 print({"passed":6,"failed":0,"phase":"4A.3.7"})
if __name__=="__main__":run()
