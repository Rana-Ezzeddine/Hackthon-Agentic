"""Figure sanitization and compact embedding helpers."""
from __future__ import annotations
import base64, re
from .config import VISION
from .fetch import fetch

def sanitize_svg(svg):
    if not svg:return None
    svg=re.sub(r"<script\b[^>]*>.*?</script>","",svg,flags=re.I|re.S)
    svg=re.sub(r"\s+on\w+\s*=\s*(['\"]).*?\1","",svg,flags=re.I|re.S)
    svg=re.sub(r"\s+(?:href|xlink:href)\s*=\s*(['\"])(?:https?:|//).*?\1","",svg,flags=re.I)
    return svg

def data_uri(fig):
    data=fig.get("image_bytes")
    return "data:%s;base64,%s"%(fig.get("mime") or "image/png",base64.b64encode(data).decode()) if data else ""

def prepare_figures(prepared,trace):
    if VISION=="off": return
    for fig in prepared.gated_figures:
        if fig.get("image_bytes") or not fig.get("src"): continue
        try:
            raw,ctype,url=fetch(fig["src"],5*1024*1024,timeout=(3,5))
            mime=ctype.split(";",1)[0].lower()
            if mime not in ("image/png","image/jpeg","image/webp"): raise ValueError("unsupported image type")
            if len(raw)>250_000:
                import fitz
                pix=fitz.Pixmap(raw)
                while max(pix.width,pix.height)>768: pix.shrink(1)
                raw=pix.tobytes("jpeg",jpg_quality=80);mime="image/jpeg"
            if len(raw)>250_000: raise ValueError("image remains above 250 KB")
            fig["image_bytes"],fig["mime"]=raw,mime
            trace.log("figures","download","ok",id=fig.get("id"),url=url,bytes=len(raw))
        except Exception as exc: trace.log("figures","download","fail",id=fig.get("id"),error=type(exc).__name__)
