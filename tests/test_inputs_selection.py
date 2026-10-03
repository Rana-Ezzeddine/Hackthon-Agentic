import json
from paperplay.inputs import load_case
from paperplay.record import PaperRecord,Section
from paperplay.selection import select

class T:
    def log(self,*a,**k):pass

def test_excerpt_detection_and_validation(tmp_path):
    p=tmp_path/"case.json";p.write_text(json.dumps({"source_url":"https://example.org/p","focus":"entropy","audience":"student","document":{"source_text":"x"*250}}))
    assert len(load_case(p).excerpt)==250

def test_focus_changes_selection_but_audience_does_not():
    record=PaperRecord(mode="supplied_excerpt",sections=[Section(anchor="a",number="1",heading="Introduction",text="background"),Section(anchor="b",number="3.2",heading="Scaled dot-product attention",text="softmax attention scores")])
    class C:source_url="https://example.org";focus="Section 3.2 scaled dot-product attention";audience="novice";hints={}
    one=select(record,C,T()).selected_anchors;C.audience="expert";two=select(record,C,T()).selected_anchors
    assert one==two and "b" in one


def test_selected_section_tables_are_sent_as_structured_context():
    record=PaperRecord(mode="arxiv_html",sections=[Section(anchor="S3",number="3",heading="Results",text="The experiment compares methods.",tab_ids=["S3.T1"])])
    record.tables=[{"id":"S3.T1","number":"1","caption":"Method comparison","section":"S3","rows":[["Method","Score"],["A","0.9"]],"markdown":"|Method|Score|\n|A|0.9|"}]
    class C:source_url="https://example.org";focus="Section 3 experiment comparison";audience="student";hints={}
    prepared=select(record,C,T())
    assert prepared.gated_tables[0]["id"]=="S3.T1"
    assert "[TABLE S3.T1" in prepared.context and "|Method|Score|" in prepared.context
