#!/usr/bin/env python3
"""
Create a news item for every new publication of the group.

Runs weekly on GitHub after scripts/update_publications.py (.github/workflows/content-update.yml).
For each publication in the group list (the same rules as the publications page) that has not
been announced before, it writes content/news/<date>-pub-<title>.md with the member authors,
the linked title and venue, and a summary of the abstract in one or two sentences.

Summary, first available of:
  1. Claude (Anthropic API) summarizes the abstract. Needs the environment variable
     ANTHROPIC_API_KEY and the package `anthropic` (pip install anthropic).
  2. The one-sentence TLDR from Semantic Scholar.
  3. The key sentence(s) of the abstract.
Abstracts come from Semantic Scholar, Crossref (via doi.org) or OpenAlex.

Announced publications are recorded in data/announced_publications.json, so every publication
is announced once. When that file does not exist yet, all current publications are recorded
without creating news. Settings: section [news] in publications.toml.

Usage
  python scripts/create_publication_news.py            # create news for new publications
  python scripts/create_publication_news.py --dry-run  # show what would be written, change nothing
  python scripts/create_publication_news.py --init     # record all current publications as announced
  python scripts/create_publication_news.py --backfill # announce recent publications that have no news yet
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import tomllib
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update_publications import (  # noqa: E402  (shared helpers)
    CURATION_FILE, MEMBERS_DIR, OUTPUT_FILE as PUBLICATIONS_FILE, ROOT,
    ascii_fold, clean_text, http_get_json, log, norm_title, read_front_matter,
)

STATE_FILE = ROOT / "data" / "announced_publications.json"
NEWS_DIR = ROOT / "content" / "news"
SETTINGS = {
    "enabled": True,
    "types": ["journal", "conference", "preprint", "chapter", "book"],  # theses are announced by hand
    "max_age_days": 365,      # older publications (e.g. added late to ORCID) are not announced
    "max_per_run": 5,         # more new publications are announced in the following weeks
}
CLAUDE_MODEL = "claude-opus-5-5"
SUMMARY_PROMPT = (
    "You write the summary for a news item on a university research group's website that "
    "announces one of the group's new publications. Summarize what the publication does and what "
    "it finds in one or two sentences, at most 45 words, for scientifically literate readers "
    "outside the field. Use only information stated in the abstract: add no claims, numbers or "
    "praise. Do not repeat the title and do not name the authors or the venue. Write in English, "
    "in the present tense, and reply with the summary text only."
)
# Sentences stating the contribution: "We train ...", "In this study, we ...", "This paper presents ...".
KEY_SENTENCE = re.compile(r"\b(we|this (paper|work|article|contribution|thesis|study))\b", re.I)
TITLES = {"journal": "New journal article", "conference": "New conference paper", "preprint": "New preprint",
          "chapter": "New book chapter", "book": "New book", "thesis": "Thesis completed"}


# ----------------------------------------------------------------------------- inputs

def read_members() -> dict[str, dict]:
    files = sorted(MEMBERS_DIR.glob("*/index.md")) + sorted(
        p for p in MEMBERS_DIR.glob("*.md") if p.name != "_index.md")
    members = {}
    for f in files:
        fm = read_front_matter(f)
        if not fm.get("draft"):
            members[f.parent.name if f.name == "index.md" else f.stem] = fm
    return members


def year_of(value, default: int) -> int:
    """Year of a member's `joined`/`left`: a year (2026), a month ("2026-07") or a date (2026-07-31)."""
    if value in (None, ""):
        return default
    if isinstance(value, (date, datetime)):
        return value.year
    m = re.match(r"\s*(\d{4})", str(value))
    return int(m.group(1)) if m else default


def in_group_list(p: dict, members: dict[str, dict]) -> bool:
    """Same rule as layouts/_partials/pubs-group.html."""
    if not p.get("members"):
        return True
    year = p.get("year") or 0
    for slug in p["members"]:
        fm = members.get(slug)
        if fm is None or fm.get("group_publications") is False:
            continue
        if year_of(fm.get("joined"), 0) <= year <= year_of(fm.get("left"), 9999):
            return True
    return False


def latest_date(p: dict) -> tuple[date | None, bool]:
    """Publication date; for partial dates the last possible day. Second value: date is exact."""
    parts = [int(x) for x in str(p.get("date") or p.get("year") or "").split("-") if x.isdigit()]
    if not parts:
        return None, False
    if len(parts) >= 3:
        return date(parts[0], parts[1], parts[2]), True
    y, m = parts[0], (parts[1] if len(parts) > 1 else 12)
    return date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1), False


# ----------------------------------------------------------------------------- abstracts

def get_json(url: str):
    try:
        return http_get_json(url)
    except Exception as e:  # network problems only cost us a source
        log(f"  note: {url.split('?')[0]} not reachable ({e})")
        return None


