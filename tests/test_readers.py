from paperplay.html_reader import read_html
from paperplay.abs_reader import read_abs
from paperplay.inputs import Case
from paperplay.record import PaperRecord, Section
from paperplay.source import acquire_and_parse, normalize_arxiv

def test_arxiv_normalization():
    assert normalize_arxiv("https://arxiv.org/pdf/1706.03762v7.pdf") == "1706.03762v7"
    assert normalize_arxiv("https://arxiv.org/abs/1706.03762") == "1706.03762"

def test_latexml_reader():
    data=b'''<html><h1 class="ltx_title_document">A Paper</h1><section class="ltx_section" id="S1"><h2 class="ltx_title">1 Method</h2><p>We compute <math alttext="x+y"></math>.</p><div class="ltx_equation" id="S1.E1"><math alttext="z=x+y"></math><span class="ltx_tag_equation">(1)</span></div></section></html>'''
    r=read_html(data,"https://arxiv.org/html/1")
    assert r.meta["title"]=="A Paper" and r.sections[0].number=="1" and r.equations[0]["latex"]=="z=x+y"


class Trace:
    def log(self, *args, **kwargs):
        pass


ABS_HTML = b'''<html><head><meta name="citation_title" content="Attention Is All You Need">
<meta name="citation_author" content="Ashish Vaswani"></head><body>
<a href="https://arxiv.org/html/1706.03762v7">HTML (experimental)</a></body></html>'''
PAPER_HTML = b'''<html><h1 class="ltx_title_document">Attention Is All You Need</h1>
<section class="ltx_section" id="S1"><h2 class="ltx_title">1 Introduction</h2>
<p>''' + b'Full paper content. ' * 20 + b'''</p></section></html>'''


def test_abs_link_uses_advertised_versioned_html(monkeypatch):
    import paperplay.source as source
    calls = []

    def fake_fetch(url, _limit):
        calls.append(url)
        if "/abs/" in url:
            return ABS_HTML, "text/html", url
        return PAPER_HTML, "text/html", url

    monkeypatch.setattr(source, "fetch", fake_fetch)
    case = Case("https://arxiv.org/abs/1706.03762", "attention", "students")
    record = acquire_and_parse(case, Trace())
    assert record.mode == "arxiv_html"
    assert calls[1] == "https://arxiv.org/html/1706.03762v7"
    assert record.meta["version"] == "v7"
    assert record.meta["urls"]["html"] == calls[1]


def test_requested_version_is_preserved(monkeypatch):
    import paperplay.source as source
    calls = []

    def fake_fetch(url, _limit):
        calls.append(url)
        return (ABS_HTML if "/abs/" in url else PAPER_HTML), "text/html", url

    monkeypatch.setattr(source, "fetch", fake_fetch)
    record = acquire_and_parse(Case("https://arxiv.org/abs/1706.03762v1", "attention", "students"), Trace())
    assert calls[1] == "https://arxiv.org/html/1706.03762v1"
    assert record.meta["version"] == "v1"


def test_abstract_redirect_falls_back_to_pdf(monkeypatch):
    import paperplay.source as source
    calls = []

    def fake_fetch(url, _limit):
        calls.append(url)
        if "/abs/" in url:
            return ABS_HTML, "text/html", url
        if "ar5iv" in url:
            raise source.FetchError("unavailable")
        if "/html/" in url:
            return ABS_HTML, "text/html", "https://arxiv.org/abs/1706.03762"
        return b"%PDF-1.7", "application/pdf", url

    def fake_pdf(_data):
        record = PaperRecord(mode="pdf_markdown")
        record.sections = [Section(text="PDF paper content. " * 20)]
        return record

    monkeypatch.setattr(source, "fetch", fake_fetch)
    monkeypatch.setattr(source, "read_pdf", fake_pdf)
    record = acquire_and_parse(Case("https://arxiv.org/abs/1706.03762", "attention", "students"), Trace())
    assert record.mode == "pdf_markdown"
    assert calls[-1] == "https://arxiv.org/pdf/1706.03762.pdf"


def test_abs_reader_extracts_versioned_html_url():
    assert read_abs(ABS_HTML)["urls"]["html"] == "https://arxiv.org/html/1706.03762v7"


def test_author_markers_and_submission_history_are_cleaned():
    paper=read_html(b'''<h1 class="ltx_title_document">Paper</h1><div class="ltx_creator ltx_role_author"><span class="ltx_personname">Ada Lovelace<sup>1</sup> footnotemark: 1</span><span class="ltx_role_affiliation">Analytical Institute</span></div><section class="ltx_section" id="S1"><h2 class="ltx_title">1 Method</h2><p>Enough source material to parse correctly.</p></section>''',"https://arxiv.org/html/1")
    assert paper.meta["authors"][0]["name"]=="Ada Lovelace"
    meta=read_abs(b'''<meta name="citation_title" content="Paper"><div class="submission-history">Submission history [v1] Fri, 1 Jan 2021 10:00:00 UTC (12,345 bytes) [v2] Sat, 2 Jan 2021 10:00:00 UTC (13,000 bytes)</div>''')
    assert len(meta["dates"]["history"])==2 and meta["dates"]["history"][0].startswith("[v1]")


def test_table_is_attached_to_its_section():
    paper=read_html(b'''<h1>Paper</h1><section class="ltx_section" id="S3"><h2 class="ltx_title">3 Results</h2><figure class="ltx_table" id="S3.T1"><figcaption><span class="ltx_tag_table">Table 1</span> Accuracy</figcaption><table><tr><th>Method</th><th>Score</th></tr><tr><td>A</td><td>0.9</td></tr></table></figure></section>''',"https://arxiv.org/html/1")
    assert paper.tables[0]["section"]=="S3"
    assert paper.sections[0].tab_ids==["S3.T1"]
