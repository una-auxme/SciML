#!/usr/bin/env python3
"""
Build the data of the publication map on the home page: data/publication_map.json.

Runs once a month on GitHub (.github/workflows/publication-map.yml). For every publication in
the group list (the same rules as the publications page) it collects
  - its topic in each grouping of the map (methods, applications), from the keywords in the
    [map] section of publications.toml,
  - citations between the group's publications: reference lists from OpenAlex and Crossref
    (Semantic Scholar for publications that OpenAlex does not know),
  - "related" links between publications that share several references,
  - the abstract (cached) and the number of citations.
Titles, authors and links come from data/publications.json when the site is built, so
corrections in publications.toml show up without running this script. The page draws the map
in the browser (layouts/_partials/pubmap.html and assets/js/pubmap.js).

Links found once are kept, so that a temporarily unreachable service does not remove lines
from the map; --refresh starts from scratch.

Usage
  python scripts/update_publication_map.py            # update citations, citation counts, new abstracts
  python scripts/update_publication_map.py --offline  # only re-apply topics and settings from publications.toml
  python scripts/update_publication_map.py --refresh  # forget cached abstracts and links, fetch everything again
"""

from __future__ import annotations

import argparse
import html
import itertools
import json
import math
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_publications as up  # noqa: E402  (shared helpers; USER_AGENT is set below)
from update_publications import (  # noqa: E402
    OUTPUT_FILE as PUBLICATIONS_FILE, ROOT, ascii_fold, clean_text, log, norm_doi, norm_title, read_curation,
)
from create_publication_news import from_crossref, get_json, in_group_list, read_members  # noqa: E402

OUTPUT_FILE = ROOT / "data" / "publication_map.json"
# Topic colors in the order of the topics in publications.toml. Checked as a set for color-vision
# deficiencies (every pair stays distinguishable, also for red-green color blindness). A topic's
# own `color` overrides its slot; more topics need a `color` each.
PALETTE = ["#009b5d", "#2a78d6", "#b5179e", "#eda100", "#a35a00", "#e87ba4"]
GRAY = "#8a94a6"   # for a `fallback` topic ("General methods") and for "Other"
OTHER = {"key": "other", "name": "Other", "color": GRAY}
# The two ways of grouping the map, in the order of the switch (the first one is shown when the
# page opens): section in publications.toml, label of the switch, field in [[map.paper]]
GROUPINGS = [("applications", "Applications", "application"), ("methods", "Methods", "method")]
SETTINGS = {
    "enabled": True,
    "related_min_shared": 4,  # dashed line between publications that share at least this many references
}
MIN_ABSTRACT = 120  # shorter texts are placeholders such as "Extended Abstract."
OPENALEX_FIELDS = "id,title,referenced_works,cited_by_count,abstract_inverted_index"
S2_FIELDS = "title,abstract,citationCount,references.title,references.externalIds"
STOPWORDS = set("""a about above after again against all also an and any are as at based be been being between
both but by can could did do does doing during each few for from further had has have having here how i if in
into is it its itself just more most no nor not now of off on once only or other our out over own same should so
some such than that the their them then there these they this those through to too under until up using very
was we were what when where which while who why will with within without would yet""".split())


# ----------------------------------------------------------------------------- settings

def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", ascii_fold(s).lower()).strip("-")


def read_topics(entries: list[dict], section: str) -> list[dict]:
    """Topics of one grouping. Colors follow the order of the topics; a `fallback` topic is gray."""
    topics, slot = [], 0
    for t in entries:
        if not t.get("name"):
            sys.exit(f"publications.toml: every [[map.{section}]] needs a `name`")
        if t.get("fallback"):
            color = t.get("color") or GRAY
        else:
            color = t.get("color") or (PALETTE[slot] if slot < len(PALETTE) else None)
            slot += 1
        if not color:
            sys.exit(f"publications.toml: topic {t['name']!r} needs a `color` "
                     f"(the default palette has {len(PALETTE)} colors); or merge topics")
        topics.append({"key": slug(t["name"]), "name": t["name"], "color": color, "fallback": bool(t.get("fallback")),
                       "keywords": [ascii_fold(k).lower() for k in t.get("keywords", [])]})
    if sum(t["fallback"] for t in topics) > 1:
        sys.exit(f"publications.toml: only one [[map.{section}]] topic can have `fallback = true`")
    return topics


