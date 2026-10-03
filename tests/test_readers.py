from paperplay.html_reader import read_html
from paperplay.abs_reader import read_abs
from paperplay.source import normalize_arxiv

def test_arxiv_normalization():
    assert normalize_arxiv("https://arxiv.org/pdf/1706.03762v7.pdf") == "1706.03762v7"
    assert normalize_arxiv("https://arxiv.org/abs/1706.03762") == "1706.03762"

def test_latexml_reader():
    data=b'''<html><h1 class="ltx_title_document">A Paper</h1><section class="ltx_section" id="S1"><h2 class="ltx_title">1 Method</h2><p>We compute <math alttext="x+y"></math>.</p><div class="ltx_equation" id="S1.E1"><math alttext="z=x+y"></math><span class="ltx_tag_equation">(1)</span></div></section></html>'''
    r=read_html(data,"https://arxiv.org/html/1")
    assert r.meta["title"]=="A Paper" and r.sections[0].number=="1" and r.equations[0]["latex"]=="z=x+y"

def test_author_markers_and_submission_history_are_cleaned():
    paper=read_html(b'''<h1 class="ltx_title_document">Paper</h1><div class="ltx_creator ltx_role_author"><span class="ltx_personname">Ada Lovelace<sup>1</sup> footnotemark: 1</span><span class="ltx_role_affiliation">Analytical Institute</span></div><section class="ltx_section" id="S1"><h2 class="ltx_title">1 Method</h2><p>Enough source material to parse correctly.</p></section>''',"https://arxiv.org/html/1")
    assert paper.meta["authors"][0]["name"]=="Ada Lovelace"
    meta=read_abs(b'''<meta name="citation_title" content="Paper"><div class="submission-history">Submission history [v1] Fri, 1 Jan 2021 10:00:00 UTC (12,345 bytes) [v2] Sat, 2 Jan 2021 10:00:00 UTC (13,000 bytes)</div>''')
    assert len(meta["dates"]["history"])==2 and meta["dates"]["history"][0].startswith("[v1]")


def test_table_is_attached_to_its_section():
    paper=read_html(b'''<h1>Paper</h1><section class="ltx_section" id="S3"><h2 class="ltx_title">3 Results</h2><figure class="ltx_table" id="S3.T1"><figcaption><span class="ltx_tag_table">Table 1</span> Accuracy</figcaption><table><tr><th>Method</th><th>Score</th></tr><tr><td>A</td><td>0.9</td></tr></table></figure></section>''',"https://arxiv.org/html/1")
    assert paper.tables[0]["section"]=="S3"
    assert paper.sections[0].tab_ids==["S3.T1"]