def from_semantic_scholar(p: dict) -> tuple[str, str]:
    """Returns (abstract, tldr)."""
    ids = (["DOI:" + p["doi"]] if p.get("doi") else []) + (["ARXIV:" + p["arxiv"]] if p.get("arxiv") else [])
    for pid in ids:
        d = get_json(f"https://api.semanticscholar.org/graph/v1/paper/{urllib.parse.quote(pid, safe=':/')}"
                     "?fields=abstract,tldr")
        if d:
            return clean_text(d.get("abstract")), clean_text((d.get("tldr") or {}).get("text"))
    d = get_json("https://api.semanticscholar.org/graph/v1/paper/search/match?"
                 + urllib.parse.urlencode({"query": p["title"], "fields": "title,abstract,tldr"}))
    for m in (d or {}).get("data", [])[:1]:
        if norm_title(m.get("title", "")) == norm_title(p["title"]):
            return clean_text(m.get("abstract")), clean_text((m.get("tldr") or {}).get("text"))
    return "", ""


def from_crossref(p: dict) -> str:
    if not p.get("doi"):
        return ""
    try:
        csl = http_get_json("https://doi.org/" + urllib.parse.quote(p["doi"], safe="/:;()._-"),
                            accept="application/vnd.citationstyles.csl+json") or {}
    except Exception:
        return ""
    return re.sub(r"^abstract[:.\s]*", "", clean_text(csl.get("abstract")), flags=re.I)


def from_openalex(p: dict) -> str:
    if not p.get("doi"):
        return ""
    d = get_json(f"https://api.openalex.org/works/doi:{urllib.parse.quote(p['doi'], safe='/')}"
                 "?select=abstract_inverted_index")
    index = (d or {}).get("abstract_inverted_index") or {}
    words = sorted((pos, w) for w, positions in index.items() for pos in positions)
    return clean_text(" ".join(w for _, w in words))


# ----------------------------------------------------------------------------- summaries

def summarize_with_claude(p: dict, abstract: str) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return ""
    try:
        import anthropic
    except ImportError:
        log("  note: ANTHROPIC_API_KEY is set, but the package is missing (pip install anthropic)")
        return ""
    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",                 # retry on another model if this one declines
            output_config={"effort": "low"},     # a short summary needs little reasoning
            system=SUMMARY_PROMPT,
            messages=[{"role": "user", "content":
                       f"Title: {p['title']}\nVenue: {p.get('venue', '')}\n\nAbstract:\n{abstract}"}],
        )
    except anthropic.AuthenticationError:
        log("  note: ANTHROPIC_API_KEY was rejected; using another summary source")
        return ""
    except anthropic.RateLimitError:
        log("  note: Anthropic API rate limit reached; using another summary source")
        return ""
    except anthropic.APIStatusError as e:
        log(f"  note: Anthropic API error {e.status_code} (request {getattr(e, 'request_id', '?')}); "
            "using another summary source")
        return ""
    except anthropic.APIConnectionError:
        log("  note: Anthropic API not reachable; using another summary source")
        return ""
    if response.stop_reason == "refusal":
        log("  note: the model declined to summarize; using another summary source")
        return ""
    return " ".join(b.text for b in response.content if b.type == "text").strip()


def key_sentences(abstract: str) -> str:
    # Also split where a space after the full stop is missing ("regressor.We").
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s*(?=[A-Z][a-z])", abstract) if s.strip()]
    key = [s for s in sentences if KEY_SENTENCE.search(s)] or sentences[:1]
    text = key[0]
    if len(key) > 1 and len(text) + len(key[1]) < 300:   # a second sentence only if both stay short
        text += " " + key[1]
    return text if len(text) <= 400 else text[:397].rsplit(" ", 1)[0] + " …"


def summarize(p: dict) -> tuple[str, str]:
    """Returns (summary, source)."""
    abstract, tldr = from_semantic_scholar(p)
    abstract = html.unescape(abstract or from_crossref(p) or from_openalex(p))   # some sources escape twice
    if abstract:
        text = summarize_with_claude(p, abstract)
        if text:
            return text, "claude"
    if tldr:
        return tldr, "semantic-scholar-tldr"
    if abstract:
        return key_sentences(abstract), "abstract"
    return "", "none"


# ----------------------------------------------------------------------------- news text

def md_escape(s: str) -> str:
    return re.sub(r"([\\*_\[\]$`])", r"\\\1", s)


def toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)   # JSON strings are valid TOML basic strings


