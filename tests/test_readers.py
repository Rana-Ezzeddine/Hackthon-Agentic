from paperplay.html_reader import read_html
from paperplay.source import normalize_arxiv

def test_arxiv_normalization():
    assert normalize_arxiv("https://arxiv.org/pdf/1706.03762v7.pdf") == "1706.03762v7"
    assert normalize_arxiv("https://arxiv.org/abs/1706.03762") == "1706.03762"

def test_latexml_reader():
    data=b'''<html><h1 class="ltx_title_document">A Paper</h1><section class="ltx_section" id="S1"><h2 class="ltx_title">1 Method</h2><p>We compute <math alttext="x+y"></math>.</p><div class="ltx_equation" id="S1.E1"><math alttext="z=x+y"></math><span class="ltx_tag_equation">(1)</span></div></section></html>'''
    r=read_html(data,"https://arxiv.org/html/1")
    assert r.meta["title"]=="A Paper" and r.sections[0].number=="1" and r.equations[0]["latex"]=="z=x+y"

