#!/usr/bin/env python3
"""
Create a news item for every new award in content/awards/.

Runs weekly on GitHub (.github/workflows/content-update.yml), which proposes the news for review
in a pull request. For every award whose `date` has been
reached and that has no news item yet, it writes content/news/<date>-award-<name>.md, dated on the
day of the award, with a link to the award (`award = "<file name>"`). The news items are ordinary
Markdown files: edit or delete them like any other news.

Fields of an award (content/awards/<date>-<name>.md):
  title      name of the award (in English)
  origtitle  original name, if not English (shown on the member pages only)
  date       day of the award, e.g. 2026-11-20
  members    member folder names, e.g. ["tobias-thummerer"]
  by         who gives the award (Markdown, may contain a link)
  reason     what it is for, completes "... for ...", e.g. "the best paper at Example Conference 2026"
  link       optional page about the award
  news       false: no news item for this award
  news_title optional title of the news item (default: "<title> for <names>")
The text below the front matter, if any, replaces the generated text of the news item.

Announced awards are recorded in data/announced_awards.json, so every award is announced once
(deleting a generated news item does not bring it back). An award that already has a news item
(field `award` in the news front matter) counts as announced. Awards older than MAX_AGE_DAYS when
they are added are not announced. When the record file does not exist yet, all awards up to today
are recorded without creating news.

Usage
  python scripts/create_award_news.py            # create news for new awards
  python scripts/create_award_news.py --dry-run  # show what would be written, change nothing
  python scripts/create_award_news.py --init     # record all awards up to today as announced
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update_publications import ROOT, log  # noqa: E402
from create_publication_news import read_members, toml_str  # noqa: E402
from create_member_news import MAX_AGE_DAYS, exact_date  # noqa: E402

AWARDS_DIR = ROOT / "content" / "awards"
NEWS_DIR = ROOT / "content" / "news"
STATE_FILE = ROOT / "data" / "announced_awards.json"


def read_awards() -> list[tuple[str, dict, str]]:
    """(file name without .md, front matter, text below the front matter) of every award."""
    awards = []
    for path in sorted(AWARDS_DIR.glob("*.md")):
        if path.name.startswith("_"):
            continue
        parts = path.read_text(encoding="utf-8").split("+++", 2)
        if len(parts) < 3:
            log(f"warning: {path.relative_to(ROOT)} has no +++ front matter, skipped")
            continue
        awards.append((path.stem, tomllib.loads(parts[1]), parts[2].strip()))
    return awards


def awards_with_news() -> set[str]:
    """Awards that already have a news item (field `award` in its front matter)."""
    found = set()
    for path in NEWS_DIR.glob("*.md"):
        m = re.search(r'^award\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8").split("+++", 2)[1], re.M)
        if m:
            found.add(m.group(1))
    return found


def join_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def news_text(fm: dict, text: str, members: dict) -> str:
    if text:
        return text
    linked = [f"[{members[s]['title']}](/members/{s}/)" if s in members else s for s in fm.get("members", [])]
    out = f"{join_names(linked) if linked else 'Our group'} received the *{fm['title']}*"
    if fm.get("by"):
        out += f" from {fm['by']}"
    if fm.get("reason"):
        out += f" for {fm['reason']}"
    return out + ". Congratulations!"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="show what would be written, change nothing")
    parser.add_argument("--init", action="store_true", help="record all awards up to today as announced")
    args = parser.parse_args()

    today = date.today()
    members = read_members()
    awards = []   # (date, name, front matter, text) of awards whose day has come
    for name, fm, text in read_awards():
        d = exact_date(fm.get("date"))
        if d is None:
            log(f"warning: content/awards/{name}.md needs a date such as 2026-11-20, skipped")
            continue
        for slug in fm.get("members", []):
            if slug not in members:
                log(f"warning: content/awards/{name}.md: {slug!r} is not a folder in content/members/")
        if d <= today:
            awards.append((d, name, fm, text))

    first_run = not STATE_FILE.exists()
    announced = set() if first_run else set(json.loads(STATE_FILE.read_text(encoding="utf-8"))["announced"])

    def save() -> None:
        if not args.dry_run:
            STATE_FILE.write_text(json.dumps({
                "_comment": "Awards announced as news (scripts/create_award_news.py). "
                            "Remove an entry to announce it again.",
                "announced": sorted(announced),
            }, indent=1) + "\n", encoding="utf-8")

    if args.init or first_run:
        announced |= {name for _, name, _, _ in awards}
        save()
        log(f"recorded {len(awards)} award(s) as announced; no news created")
        return

    existing = awards_with_news()
    created = 0
    for d, name, fm, text in sorted(awards):
        if name in announced:
            continue
        if name in existing:
            log(f"already has a news item: {name}")
            announced.add(name)
            continue
        if fm.get("news") is False:
            log(f"skipping ({name} has news = false)")
            continue
        if (today - d).days > MAX_AGE_DAYS:
            log(f"not announced (older than {MAX_AGE_DAYS} days): {name}")
            announced.add(name)   # recorded, so it is reported only once
            continue
        names = [members[s]["title"] if s in members else s for s in fm.get("members", [])]
        title = fm.get("news_title") or (f"{fm['title']} for {join_names(names)}" if names else fm["title"])
        short = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)
        path = NEWS_DIR / f"{d.isoformat()}-award-{short}.md"
        content = (f'+++\ntitle = {toml_str(title)}\ndate = {d.isoformat()}\nlink = {toml_str(fm.get("link", ""))}\n'
                   f'award = "{name}"      # created automatically by scripts/create_award_news.py\n'
                   f'+++\n\n{news_text(fm, text, members)}\n')
        if args.dry_run:
            log(f"\n--- would write {path.relative_to(ROOT)}\n{content}")
        elif path.exists():
            log(f"exists, not overwritten: {path.relative_to(ROOT)}")
        else:
            path.write_text(content, encoding="utf-8")
            log(f"wrote {path.relative_to(ROOT)}")
        announced.add(name)
        created += 1
    save()
    log(f"{created} news item(s) {'would be ' if args.dry_run else ''}created")


if __name__ == "__main__":
    main()
