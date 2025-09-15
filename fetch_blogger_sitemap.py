#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
SITEMAP_MAX_URLS = 49000  # room < 50k để an toàn

def fetch_atom_entries(blog_base: str, page_size: int = 500):
    entries = []
    start_index = 1

    while True:
        feed_url = f"{blog_base.rstrip('/')}/atom.xml?redirect=false&start-index={start_index}&max-results={page_size}"
        with urllib.request.urlopen(feed_url, timeout=30) as resp:
            data = resp.read()

        root = ET.fromstring(data)
        page_entries = []
        for entry in root.findall("atom:entry", ATOM_NS):
            link = None
            for l in entry.findall("atom:link", ATOM_NS):
                if l.get("rel") == "alternate" and (l.get("type") or "").startswith("text/html"):
                    link = l.get("href")
                    break
            if not link:
                continue

            updated = entry.findtext("atom:updated", default="", namespaces=ATOM_NS) or \
                      entry.findtext("atom:published", default="", namespaces=ATOM_NS) or ""
            lastmod = ""
            if updated:
                try:
                    dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    lastmod = dt.date().isoformat()
                except Exception:
                    lastmod = updated[:10]

            page_entries.append({"loc": link, "lastmod": lastmod})

        entries.extend(page_entries)

        if len(page_entries) < page_size:
            break
        start_index += page_size

    return entries

def build_url_element(url, lastmod=None, priority=None, changefreq=None):
    url_el = ET.Element("url")
    loc_el = ET.SubElement(url_el, "loc")
    loc_el.text = url
    if lastmod:
        lm_el = ET.SubElement(url_el, "lastmod")
        lm_el.text = lastmod
    if changefreq:
        cf_el = ET.SubElement(url_el, "changefreq")
        cf_el.text = changefreq
    if priority:
        pr_el = ET.SubElement(url_el, "priority")
        pr_el.text = f"{priority:.1f}" if isinstance(priority, float) else str(priority)
    return url_el

def write_sitemap_files(all_urls, out_dir="."):
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    ns_urlset = "http://www.sitemaps.org/schemas/sitemap/0.9"

    chunks = [all_urls[i:i+SITEMAP_MAX_URLS] for i in range(0, len(all_urls), SITEMAP_MAX_URLS)]
    written = []

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    def write_one(filename, urls):
        urlset = ET.Element(ET.QName(ns_urlset, "urlset"))
        for u in urls:
            urlset.append(build_url_element(u["loc"], u.get("lastmod")))
        tree = ET.ElementTree(urlset)
        tree.write(os.path.join(out_dir, filename), encoding="utf-8", xml_declaration=True)

    if len(chunks) <= 1:
        write_one("sitemap.xml", chunks[0] if chunks else [])
        written.append("sitemap.xml")
        return written, None
    else:
        part_files = []
        for idx, ch in enumerate(chunks, start=1):
            fname = f"sitemap-{idx}.xml"
            write_one(fname, ch)
            part_files.append(fname)
            written.append(fname)

        ns_sm = "http://www.sitemaps.org/schemas/sitemap/0.9"
        smindex = ET.Element(ET.QName(ns_sm, "sitemapindex"))
        today = datetime.now(timezone.utc).date().isoformat()

        base_url = os.environ.get("PAGES_BASE_URL", "").rstrip("/")
        for pf in part_files:
            sm_el = ET.SubElement(smindex, "sitemap")
            loc_el = ET.SubElement(sm_el, "loc")
            loc_el.text = f"{base_url}/{pf}" if base_url else pf
            lm_el = ET.SubElement(sm_el, "lastmod")
            lm_el.text = today

        ET.ElementTree(smindex).write(os.path.join(out_dir, "sitemap-index.xml"),
                                      encoding="utf-8", xml_declaration=True)
        written.append("sitemap-index.xml")
        return written, "sitemap-index.xml"

def main():
    blog_base = os.environ.get("BLOG_BASE", "https://weirdwildly.blogspot.com").strip()
    homepage = blog_base if blog_base.endswith("/") else (blog_base + "/")

    entries = fetch_atom_entries(blog_base)

    today = datetime.now(timezone.utc).date().isoformat()
    urls = [{"loc": homepage, "lastmod": today}]
    urls.extend(entries)

    written, index_file = write_sitemap_files(urls, out_dir=".")

    print(f"Total URLs: {len(urls)}")
    print("Written files:", ", ".join(written))
    if index_file:
        print("Sitemap index:", index_file)

if __name__ == "__main__":
    main()
