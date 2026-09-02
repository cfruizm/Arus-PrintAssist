import json,sys
from pathlib import Path
def main():
 data=json.loads(Path(sys.argv[1] if len(sys.argv)>1 else "tools/agent_core_v2/real_lab_scenarios.json").read_text(encoding="utf-8"));print(json.dumps({"scenarios":len(data),"ids":[x["id"] for x in data]},indent=2))
if __name__=="__main__":main()
