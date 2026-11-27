# Website manual

How to edit and maintain the website of the Scientific Machine Learning Research Group. For an
overview of the repository and the license, see [README.md](README.md).

The website is built with [Hugo](https://gohugo.io) and hosted on GitHub Pages.
All content lives in Markdown and TOML files. Edit a file, commit it, and the site redeploys
within about a minute. You can do this directly in the GitHub web editor; no local setup is needed.

The site loads no external fonts, scripts or trackers. Embedded YouTube videos are loaded only
after a visitor clicks play.

## Where things live

| What | Where |
| --- | --- |
| Home page text, research focus, hero | `content/_index.md` |
| Rotating words in the home page title | `data/hero_words.toml` (list, singular words that take "meets", seconds per word) |
| Publication map (home page) | automatic, topics in the `[map]` section of `publications.toml` |
| Group photo | `content/group-photo.jpg` (any `group-photo.*` works; shown instead of the map with `publicationMap = false` in `content/_index.md`) |
| Members | `content/members/<name>/index.md` (+ optional `photo.jpg`) |
| Projects | `content/projects/<name>/index.md` (+ optional `cover.jpg`) |
| News | `content/news/<date>-<title>.md` |
| Awards | `content/awards/<date>-<name>.md` (shown on the members' pages; news created automatically) |
| Workshops | `content/workshops/<name>.md` (all on one page, newest first) |
| Software | `data/software.toml` (GitHub stars are fetched automatically) |
| Publications | automatic from ORCID, corrections in `publications.toml` |
| Join us, contact, imprint, privacy | `content/join.md`, `content/contact.md`, ... |
| Site name, address, menu, member groups | `hugo.toml` |
| Colors | `--accent` at the top of `assets/css/main.css` |
| Logo | `static/logo/` (SVG + PNG exports, shown via `layouts/_partials/logo.html`); favicons `static/favicon.svg`, `static/favicon.ico`, `static/apple-touch-icon.png` |
| Chair logo (AuxMe, right of the header) | `static/chair/` (SVG wordmark + "X" mark for phones, from `M:\01_Vorlagen\11_Logo` with the text converted to outlines); file names and link in `hugo.toml` (`chairLogo`, `chairIcon`, `chairURL`) |

## Everyday tasks

### Add a member

1. Create the folder `content/members/firstname-lastname/`.
2. Add `index.md`; copy an existing member's file as a template.
3. Optional: add a square-ish portrait as `photo.jpg` in the same folder. It is cropped to a square
   and resized automatically. Without a photo, the person's initials are shown.
4. Set `orcid` so the member's publications appear automatically.

| Field | Meaning |
| --- | --- |
| `title` | Full name |
| `prefix` | Academic title shown before the name, e.g. `Dr.` |
| `suffix` | Degree shown after the name, e.g. `M.Sc.` |
| `position` | Shown below the name, e.g. `Research associate` |
| `group` | Section on the members page: `chair`, `lead`, `postdoc`, `researcher`, `phd`, `staff`, `student` (labels and order in `hugo.toml`). Keep it when the person leaves: `left` moves them to "Former members". |
| `weight` | Order within the section (smaller comes first) |
| `email`, `phone`, `office`, `website` | Contact details (all optional) |
| `orcid`, `scholar`, `github`, `linkedin` | Profile links: ORCID iD, Google Scholar user id, GitHub user name (each also works as the full profile URL), LinkedIn URL |
| `interests` | Keywords, the first three are shown on the member card |
| `joined`, `left` | First and last day in the group: an exact date (`2026-05-01`, no quotes) or just a year (`2022`). See below. |
| `now` | After leaving: current position, e.g. `"Research engineer at Example GmbH"` |
| `news`, `welcome`, `farewell` | `news = false` switches off the welcome and farewell news; `welcome`/`farewell` replace their generated text |
| `name_variants` | Other spellings of the name in author lists, e.g. `["J. Doe"]` |
| `group_publications` | `false` lists this person's papers group-wide only when a group member co-authored them (used for the head of chair) |

The text below the front matter is the research statement. Math works: `$f_\theta(x)$`.

### Joining and leaving

The dates `joined` and `left` control the members page and the news feed automatically:

- **Members page:** a new member appears on the day given in `joined`. After the day given in
  `left`, the person moves to "Former members", with the years of membership (and `now`, if
  given). Their page and publications stay online. Keep `group` as it was, and remove contact
  details that are no longer valid, such as the office. If only the year (or month) of leaving
  is known, e.g. `left = 2026`, the person counts as former from the beginning of that year (or
  month); to prepare a departure in advance, use the exact last day.
- **News:** on the `joined` date, a news item "Welcome, …!" appears with the position and the
  first two `interests`; on the `left` date, "Farewell, …!" with the time in the group and `now`.
  This needs an exact date; with only a year, no news is created. The texts are ordinary files in
  `content/news/` and can be edited afterwards. Events more than 60 days in the past are not
  announced, so adding dates for former members later does not fill the news feed.
- **Publications:** the group-wide list only counts a member's papers from the years between
  `joined` and `left`.

Dates can be entered in advance. The site is rebuilt every morning, so the members page changes on
the exact day. The news items are written by the weekly *Content update* and published once its pull
request is reviewed and merged (see [Automatic content updates](#automatic-content-updates)); they
are dated on the day of the event. `data/announced_members.json` records what has been announced.
To preview the news locally without writing files:

```bash
python scripts/create_member_news.py --dry-run
```

### Add a project

Create `content/projects/<short-name>/index.md` (copy an existing project) and add a cover image
`cover.jpg` (landscape, ideally 16:9). `funding` is `public` or `internal`. `members` lists member
folder names; the build fails with a clear message if one does not exist. `start` and `end` are a
year (`2026`) or a month (`"2026-07"`, with quotes). Projects whose `end` has passed are shown as
completed and no longer appear under "Current projects" on the home page.

### Add news

Create `content/news/2026-11-18-short-title.md` with `title`, `date` and one or two sentences.
The three newest items appear on the home page.

### Add an award

Create `content/awards/2026-11-20-short-name.md` (copy an existing one, or run
`hugo new content awards/2026-11-20-short-name.md`). Awards have no page of their own: each award
is listed on the pages of its `members`, newest first, from its `date` on.

| Field | Meaning |
| --- | --- |
| `title` | Name of the award (in English), e.g. `Best Paper Award` |
| `origtitle` | Original name, if it is not English; shown in grey under the title on the member pages |
| `date` | Day of the award, e.g. `2026-11-20` |
| `members` | Member folder names, e.g. `["tobias-thummerer", "yi-zhang"]` |
| `by` | Who gives the award, as it reads after "from", e.g. `"the Example Conference 2026"` (Markdown, links allowed) |
| `reason` | What it is for, as it reads after "for", e.g. `"the paper *Title*"` (Markdown, links allowed) |
| `link` | Optional page about the award |
| `news`, `news_title` | `news = false` creates no news item; `news_title` replaces the generated title |

**News:** the weekly *Content update* proposes a news item for each new award, e.g. "Yi Zhang and
Andreas Hofmann received the *Best Paper Award* from the Example Conference 2026 for the paper
*Title*. Congratulations!" Text below the front matter of the award replaces this sentence. The
news item is an ordinary file in `content/news/` and can be edited afterwards. Awards whose date is
more than 60 days in the past when they are added are not announced. `data/announced_awards.json`
records what has been announced; a news item written by hand counts as well if its front matter
has `award = "<file name of the award>"`. Preview without writing files:
`python scripts/create_award_news.py --dry-run`.

### Add a workshop

Create `content/workshops/<short-name>.md` (copy an existing one, or run
`hugo new content workshops/<short-name>.md`). All workshops are shown on the workshops page,
newest first; link to one with `/workshops/#<short-name>`. Workshops that have not ended yet are
marked as upcoming.

| Field | Meaning |
| --- | --- |
| `title`, `event`, `format` | Title of the workshop, the conference or event, and a label such as `Hands-on workshop` |
| `start`, `end` | First and last day, e.g. `2026-09-22` (`end` only for workshops over several days) |
| `location` | Place |
| `role`, `people`, `guests` | e.g. `role = "Organized by"`, member folder names, and other people by name |
| `youtube` | YouTube video ID, the part after `watch?v=` in the video URL |
| `[[links]]` | Buttons with `label` and `url`, e.g. workshop website, materials, program |

The text below the front matter is the description.

Videos are privacy-friendly: the preview image is downloaded from YouTube when the site is built.
The player is loaded from youtube-nocookie.com only after a click. The same works in any
Markdown page with `{{</* youtube VIDEO_ID */>}}`. The privacy page has a matching section on YouTube.

### Publications

Publications are **not** maintained by hand. Once a week, the workflow *Content update*
runs `scripts/update_publications.py`, which

1. reads the ORCID iD of every member,
2. downloads their public works from ORCID,
3. completes authors, venue and type through the DOI (Crossref, DataCite/arXiv, ...),
4. merges duplicates (co-authored papers appear once; a preprint becomes a link on its published version),
5. writes `data/publications.json`, which is then proposed for review in a pull request
   (see [Automatic content updates](#automatic-content-updates)).

Members keep their ORCID record up to date, ideally with Crossref auto-update switched on in ORCID,
and the website follows. Co-authored papers appear once in the group list and on each author's page.

To fix things, edit `publications.toml`:

- `exclude`: hide a publication (DOI or exact title)
- `[[override]]`: add a code or PDF link, an award note, or fix the type or venue of a publication;
  with `title` and `doi`, add a missing DOI (authors, venue and link are then completed automatically)
- `[[manual]]`: add a publication that is not on ORCID

To update right away: *Actions → Content update → Run workflow*.

Only papers with at least one group member (in the group during that year) are listed group-wide.
Papers of the head of chair (`group_publications = false`) count only when co-authored by a group
member; all of that person's papers still appear on their own member page.

### News for new publications

After fetching publications, the content update runs `scripts/create_publication_news.py`. For every
new publication in the group list, it writes a news item to `content/news/` naming the member
authors, the title and venue, with a one- or two-sentence summary of the abstract:

- With the repository secret `ANTHROPIC_API_KEY` (*Settings → Secrets and variables → Actions*),
  Claude writes the summary from the abstract (model `claude-opus-5-5`; a few cents per paper).
- Without it, the summary is the TLDR from Semantic Scholar or the key sentence of the abstract.

Generated news items are ordinary Markdown files: edit or delete them like any other news.
`data/announced_publications.json` records what was announced, so nothing is announced twice.
Settings (publication types, maximum age, maximum items per week) are in the `[news]` section of
`publications.toml`. Theses are not announced automatically. To preview locally without writing files:

```bash
python scripts/create_publication_news.py --dry-run
```

After adding new members' ORCID iDs, `--backfill` also announces their publications from the last year
(within `max_age_days`), dated at the publication date:

```bash
python scripts/create_publication_news.py --backfill
```

### Publication map

Below the introduction, the home page shows an interactive map of the group's publications
(the same publications as the group list):

- Each circle is a publication, sized by its number of citations and colored by its topic.
- A switch above the map groups the publications by **applications** (shown first) or by **methods**.
  The circles then move to their clusters in the other grouping.
- Solid lines connect publications where one cites the other. Dashed lines connect publications
  that share at least `related_min_shared` references.
- Hovering over a circle, focusing it with the keyboard or tapping it on a phone shows the title,
  authors, venue and abstract. Member names link to their pages and other authors to their ORCID profile.
- The topic chips below the map highlight one topic.

Every week, the *Content update* also runs `scripts/update_publication_map.py`. It fetches the
reference lists and citation counts from OpenAlex and Crossref, and abstracts from OpenAlex, Crossref,
arXiv or Semantic Scholar, and writes `data/publication_map.json`. Titles, authors and links come
from `data/publications.json` when the site is built, so a new publication appears on the map once
the content update that found it is merged. Refreshed citation counts alone do not open a pull
request; they are included with the next real change. To update right away:
*Actions → Content update → Run workflow*.

Topics are set in the `[map]` section of `publications.toml`: `[[map.applications]]` for the
application grouping and `[[map.methods]]` for the method grouping. Topic names appear on the map
exactly as written there (Title Case). Each topic has a name and keywords;
each grouping has at most six topics with the default colors. In each grouping, every publication gets
the topic whose keywords appear most often in its title (counts three times) and abstract. Publications
without any application keyword go to the gray `fallback` topic ("General Methods"). When the script
runs, it prints how each publication was assigned. `[[map.paper]]` entries can:

- pin a publication's `method` or `application`,
- add an `abstract` where none was found,
- add citations the databases miss (`cites`),
- remove a publication from the map (`hide = true`).
After editing topics, re-apply them without network access:

```bash
python scripts/update_publication_map.py --offline
```

### Software

Add a `[[package]]` block to `data/software.toml` with `name`, `description`, `repo`, `docs` and `tags`.
For GitHub repositories, `scripts/update_github_stars.py` fetches the current star counts every
time the site is built (every morning and after every change). The software page shows them with a
star icon and sorts the packages by stars (most first). The numbers in `data/github_stars.json` are
only used when GitHub cannot be reached; they are not committed automatically. To fetch them locally:

```bash
python scripts/update_github_stars.py
```

## Automatic content updates

Every Monday, the workflow *Content update* (`.github/workflows/content-update.yml`) collects
everything that changed in the meantime:

- new, updated or removed publications from the members' ORCID records,
- news items for new publications, for members who joined or left, and for new awards,
- the publication map on the home page.

If it finds anything new, it opens a **pull request** with these changes and an **issue** that asks
for a review; nothing is published before the pull request is merged. The description of the pull
request summarizes the changes by category (new publications, updated publications, news feed
items by kind, changes to the publication map), with a link to every new news item.

To review:

1. Open the pull request from the issue (or the *Pull requests* tab) and read the summary. The
   *Files changed* tab shows every change in detail.
2. To change a news item, open it from the summary and click the pencil icon (*Edit this file*);
   commit to the same branch (`content-update`). To drop a news item, delete its file the same way.
3. Merge the pull request. The site is rebuilt and published within a few minutes, and the issue
   is closed.

While a pull request is open, later runs add their changes to it (your edits stay), and the summary
is updated. Closing a pull request without merging discards its changes, and they are proposed again
in the next run; to drop something for good, delete it in the pull request and merge. The site is
also rebuilt every morning without review, so that date-dependent content stays current; this
changes no files.

## Local preview (optional)

Install Hugo (extended edition, v0.156 or newer) and run the server:

```bash
winget install Hugo.Hugo.Extended
```

```bash
hugo server
```

Then open the address Hugo prints (<http://localhost:1313/SciML/>, following the `baseURL` in
`hugo.toml`). Pages reload as you edit. To refresh publications locally
(Python 3.11+, no packages needed):

```bash
python scripts/update_publications.py
```

DOI metadata is cached in `data/publications.json`; add `--refresh` to look up every DOI again
(e.g. after removing an override), or `--offline` to only re-apply `publications.toml`.

New pages can also be created from templates, e.g. `hugo new content members/jane-doe/index.md`.

## One-time setup on GitHub

1. Push this repository to GitHub (for example `your-org/website`).
2. *Settings → Pages → Build and deployment → Source*: select **GitHub Actions**.
3. Push to `main` (or run *Actions → Deploy site*). The site appears at
   `https://<org>.github.io/<repo>/`. The base URL is set automatically.
4. *Settings → Actions → General → Workflow permissions*: check **Allow GitHub Actions to create
   and approve pull requests**, so that the weekly content update can open its pull request.
5. Optional: under *Settings → Secrets and variables → Actions → Variables*, add the variable
   `CONTENT_REVIEWERS` with the GitHub user names of the reviewers, separated by commas. They are
   assigned to each review issue and asked to review the pull request.
6. Run *Actions → Content update* once after adding ORCID iDs.
7. Optional: set a custom domain such as `sciml.your-university.de` under *Settings → Pages*.
   Your university's IT department has to add a DNS CNAME record for it.

Note: GitHub pauses scheduled workflows in repositories without activity for 60 days. If that
happens, GitHub shows a banner on the Actions tab; one click re-enables the workflow.

## Before going live

- Replace all placeholder content (members, projects, news, `publications.toml`).
- **Imprint and privacy policy**: required for German websites. Ask your university for its standard texts.
  Keep the section on YouTube videos (anchor `#youtube`, linked below every video) in the final privacy policy.
- Check whether your university requires a link to, or a mention on, its official website.
