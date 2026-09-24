from src.documented_answer import evidence_pack, contradicted_absence, validate_citations

def _e(i, page, text):
    return {"id": f"R{i}", "title": "Guide", "page": str(page), "source": "guide.pdf", "text": text}

def run():
    retrieval = {"evidence": [
        _e(1, 1, "The platform is a centralized print management system for enterprise environments."),
        _e(2, 2, "It provides monitoring, device administration, reporting and secure release capabilities."),
        _e(3, 7, "Additional capabilities include policy management and usage visibility."),
    ]}
    u = {"intent": "conceptual", "current_goal": "Explain the platform", "goal_updates": {"subject": "platform"}}
    packed = evidence_pack(retrieval, "What is the platform and what can it do?", u)
    assert len(packed) == 3
    assert {x["page"] for x in packed} == {"1", "2", "7"}
    valid, cited = validate_citations("It is a system [R1] with monitoring [R2].", ["R1", "R2", "R3"])
    assert valid and cited == ["R1", "R2"]
    blocked, coverage = contradicted_absence("The document does not specify monitoring.", "Which monitoring capabilities exist?", u, packed)
    assert blocked and "monitoring" in coverage["covered"]
    print({"passed": 4, "failed": 0, "phase": "3C.1"})

if __name__ == "__main__":
    run()
