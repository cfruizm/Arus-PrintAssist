import sys,types
app=types.ModuleType("app");gateway=types.ModuleType("app.llm_gateway");models=types.ModuleType("app.llm_gateway.models")
class LLMRequest:
 def __init__(self,*args,**kwargs):self.args=args;self.kwargs=kwargs
models.LLMRequest=LLMRequest;sys.modules.setdefault("app",app);sys.modules.setdefault("app.llm_gateway",gateway);sys.modules.setdefault("app.llm_gateway.models",models)
from src.documented_answer import DocumentedAnswerComposer,safe_cited_partial

class Result:
 ok=True;provider="fixture";model="fixture";usage={"prompt_tokens":10,"completion_tokens":30,"total_tokens":40};finish_reason="length"
 text="**1. Primera validación**\nComprueba la evidencia disponible [R1].\n\n**2. Segunda validación**\nEsta oración queda incompleta"
 def to_dict(self):return {"ok":self.ok,"text":self.text,"provider":self.provider,"model":self.model,"usage":self.usage,"finish_reason":self.finish_reason,"purpose":"agent_core_v2_clean_documented_answer"}
class Gateway:
 def complete(self,request):return Result()

def run():
 partial,cited=safe_cited_partial(Result.text,["R1"],"length")
 assert partial.endswith("[R1]") and cited==["R1"] and "incompleta" not in partial
 evidence=[{"id":"R1","title":"Web KB","url":"https://example.com/kb","source":"https://example.com/kb","page":"","text":"Validar comprobar configurar confirmar requisito compatible instalar actualizar guardar abrir. "*5,"metadata":{"canonical_url":"https://example.com/kb"}}]
 retrieval={"generation_evidence":evidence,"evidence":evidence,"evidence_verdict":{"selected_evidence":evidence},"_answer_context":{},"_case_context":{"attempts":[]}}
 c=DocumentedAnswerComposer(Gateway(),480)
 a=c.compose("Necesito un diagnóstico documentado",{"intent":"troubleshooting","current_goal":"Diagnosticar","user_act":"new_request","topic_relation":"new_topic"},retrieval)
 assert a.mode=="documented_answer_partial" and a.finish_reason=="safe_partial"
 assert "Respuesta parcial segura" in a.text and "https://example.com/kb" in a.text
 assert c.validation["safe_partial_terminal"] is True
 import pathlib
 root=pathlib.Path(__file__).parent
 lab=(root/"lab_session.py").read_text()
 assert '"documented_answer","documented_answer_partial"' in lab
 assert 'authorized_documented_answer_is_terminal' in lab
 assert 'phase4a3_9_3_documented_partial_terminal_arbitration' in lab
 forbidden=(root/"documented_answer.py").read_text().casefold()
 for phrase in ("papercut","find-me","trabajos desaparecen","cola del servidor"):
  assert phrase not in forbidden
 print({"passed":8,"failed":0,"phase":"4A.3.9.3"})
if __name__=="__main__":run()
