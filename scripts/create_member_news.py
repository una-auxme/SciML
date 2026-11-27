#!/usr/bin/env python3
"""
Create welcome and farewell news when members join or leave the group.

Runs weekly on GitHub (.github/workflows/content-update.yml), which proposes the news for review
in a pull request. For every member whose exact `joined`
or `left` date (a day such as 2026-05-01, not only a year or month) has been reached, it writes a
news item content/news/<date>-welcome-<member>.md or <date>-farewell-<member>.md, dated on that
day. The news items are ordinary Markdown files: edit or delete them like any other news.

Optional fields on a member page (content/members/<name>/index.md):
  news = false      no welcome or farewell news for this person
  welcome = "..."   own text (Markdown) for the welcome news instead of the generated one
  farewell = "..."  own text (Markdown) for the farewell news

Announced events are recorded in data/announced_members.json, so every event is announced once
(deleting a generated news item does not bring it back). Events older than MAX_AGE_DAYS are not
announced, for example when the dates of former members are added later. When the record file
does not exist yet, all events up to today are recorded without creating news.

Usage
  python scripts/create_member_news.py            # create news for new events
  python scripts/create_member_news.py --dry-run  # show what would be written, change nothing
  python scripts/create_member_news.py --init     # record all events up to today as announced
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update_publications import ROOT, log  # noqa: E402
from create_publication_news import read_members, toml_str  # noqa: E402

STATE_FILE = ROOT / "data" / "announced_members.json"
NEWS_DIR = ROOT / "content" / "news"
MAX_AGE_DAYS = 60   # events further in the past are not announced


def exact_date(value) -> date | None:
    """The day of a `joined`/`left` value, or None if only a year or month is given."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return date.fromisoformat(value.strip())
    return None


def day_label(d: date) -> str:
    return f"{d.day} {d.strftime('%B')} {d.year}"


def lower_first(s: str) -> str:
    """'Research associate' -> 'research associate', but keep acronyms such as 'FMI'."""
    return s[0].lower() + s[1:] if len(s) > 1 and s[1].islower() else s


def with_article(role: str) -> str:
    """'Research associate' -> 'a research associate'; titles such as 'Head of ...' get no article."""
    role = lower_first(role.strip())
    if not role or re.match(r"(head|chair|professor|director|leader)\b", role):
        return role
    return ("an " if role[0] in "aeiou" else "a ") + role


def duration(start: date, end: date) -> str:
    months = (end.year - start.year) * 12 + end.month - start.month + (1 if end.day >= start.day else 0)
    if months >= 18:
        return f"{round(months / 12)} years"
    if months >= 12:
        return "one year"
    return f"{months} months" if months > 1 else "one month"


def welcome_text(slug: str, fm: dict, d: date) -> str:
    name, first = fm["title"], fm["title"].split()[0]
    if fm.get("welcome"):
        return fm["welcome"].strip()
    text = f"[{name}](/members/{slug}/) joined the group"
    if fm.get("position"):
        text += f" as {with_article(fm['position'])}"
    text += f" on {day_label(d)}."
    interests = [lower_first(i) for i in fm.get("interests", [])[:2]]
    if interests:
        text += f" {first} works on {' and '.join(interests)}."
    return text + " Welcome to the team!"


def farewell_text(slug: str, fm: dict, d: date) -> str:
    name, first = fm["title"], fm["title"].split()[0]
    if fm.get("farewell"):
        return fm["farewell"].strip()
    text = f"[{name}](/members/{slug}/) left the group on {day_label(d)}"
    start = exact_date(fm.get("joined"))
    if start and start < d:
        text += f" after {duration(start, d)}"
    if fm.get("position"):
        text += f" as {with_article(fm['position'])}"
    text += "."
    if fm.get("now"):
        text += f" {first} is now {with_article(fm['now'])}."
    return text + " Thank you for your work in the group, and all the best!"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="show what would be written, change nothing")
    parser.add_argument("--init", action="store_true", help="record all events up to today as announced")
    args = parser.parse_args()

    today = date.today()
    members = read_members()
    events = []   # (date, kind, slug, front matter)
    for slug, fm in sorted(members.items()):
        for kind in ("joined", "left"):
            d = exact_date(fm.get(kind))
            if d and d <= today:
                events.append((d, kind, slug, fm))

    first_run = not STATE_FILE.exists()
    announced = set() if first_run else set(json.loads(STATE_FILE.read_text(encoding="utf-8"))["announced"])

    def save() -> None:
        if not args.dry_run:
            STATE_FILE.write_text(json.dumps({
                "_comment": "Member events announced as news (scripts/create_member_news.py). "
                            "Remove an entry to announce it again.",
                "announced": sorted(announced),
            }, indent=1) + "\n", encoding="utf-8")

    if args.init or first_run:
        announced |= {f"{slug}/{kind}/{d.isoformat()}" for d, kind, slug, _ in events}
        save()
        log(f"recorded {len(events)} past event(s) as announced; no news created")
        return

    created = 0
    for d, kind, slug, fm in sorted(events):
        key = f"{slug}/{kind}/{d.isoformat()}"
        if key in announced:
            continue
        if fm.get("news") is False:
            log(f"skipping ({slug} has news = false): {kind} {d}")
            continue
        if (today - d).days > MAX_AGE_DAYS:
            log(f"not announced (older than {MAX_AGE_DAYS} days): {slug} {kind} {d}")
            announced.add(key)   # recorded, so it is reported only once
            continue
        first = fm["title"].split()[0]
        if kind == "joined":
            title, body, name = f"Welcome, {first}!", welcome_text(slug, fm, d), f"{d.isoformat()}-welcome-{slug}.md"
        else:
            title, body, name = f"Farewell, {first}!", farewell_text(slug, fm, d), f"{d.isoformat()}-farewell-{slug}.md"
        path = NEWS_DIR / name
        content = (f'+++\ntitle = {toml_str(title)}\ndate = {d.isoformat()}\nlink = ""\n'
                   f'member = "{slug}"      # created automatically by scripts/create_member_news.py\n'
                   f'event = "{kind}"\n+++\n\n{body}\n')
        if args.dry_run:
            log(f"\n--- would write {path.relative_to(ROOT)}\n{content}")
        elif path.exists():
            log(f"exists, not overwritten: {path.relative_to(ROOT)}")
        else:
            path.write_text(content, encoding="utf-8")
            log(f"wrote {path.relative_to(ROOT)}")
        announced.add(key)
        created += 1
    save()
    log(f"{created} news item(s) {'would be ' if args.dry_run else ''}created")


if __name__ == "__main__":
    main()
