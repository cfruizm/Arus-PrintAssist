import json
from .documented_answer import DocumentedAnswerComposer

class Result:
 def __init__(self,text,purpose="test"):
  self.ok=True;self.text=text;self.provider="fixture";self.model="fixture";self.usage={"prompt_tokens":10,"completion_tokens":10,"total_tokens":20};self.finish_reason="stop";self.purpose=purpose
 def to_dict(self):return {"ok":self.ok,"text":self.text,"provider":self.provider,"model":self.model,"usage":self.usage,"finish_reason":self.finish_reason,"purpose":self.purpose}
class Gateway:
 def __init__(self,answers):self.answers=list(answers);self.calls=[]
 def complete(self,request):
  self.calls.append(request)
  return Result(self.answers.pop(0),request.purpose)

def retrieval():
 evidence=[
  {"id":"R1","title":"Generic network requirements","source":"/generic.pdf","page":"1","text":"Puertos requeridos: 443 TCP para HTTPS; 80 TCP para HTTP."},
  {"id":"R2","title":"Generic network requirements","source":"/generic.pdf","page":"2","text":"5222 TCP: mensajería segura mediante TLS. 3702 UDP: descubrimiento local."},
 ]
 return {"evidence_verdict":{"accepted":True,"selected_evidence":evidence},"generation_evidence":evidence,"evidence":evidence}

def understanding():return {"intent":"requirements","user_act":"request_elaboration","topic_relation":"same_topic","current_goal":"Document network ports","goal_updates":{}}

def run():
 initial="| Puerto | Protocolo | Descripción |\n|---|---|---|\n| 80 | TCP | HTTP [R1] |\n| 443 | TCP | HTTPS [R1] |"
 repaired="| Puerto | Protocolo | Descripción |\n|---|---|---|\n| 80 | TCP | HTTP [R1] |\n| 443 | TCP | HTTPS [R1] |\n| 3702 | UDP | Descubrimiento local [R2] |\n| 5222 | TCP | Mensajería TLS [R2] |"
 gateway=Gateway([initial,repaired]);composer=DocumentedAnswerComposer(gateway,760)
 answer=composer.compose("Consideraciones de red, puertos o firewall",understanding(),retrieval())
 complete_gateway=Gateway([repaired]);complete_composer=DocumentedAnswerComposer(complete_gateway,760)
 complete_answer=complete_composer.compose("Consideraciones de red, puertos o firewall",understanding(),retrieval())
 checks={
  "one_controlled_repair":len(gateway.calls)==2 and gateway.calls[1].purpose.endswith("coverage_repair"),
  "repair_completes_material_facts":composer.validation["factual_coverage"]["complete"] is True,
  "initial_omissions_exported":composer.validation["initial_factual_coverage"]["missing"]==["3702","5222"],
  "repair_diagnostic_exported":composer.validation["coverage_repair"]=={"attempted":True,"succeeded":True,"attempt_count":2},
  "repaired_answer_not_partial":answer.mode=="documented_answer" and answer.finish_reason=="coverage_repaired",
  "natural_markdown_table_preserved":"| Puerto |" in answer.text and "5222" in answer.text and "3702" in answer.text,
  "already_complete_answer_uses_one_call":len(complete_gateway.calls)==1 and complete_answer.mode=="documented_answer",
  "provider_attempts_available_for_telemetry":len(composer.last_provider_result.get("attempts") or [])==2,
 }
 failed=[k for k,v in checks.items() if not v]
 return {"phase":"4B.1.7","passed":len(checks)-len(failed),"failed":len(failed),"checks":checks}
if __name__=="__main__":
 result=run();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(1 if result["failed"] else 0)
