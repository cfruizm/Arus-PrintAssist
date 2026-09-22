from dataclasses import dataclass
@dataclass(frozen=True)
class CoverageAudit: required:tuple;represented:tuple;missing:tuple;complete:bool
def audit_enumerated_coverage(options,answer):
 required=tuple(dict.fromkeys(str(x).strip() for x in options if str(x).strip()));low=str(answer or "").casefold();represented=tuple(x for x in required if x.casefold() in low);missing=tuple(x for x in required if x not in represented);return CoverageAudit(required,represented,missing,not missing)
def response_shape(intent):return {"requirements":{"primary":"prerequisites_not_procedure"},"enumeration":{"cover_all_documented_options":True},"comparison":{"compare_all_requested_subjects":True},"procedural":{"ordered_steps":True},"troubleshooting":{"respect_confirmed_attempts":True}}.get(str(intent or "").casefold(),{"proportional":True})
