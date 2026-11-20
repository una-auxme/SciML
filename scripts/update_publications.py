#!/usr/bin/env python3
"""
Update data/publications.json from the ORCID records of all group members.

How it works
  1. Reads every member page in content/members/ and collects its `orcid` field.
  2. Downloads each member's public works from the ORCID public API.
  3. Completes the metadata of works with a DOI (authors, venue, type, date) through
     doi.org content negotiation, which covers Crossref, DataCite (arXiv, Zenodo), etc.
     Resolved DOIs are cached in the output file, so later runs only look up new DOIs.
  4. Merges duplicates: the same DOI listed by several members, and preprints that were
     later published (the preprint becomes a link on the published version).
  5. Applies publications.toml: manual entries, per-publication overrides, exclusions.
  6. Writes data/publications.json, from which Hugo builds every publication list.

Needs Python 3.11 or newer and no third-party packages.

Usage
  python scripts/update_publications.py            # fetch and update
  python scripts/update_publications.py --offline  # no network: re-apply publications.toml only
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import tomllib
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMBERS_DIR = ROOT / "content" / "members"
CURATION_FILE = ROOT / "publications.toml"
OUTPUT_FILE = ROOT / "data" / "publications.json"

ORCID_API = "https://pub.orcid.org/v3.0"
DEFAULT_TYPES = ["journal", "conference", "preprint", "chapter", "book", "thesis", "report"]

# Lower rank = preferred when duplicates are merged.
TYPE_RANK = {"journal": 0, "conference": 1, "chapter": 2, "book": 3, "thesis": 4,
             "report": 5, "other": 6, "software": 7, "dataset": 8, "preprint": 9}

ORCID_TYPES = {
    "journal-article": "journal", "magazine-article": "journal", "review": "journal",
    "conference-paper": "conference", "conference-proceedings": "conference",
    "preprint": "preprint", "working-paper": "preprint",
    "book-chapter": "chapter", "book": "book", "edited-book": "book",
    "dissertation-thesis": "thesis", "dissertation": "thesis", "supervised-student-publication": "thesis",
    "report": "report", "research-technique": "report",
    "software": "software", "data-set": "dataset",
    "conference-abstract": "abstract", "conference-poster": "poster",
    "lecture-speech": "talk", "conference-presentation": "talk",
}
CSL_TYPES = {
    # CSL types (DataCite, others)
    "article-journal": "journal", "article-magazine": "journal", "review": "journal",
    "paper-conference": "conference",
    "chapter": "chapter", "book": "book",
    "thesis": "thesis", "report": "report",
    "dataset": "dataset", "software": "software",
    "article": "preprint", "posted-content": "preprint", "manuscript": "preprint",
    # Crossref's own type names, which doi.org returns for Crossref DOIs
    "journal-article": "journal", "proceedings-article": "conference",
    "book-chapter": "chapter", "book-section": "chapter", "book-part": "chapter", "reference-entry": "chapter",
    "monograph": "book", "edited-book": "book", "reference-book": "book",
    "dissertation": "thesis",
}
# Venue names that indicate conference proceedings (but not journals such as "... Conference Series").
CONFERENCE_VENUE = re.compile(r"conference|konferenz|proceedings|symposium|workshop|tagung", re.I)
BIBTEX_TYPES = {"journal": "article", "conference": "inproceedings", "chapter": "incollection",
                "book": "book", "thesis": "phdthesis", "report": "techreport"}
STOPWORDS = {"a", "an", "the", "on", "of", "for", "and", "in", "to", "with", "towards", "toward"}

USER_AGENT = "group-website-publication-sync/1.0"


# ----------------------------------------------------------------------------- helpers

def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def norm_title(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", ascii_fold(s).lower())


def clean_text(s) -> str:
    if isinstance(s, list):
        s = s[0] if s else ""
    s = html.unescape(re.sub(r"<[^>]+>", "", str(s or "")))
    return re.sub(r"\s+", " ", s).strip()


def norm_doi(s: str | None) -> str:
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", s, flags=re.I)
    s = re.sub(r"^doi:\s*", "", s, flags=re.I)
    return s.lower()


def norm_orcid(s: str | None) -> str:
    if not s:
        return ""
    m = re.search(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", s)
    return m.group(1) if m else ""


def deep(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def http_get_json(url: str, accept: str = "application/json"):
    """GET a JSON document; returns None on 404, raises after three failed attempts."""
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (404, 406, 410):
                return None
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            raise


def split_name(name: str) -> tuple[str, str]:
    """'Jane Doe' or 'Doe, Jane' -> ('Jane', 'Doe')."""
    name = clean_text(name)
    if "," in name:
        family, given = [p.strip() for p in name.split(",", 1)]
        return given, family
    parts = name.split()
    if len(parts) == 1:
        return "", parts[0]
    return " ".join(parts[:-1]), parts[-1]


def make_author(given: str = "", family: str = "", orcid: str = "", literal: str = "") -> dict:
    given, family = clean_text(given), clean_text(family)
    if literal and not family:
        given, family = split_name(literal)
    name = f"{given} {family}".strip()
    a = {"name": name, "given": given, "family": family}
    if orcid:
        a["orcid"] = orcid
    return a


def bibtex_field(text: str, field: str) -> str:
    """Extract a field value from a BibTeX entry (handles nested braces)."""
    m = re.search(rf"\b{field}\s*=\s*", text, flags=re.I)
    if not m:
        return ""
    i = m.end()
    if i >= len(text):
        return ""
    if text[i] == "{":
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    return text[i + 1:j]
            j += 1
        return ""
    if text[i] == '"':
        j = text.find('"', i + 1)
        return text[i + 1:j] if j > 0 else ""
    m2 = re.match(r"[^,}\s]+", text[i:])
    return m2.group(0) if m2 else ""


def strip_latex(s: str) -> str:
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)
    return clean_text(s.replace("{", "").replace("}", "").replace("\\", ""))


# ----------------------------------------------------------------------------- inputs

def read_front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").lstrip("\ufeff")
    if text.startswith("+++"):
        end = text.find("\n+++", 3)
        if end < 0:
            raise SystemExit(f"{path}: front matter is not closed with +++")
        try:
            return tomllib.loads(text[3:end])
        except tomllib.TOMLDecodeError as e:
            raise SystemExit(f"{path}: invalid TOML front matter: {e}")
    if text.startswith("---"):
        raise SystemExit(f"{path}: please use TOML front matter (between +++ lines), like the other member pages.")
    return {}


def read_members() -> list[dict]:
    files = sorted(MEMBERS_DIR.glob("*/index.md")) + sorted(
        p for p in MEMBERS_DIR.glob("*.md") if p.name != "_index.md")
    members = []
    for f in files:
        fm = read_front_matter(f)
        if fm.get("draft"):
            continue
        slug = f.parent.name if f.name == "index.md" else f.stem
        names = [fm.get("title", "")] + list(fm.get("name_variants", []))
        keys, fullnames = set(), set()
        for n in names:
            given, family = split_name(n)
            if family:
                keys.add((ascii_fold(family).lower(), ascii_fold(given)[:1].lower()))
                fullnames.add(full_name_key(given, family))
        members.append({"slug": slug, "name": fm.get("title", slug),
                        "orcid": norm_orcid(fm.get("orcid", "")), "keys": keys, "fullnames": fullnames})
    return members


def read_curation() -> dict:
    if not CURATION_FILE.exists():
        return {}
    with CURATION_FILE.open("rb") as fh:
        return tomllib.load(fh)


def read_previous() -> dict:
    if OUTPUT_FILE.exists():
        try:
            return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log(f"warning: {OUTPUT_FILE} is not valid JSON, starting from scratch")
    return {}


# ----------------------------------------------------------------------------- ORCID

def fetch_orcid_works(orcid: str, names_by_orcid: dict[str, str]) -> list[dict]:
    data = http_get_json(f"{ORCID_API}/{orcid}/works")
    if data is None:
        raise RuntimeError("ORCID record not found")
    works, missing_authors = [], []
    for group in data.get("group", []):
        summaries = group.get("work-summary") or []
        if not summaries:
            continue
        s = max(summaries, key=lambda x: int(x.get("display-index") or 0))
        title = re.sub(r"\s*[*†‡]+$", "", clean_text(deep(s, "title", "title", "value")))   # footnote markers
        if not title:
            continue
        ids = (deep(group, "external-ids", "external-id") or []) + (deep(s, "external-ids", "external-id") or [])
        doi = arxiv = urn = ""
        for eid in ids:
            kind = (eid.get("external-id-type") or "").lower()
            if eid.get("external-id-relationship") not in (None, "self"):
                continue
            val = eid.get("external-id-value") or ""
            if kind == "doi" and not doi:
                doi = norm_doi(val)
            elif kind == "arxiv" and not arxiv:
                arxiv = re.sub(r"^arxiv:\s*", "", val, flags=re.I)
            elif kind == "urn" and not urn:
                urn = val.strip()
        year = deep(s, "publication-date", "year", "value")
        month = deep(s, "publication-date", "month", "value")
        day = deep(s, "publication-date", "day", "value")
        venue = clean_text(deep(s, "journal-title", "value"))
        otype = ORCID_TYPES.get(s.get("type") or "", "other")
        if arxiv or venue.lower().startswith("arxiv"):   # arXiv preprints imported as journal articles
            arxiv = arxiv or (re.search(r"(\d{4}\.\d{4,5})", venue) or [None, ""])[1]   # "arXiv preprint arXiv:2302.10892"
            otype, venue = "preprint", "arXiv"
        w = {
            "title": title,
            "orcid_type": otype,
            "year": int(year) if year else None,
            "date": "-".join(p for p in (year, month, day) if p) if year else "",
            "venue": venue,
            "doi": doi,
            "arxiv": arxiv,
            "url": deep(s, "url", "value") or (f"https://nbn-resolving.org/{urn}" if urn and not doi else ""),
            "authors": [],
            "put_code": s.get("put-code"),
        }
        if not doi:
            missing_authors.append(w)
        works.append(w)

    # Works without DOI: get contributors (or a BibTeX citation) from the detailed records.
    for i in range(0, len(missing_authors), 100):
        chunk = missing_authors[i:i + 100]
        codes = ",".join(str(w["put_code"]) for w in chunk)
        detail = http_get_json(f"{ORCID_API}/{orcid}/works/{codes}") or {}
        by_code = {}
        for item in detail.get("bulk", []):
            work = item.get("work")
            if work:
                by_code[work.get("put-code")] = work
        for w in chunk:
            work = by_code.get(w["put_code"]) or {}
            for c in deep(work, "contributors", "contributor") or []:
                c_orcid = norm_orcid(deep(c, "contributor-orcid", "path"))
                # Records synced from repositories often list the ORCID owner by iD only, without a name.
                name = deep(c, "credit-name", "value") or names_by_orcid.get(c_orcid, "")
                if name:
                    given, family = split_name(name)
                    w["authors"].append(make_author(given, family, c_orcid))
            cit = deep(work, "citation") or {}
            if (cit.get("citation-type") or "").lower() == "bibtex":
                bib = cit.get("citation-value") or ""
                if not w["authors"]:
                    for n in re.split(r"\s+and\s+", bibtex_field(bib, "author")):
                        if n.strip():
                            given, family = split_name(strip_latex(n))
                            w["authors"].append(make_author(given, family))
                if not w["venue"]:
                    w["venue"] = strip_latex(bibtex_field(bib, "journal") or bibtex_field(bib, "booktitle"))
    return works


# ----------------------------------------------------------------------------- DOI metadata

def fetch_doi(doi: str) -> dict | None:
    url = "https://doi.org/" + urllib.parse.quote(doi, safe="/:;()._-")
    csl = http_get_json(url, accept="application/vnd.citationstyles.csl+json")
    if not csl:
        return None
    authors = []
    for a in csl.get("author") or []:
        authors.append(make_author(a.get("given", ""), a.get("family", ""),
                                   norm_orcid(a.get("ORCID")), a.get("literal") or a.get("name") or ""))
    # Earliest of the known dates: journals often set "issued" to a later issue than the online release.
    candidates = []
    for key in ("published-online", "published-print", "issued"):
        dp = deep(csl, key, "date-parts")
        if dp and dp[0] and dp[0][0]:
            candidates.append([int(p) for p in dp[0] if p])
    if not candidates:
        dp = deep(csl, "created", "date-parts")
        if dp and dp[0] and dp[0][0]:
            candidates.append([int(p) for p in dp[0] if p])
    parts = min(candidates, key=lambda d: (d + [12, 31])[:3]) if candidates else None
    created = deep(csl, "created", "date-parts")
    created = [int(p) for p in created[0] if p] if created and created[0] and created[0][0] else None
    if parts and created:
        if (parts + [1, 1])[:3] > list(date.today().timetuple()[:3]):
            # Some publishers register only a future print issue; the DOI's creation is the online release.
            parts = created
        elif len(parts) < 3 and len(created) == 3 and created[:len(parts)] == parts:
            # Incomplete date (e.g. only the year for SSRN preprints): the DOI's creation is more precise.
            parts = created
    ctype = CSL_TYPES.get(csl.get("type") or "", "other")
    event = clean_text(csl.get("event-title")) \
        or clean_text(deep(csl, "event", "name") if isinstance(csl.get("event"), dict) else csl.get("event"))
    # For conference papers the conference name says more than a proceedings series title.
    venue = (event if ctype == "conference" and event else "") or clean_text(csl.get("container-title")) or event
    if doi.startswith("10.48550/"):
        venue, ctype = "arXiv", "preprint"
    elif doi.startswith("10.2139/ssrn"):
        venue, ctype = "SSRN", "preprint"
    elif not venue and ctype in ("preprint", "book", "thesis", "report"):
        venue = clean_text(csl.get("publisher"))
    return {
        "title": clean_text(csl.get("title")),
        "authors": authors,
        "csl_type": ctype,
        "year": int(parts[0]) if parts else None,
        "date": "-".join(f"{p:02d}" if i else str(p) for i, p in enumerate(parts)) if parts else "",
        "venue": venue,
    }


# ----------------------------------------------------------------------------- assembly

def work_key(w: dict) -> str:
    if w.get("doi"):
        return w["doi"]
    return "t" + hashlib.sha1(f"{norm_title(w['title'])}:{w.get('year')}".encode()).hexdigest()[:12]


def pick_type(orcid_type: str | None, csl_type: str | None, venue: str = "") -> str:
    if orcid_type == "preprint" and csl_type in (None, "other", "journal"):
        return "preprint"
    if csl_type and csl_type != "other":
        t = orcid_type if orcid_type in ("conference", "thesis", "chapter") and csl_type == "journal" else csl_type
    else:
        t = orcid_type or "other"
    # Papers in conference proceedings, often registered as "book" or "journal article".
    if t in ("journal", "book", "chapter", "other") and CONFERENCE_VENUE.search(venue or "") \
            and not re.search(r"journal", venue, re.I):
        t = "conference"
    return t


def merge_into(target: dict, other: dict) -> None:
    target["members"] = sorted(set(target["members"]) | set(other["members"]))
    for k in ("doi", "venue", "url", "pdf", "code", "arxiv", "note", "date"):
        if not target.get(k) and other.get(k):
            target[k] = other[k]
    if not target.get("authors") and other.get("authors"):
        target["authors"] = other["authors"]


def preprint_link(w: dict) -> str:
    if w.get("arxiv"):
        return f"https://arxiv.org/abs/{w['arxiv']}"
    if w.get("doi"):
        return f"https://doi.org/{w['doi']}"
    return w.get("url", "")


def deduplicate(works: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for w in works:
        k = work_key(w)
        if k in by_key:
            merge_into(by_key[k], w)
        else:
            by_key[k] = w
    by_title = defaultdict(list)
    for w in by_key.values():
        by_title[norm_title(w["title"]) or work_key(w)].append(w)
    result = []
    for ws in by_title.values():
        ws.sort(key=lambda w: (TYPE_RANK.get(w["type"], 6), not w.get("doi")))
        kept: list[dict] = []
        for w in ws:
            target = None
            if w["type"] == "preprint":
                target = next((k for k in kept if k["type"] != "preprint"), None)
                if target and not target.get("preprint"):
                    target["preprint"] = preprint_link(w)
            if target is None:
                target = next((k for k in kept
                               if (not k.get("doi") or not w.get("doi") or k["doi"] == w["doi"])
                               and abs((k.get("year") or 0) - (w.get("year") or 0)) <= 1), None)
            if target:
                merge_into(target, w)
            else:
                kept.append(w)
        result.extend(kept)
    return result


def full_name_key(given: str, family: str) -> str:
    return re.sub(r"[^a-z ]", "", ascii_fold(f"{given} {family}").lower()).strip()


def mark_member_authors(w: dict, members: list[dict]) -> None:
    """Links authors to members: by ORCID, by exact full name (also former names in `name_variants`),
    or by family name + initial among the members whose ORCID record lists the work."""
    by_orcid = {m["orcid"]: m["slug"] for m in members if m["orcid"]}
    by_fullname = {k: m["slug"] for m in members for k in m["fullnames"]}
    candidates = [m for m in members if m["slug"] in w["members"]] or members
    found = set()
    for a in w["authors"]:
        a.pop("member", None)
        slug = by_orcid.get(a.get("orcid", "")) or by_fullname.get(full_name_key(a.get("given", ""), a.get("family", "")))
        if not slug:
            family = ascii_fold(a.get("family", "")).lower().split()
            initial = ascii_fold(a.get("given", ""))[:1].lower()
            for m in candidates:
                if family and any(family[-1] == f and (not initial or initial == i) for f, i in m["keys"]):
                    slug = m["slug"]
                    break
        if slug and slug not in found:
            a["member"] = slug
            found.add(slug)
    w["members"] = sorted(set(w["members"]) | found)


def make_bibtex(w: dict, used_keys: set) -> str:
    first = w["authors"][0]["family"] if w["authors"] else "anon"
    first = re.sub(r"[^a-z]", "", ascii_fold(first).lower()) or "anon"
    word = next((t for t in re.findall(r"[a-z0-9]+", ascii_fold(w["title"]).lower()) if t not in STOPWORDS), "")
    key = base = f"{first}{w.get('year') or ''}{word}"
    n = 0
    while key in used_keys:
        n += 1
        key = base + "abcdefghijklmnopqrstuvwxyz"[(n - 1) % 26]
    used_keys.add(key)

    def esc(s: str) -> str:
        return re.sub(r"([&%#])", r"\\\1", s)

    etype = BIBTEX_TYPES.get(w["type"], "misc")
    fields = [("author", " and ".join(f"{a['family']}, {a['given']}".strip(", ") for a in w["authors"])),
              ("title", esc(w["title"]))]
    venue_field = {"article": "journal", "inproceedings": "booktitle", "incollection": "booktitle",
                   "book": "publisher", "phdthesis": "school", "techreport": "institution"}.get(etype)
    if w.get("arxiv") and w["type"] == "preprint":
        fields += [("eprint", w["arxiv"]), ("archiveprefix", "arXiv")]
    elif venue_field and w.get("venue"):
        fields.append((venue_field, esc(w["venue"])))
    elif w.get("venue"):
        fields.append(("howpublished", esc(w["venue"])))
    fields += [("year", str(w.get("year") or "")), ("doi", w.get("doi", "")), ("url", w.get("url", ""))]
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields if v)
    return f"@{etype}{{{key},\n{body}\n}}"


# ----------------------------------------------------------------------------- main

def main() -> None:
    global USER_AGENT
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--offline", action="store_true", help="do not access the network")
    parser.add_argument("--refresh", action="store_true", help="look up all DOIs again instead of using cached metadata")
    args = parser.parse_args()

    curation = read_curation()
    if curation.get("contact_email"):
        USER_AGENT += f" (mailto:{curation['contact_email']})"
    include_types = set(curation.get("include_types", DEFAULT_TYPES))
    members = read_members()
    previous = read_previous()
    old_pubs = previous.get("publications", [])
    doi_cache = {} if args.refresh else {p["doi"]: p for p in old_pubs if p.get("doi") and p.get("resolved")}
    names_by_orcid = {m["orcid"]: m["name"] for m in members if m["orcid"]}

    # 1) Works from ORCID (falls back to the previous data if ORCID cannot be reached).
    works, failed = [], []
    for m in members:
        if not m["orcid"]:
            continue
        try:
            if args.offline:
                raise RuntimeError("offline mode")
            fetched = fetch_orcid_works(m["orcid"], names_by_orcid)
            log(f"{m['slug']}: {len(fetched)} works on ORCID")
            for w in fetched:
                w["members"] = [m["slug"]]
                w["source"] = "orcid"
                works.append(w)
        except Exception as e:  # keep what we had for this member
            failed.append(m["slug"])
            kept = [dict(p, members=[m["slug"]], orcid_type=p.get("type")) for p in old_pubs
                    if m["slug"] in p.get("members", []) and p.get("source") == "orcid"]
            log(f"{m['slug']}: could not fetch ORCID record ({e}); keeping {len(kept)} previous entries")
            works.extend(kept)

    # 2) Manual entries from publications.toml.
    for entry in curation.get("manual", []):
        if not entry.get("title"):
            log(f"warning: skipping manual entry without title: {entry}")
            continue
        w = {k: v for k, v in entry.items() if k not in ("authors", "month", "members")}
        w["doi"] = norm_doi(entry.get("doi"))
        w["authors"] = [make_author(*split_name(n)) for n in entry.get("authors", [])]
        w["orcid_type"] = entry.get("type", "other")
        if entry.get("year") and entry.get("month"):
            w["date"] = f"{entry['year']}-{int(entry['month']):02d}"
        elif entry.get("year"):
            w["date"] = str(entry["year"])
        w["members"] = list(entry.get("members", []))
        w["source"] = "manual"
        w["manual_fields"] = {k for k, v in entry.items() if v not in ("", [], None)}
        works.append(w)

    # 3) Complete metadata via DOI (only for DOIs not resolved before).
    todo = sorted({w["doi"] for w in works if w.get("doi") and w["doi"] not in doi_cache})
    resolved: dict[str, dict | None] = {}
    if todo and not args.offline:
        log(f"resolving {len(todo)} new DOI(s) ...")
        with ThreadPoolExecutor(max_workers=4) as pool:
            for doi, meta in zip(todo, pool.map(lambda d: _safe_fetch_doi(d), todo)):
                resolved[doi] = meta
    for w in works:
        doi = w.get("doi")
        meta = resolved.get(doi) if doi in resolved else None
        if doi and doi in doi_cache and not meta:
            c = doi_cache[doi]
            meta = {"title": c["title"], "authors": c["authors"], "csl_type": c.get("csl_type"),
                    "year": c.get("year"), "date": c.get("date"), "venue": c.get("venue")}
        manual = w.pop("manual_fields", set())
        if meta:
            w["resolved"] = True
            w["csl_type"] = meta.get("csl_type")
            for k in ("title", "year", "date", "venue"):
                if meta.get(k) and k not in manual:
                    w[k] = meta[k]
            if meta.get("authors") and "authors" not in manual:
                w["authors"] = meta["authors"]
        w["type"] = w.get("type") if "type" in manual else pick_type(w.get("orcid_type"), w.get("csl_type"), w.get("venue", ""))
        w["type_fixed"] = "type" in manual
        if w.get("doi") and "url" not in manual:
            w["url"] = f"https://doi.org/{w['doi']}"   # prefer the DOI over e.g. Scopus links
        elif not w.get("url") and w.get("arxiv"):
            w["url"] = f"https://arxiv.org/abs/{w['arxiv']}"
        if w["type"] == "preprint" and w.get("arxiv") and not w.get("venue"):
            w["venue"] = "arXiv"
        if not w["authors"]:
            w["authors"] = [make_author(*split_name(m["name"])) for m in members if m["slug"] in w["members"]]

    # 4) Filter, merge duplicates, apply exclusions and overrides.
    works = [w for w in works if w["type"] in include_types or w.get("source") == "manual"]
    works = deduplicate(works)
    for w in works:   # merging can bring in a venue that says more about the type
        if w.get("type_fixed"):
            continue
        if w.get("venue", "").lower().startswith("arxiv") and w["type"] != "preprint" and not w.get("doi"):
            w["type"], w["venue"] = "preprint", "arXiv"
        else:
            w["type"] = pick_type(w["type"], None, w.get("venue", ""))
    excluded ={norm_doi(x) for x in curation.get("exclude", [])} | {norm_title(x) for x in curation.get("exclude", [])}
    works = [w for w in works if w.get("doi", "") not in excluded and norm_title(w["title"]) not in excluded]
    for ov in curation.get("override", []):
        target = None
        if ov.get("doi"):
            target = next((w for w in works if w.get("doi") == norm_doi(ov["doi"])), None)
        elif ov.get("title"):
            target = next((w for w in works if norm_title(w["title"]) == norm_title(ov["title"])), None)
        if not target:
            log(f"warning: override did not match any publication: {ov.get('doi') or ov.get('title')}")
            continue
        for k, v in ov.items():
            if k in ("doi", "title"):
                continue
            if k == "authors":
                v = [make_author(*split_name(n)) for n in v]
            target[k] = v

    # 5) Finish entries and write the output.
    used_keys: set[str] = set()
    out = []
    works.sort(key=lambda w: w["title"].lower())
    works.sort(key=lambda w: str(w.get("date") or w.get("year") or ""), reverse=True)
    for w in works:
        mark_member_authors(w, members)
        entry = {
            "id": work_key(w),
            "title": w["title"],
            "authors": w["authors"],
            "year": w.get("year"),
            "date": w.get("date") or (str(w["year"]) if w.get("year") else ""),
            "type": w["type"],
            "venue": w.get("venue", ""),
            "doi": w.get("doi", ""),
            "url": w.get("url", ""),
            "arxiv": w.get("arxiv", ""),
            "preprint": w.get("preprint", ""),
            "pdf": w.get("pdf", ""),
            "code": w.get("code", ""),
            "note": w.get("note", ""),
            "members": w["members"],
            "source": w.get("source", ""),
        }
        if w.get("resolved"):
            entry["resolved"] = True
            entry["csl_type"] = w.get("csl_type")
        entry["bibtex"] = make_bibtex(entry, used_keys)
        out.append({k: v for k, v in entry.items() if v not in ("", None, [])} | {"members": w["members"]})

    changed = out != old_pubs
    result = {
        "_comment": "Generated by scripts/update_publications.py. Do not edit; use publications.toml instead.",
        "updated": date.today().isoformat() if changed else previous.get("updated", date.today().isoformat()),
        "publications": out,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    new = {p["id"] for p in out} - {p.get("id") for p in old_pubs}
    log(f"wrote {len(out)} publications ({len(new)} new) to {OUTPUT_FILE.relative_to(ROOT)}")
    if failed:
        log(f"warning: ORCID could not be read for: {', '.join(failed)}")


def _safe_fetch_doi(doi: str):
    try:
        return fetch_doi(doi)
    except Exception as e:
        log(f"warning: could not resolve DOI {doi}: {e}")
        return None


if __name__ == "__main__":
    main()
