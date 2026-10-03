from paperplay.design import normalize_design,validate_design


def lesson(component=None, control_type="slider"):
    return {"steps":[{"id":"definition","outcome_id":"o1","heading":"Definition","explanation":["Explain it."],"controls":[{"id":"x","type":control_type,"label":"Input","default":1,"min":0,"max":2,"step":0.1}],"components":[component or {"type":"bar","bind":"values.x"}],"guide":{"try":"Change it","notice":"It changes","why":"The value changed","preset":{"x":2},"evidence_bind":"values.x","expect":"r.values.x===2"},"takeaway":"The input matters."}]}


def test_lesson_components_are_governed():
    spec=lesson({"type":"flow_diagram","nodes":[{"id":"a","label":"Input"}],"edges":[]})
    normalize_design(spec)
    assert not validate_design(spec)


def test_unknown_component_and_inconsistent_shared_control_are_rejected():
    spec=lesson({"type":"iframe"})
    second={**spec["steps"][0],"id":"second"}
    second["controls"]=[{**spec["steps"][0]["controls"][0],"max":99}]
    spec["steps"].append(second)
    errors=validate_design(spec)
    assert "unknown display component" in errors
    assert "shared control has inconsistent definitions: x" in errors


def test_consistent_shared_control_is_allowed_across_steps():
    spec=lesson();spec["steps"].append({**spec["steps"][0],"id":"second"})
    assert not validate_design(spec)


def test_matrix_alias_is_normalized():
    spec=lesson(control_type="matrix")
    normalize_design(spec)
    assert spec["steps"][0]["controls"][0]["type"]=="matrix_editor"


def test_math_notation_alias_for_sweep_parameter_is_normalized():
    spec=lesson({"type":"sweep_plot","parameter":"d_k","min":1,"max":8,"points":4,"bind":"values.x"})
    spec["steps"][0]["controls"][0]["id"]="dk"
    normalize_design(spec)
    assert spec["steps"][0]["components"][0]["parameter"]=="dk"


def test_step_through_accepts_operations_or_array_binding():
    bound=lesson({"type":"step_through","title":"Walk it","bind":"series.levels"})
    operations=lesson({"type":"step_through","title":"Walk it","operations":[{"label":"First","bind":"values.x"}]})
    broken=lesson({"type":"step_through","title":"Walk it","operations":[{"label":"First"}]})
    assert not validate_design(bound)
    assert not validate_design(operations)
    assert "step_through operations need label and bind" in validate_design(broken)
