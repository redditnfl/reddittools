#!/usr/bin/env python
import os.path
import time
import re
import difflib
from configparser import ConfigParser
import sys
from redditnfl.reddittools import RedditTool
import logging
import importlib


class SidebarUpdater(RedditTool):
    MAX_EDIT_REASON_LENGTH = 256
    MAX_SIDEBAR_LENGTH = 10240
    PROGRAM = "sidebarupdater"
    VERSION = "0.1"
    UA = "%s/%s" % (PROGRAM, VERSION)
    WP = 'config/sidebar'

    def __init__(self, *args, **kwargs):
        self.arg_parser()
        self.argparser.add_argument("-n", "--dry-run", action="store_true", dest="dry_run")
        self.argparser.add_argument("subreddit")
        self.argparser.add_argument("config")
        super(SidebarUpdater, self).__init__(self.PROGRAM, user_agent = self.UA, *args, **kwargs)
        self.ensure_scopes('read,wikiread,wikiedit')
        self.subreddit = self.subreddit(self.args.subreddit)
        self.cfg = ConfigParser()
        self.cfg.read(self.args.config)
        self.log.info('Startup')

    def marker_replace(self, marker_start, marker_end, content, subject):
        replacement = "%s\n\n%s\n\n%s" % (marker_start, content, marker_end)
        return re.sub(r'(?ms)' + re.escape(marker_start) + '.*' + re.escape(marker_end), replacement, subject)

    def logdiff(self, before, sb, revision):
        diff = ""
        for line in difflib.unified_diff(before.split("\n"), sb.split("\n"), fromfile="previous_sidebar", tofile="new_sidebar", n=3, lineterm="", fromfiledate=str(revision), tofiledate=str(time.time())):
            diff += line + "\n"
        self.log.info("Sidebar diff:\n%s", diff)

    def get_sidebar(self):
        w = self.subreddit.wiki[self.WP]
        return w.revision_date, w.content_md

    def update_sidebar(self, sidebar, updated_plugins):
        reason = "Automatic update of: %s" % (", ".join(updated_plugins))
        try:
            reason = reason[:self.MAX_EDIT_REASON_LENGTH]
            r = self.subreddit.wiki[self.WP].edit(sidebar, reason=reason)
            self.log.debug("Edit result: %r", r)
        except Exception as e:
            self.log.exception("Error updating sidebar")


    def main(self):
        revision, sb = self.get_sidebar()
        before = sb
        updates = []
        self.log.debug(before)
        for title in self.cfg.sections():
            self.log.info("Handling %s", title)
            marker_start = self.cfg.get(title, 'marker_start').replace("CONFIGNAME", title)
            marker_end = self.cfg.get(title, 'marker_end').replace("CONFIGNAME", title)
            self.log.debug("Looking for start=<%s>, end=<%s>", marker_start, marker_end)
            if marker_start in sb and marker_end in sb:
                self.log.debug("Found")
                try:
                    output = self.run_plugin(self.cfg.get(title, 'plugin'), dict(self.cfg.items(title)))
                    sb_copy = sb
                    sb = self.marker_replace(marker_start, marker_end, output, sb)
                    if sb_copy != sb:
                        updates.append(title)
                except Exception as e:
                    self.log.exception("Error running plugin")
            else:
                self.log.debug("Not found")

        if len(sb) > self.MAX_SIDEBAR_LENGTH:
            self.log.warn("Sidebar too large %d>%d!" % (len(sb), self.MAX_SIDEBAR_LENGTH))
        else:
            self.log.debug("Sidebar size: %d chars" % len(sb))
        if before != sb:
            self.logdiff(before, sb, revision)
            self.update_sidebar(sb, updates)
        else:
            self.log.info("No changes")

    def run_plugin(self, name, config):
        self.log.debug("Run %s with config %r", name, config)
        plugin = importlib.import_module(name, package=__loader__.name)
        output = plugin.run(reddit_session = self, **config)
        self.log.debug("Output = %s", output)
        return output


def main():
    rc = SidebarUpdater()
    rc.main()
    rc.log.info('Complete')
