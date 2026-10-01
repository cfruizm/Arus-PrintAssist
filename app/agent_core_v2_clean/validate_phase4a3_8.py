from src.guidance_integrity import build_guidance_integrity_contract

def run():
 r={"_case_context":{"attempts":[{"action":"check credentials","result":"failure continues","outcome":"unchanged"}]},"_answer_context":{"delivered_guidance":[{"action":"run as administrator","status":"delivered"}]}}
 c=build_guidance_integrity_contract(r)
 assert c["user_confirmed_attempts"][0]["action"]=="check credentials"
 assert c["assistant_delivered_guidance"][0]["action"]=="run as administrator"
 assert c["user_confirmed_attempts"][0]["authority"]=="user_confirmed_case_memory"
 assert c["assistant_delivered_guidance"][0]["authority"]=="assistant_recommendation_only"
 assert c["disruptive_guidance_policy"]["required_elements"]
 import pathlib
 root=pathlib.Path(__file__).parent
 doc=(root/"documented_answer.py").read_text();proc=(root/"procedural_answer.py").read_text();internal=(root/"internal_knowledge.py").read_text();lab=(root/"lab_session.py").read_text()
 for code in (doc,proc,internal):
  assert "user_confirmed_attempts" in code and "assistant_delivered_guidance" in code and "guidance_integrity_contract" in code
 assert "phase4a3_8_confirmed_action_integrity" in lab
 assert "HP Access Control" not in (root/"guidance_integrity.py").read_text()
 print({"passed":8,"failed":0,"phase":"4A.3.8"})
if __name__=="__main__":run()
