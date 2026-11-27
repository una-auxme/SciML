# SciML Research Group website

Website of the Scientific Machine Learning (SciML) Research Group at the
[Chair of Mechatronics (AuxMe)](https://www.uni-augsburg.de/en/fakultaet/fai/informatik/prof/imech/),
University of Augsburg: members, projects, publications, software, workshops and news.

How to edit content and maintain the site is described in [MANUAL.md](MANUAL.md).

## Building the site

The site is built with [Hugo](https://gohugo.io) (extended edition, v0.156 or newer). From the
repository root:

```bash
hugo server   # local preview with live reload
hugo          # build into public/
```

Pushing to `main` builds the site via GitHub Actions and publishes it to GitHub Pages. Further
workflows rebuild the site and announce new and departing members and new awards every day, update the
publication list, the news for new publications and the GitHub stars once a week, and the
publication map on the home page once a month.

## License

The **source code** in this repository is licensed under the MIT license, see [LICENSE](LICENSE).
This covers the Hugo templates (`layouts/`, `archetypes/`), stylesheets and scripts (`assets/`,
`scripts/`), the GitHub Actions workflows, the configuration files, the Markdown and TOML content
written by the group, and the project illustrations `content/projects/*/cover.svg` (except as
noted below).

The following files are **not** covered by the MIT license and may not be reused without
permission of the respective rights holders:

| File | Rights |
|------|--------|
| `static/chair/auxme-logo.svg`, `static/chair/auxme-icon.svg` | Logo of the Chair of Mechatronics (AuxMe), all rights reserved |
| `static/logo/*`, `static/favicon.svg`, `static/favicon.ico`, `static/apple-touch-icon.png` | Logo of the SciML Research Group, all rights reserved |
| `content/members/*/photo.jpg` | Portrait photographs, all rights reserved |
| `content/projects/juliafmi/cover.svg` | Contains the logo of [FMI.jl](https://github.com/JuliaFMI/FMI.jl), © the JuliaFMI developers |

**Third-party content.** The abstracts in `data/publication_map.json` are quoted from the respective
publications; their copyright remains with the authors and publishers. The publication metadata in
`data/publications.json` and `data/publication_map.json` is collected from public databases
([ORCID](https://orcid.org), [Crossref](https://www.crossref.org), [DataCite](https://datacite.org),
[OpenAlex](https://openalex.org)). Names and trademarks of third parties (for example funding
programs, conferences and software projects) belong to their respective owners.

The YouTube preview images and videos on the workshops page are not part of this repository: the
preview images are downloaded from YouTube when the site is built, and the videos are loaded from
YouTube only when a visitor plays them.
