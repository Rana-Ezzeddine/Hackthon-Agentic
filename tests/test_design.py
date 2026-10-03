from paperplay.design import normalize_design,validate_design

def test_subject_defaults_are_distinct_and_governed():
    attention={"title":"Scaled dot-product attention","plan":{"core_idea":"matrix attention"}}
    circuit={"title":"RC low-pass filter","plan":{"core_idea":"frequency response"}}
    normalize_design(attention);normalize_design(circuit)
    assert attention["design"]["interaction"]["component"]=="matrix_lab"
    assert circuit["design"]["interaction"]["component"]=="parameter_sweep"
    assert not validate_design(attention) and not validate_design(circuit)

def test_invalid_composition_is_normalized_without_arbitrary_components():
    spec={"title":"Entropy","plan":{"core_idea":"probability distribution"},"design":{"palette":"unknown","accent":"red","orientation":{"formulation":"unsafe"},"interaction":{"component":"script","layout":"wild","diagram":"iframe"}}}
    normalize_design(spec)
    assert spec["design"]["interaction"]["component"]=="distribution_lab"
    assert spec["design"]["orientation"]["formulation"]=="intuition_first"
    assert spec["design"]["interaction"]["diagram"]=="bar"
    assert spec["design"]["accent"]==""
