from paperplay.design import normalize_design,validate_design

def test_subject_defaults_are_distinct_and_governed():
    attention={"title":"Scaled dot-product attention","plan":{"core_idea":"matrix attention"}}
    circuit={"title":"RC low-pass filter","plan":{"core_idea":"frequency response"}}
    normalize_design(attention);normalize_design(circuit)
    assert attention["design"]["theme"]=="blueprint"
    assert circuit["design"]["theme"]=="circuit"
    assert not validate_design(attention) and not validate_design(circuit)

def test_invalid_composition_is_normalized_without_arbitrary_components():
    spec={"title":"Entropy","plan":{"core_idea":"probability distribution"},"design":{"theme":"unknown","accent":"red","composition":[{"component":"script","variant":"anything"},{"component":"hero","variant":"wild"}]}}
    normalize_design(spec)
    names=[x["component"] for x in spec["design"]["composition"]]
    assert names[0]=="hero" and names[-1]=="evidence"
    assert "script" not in names
    assert all(name in names for name in ("concept","playground","explorations","limitation"))
    assert spec["design"]["accent"]==""
