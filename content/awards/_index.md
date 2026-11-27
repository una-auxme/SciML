+++
title = "Awards"

# Awards have no page of their own: each one is listed on the pages of the members who received it
# (field `members`), and a news item is created for it automatically (scripts/create_award_news.py).
[build]
  render = "never"
  list = "never"
[[cascade]]
  [cascade.build]
    render = "never"
    list = "always"
  [cascade.target]
    kind = "page"
+++
