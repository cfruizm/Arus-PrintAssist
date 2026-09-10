from app.agent_core_v2_clean.semantic_fit import evaluate_item,apply_semantic_fit,capture_answer_context

def test_bilingual_concepts_match():
 item={"title":"Authentication validation","text":"Verify supported authentication requirements"}
 fit=evaluate_item(item,"validar autenticación segura",{"goal":"autenticación segura"},{})
 assert "concept:authentication" in fit["concept_matches"] and "concept:validation" in fit["concept_matches"]
def test_coherent_group_selected():
 r={"query":{"text":"tracking de impresion","fields":{"goal":"tracking de impresion"}},"selection":{"quality":0.5},"evidence":[{"id":"R1","title":"Generic tool","source":"a","text":"tracking impresoras"},{"id":"R2","title":"About print tracking","source":"b","text":"print tracking records who prints"},{"id":"R3","title":"Configure print tracking","source":"b","text":"enable print tracking and verify job log"}]}
 out=apply_semantic_fit(r,{})
 assert out["semantic_fit"]["selected_document"]=="b" and set(out["semantic_fit"]["selected_group_ids"])=={"R2","R3"}
def test_previous_cited_evidence_carried_into_followup():
 context={"source_identities":["a"],"cited_evidence":[{"id":"R1","title":"Access guide","source":"a","text":"verify access compatibility"}],"main_text_excerpt":"access guidance"}
 r={"query":{"text":"what should I validate","fields":{"goal":"configure access","user_act":"follow_up"}},"selection":{"quality":0.2},"evidence":[{"id":"R2","title":"Other document","source":"b","text":"unrelated billing"}]}
 out=apply_semantic_fit(r,context)
 assert out["semantic_fit"]["carried_previous_evidence"]==1 and any(x.get("carried_from_previous_answer") for x in out["evidence"])
def test_capture_stores_compact_cited_evidence():
 result={"answer":{"text":"fact [R1]","mode":"documented_answer","finish_reason":"stop"},"understanding":{"current_goal":"goal"},"retrieval":{"evidence":[{"id":"R1","title":"Doc","source":"a","text":"fact text","metadata":{"product":"x","noise":"y"}}]}}
 ctx=capture_answer_context(result)
 assert ctx["cited_evidence"][0]["text"]=="fact text" and "noise" not in ctx["cited_evidence"][0]["metadata"]
