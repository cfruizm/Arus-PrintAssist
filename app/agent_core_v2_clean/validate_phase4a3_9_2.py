import sys,types
app=types.ModuleType("app");gateway=types.ModuleType("app.llm_gateway");models=types.ModuleType("app.llm_gateway.models")
class LLMRequest:
 def __init__(self,*args,**kwargs):self.args=args;self.kwargs=kwargs
models.LLMRequest=LLMRequest;sys.modules.setdefault("app",app);sys.modules.setdefault("app.llm_gateway",gateway);sys.modules.setdefault("app.llm_gateway.models",models)
from src.procedural_answer import ProceduralAnswerComposer,evidence_pack,_limit_web_document_chunks
class Result:
 ok=True; text="**1. Primera validación**\nComprueba el estado documentado [R1].\n\n**Validaciones finales**\nConfirma el resultado [R1]."; provider="fixture"; model="fixture"; usage={"prompt_tokens":10,"completion_tokens":20,"total_tokens":30}; finish_reason="stop"
 def to_dict(self):return {"ok":self.ok,"text":self.text,"provider":self.provider,"model":self.model,"usage":self.usage,"finish_reason":self.finish_reason}
class Gateway:
 def complete(self,request):return Result()
def rows(n=8):
 text="Validar comprobar configurar confirmar requisito compatible instalar actualizar guardar abrir. "*4
 return [{"id":f"R{i}","title":"Web KB","url":"https://example.com/kb","source":"https://example.com/kb","page":"","text":text+str(i),"metadata":{"canonical_url":"https://example.com/kb"}} for i in range(1,n+1)]
def run():
 retrieval={"evidence":rows(),"procedural_expansion":{"ok":True,"same_document_only":True,"ordered":True,"seed_document":"https://example.com/kb","pages":[]},"query":{"fields":{}}}
 packed=evidence_pack(retrieval);assert len(packed)>4 and len(_limit_web_document_chunks(packed))==4
 c=ProceduralAnswerComposer(Gateway(),900);a=c.compose("Necesito validaciones documentadas",{"intent":"troubleshooting","current_goal":"Validar falla","user_act":"new_request","topic_relation":"new_topic"},retrieval)
 assert a.mode=="procedural_documented_answer"
 assert c.validation["web_chunk_limit_applied"] is True
 assert c.validation["packed_evidence_count"]>c.validation["generation_evidence_count"]==4
 assert "https://example.com/kb" in a.text and "página no especificada" not in a.text
 import pathlib
 root=pathlib.Path(__file__).parent;code=(root/"procedural_answer.py").read_text();lab=(root/"lab_session.py").read_text()
 assert "len(pack(retrieval))" not in code and "phase4a3_9_2_web_evidence_pack_runtime_fix" in lab
 print({"passed":8,"failed":0,"phase":"4A.3.9.2"})
if __name__=="__main__":run()
