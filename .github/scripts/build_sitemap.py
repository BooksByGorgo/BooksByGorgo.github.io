#!/usr/bin/env python3
"""Build a unified sitemap.xml + robots.txt for gorgo.dev.

gorgo.dev is composed of four GitHub Pages deployments under one apex domain.
The three content sites (/cpp, /os, /go) each emit their own sitemap via the
jekyll-sitemap plugin. This script fetches those live per-site sitemaps, merges
their <url> entries with the apex landing page, and writes a single flat
sitemap.xml plus a robots.txt that points crawlers at it.

Any fetch/parse failure aborts with a non-zero exit so a transient outage never
overwrites a good sitemap with a partial one.
"""

import sys
import urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

SITE = "https://gorgo.dev"
SUBSITE_SITEMAPS = [
    f"{SITE}/cpp/sitemap.xml",
    f"{SITE}/os/sitemap.xml",
    f"{SITE}/go/sitemap.xml",
]
# Pages owned directly by the apex repo (BooksByGorgo.github.io).
APEX_URLS = [f"{SITE}/"]

SM_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
NS = {"sm": SM_NS}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "gorgo-sitemap-builder"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_urls(xml_bytes, source):
    root = ET.fromstring(xml_bytes)
    entries = []
    for url_el in root.findall("sm:url", NS):
        loc_el = url_el.find("sm:loc", NS)
        if loc_el is None or not (loc_el.text or "").strip():
            continue
        loc = loc_el.text.strip()
        lastmod_el = url_el.find("sm:lastmod", NS)
        lastmod = (lastmod_el.text.strip()
                   if lastmod_el is not None and lastmod_el.text else None)
        entries.append((loc, lastmod))
    if not entries:
        raise RuntimeError(f"{source} contained no <url> entries")
    return entries


def main():
    merged = {}  # loc -> lastmod (dedup; last writer wins)
    for loc in APEX_URLS:
        merged.setdefault(loc, None)

    for sm_url in SUBSITE_SITEMAPS:
        try:
            entries = parse_urls(fetch(sm_url), sm_url)
        except Exception as exc:  # noqa: BLE001 - fail loudly on any problem
            print(f"ERROR: failed to process {sm_url}: {exc}", file=sys.stderr)
            return 1
        for loc, lastmod in entries:
            merged[loc] = lastmod
        print(f"{sm_url}: {len(entries)} urls")

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<urlset xmlns="{SM_NS}">']
    for loc in sorted(merged):
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(loc)}</loc>")
        if merged[loc]:
            lines.append(f"    <lastmod>{escape(merged[loc])}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")
    with open("sitemap.xml", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"Wrote sitemap.xml with {len(merged)} urls")

    with open("robots.txt", "w", encoding="utf-8") as fh:
        fh.write("User-agent: *\n")
        fh.write("Allow: /\n")
        fh.write(f"Sitemap: {SITE}/sitemap.xml\n")
    print("Wrote robots.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
