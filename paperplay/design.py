"""Govern the model's pedagogical and visual choices inside the flexible shell."""
from __future__ import annotations
import re

FORMULATIONS={"equation_first","visual_first","intuition_first","derivation","comparison","worked_example"}
INTERACTIONS={"matrix_lab","parameter_sweep","distribution_lab","network_flow","process_simulator","comparator","custom_canvas"}
LAYOUTS={"controls_left","controls_top","split_canvas","full_canvas"}
DIAGRAMS={"custom_svg","bar","line","heatmap","table","process","vector","network"}
DISCOVERY={"cards","steps","challenges","compare"}
CONTEXT={"ledger","source_map","annotated_notes"}
PALETTES={"research","ocean","forest","sunset","violet","graphite"}

def _defaults(spec):
    text=" ".join((str(spec.get("title","")),str(spec.get("plan",{}).get("core_idea","")))).lower()
    if re.search(r"attention|matrix|vector|transformer",text): return "equation_first","matrix_lab","heatmap","research"
    if re.search(r"entropy|probab|bayes|distribution",text): return "intuition_first","distribution_lab","bar","violet"
    if re.search(r"circuit|filter|frequency|signal",text): return "visual_first","parameter_sweep","line","sunset"
    if re.search(r"graph|network|node|page.?rank",text): return "visual_first","network_flow","network","forest"
    return "worked_example","process_simulator","process","ocean"

def normalize_design(spec):
    formulation,component,diagram,palette=_defaults(spec)
    raw=spec.get("design") if isinstance(spec.get("design"),dict) else {}
    def block(name): return raw.get(name) if isinstance(raw.get(name),dict) else {}
    orientation=block("orientation");interaction=block("interaction");discover=block("discover");context=block("context")
    accent=raw.get("accent","")
    if not isinstance(accent,str) or not re.fullmatch(r"#[0-9a-fA-F]{6}",accent): accent=""
    spec["design"]={
        "palette":raw.get("palette") if raw.get("palette") in PALETTES else palette,
        "accent":accent,"rationale":str(raw.get("rationale",""))[:360],
        "orientation":{"heading":str(orientation.get("heading","The idea, made clear."))[:90],"intro":str(orientation.get("intro","Build intuition before experimenting."))[:180],"formulation":orientation.get("formulation") if orientation.get("formulation") in FORMULATIONS else formulation},
        "interaction":{"heading":str(interaction.get("heading","Explore the mechanism."))[:90],"intro":str(interaction.get("intro","Change meaningful quantities and watch the mechanism respond."))[:180],"component":interaction.get("component") if interaction.get("component") in INTERACTIONS else component,"layout":interaction.get("layout") if interaction.get("layout") in LAYOUTS else "controls_left","diagram":interaction.get("diagram") if interaction.get("diagram") in DIAGRAMS else diagram},
        "discover":{"heading":str(discover.get("heading","What happens if…?"))[:90],"intro":str(discover.get("intro","Use guided changes to reveal the key insight."))[:180],"format":discover.get("format") if discover.get("format") in DISCOVERY else "cards"},
        "context":{"heading":str(context.get("heading","Keep the paper in view."))[:90],"intro":str(context.get("intro","Separate source claims from teaching simplifications."))[:180],"format":context.get("format") if context.get("format") in CONTEXT else "ledger"},
    }
    return spec

def validate_design(spec):
    design=spec.get("design")
    if not isinstance(design,dict): return ["design must be an object"]
    errors=[]
    if design.get("palette") not in PALETTES: errors.append("invalid palette")
    blocks=(("orientation","formulation",FORMULATIONS),("interaction","component",INTERACTIONS),("interaction","layout",LAYOUTS),("interaction","diagram",DIAGRAMS),("discover","format",DISCOVERY),("context","format",CONTEXT))
    for section,key,allowed in blocks:
        value=design.get(section)
        if not isinstance(value,dict) or value.get(key) not in allowed: errors.append("invalid %s %s"%(section,key))
    return errors
