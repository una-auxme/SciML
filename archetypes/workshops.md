+++
title = "{{ replace .File.ContentBaseName "-" " " | title }}"
event = "Name of the conference or event"
format = "Hands-on workshop"    # e.g. Hands-on workshop, Organized workshop, Tutorial
start = {{ now.Format "2006-01-02" }}
# end = {{ now.Format "2006-01-02" }}    # last day, for workshops over several days
location = "City, Country"
role = "Given by"               # label for the people below, e.g. "Organized by"
people = []                     # folder names in content/members/
guests = []                     # other people, by name
youtube = ""                    # YouTube video ID (the part after watch?v=); loads only after a click

[[links]]
  label = "Workshop website"
  url = ""
+++

One paragraph about the workshop.