def paper_settings(p: dict, papers: list[dict]) -> dict:
    """The [[map.paper]] entry of a publication (matched by DOI or exact title), or {}."""
    for e in papers:
        if e.get("doi") and norm_doi(e["doi"]) in doi_aliases(p):
            return e
        if e.get("title") and norm_title(e["title"]) == norm_title(p["title"]):
            return e
    return {}


# ----------------------------------------------------------------------------- identifiers

def doi_aliases(p: dict) -> set[str]:
    """All DOIs of a publication: its own, the arXiv DOI and the DOI of a linked preprint."""
    out = {norm_doi(p.get("doi"))} if p.get("doi") else set()
    if p.get("arxiv"):
        out.add(f"10.48550/arxiv.{p['arxiv']}".lower())
    for key in ("preprint", "url"):
        m = re.search(r"doi\.org/(10\.[^\s?#]+)", p.get(key) or "")
        if m:
            out.add(norm_doi(urllib.parse.unquote(m.group(1))))
    return out


def arxiv_id(p: dict) -> str:
    if p.get("arxiv"):
        return p["arxiv"]
    for d in doi_aliases(p):
        if d.startswith("10.48550/arxiv."):
            return d.split("arxiv.", 1)[1]
    return ""


# ----------------------------------------------------------------------------- sources

def openalex_abstract(work: dict) -> str:
    index = work.get("abstract_inverted_index") or {}
    words = sorted((pos, w) for w, positions in index.items() for pos in positions)
    return clean_text(" ".join(w for _, w in words))


def fetch_openalex(p: dict) -> list[dict]:
    """OpenAlex records of a publication (published version and preprint, if both exist)."""
    works, seen = [], set()
    for d in sorted(doi_aliases(p)):
        w = get_json(f"https://api.openalex.org/works/doi:{urllib.parse.quote(d, safe='/')}?select={OPENALEX_FIELDS}")
        if w and w["id"] not in seen:
            works.append(w)
            seen.add(w["id"])
    if not works:  # no DOI, or not registered: search by title
        r = get_json("https://api.openalex.org/works?" + urllib.parse.urlencode(
            {"search": p["title"], "per-page": 5, "select": OPENALEX_FIELDS}))
        works = [w for w in (r or {}).get("results", [])[:5]
                 if norm_title(w.get("title") or "") == norm_title(p["title"])][:1]
    return works


def fetch_crossref_references(p: dict) -> list[dict]:
    if not p.get("doi") or norm_doi(p["doi"]).startswith("10.48550/"):
        return []
    r = get_json(f"https://api.crossref.org/works/{urllib.parse.quote(norm_doi(p['doi']), safe='/')}")
    return ((r or {}).get("message") or {}).get("reference") or []


def fetch_semantic_scholar(p: dict) -> dict:
    """Best effort (the public API is rate-limited): abstract, citation count, references."""
    r = get_json("https://api.semanticscholar.org/graph/v1/paper/search/match?"
                 + urllib.parse.urlencode({"query": p["title"], "fields": S2_FIELDS}))
    for m in (r or {}).get("data", [])[:1]:
        if norm_title(m.get("title") or "") == norm_title(p["title"]):
            return m
    return {}


def fetch_arxiv_abstract(aid: str) -> str:
    try:
        import urllib.request
        req = urllib.request.Request(f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(aid)}",
                                     headers={"User-Agent": up.USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml = resp.read().decode("utf-8")
    except Exception as e:
        log(f"  note: arXiv not reachable ({e})")
        return ""
    m = re.search(r"<entry>.*?<summary[^>]*>(.*?)</summary>", xml, re.S)
    return clean_text(html.unescape(m.group(1))) if m else ""


def tidy_abstract(text: str) -> str:
    text = re.sub(r"^\s*(abstract|summary)\s*[:.\-–]?\s*", "", clean_text(text), flags=re.I)
    return text.strip()


# ----------------------------------------------------------------------------- topics

def keyword_hits(text: str, keywords: list[str]) -> int:
    return sum(1 for k in keywords if re.search(r"(?<![a-z0-9])" + re.escape(k), text))


def tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9\-]{2,}", ascii_fold(text).lower()) if w not in STOPWORDS]