def join_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def news_text(p: dict, members: dict[str, dict], summary: str) -> str:
    # Full names from the member pages (author lists often only have initials).
    linked = [f"[{members[a['member']].get('title', a['name'])}](/members/{a['member']}/)"
              for a in p.get("authors", []) if a.get("member") in members]
    if linked and any(not a.get("member") for a in p.get("authors", [])):
        linked.append("co-authors")
    who = join_names(linked) if linked else "Our group"
    title = f"*[{md_escape(p['title'])}]({p['url']})*" if p.get("url") else f"*{md_escape(p['title'])}*"
    venue = md_escape(p.get("venue", ""))
    t = p["type"]
    if t == "journal":
        sentence = f"{who} published {title}" + (f" in *{venue}*" if venue else "")
    elif t == "conference":
        prep = "in the" if venue.lower().startswith("proc") else "at the"
        sentence = f"{who} presented {title}" + (f" {prep} *{venue}*" if venue else "")
    elif t == "preprint":
        sentence = f"{who} released the preprint {title}" + (f" on {venue}" if venue else "")
    elif t == "chapter":
        sentence = f"{who} contributed the chapter {title}" + (f" to *{venue}*" if venue else "")
    elif t == "book":
        sentence = f"{who} published the book {title}"
    elif t == "thesis":
        sentence = f"{who} completed the thesis {title}"
    else:
        sentence = f"{who} published {title}"
    return sentence + "." + (f"\n\n{summary}" if summary else "")


def slugify(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", ascii_fold(title).lower())
    return "-".join(words[:6]) or "publication"


# ----------------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="only show what would be written")
    parser.add_argument("--init", action="store_true", help="record all current publications as announced")
    parser.add_argument("--backfill", action="store_true",
                        help="also announce publications from the last max_age_days that have no news item yet, "
                             "dated at their publication date (no limit per run)")
    args = parser.parse_args()

    settings = dict(SETTINGS)
    if CURATION_FILE.exists():
        with CURATION_FILE.open("rb") as fh:
            settings.update(tomllib.load(fh).get("news", {}))
    pubs = json.loads(PUBLICATIONS_FILE.read_text(encoding="utf-8")).get("publications", [])
    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else None

    def save(ids: set[str], titles: set[str]) -> None:
        if args.dry_run:
            return
        STATE_FILE.write_text(json.dumps({
            "_comment": "Publications that already have a news item (or existed before the news feature). "
                        "Written by scripts/create_publication_news.py; remove an entry to announce it again.",
            "announced": sorted(ids), "titles": sorted(titles)}, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8")

    if state is None or args.init:
        save({p["id"] for p in pubs}, {norm_title(p["title"]) for p in pubs})
        log(f"recorded {len(pubs)} existing publications as announced; no news created")
        return
    if not settings["enabled"]:
        log("news for new publications are disabled ([news] enabled = false in publications.toml)")
        return

    announced, titles = set(state.get("announced", [])), set(state.get("titles", []))
    members = read_members()
    today = date.today()
    if args.backfill:
        # Recent publications that were only recorded (e.g. at the first run) but have no news item.
        with_news = {m.group(1) for f in NEWS_DIR.glob("*.md")
                     for m in [re.search(r'^publication = "([^"]+)"', f.read_text(encoding="utf-8"), re.M)] if m}
        for p in pubs:
            when, _ = latest_date(p)
            if p["id"] not in with_news and when and (today - when).days <= settings["max_age_days"]:
                announced.discard(p["id"])
                titles.discard(norm_title(p["title"]))
        settings["max_per_run"] = 10 ** 6
    new = [p for p in pubs
           if p["id"] not in announced and norm_title(p["title"]) not in titles
           and p.get("type") in settings["types"] and in_group_list(p, members)]
    created = 0
    for p in new:
        when, exact = latest_date(p)
        if when and (today - when).days > settings["max_age_days"]:
            log(f"skipping (older than {settings['max_age_days']} days): {p['title']}")
            announced.add(p["id"])
            titles.add(norm_title(p["title"]))
            continue
        if created >= settings["max_per_run"]:
            log(f"limit of {settings['max_per_run']} news per run reached; the rest follow next time")
            break
        log(f"new publication: {p['title']}")
        summary, source = summarize(p)
        log(f"  summary from: {source}")
        if args.backfill and when:
            news_date = min(when, today)   # place older items at their publication date
        else:
            news_date = when if exact and when <= today and (today - when).days <= 60 else today
        front = "\n".join([
            "+++",
            f"title = {toml_str(TITLES.get(p['type'], 'New publication') + ': ' + p['title'])}",
            f"date = {news_date.isoformat()}",
            f"link = {toml_str(p.get('url', ''))}",
            f"publication = {toml_str(p['id'])}      # created automatically by scripts/create_publication_news.py",
            f"summary_source = {toml_str(source)}",
            "+++",
        ])
        content = f"{front}\n\n{news_text(p, members, summary)}\n"
        path = NEWS_DIR / f"{news_date.isoformat()}-pub-{slugify(p['title'])}.md"
        n = 2
        while path.exists():
            path = path.with_name(f"{news_date.isoformat()}-pub-{slugify(p['title'])}-{n}.md")
            n += 1
        if args.dry_run:
            print(f"--- would write {path.relative_to(ROOT)}\n{content}")
        else:
            path.write_text(content, encoding="utf-8")
            log(f"  wrote {path.relative_to(ROOT)}")
        announced.add(p["id"])
        titles.add(norm_title(p["title"]))
        created += 1
    save(announced, titles)
    log(f"{created} news item(s) {'would be ' if args.dry_run else ''}created")


if __name__ == "__main__":
    main()
