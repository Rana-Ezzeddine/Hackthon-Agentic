"""Bounded HTTP retrieval with redirect and size controls."""
from __future__ import annotations
import requests, certifi

class FetchError(RuntimeError): pass

def fetch(url: str, max_bytes: int, timeout=(3, 8)) -> tuple[bytes, str, str]:
    try:
        with requests.get(url, stream=True, timeout=timeout, allow_redirects=True,
                          headers={"User-Agent":"PaperToPlayground/1.0 (educational generator)"}, verify=certifi.where()) as response:
            response.raise_for_status()
            if len(response.history) > 5 or any(r.url.split(":",1)[0] not in ("http","https") for r in response.history): raise FetchError("unsafe redirect chain")
            chunks=[]; total=0
            for chunk in response.iter_content(65536):
                total += len(chunk)
                if total > max_bytes: raise FetchError("response exceeds size limit")
                chunks.append(chunk)
            return b"".join(chunks), response.headers.get("content-type", ""), response.url
    except (requests.RequestException, FetchError) as exc:
        raise FetchError(str(exc)[:240]) from None

