+++
title = "{{ replace .File.ContentBaseName "-" " " | title }}"
prefix = ""                     # e.g. "Dr." or "Prof. Dr.", shown before the name
suffix = "M.Sc."                # e.g. "M.Sc.", shown after the name
position = "Research associate"
group = "researcher"            # chair | lead | postdoc | researcher | phd | staff | student | alumni
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
joined = {{ now.Year }}
+++

A short research statement (two or three paragraphs).
