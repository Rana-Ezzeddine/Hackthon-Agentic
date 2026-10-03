from paperplay.design import normalize_design,validate_design


def lesson(component=None, control_type="slider"):
    return {"steps":[{"id":"definition","outcome_id":"o1","heading":"Definition","explanation":["Explain it."],"controls":[{"id":"x","type":control_type,"label":"Input","default":1,"min":0,"max":2,"step":0.1}],"components":[component or {"type":"bar","bind":"values.x"}],"guide":{"try":"Change it","notice":"It changes","why":"The value changed","preset":{"x":2},"evidence_bind":"values.x","expect":"r.values.x===2"},"takeaway":"The input matters."}]}


def test_lesson_components_are_governed():
    spec=lesson({"type":"flow_diagram","nodes":[{"id":"a","label":"Input"}],"edges":[]})
    normalize_design(spec)
    assert not validate_design(spec)


def test_unknown_component_and_duplicate_control_are_rejected():
    spec=lesson({"type":"iframe"})
    spec["steps"].append({**spec["steps"][0],"id":"second"})
    errors=validate_design(spec)
    assert "unknown display component" in errors
    assert "invalid or duplicate control id" in errors


def test_matrix_alias_is_normalized():
    spec=lesson(control_type="matrix")
    normalize_design(spec)
    assert spec["steps"][0]["controls"][0]["type"]=="matrix_editor"
