from app.agent_core_v2_clean.citation_finalizer import finalize_citations
def plan(ids,mapping):return {'evidence_plan':{'documented_ids':ids,'citation_map':mapping,'citation_namespace':'canonical'},'response_plan':{'allow_documented_claims':True}}
def test_canonical_collision_is_not_remapped():
 text,a=finalize_citations('Pages [R1][R2][R3].',plan(['R1','R2','R3','R7'],{'R1':'R7','R2':'R1','R3':'R2'}));assert text=='Pages [R1][R2][R3].';assert a.remapped_ids=={}
def test_noncanonical_original_can_be_remapped():
 text,a=finalize_citations('Page [R8].',plan(['R1'],{'R8':'R1'}));assert text=='Page [R1].' and a.valid
def test_unknown_is_rejected():
 _,a=finalize_citations('Page [R9].',plan(['R1'],{}));assert not a.valid and a.unknown_ids==['R9']
