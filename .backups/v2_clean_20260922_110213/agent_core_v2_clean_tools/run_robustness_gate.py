from __future__ import annotations
import argparse,json
from app.agent_core_v2_clean.evidence_sufficiency import assess_procedural_evidence
from app.agent_core_v2_clean.robustness_gate import write_report

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',default='agent_core_v2_clean_robustness_report.json');a=p.parse_args();r=write_report(a.output,assess_procedural_evidence);print(json.dumps({'approved':r['approved'],'passed':r['passed'],'failed':r['failed'],'output':a.output},ensure_ascii=False));raise SystemExit(0 if r['approved'] else 1)
if __name__=='__main__':main()
