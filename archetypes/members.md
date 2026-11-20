+++
title = "{{ replace .File.ContentBaseName "-" " " | title }}"
prefix = ""                     # e.g. "Dr." or "Prof. Dr.", shown before the name
suffix = "M.Sc."                # e.g. "M.Sc.", shown after the name
position = "Research associate"
group = "researcher"            # chair | lead | postdoc | researcher | phd | staff | student
weight = 10

email = ""
phone = ""
office = ""
orcid = ""                      # publications are fetched automatically from ORCID
scholar = ""
github = ""
linkedin = ""
website = ""

interests = []
joined = {{ now.Format "2006-01-02" }}           # first day in the group; an exact date creates a welcome news item
# left = 2029-09-30             # last day; afterwards listed under "Former members", with a farewell news item
# now = ""                      # after leaving, e.g. "Research engineer at Example GmbH"
+++

A short research statement (two or three paragraphs).
