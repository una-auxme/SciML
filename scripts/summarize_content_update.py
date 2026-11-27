#!/usr/bin/env python3
"""
Summarize the content changes between a git revision and the working tree, sorted by category, as
Markdown for the review pull request of the weekly content update (.github/workflows/content-update.yml).

Categories:
  - publications (data/publications.json): new, updated and removed entries
  - news (content/news/): new and changed items, sorted into publication, member and award news
  - publication map (data/publication_map.json): papers, citation links and topics
  - other changed files

Only these count as changes ("significant"): new, updated or removed publications, new or changed
news items, and new or removed papers, citation links or topic assignments in the publication map.
Updated citation counts or dates alone do not, so they never open a pull request on their own.

Usage
  python scripts/summarize_content_update.py --base origin/main
  python scripts/summarize_content_update.py --base origin/main --repo owner/name --branch content-update \\
      --out summary.md
  python scripts/summarize_content_update.py --base HEAD --count   # number of significant changes only
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update_publications import ROOT  # noqa: E402
from create_publication_news import in_group_list, read_members  # noqa: E402

PUBS = "data/publications.json"
MAP = "data/publication_map.json"
NEWS = "content/news/"
BOOKKEEPING = {"data/announced_publications.json", "data/announced_members.json", "data/announced_awards.json"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


def at_base(base: str, path: str) -> str | None:
    """Content of a file at the base revision, or None if it did not exist there."""
    try:
        return git("show", f"{base}:{path}")
    except subprocess.CalledProcessError:
        return None


def changed_files(base: str) -> dict[str, str]:
    """{path: status} of files that differ between the base and the working tree (A, M, D)."""
    out = {}
    for line in git("diff", "--name-status", "--no-renames", base, "--").splitlines():
        status, path = line.split("\t", 1)
        out[path] = status[0]
    for path in git("ls-files", "--others", "--exclude-standard").splitlines():
        out[path] = "A"
    return out


def front_matter(text: str) -> dict:
    parts = text.split("+++", 2)
    try:
        return tomllib.loads(parts[1]) if len(parts) == 3 else {}
    except tomllib.TOMLDecodeError:
        return {}


def type_labels() -> dict[str, str]:
    cfg = tomllib.loads((ROOT / "hugo.toml").read_text(encoding="utf-8"))
    return cfg.get("params", {}).get("publicationTypes", {})


def pub_line(p: dict, members: dict, labels: dict) -> str:
    names = [members[s]["title"] for s in p.get("members", []) if s in members]
    bits = [str(p.get("year") or "n.d."), labels.get(p.get("type", ""), p.get("type", ""))]
    if p.get("venue"):
        bits.append(f"*{p['venue']}*")
    line = f"- **{p.get('title', '(untitled)')}** ({', '.join(b for b in bits if b)})"
    if names:
        line += " · " + ", ".join(names)
    if p.get("doi"):
        line += f" · [{p['doi']}](https://doi.org/{p['doi']})"
    elif p.get("url"):
        line += f" · [link]({p['url']})"
    if not in_group_list(p, members):
        line += " · *member page only (not in the group list)*"
    return line


def summarize(base: str, repo: str | None, branch: str | None) -> tuple[str, int]:
    members = read_members()
    labels = type_labels()
    files = changed_files(base)
    sections: list[str] = []
    significant = 0

    def file_link(path: str) -> str:
        return f"https://github.com/{repo}/blob/{branch}/{path}" if repo and branch else path

    # --- Publications -----------------------------------------------------------------------------
    if PUBS in files:
        old_raw = at_base(base, PUBS)
        old = {p["id"]: p for p in json.loads(old_raw)["publications"]} if old_raw else {}
        new = {p["id"]: p for p in json.loads((ROOT / PUBS).read_text(encoding="utf-8"))["publications"]}
        added = [new[i] for i in new if i not in old]
        removed = [old[i] for i in old if i not in new]
        updated = [new[i] for i in new if i in old and new[i] != old[i]]
        # A publication whose ID changed (e.g. because it got a DOI) is an update, not new + removed.
        key = lambda p: re.sub(r"[^a-z0-9]", "", (p.get("title") or "").lower())
        for p in list(added):
            twin = next((q for q in removed if q.get("year") == p.get("year") and
                         SequenceMatcher(None, key(p), key(q)).ratio() >= 0.9), None)
            if twin:
                added.remove(p); removed.remove(twin); updated.append(p)
        by_year = lambda ps: sorted(ps, key=lambda p: (-(p.get("year") or 0), p.get("title", "")))
        if added:
            sections.append(f"### New publications ({len(added)})\n\n" +
                            "\n".join(pub_line(p, members, labels) for p in by_year(added)))
        if updated:
            sections.append(f"### Updated publications ({len(updated)})\n\nMetadata changed, for example "
                            "the venue, the authors or the DOI:\n\n" +
                            "\n".join(pub_line(p, members, labels) for p in by_year(updated)))
        if removed:
            sections.append(f"### Removed publications ({len(removed)})\n\nNo longer in the members' ORCID "
                            "records (or now hidden in `publications.toml`):\n\n" +
                            "\n".join(pub_line(p, members, labels) for p in by_year(removed)))
        significant += len(added) + len(updated) + len(removed)

    # --- News -------------------------------------------------------------------------------------
    news = {path: st for path, st in files.items() if path.startswith(NEWS) and path.endswith(".md")
            and not path.endswith("_index.md")}
    if news:
        groups = {"Publication news": [], "Welcome and farewell news": [], "Award news": [], "Other news": []}
        for path, st in sorted(news.items()):
            if st == "D":
                groups["Other news"].append(f"- removed: `{path}`")
                continue
            fm = front_matter((ROOT / path).read_text(encoding="utf-8"))
            kind = ("Publication news" if fm.get("publication") else "Welcome and farewell news" if fm.get("member")
                    else "Award news" if fm.get("award") else "Other news")
            date = fm.get("date", "")
            label = "" if st == "A" else " *(changed)*"
            groups[kind].append(f"- [{fm.get('title', path)}]({file_link(path)}) · {date}{label}")
        body = "\n\n".join(f"**{k}**\n\n" + "\n".join(v) for k, v in groups.items() if v)
        sections.append(f"### News feed ({len(news)})\n\nNew items appear on the news page and the three "
                        f"newest on the home page. Click an item to read or edit it.\n\n{body}")
        significant += len(news)

    # --- Publication map --------------------------------------------------------------------------
    if MAP in files:
        old_raw = at_base(base, MAP)
        old = json.loads(old_raw) if old_raw else {"nodes": [], "links": []}
        new = json.loads((ROOT / MAP).read_text(encoding="utf-8"))
        base_pubs = at_base(base, PUBS)   # titles of publications that are gone now come from the base
        titles = {p["id"]: p.get("title", p["id"])
                  for p in (json.loads(base_pubs)["publications"] if base_pubs else []) +
                  json.loads((ROOT / PUBS).read_text(encoding="utf-8"))["publications"]}
        on, nn = {n["id"]: n for n in old["nodes"]}, {n["id"]: n for n in new["nodes"]}
        ol = {(l["source"], l["target"], l.get("kind", "")) for l in old["links"]}
        nl = {(l["source"], l["target"], l.get("kind", "")) for l in new["links"]}
        added, removed = [i for i in nn if i not in on], [i for i in on if i not in nn]
        moved = [i for i in nn if i in on and nn[i].get("topics") != on[i].get("topics")]
        lines = [f"- {len(nn)} publications (before: {len(on)}), {len(nl)} links (before: {len(ol)})"]
        lines += [f"- added: {titles.get(i, i)}" for i in added]
        lines += [f"- removed: {titles.get(i, i)}" for i in removed]
        lines += [f"- new topic: {titles.get(i, i)} → " + ", ".join(f"{g}: {t}" for g, t in nn[i]["topics"].items())
                  for i in moved]
        if len(nl - ol) or len(ol - nl):
            lines.append(f"- citation links: {len(nl - ol)} new, {len(ol - nl)} removed")
        structural = len(added) + len(removed) + len(moved) + len(nl ^ ol)
        if structural:
            sections.append("### Publication map (home page)\n\n" + "\n".join(lines))
        else:
            sections.append("### Publication map (home page)\n\nOnly citation counts and abstracts were refreshed.")
        significant += structural

    # --- Everything else --------------------------------------------------------------------------
    rest = sorted(p for p in files if p not in (PUBS, MAP) and p not in news)
    if rest:
        sections.append("### Other files\n\n" + "\n".join(
            f"- `{p}`" + (" (bookkeeping: what has been announced)" if p in BOOKKEEPING else "") for p in rest))

    return "\n\n".join(sections), significant


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="origin/main", help="git revision to compare with")
    parser.add_argument("--repo", help="owner/name, for links to the files")
    parser.add_argument("--branch", help="branch of the changes, for links to the files")
    parser.add_argument("--out", help="write the Markdown here instead of printing it")
    parser.add_argument("--count", action="store_true", help="print only the number of significant changes")
    args = parser.parse_args()

    text, significant = summarize(args.base, args.repo, args.branch)
    if args.count:
        print(significant)
        return
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text or "(no changes)")
    print(f"{significant} significant change(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
