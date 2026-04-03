"""
html_to_txt.py  —  HTML → TXT

Handles ALL known HTML formats:

  Style A  — subject_template.html
             (folder-content divs, video-item / pdf-item classes)

  Style B  — tab-based crwill / Maths-Spl style
             (videos-tab / pdfs-tab, list-item class, onclick)

  Style C  — JS CONFIG object with base64-encoded URLs
             (GS_special_2 style — JSON data inside <script>)

  Style D  — Generic fallback
             (any HTML with onclick / href containing direct URLs)
"""

import re
import base64
from bs4 import BeautifulSoup


# ── Base64 helpers ─────────────────────────────────────────────────────────────
def _b64_decode(s: str) -> str:
    try:
        padded = s + "=" * (-len(s) % 4)
        result = base64.b64decode(padded).decode("utf-8")
        return result
    except Exception:
        return s


def _is_b64_url(s: str) -> bool:
    if not s or len(s) < 20:
        return False
    try:
        padded = s + "=" * (-len(s) % 4)
        decoded = base64.b64decode(padded).decode("utf-8")
        return decoded.startswith("http")
    except Exception:
        return False


# ── Extract URL from onclick string ───────────────────────────────────────────
def _onclick_url(onclick: str) -> str:
    for pat in [
        r"playVideo\(['\"]([^'\"]+)['\"]",
        r"playVideo\((?:&#39;|&quot;)([^'\"&]+)(?:&#39;|&quot;)",
        r"openPDF\(['\"]([^'\"]+)['\"]",
        r"window\.open\(['\"]([^'\"]+)['\"]",
    ]:
        m = re.search(pat, onclick)
        if m:
            return m.group(1).strip()
    return ""


