from src.models import ConversationMemory
from src.escalation_coordinator import start,handle
from src.escalation_export import build_export

def run():
 m=ConversationMemory(conversation_id='test-conversation');m.active_subject='Product Alpha';m.support_case.symptoms=['jobs disappear'];m.support_case.attempts=[{'action':'restart client','result':'failed'}];m.support_case.affected_scope='multiple users'
 s=m.escalation
 r=start(s,m,{},'User requested escalation');assert s.status=='collecting' and s.pending_field=='client_contract_location';assert s.fields['product_or_service']['value']=='Product Alpha';assert s.fields['issue_description']['source']=='support_case';assert 'failed' in s.fields['troubleshooting_performed']['value']
 # Pending field owns response and unknown values advance without cross-field inference.
 r=handle(s,'Client One',m,{});assert s.fields['client_contract_location']['value']=='Client One' and s.pending_field=='software_version'
 r=handle(s,'no sé',m,{});assert 'software_version' in s.unknown_fields and s.pending_field=='device_data'
 r=handle(s,'Printer Q123, main site',m,{});assert s.fields['device_data']['value']=='Printer Q123, main site' and s.fields['client_contract_location']['value']=='Client One'
 assert s.pending_field=='evidence'
 r=handle(s,'no tengo evidencia',m,{});assert s.pending_field is None or s.pending_field=='impact_scope'
 if s.pending_field=='impact_scope':r=handle(s,'multiple users',m,{})
 assert s.status=='review'
 # Correction and confirmation.
 r=handle(s,'corrige cliente a Client Two',m,{});assert s.fields['client_contract_location']['value']=='client two' and s.corrections
 r=handle(s,'confirmar',m,{});assert s.status=='completed' and s.confirmed and r['export']['schema_version']=='agent_core_v2_clean_escalation_v1'
 # Next message exits terminal lifecycle and does not repeat summary.
 r=handle(s,'gracias',m,{});assert not r['handled'] and s.status=='inactive'
 # Cancellation path.
 s2=ConversationMemory().escalation;start(s2,ConversationMemory(),{},'explicit');r=handle(s2,'cancelar',ConversationMemory(),{});assert s2.status=='cancelled'
 # Suspension/resumption path.
 s3=ConversationMemory().escalation;start(s3,ConversationMemory(),{},'explicit');handle(s3,'pausar',ConversationMemory(),{});assert s3.status=='suspended';r=handle(s3,'reanudar escalamiento',ConversationMemory(),{});assert r['handled'] and s3.status=='collecting'
 # Export has provenance and unknown fields.
 x=build_export(s,'test-conversation');assert x['incident']['product_or_service']['status']=='confirmed' and 'software_version' in x['unknown_fields']
 # No campaign product vocabulary in production escalation modules.
 import pathlib
 policy=''.join((pathlib.Path(__file__).parent/f).read_text() for f in ('escalation_contract.py','escalation_coordinator.py','escalation_export.py'))
 for forbidden in ('PaperCut','HP SDS','DA0390','facturación con template'):assert forbidden.casefold() not in policy.casefold()
 print({'passed':9,'failed':0,'phase':'4A.1'})
if __name__=='__main__':run()
