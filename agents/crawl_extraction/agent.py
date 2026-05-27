import httpx
import pdfplumber
import io
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Optional
from pydantic import BaseModel


class CrawlPayload(BaseModel):
    url: str
    canonical_url: str
    page_title: str
    body_text: str
    body_word_count: int
    links_found: list[str]
    pdfs_detected: bool
    pdf_texts: list[str]
    http_status: int
    crawl_error: Optional[str] = None


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; UniversityAuditAgent/1.0; "
        "+https://github.com/afreiman-bit/university-audit-agent)"
    )
}


def extract_canonical(soup, fallback_url):
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        return canonical["href"]
    og_url = soup.find("meta", property="og:url")
    if og_url and og_url.get("content"):
        return og_url["content"]
    return fallback_url


def strip_noise(soup):
    for tag in soup.find_all(["nav", "header", "footer", "aside", "script", "style", "noscript"]):
        tag.decompose()
    for pattern in ["menu", "nav", "cookie", "banner", "sidebar", "breadcrumb"]:
        for tag in soup.find_all(class_=re.compile(pattern, re.I)):
            tag.decompose()
        for tag in soup.find_all(id=re.compile(pattern, re.I)):
            tag.decompose()
    return soup


def extract_pdf_text(pdf_url):
    try:
        r = httpx.get(pdf_url, headers=HEADERS, timeout=15, follow_redirects=True)
        if r.status_code == 200:
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                return "\n".join(
                    page.extract_text() or "" for page in pdf.pages[:5]
                ).strip()
    except Exception:
        pass
    return None


async def crawl_page(url: str) -> CrawlPayload:
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            response = await client.get(url)

        if response.status_code != 200:
            return CrawlPayload(
                url=url, canonical_url=url, page_title="",
                body_text="", body_word_count=0,
                links_found=[], pdfs_detected=False, pdf_texts=[],
                http_status=response.status_code,
                crawl_error=f"HTTP {response.status_code}",
            )

        soup = BeautifulSoup(response.text, "lxml")
        canonical_url = extract_canonical(soup, url)

        title_tag = soup.find("title")
        h1_tag = soup.find("h1")
        page_title = (
            h1_tag.get_text(strip=True) if h1_tag
            else (title_tag.get_text(strip=True) if title_tag else "")
        )

        links_found = []
        pdf_urls = []
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            links_found.append(href)
            if href.lower().endswith(".pdf"):
                pdf_urls.append(href)

        soup = strip_noise(soup)

        main = soup.find("main") or soup.find(id="main") or soup.find(id="content")
        target = main if main else soup.find("body") or soup
        body_text = target.get_text(separator="\n", strip=True)
        body_text = re.sub(r"\n{3,}", "\n\n", body_text).strip()
        body_word_count = len(body_text.split())

        pdf_texts = []
        for pdf_url in pdf_urls[:2]:
            text = extract_pdf_text(pdf_url)
            if text:
                pdf_texts.append(text)

        return CrawlPayload(
            url=url,
            canonical_url=canonical_url,
            page_title=page_title,
            body_text=body_text,
            body_word_count=body_word_count,
            links_found=links_found[:100],
            pdfs_detected=len(pdf_urls) > 0,
            pdf_texts=pdf_texts,
            http_status=200,
        )

    except Exception as e:
        return CrawlPayload(
            url=url, canonical_url=url, page_title="",
            body_text="", body_word_count=0,
            links_found=[], pdfs_detected=False, pdf_texts=[],
            http_status=0,
            crawl_error=str(e),
        )