# ══════════════════════════════════════════════════════════════════════════════
def html_to_txt(html_text: str) -> tuple[str, str]:
    """Returns (batch_name, txt_string)."""

    soup  = BeautifulSoup(html_text, "html.parser")
    lines: list[str] = []

    # ── Batch name ────────────────────────────────────────────────────────────
    batch_name = ""
    title_tag  = soup.find("title")
    if title_tag:
        batch_name = title_tag.get_text(strip=True)
    if not batch_name:
        for sel in ["h1", ".title-box h1", ".header h1", ".batch-title", "h2"]:
            el = soup.select_one(sel)
            if el:
                batch_name = el.get_text(strip=True)
                break
    if not batch_name:
        batch_name = "Batch"

    # ── Thumbnail URL ─────────────────────────────────────────────────────────
    thumbnail_url = ""
    for a in soup.find_all("a"):
        t = a.get_text(strip=True).lower()
        if "thumbnail" in t:
            href = a.get("href", "").strip()
            if href and href not in ("#", ""):
                thumbnail_url = href
                break
    if not thumbnail_url:
        og = soup.find("meta", property="og:image")
        if og:
            thumbnail_url = og.get("content", "")

    lines.append(
        f"[Batch Thumbnail] {batch_name} : "
        f"{thumbnail_url or 'https://example.com/thumbnail.jpg'}"
    )

    # ══════════════════════════════════════════════════════════════════════════
    # STYLE C — JS CONFIG with base64 URLs
    # Pattern: {"title":"...","link":"BASE64...","type":"VIDEO/PDF"}
    # ══════════════════════════════════════════════════════════════════════════
    b64_items = re.findall(
        r'\{"title"\s*:\s*"([^"]+)"\s*,\s*"link"\s*:\s*"([A-Za-z0-9+/]{20,}=*)"\s*,\s*"type"\s*:\s*"([^"]+)"\}',
        html_text
    )

    if b64_items:
        # Map items to subjects using surrounding JS object keys
        subj_order: list[str] = []
        subj_items: dict[str, list] = {}

        for subj_match in re.finditer(
            r'"([^"]{1,80})":\s*\[(\s*\{[^\]]*?\}[\s,]*)+\]',
            html_text
        ):
            subj_name   = subj_match.group(0).split('"')[1]
            block_items = re.findall(
                r'\{"title"\s*:\s*"([^"]+)"\s*,\s*"link"\s*:\s*"([A-Za-z0-9+/]{20,}=*)"\s*,\s*"type"\s*:\s*"([^"]+)"\}',
                subj_match.group(0)
            )
            if block_items:
                subj_items[subj_name] = block_items
                if subj_name not in subj_order:
                    subj_order.append(subj_name)

        if subj_order:
            for subj in subj_order:
                for title, link, typ in subj_items[subj]:
                    url = _b64_decode(link) if _is_b64_url(link) else link
                    lines.append(f"[{subj}] {title} : {url}")
        else:
            # No subject grouping found — use type as subject
            for title, link, typ in b64_items:
                url  = _b64_decode(link) if _is_b64_url(link) else link
                subj = "Videos" if typ == "VIDEO" else "PDFs"
                lines.append(f"[{subj}] {title} : {url}")

        return batch_name, "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════════════
    # STYLE A — subject_template.html (folder-content divs)
    # ══════════════════════════════════════════════════════════════════════════
    folder_divs = soup.find_all("div", class_="folder-content")
    if folder_divs:
        for folder in folder_divs:
            h2      = folder.find("h2")
            subject = h2.get_text(strip=True) if h2 else "Unknown"

            for a in folder.find_all("a", class_="video-item"):
                title   = a.get_text(strip=True)
                onclick = a.get("onclick", "")
                url     = _onclick_url(onclick)
                if url:
                    lines.append(f"[{subject}] {title} : {url}")

            for a in folder.find_all("a", class_="pdf-item"):
                title = a.get_text(strip=True).lstrip("📄").strip()
                href  = a.get("href", "").strip()
                if href and href != "#":
                    lines.append(f"[{subject}] {title} : {href}")

            for a in folder.find_all("a", class_="other-item"):
                title = a.get_text(strip=True)
                href  = a.get("href", "").strip()
                if href and href != "#":
                    lines.append(f"[{subject}] {title} : {href}")

        return batch_name, "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════════════
    # STYLE B — tab-based HTML (videos-tab / pdfs-tab, list-item class)
    # ══════════════════════════════════════════════════════════════════════════
    videos_tab = soup.find(id="videos-tab")
    pdfs_tab   = soup.find(id="pdfs-tab")

    if videos_tab or pdfs_tab:
        for tab, default_subj in [(videos_tab, "Videos"), (pdfs_tab, "PDFs")]:
            if not tab:
                continue
            for a in tab.find_all("a", class_="list-item"):
                text    = a.get_text(strip=True)
                onclick = a.get("onclick", "")
                href    = a.get("href", "").strip()

                sm      = re.match(r'^\[(.+?)\]\s*(.+)$', text)
                subject = sm.group(1).strip() if sm else default_subj
                title   = sm.group(2).strip() if sm else text

                url = _onclick_url(onclick) or (href if href != "#" else "")
                if url:
                    lines.append(f"[{subject}] {title} : {url}")

        return batch_name, "\n".join(lines)

    # ══════════════════════════════════════════════════════════════════════════
    # STYLE D — Generic fallback
    # ══════════════════════════════════════════════════════════════════════════
    seen: set[str] = set()

    for a in soup.find_all("a"):
        text    = a.get_text(strip=True)
        onclick = a.get("onclick", "")
        href    = a.get("href", "").strip()

        url = _onclick_url(onclick)
        if not url and href and href not in ("#", "javascript:void(0)", ""):
            url = href

        if not url or url in seen:
            continue
        seen.add(url)

        sm = re.match(r'^\[(.+?)\]\s*(.+)$', text)
        if sm:
            subject = sm.group(1).strip()
            title   = sm.group(2).strip()
        else:
            ul = url.lower()
            if ".m3u8" in ul or ".mp4" in ul:
                subject = "Videos"
            elif ".pdf" in ul:
                subject = "PDFs"
            else:
                subject = "Others"
            title = text or url.split("/")[-1].split("?")[0]

        if title:
            lines.append(f"[{subject}] {title} : {url}")

    return batch_name, "\n".join(lines)
