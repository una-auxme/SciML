+++
title = "{{ replace .File.ContentBaseName "-" " " | title }}"
acronym = ""
funding = "public"              # public | internal
funder = ""
grant = ""
start = "{{ now.Format "2006-01" }}"         # year (2026) or month ("2026-07")
end = "{{ (now.AddDate 3 0 0).Format "2006-01" }}"
summary = "One or two sentences for the project card."
members = []                    # folder names in content/members/
partners = []
website = ""
weight = 10
+++

Describe the project here. Put a cover image named cover.jpg into this folder.
