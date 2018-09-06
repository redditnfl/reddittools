#!/usr/bin/env python
from praw import Reddit

def run(reddit_session, submissions_subreddit, *args, **kwargs):
    site = kwargs.get('reddit_site', 'sidebarupdater-submissions')
    count = int(kwargs.get('submissions_count', 5))
    listing = kwargs.get('submissions_listing', 'hot')
    fmt = kwargs.get('submission_format', '* {s.title}\n')

    r = Reddit(site)

    sub = r.subreddit(submissions_subreddit)
    ret = ""
    for submission in sub.hot(limit=count):
        ret += fmt.format(s=submission)
    return ret
