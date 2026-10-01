import json
from .documented_answer import _evidence_fact_obligations,factual_coverage

def run():
 evidence=[
  {"id":"R1","page":"1","text":"Puertos requeridos: 443 TCP para HTTPS; 80 TCP para HTTP."},
  {"id":"R2","page":"2","text":"5222 TCP: mensajería segura mediante TLS. 3702 UDP: descubrimiento local."},
 ]
 broad=_evidence_fact_obligations("Consideraciones de red, puertos o firewall",evidence)
 broad_missing=factual_coverage("Consideraciones de red, puertos o firewall",evidence,"Se requieren 443 y 80.")
 broad_complete=factual_coverage("Consideraciones de red, puertos o firewall",evidence,"Se requieren 80, 443, 3702 y 5222.")
 tls=factual_coverage("¿Qué puertos utilizan TLS?",evidence,"El puerto 5222 utiliza TLS.")
 one_page_complete=factual_coverage("¿Qué puertos utilizan TLS?",evidence,"El puerto 5222 utiliza TLS.")
 checks={
  "broad_query_derives_all_material_ports":broad["facts"]==["80","443","3702","5222"],
  "broad_omission_detected":broad_missing["missing"]==["3702","5222"] and not broad_missing["complete"],
  "broad_complete_answer_accepted":broad_complete["complete"],
  "protocol_followup_scoped_to_tls":tls["facts"]==["5222"] and tls["complete"],
  "single_page_can_be_complete":one_page_complete["complete"],
  "no_product_or_document_identity_required":all(x not in json.dumps(broad).casefold() for x in ["hp","sds","papercut"]),
 }
 failed=[k for k,v in checks.items() if not v]
 return {"phase":"4B.1.6","passed":len(checks)-len(failed),"failed":len(failed),"checks":checks}
if __name__=="__main__":
 result=run();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(1 if result["failed"] else 0)