def assign_topics(nodes: list[dict], pubs: dict[str, dict], topics: list[dict],
                  pinned: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Topic of every publication, with how it was found: pinned in publications.toml, else most
    keyword hits (title counts 3x), else the `fallback` topic, else the topic with the most similar
    wording. Returns {publication id: (topic key, how)}."""
    keys = {t["key"] for t in topics}
    fallback = next((t["key"] for t in topics if t["fallback"]), None)
    result, open_nodes = {}, []
    for n in nodes:
        p = pubs[n["id"]]
        if pinned.get(n["id"]) in keys:
            result[n["id"]] = (pinned[n["id"]], "setting")
            continue
        title = " " + ascii_fold(p["title"]).lower()
        abstract = " " + ascii_fold(n.get("abstract", "")).lower()
        best = max(((3 * keyword_hits(title, t["keywords"]) + keyword_hits(abstract, t["keywords"]),
                     keyword_hits(title, t["keywords"]), -i, t["key"]) for i, t in enumerate(topics)),
                   default=(0, 0, 0, ""))
        if best[0] > 0:
            result[n["id"]] = (best[3], "keywords")
        elif fallback:
            result[n["id"]] = (fallback, "fallback")
        else:
            open_nodes.append(n)
    if not open_nodes:
        return result
    # TF-IDF similarity to the publications already in each topic
    docs = {n["id"]: tokens(pubs[n["id"]]["title"]) * 2 + tokens(n.get("abstract", "")) for n in nodes}
    df = Counter(w for d in docs.values() for w in set(d))
    idf = {w: math.log(len(docs) / c) for w, c in df.items()}

    def vec(words):
        v = Counter(words)
        return {w: c * idf[w] for w, c in v.items()}

    def cos(a, b):
        dot = sum(a[w] * b.get(w, 0) for w in a)
        na, nb = math.sqrt(sum(x * x for x in a.values())), math.sqrt(sum(x * x for x in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    centroids = {}
    for t in topics:
        words = [w for pid, (key, _) in result.items() if key == t["key"] for w in docs[pid]]
        if words:
            centroids[t["key"]] = vec(words)
    for n in open_nodes:
        v = vec(docs[n["id"]])
        score, key = max(((cos(v, c), k) for k, c in centroids.items()), default=(0.0, ""))
        result[n["id"]] = (key, "similarity") if score > 0.02 else (OTHER["key"], "none")
    return result


def ring_order(topic_keys: list[str], links: list[dict], topic_of: dict[str, str]) -> dict:
    """Arrangement of the topic clusters: the best-connected topic in the middle (from five topics
    on), the others around it so that topics with many links between them are neighbors."""
    weight = defaultdict(float)
    for l in links:
        a, b = topic_of.get(l["source"]), topic_of.get(l["target"])
        if a and b and a != b:
            weight[frozenset((a, b))] += 1.0 if l["kind"] == "cites" else 0.5
    if len(topic_keys) < 5:
        center, ring = None, list(topic_keys)
    else:
        center = max(topic_keys, key=lambda k: (sum(w for pair, w in weight.items() if k in pair), -topic_keys.index(k)))
        ring = [k for k in topic_keys if k != center]
    if len(ring) > 3:
        n = len(ring)

        def cost(order):
            pos = {k: i for i, k in enumerate(order)}
            return sum(w * min(abs(pos[a] - pos[b]), n - abs(pos[a] - pos[b]))
                       for pair, w in weight.items() for a, b in [tuple(pair)] if a in pos and b in pos)
        first, rest = ring[0], ring[1:]
        ring = min(([first, *perm] for perm in itertools.permutations(rest)), key=cost)
    return {"center": center, "ring": ring}


# ----------------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--offline", action="store_true", help="do not access the network")
    parser.add_argument("--refresh", action="store_true", help="forget cached abstracts and links")
    args = parser.parse_args()

    curation = read_curation()
    if curation.get("contact_email"):
        up.USER_AGENT += f" (mailto:{curation['contact_email']})"
    map_cfg = curation.get("map", {})
    settings = {**SETTINGS, **{k: v for k, v in map_cfg.items() if not isinstance(v, list)}}
    if not settings["enabled"]:
        log("Publication map disabled ([map] enabled = false)")
        return
    groupings = []
    for key, label, field in GROUPINGS:
        entries = map_cfg.get(key) or (map_cfg.get("topic", []) if key == "methods" else [])  # [[map.topic]]: older name
        topics = read_topics(entries, key)
        if topics:
            groupings.append({"key": key, "name": label, "field": field, "topics": topics})
    if not groupings:
        sys.exit("publications.toml: add topics as [[map.methods]] (and [[map.applications]])")
    papers = map_cfg.get("paper", [])

    members = read_members()
    all_pubs = json.loads(PUBLICATIONS_FILE.read_text(encoding="utf-8"))["publications"]
    pubs = {p["id"]: p for p in all_pubs if in_group_list(p, members) and not paper_settings(p, papers).get("hide")}
    previous = {}
    if OUTPUT_FILE.exists() and not args.refresh:
        previous = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    old_nodes = {n["id"]: n for n in previous.get("nodes", [])}

    # Lookup tables for matching references to the group's publications
    by_doi = {d: pid for pid, p in pubs.items() for d in doi_aliases(p)}
    by_title = {norm_title(p["title"]): pid for pid, p in pubs.items() if len(norm_title(p["title"])) >= 25}

    def match_text(text: str) -> str | None:
        t = norm_title(text or "")
        return next((pid for key, pid in by_title.items() if key in t), None) if len(t) >= 25 else None

    nodes, refs, cites = [], {}, set()
    for pid, p in pubs.items():
        old = old_nodes.get(pid, {})
        cfg = paper_settings(p, papers)
        node = {"id": pid, "cited_by": old.get("cited_by", 0), "openalex": old.get("openalex", [])}
        abstract, source = old.get("abstract", ""), old.get("abstract_source", "")
        if not args.offline:
            log(f"- {p['title'][:80]}")
            works = fetch_openalex(p)
            node["openalex"] = [w["id"].rsplit("/", 1)[-1] for w in works]
            refs[pid] = {r.rsplit("/", 1)[-1] for w in works for r in w.get("referenced_works") or []}
            if works:
                node["cited_by"] = max(w.get("cited_by_count") or 0 for w in works)
            for ref in fetch_crossref_references(p):
                target = by_doi.get(norm_doi(ref.get("DOI"))) or match_text(
                    " ".join(str(ref.get(k, "")) for k in ("article-title", "unstructured", "volume-title")))
                if target and target != pid:
                    cites.add((pid, target))
            s2 = {}
            if not works:
                s2 = fetch_semantic_scholar(p)
                node["cited_by"] = max(node["cited_by"], s2.get("citationCount") or 0)
                for ref in s2.get("references") or []:
                    ext = ref.get("externalIds") or {}
                    target = (by_doi.get(norm_doi(ext.get("DOI"))) or by_doi.get(f"10.48550/arxiv.{ext.get('ArXiv', '')}".lower())
                              or match_text(ref.get("title", "")))
                    if target and target != pid:
                        cites.add((pid, target))
            candidates = [(lambda w=w: openalex_abstract(w), "OpenAlex") for w in works] + [
                (lambda: from_crossref(p), "Crossref"),
                (lambda: fetch_arxiv_abstract(arxiv_id(p)) if arxiv_id(p) else "", "arXiv"),
                (lambda: (s2 or fetch_semantic_scholar(p)).get("abstract"), "Semantic Scholar")]
            for fetch, name in candidates:
                if len(abstract) >= MIN_ABSTRACT:
                    break
                abstract, source = tidy_abstract(fetch() or ""), name
        if cfg.get("abstract"):
            abstract, source = cfg["abstract"], "publications.toml"
        abstract = tidy_abstract(abstract)
        if len(abstract) >= MIN_ABSTRACT or cfg.get("abstract"):
            node["abstract"], node["abstract_source"] = abstract, source
        else:
            log(f"  no abstract found: {p['title'][:80]}")
        for target in cfg.get("cites", []):
            t = by_doi.get(norm_doi(target)) or by_title.get(norm_title(target))
            if t and t != pid:
                cites.add((pid, t))
            else:
                log(f"  warning: [[map.paper]] cites {target!r}: not a publication of the group")
        nodes.append(node)

    # Links: citations (either direction counts once), then publications sharing references
    by_openalex = {oa: n["id"] for n in nodes for oa in n["openalex"]}
    for pid, rs in refs.items():
        cites.update((pid, by_openalex[r]) for r in rs if by_openalex.get(r, pid) != pid)
    links, linked = [], set()
    for a, b in sorted(cites):
        if frozenset((a, b)) not in linked:
            links.append({"source": a, "target": b, "kind": "cites"})
            linked.add(frozenset((a, b)))
    for a, b in itertools.combinations(sorted(refs), 2):
        shared = len(refs[a] & refs[b])
        if shared >= settings["related_min_shared"] and frozenset((a, b)) not in linked:
            links.append({"source": a, "target": b, "kind": "related", "shared": shared})
            linked.add(frozenset((a, b)))
    for l in previous.get("links", []):  # keep links found earlier (sources can be temporarily unreachable)
        pair = frozenset((l["source"], l["target"]))
        if l["source"] in pubs and l["target"] in pubs and pair not in linked:
            if l["kind"] == "cites" or args.offline:
                links.append(l)
                linked.add(pair)

    # Topics: one per grouping (methods, applications)
    out_groupings = []
    for g in groupings:
        pinned = {}
        for pid, p in pubs.items():
            cfg = paper_settings(p, papers)
            name = cfg.get(g["field"]) or (cfg.get("topic") if g["key"] == "methods" else None)
            if name:
                match = next((t["key"] for t in g["topics"] if slug(name) == t["key"]), None)
                if match:
                    pinned[pid] = match
                else:
                    log(f"  warning: [[map.paper]] {g['field']} = {name!r} is not a [[map.{g['key']}]] name")
        assigned = assign_topics(nodes, pubs, g["topics"], pinned)
        for n in nodes:
            n.setdefault("topics", {})[g["key"]], n.setdefault("assigned", {})[g["key"]] = assigned[n["id"]]
        used = Counter(key for key, _ in assigned.values())
        topics = [{"key": t["key"], "name": t["name"], "color": t["color"], "count": used[t["key"]]}
                  for t in g["topics"] if used[t["key"]]]
        if used[OTHER["key"]]:
            topics.append({**OTHER, "count": used[OTHER["key"]]})
        layout = ring_order([t["key"] for t in topics], links, {pid: key for pid, (key, _) in assigned.items()})
        out_groupings.append({"key": g["key"], "name": g["name"], "topics": topics, "layout": layout})

    nodes.sort(key=lambda n: (str(pubs[n["id"]].get("date") or pubs[n["id"]].get("year") or ""), n["id"]), reverse=True)
    links.sort(key=lambda l: (l["kind"], l["source"], l["target"]))
    data = {
        "_comment": "Generated by scripts/update_publication_map.py; topics and settings: [map] in publications.toml",
        "updated": previous.get("updated", "") if args.offline else date.today().isoformat(),
        "groupings": out_groupings,
        "nodes": nodes,
        "links": links,
    }
    OUTPUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    log(f"\n{len(nodes)} publications, {sum(l['kind'] == 'cites' for l in links)} citation links, "
        f"{sum(l['kind'] == 'related' for l in links)} related links -> {OUTPUT_FILE.relative_to(ROOT)}")
    for g in out_groupings:
        log(f"{g['name']}:")
        for t in g["topics"]:
            log(f"  {t['name']}: {t['count']}")
            for n in nodes:
                if n["topics"][g["key"]] == t["key"] and n["assigned"][g["key"]] != "keywords":
                    log(f"    ({n['assigned'][g['key']]}) {pubs[n['id']]['title'][:70]}")
    missing = [pubs[n["id"]]["title"][:70] for n in nodes if not n.get("abstract")]
    if missing:
        log(f"  {len(missing)} without abstract (add `abstract` in a [[map.paper]] entry): " + "; ".join(missing))


if __name__ == "__main__":
    main()
