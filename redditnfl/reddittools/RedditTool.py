#!/usr/bin/env python
import logging
from os.path import basename
import argparse
import os
import praw
import sys
import warnings
from .reddittoken import ensure_scopes

class RedditTool(praw.Reddit):

    def __init__(self, site, *args, **kwargs):
        warnings.simplefilter("ignore", ResourceWarning)
        self.log = logging.getLogger(self.__class__.__name__)
        self.parse_args()
        level = logging.DEBUG if self.args.verbose else logging.INFO
        logging.basicConfig(format='[%(asctime)s] %(name)s (%(filename)s:%(lineno)d) %(levelname)s %(message)s', level=level)
        self.site = self.args.site or site
        super(RedditTool, self).__init__(self.site, *args, **kwargs)

    def arg_parser(self):
        self.argparser = argparse.ArgumentParser(prog=basename(sys.argv[0]), description="Reddit client script")
        self.argparser.add_argument('-s', '--site', default=os.getenv('REDDIT_SITE'))
        self.argparser.add_argument('-v', '--verbose', action='store_true')
        return self.argparser
    
    def parse_args(self):
        self.args = self.argparser.parse_args()

    def ensure_scopes(self, scopes=None):
        ensure_scopes(self, scopes)
