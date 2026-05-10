"""Fetch true-north.berlin and convert each page to Markdown under
`data/corpus/website/`.

PRD §7.4 FR-PRO-05.

This is invoked ONLY by `jobbot profile fetch-website`. The website is
considered static; we don't auto-refresh on every distiller run.

Behavior:
- Start at https://true-north.berlin and crawl same-domain links breadth-first.
- Skip non-HTML resources (.pdf, images, .css, .js).
- Convert each HTML page to Markdown via markdownify (or html2text — Copilot's
  pick).
- Write to `data/corpus/website/<slug>.md`. Slug = sanitized URL path.
- Overwrite existing files unconditionally — the website is the source of truth.
- Be polite: 1-second delay between requests, real User-Agent.
- Cap at 50 pages per run to avoid surprises.
- Print a summary: N pages fetched, total bytes.
"""
from __future__ import annotations

import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..config import REPO_ROOT

DEFAULT_BASE_URL = "https://true-north.berlin"
DEFAULT_OUTPUT_DIR_REL = "data/corpus/website"
PAGE_CAP = 50
DELAY_SECONDS = 1.0


SKIP_SUFFIXES = {
  ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
  ".css", ".js", ".xml", ".ico", ".zip", ".mp4", ".mp3",
}


def _is_same_domain(url: str, base_domain: str) -> bool:
  """PRD §7.4 FR-PRO-05: crawl only same-domain pages."""
  return urlparse(url).netloc == base_domain


def _should_skip_url(url: str) -> bool:
  """PRD §7.4 FR-PRO-05: skip obvious non-HTML resources."""
  path = urlparse(url).path.lower()
  return any(path.endswith(suffix) for suffix in SKIP_SUFFIXES)


def _slug_for_url(url: str) -> str:
  """PRD §7.4 FR-PRO-05: map URL path to deterministic markdown filename."""
  parsed = urlparse(url)
  path = parsed.path.strip("/") or "index"
  if path.endswith("/"):
    path = path[:-1]
  name = f"{path}"
  if parsed.query:
    name = f"{name}-{parsed.query}"
  name = re.sub(r"[^a-zA-Z0-9._/-]+", "-", name).strip("-")
  name = name.replace("/", "__")
  if not name:
    name = "index"
  return f"{name}.md"


def _html_to_markdown(html: str, source_url: str) -> str:
  """PRD §7.4 FR-PRO-05: convert fetched HTML to readable Markdown."""
  soup = BeautifulSoup(html, "html.parser")
  for node in soup(["script", "style", "noscript", "svg"]):
    node.decompose()

  title = (soup.title.string or "").strip() if soup.title else ""
  lines: list[str] = []
  if title:
    lines.append(f"# {title}")
    lines.append("")
  lines.append(f"Source: {source_url}")
  lines.append("")

  for heading in soup.find_all(["h1", "h2", "h3"]):
    level = int(heading.name[1])
    text = heading.get_text(" ", strip=True)
    if text:
      lines.append(f"{'#' * level} {text}")
      lines.append("")

  for paragraph in soup.find_all(["p", "li"]):
    text = paragraph.get_text(" ", strip=True)
    if not text:
      continue
    if paragraph.name == "li":
      lines.append(f"- {text}")
    else:
      lines.append(text)
      lines.append("")

  content = "\n".join(lines).strip()
  return content if content else f"Source: {source_url}\n"


def fetch_website(base_url: str = DEFAULT_BASE_URL,
                  output_dir: Path | None = None) -> int:
  """Crawl the website, write Markdown files, return count of pages saved."""
  output_dir = output_dir or (REPO_ROOT / DEFAULT_OUTPUT_DIR_REL)
  output_dir.mkdir(parents=True, exist_ok=True)

  start = urldefrag(base_url)[0]
  base_domain = urlparse(start).netloc
  queue: deque[str] = deque([start])
  seen: set[str] = set()
  pages_saved = 0
  total_bytes = 0

  with httpx.Client(
    timeout=20.0,
    follow_redirects=True,
    headers={
      "User-Agent": (
        "jobbot/1.0 (+https://true-north.berlin; "
        "profile-corpus-refresh)"
      )
    },
  ) as client:
    while queue and pages_saved < PAGE_CAP:
      current = queue.popleft()
      current = urldefrag(current)[0]
      if current in seen or _should_skip_url(current):
        continue
      if not _is_same_domain(current, base_domain):
        continue
      seen.add(current)

      try:
        resp = client.get(current)
        resp.raise_for_status()
      except Exception:
        continue

      content_type = (resp.headers.get("content-type") or "").lower()
      if "text/html" not in content_type:
        continue

      markdown = _html_to_markdown(resp.text, current)
      out_path = output_dir / _slug_for_url(current)
      out_path.write_text(markdown, encoding="utf-8")
      pages_saved += 1
      total_bytes += len(markdown.encode("utf-8"))

      soup = BeautifulSoup(resp.text, "html.parser")
      for link in soup.find_all("a", href=True):
        absolute = urldefrag(urljoin(current, link["href"]))[0]
        if absolute in seen or _should_skip_url(absolute):
          continue
        if _is_same_domain(absolute, base_domain):
          queue.append(absolute)

      time.sleep(DELAY_SECONDS)

  print(f"Fetched {pages_saved} pages, wrote {total_bytes} bytes to {output_dir}")
  return pages_saved
