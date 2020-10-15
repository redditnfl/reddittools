#!/usr/bin/env python
import argparse
import sys
import traceback
from pathlib import Path
from pprint import pprint
from typing import TextIO, List

import csv
import yaml
from praw import Reddit
from praw.exceptions import ClientException
from praw.models import Subreddit

from redditnfl.reddittools.reddittoken import ensure_scopes

FLAIR_FIELD_NAMES = ['user', 'flair_text', 'flair_css_class']


def yaml_file_type(filename):
    with open(filename) as fp:
        return yaml.load(fp, Loader=yaml.SafeLoader)


def dir_path_type(must_exist=True, create=False, mode=0o777):
    def f(path):
        p = Path(path)
        if not p.is_dir():
            if must_exist:
                raise argparse.ArgumentError("Path %s does not exist" % path)
            elif create:
                try:
                    p.mkdir(parents=True, mode=mode)
                except Exception as e:
                    raise argparse.ArgumentError("Could not create path %s" % path) from e
        return p

    return f


class Command:
    def setup_argparse(self, sp: argparse.ArgumentParser):
        raise NotImplementedError("Not Implemented")

    def run(self, sr: Subreddit, args):
        raise NotImplementedError("Not implemented")


class Dump(Command):
    def setup_argparse(self, sp: argparse.ArgumentParser):
        sp.add_argument('outfile', nargs='?', type=argparse.FileType('w', encoding="UTF-8"), default=sys.stdout)

    def run(self, sr: Subreddit, args):
        self.dump_flair(sr, args.outfile)

    @staticmethod
    def dump_flair(sr: Subreddit, outfile: TextIO):
        writer = csv.DictWriter(outfile, FLAIR_FIELD_NAMES, extrasaction='ignore')
        writer.writeheader()
        for user in sr.flair():
            user['username'] = user['user'].name
            writer.writerow(user)


class SetTemplates(Command):
    def setup_argparse(self, sp: argparse.ArgumentParser):
        sp.add_argument('flairconfig', help='Config file detailing flair', type=yaml_file_type)
        sp.add_argument('emojidir', type=dir_path_type(), help="Directory containing emoji images")

    def run(self, sr: Subreddit, args):
        self.clear_templates(sr, args.dry_run)
        self.create_templates(sr, args.flairconfig, args.emojidir, args.dry_run)
        if args.verbose:
            self.dump_templates(sr)

    @staticmethod
    def dump_templates(sr: Subreddit):
        from pprint import pprint
        pprint(list(sr.flair.templates))

    def create_templates(self, sr: Subreddit, flairconfig: List, emoji_dir: Path, dry_run=False):
        for flair in flairconfig:
            emoji_file = emoji_dir / (flair['emoji'] + ".png")
            if not emoji_file.exists():
                raise Exception("File does not exist: %s" % emoji_file)
            print("Upload %s as :%s:" % (emoji_file, flair['emoji']))
            if not dry_run:
                sr.emoji.add(flair['emoji'], str(emoji_file))
            print("Create template class=<{class}>, text=<{text}>, emojis=<{emoji}>".format(**flair))
            if not dry_run:
                self.create_template(sr, flair['text'], flair['class'], [flair['emoji']], flair.get('mod_only', False))

    @staticmethod
    def create_template(sr: Subreddit, text: str, css_class: str, emojis: List[str],
                        mod_only: bool = True) -> str:
        """
        Create a flair template that fullfills the following criteria:
        * Only shows text on old reddit (no emoji)
        * Shows emoji + Text on new reddit

        :param sr: The subreddit to work on
        :param text: (Plain) Text for the flair
        :param css_class: CSS class
        :param emojis: Emojis to add in front
        :param mod_only: Whether to make the template mod_only (Default: True)
        :return: The created template
        """
        templates_before = [template['id'] for template in sr.flair.templates]
        # First we create an old-style template
        sr.flair.templates.add(text=text, css_class=css_class)
        # Find the id of the template we created
        new_template = list(filter(lambda t: t['id'] not in templates_before, sr.flair.templates))[0]
        # Then we update the text with the emojis in it on the new flair endpoint. This seems to be preferable.
        if emojis:
            # Prepend any emojis
            text = ":" + ("::".join(emojis)) + ": " + text
        sr.flair.templates.update(new_template['id'], mod_only=mod_only, text_editable=False,
                                  background_color='transparent', text=text, css_class=css_class)
        new_template = list(filter(lambda t: t['id'] not in templates_before, sr.flair.templates))[0]
        return new_template

    @staticmethod
    def create_template2(sr: Subreddit, text: str, css_class: str, emojis: List[str],
                        mod_only: bool = True) -> str:
        """
        Create a flair template that fullfills the following criteria:
        * Only shows text on old reddit (no emoji)
        * Shows emoji + Text on new reddit

        :param sr: The subreddit to work on
        :param text: (Plain) Text for the flair
        :param css_class: CSS class
        :param emojis: Emojis to add in front
        :param mod_only: Whether to make the template mod_only (Default: True)
        :return: The created template
        """
        templates_before = [template['id'] for template in sr.flair.templates]
        if emojis:
            # Prepend any emojis
            text = ":" + ("::".join(emojis)) + ": " + text
        sr.flair.templates.add(mod_only=mod_only, text_editable=False,
                               background_color='transparent', text=text, css_class=css_class)
        # Find the id of the template we created
        new_template = list(filter(lambda t: t['id'] not in templates_before, sr.flair.templates))[0]
        return new_template

    @staticmethod
    def clear_templates(sr: Subreddit, dry_run=False):
        print("Deleting all templates")
        if not dry_run:
            sr.flair.templates.clear()
        for emoji in sr.emoji:
            print("Delete emoji %s" % emoji)
            if not dry_run:
                emoji.delete()


class Clear(Command):
    def setup_argparse(self, sp: argparse.ArgumentParser):
        pass

    def run(self, sr: Subreddit, args):
        want_input = "Yes I am sure!"
        answer = input("This will delete ALL assigned flair in /r/{}!\n\nPlease type '{}' to confirm: ".format(sr.display_name, want_input))
        if answer == want_input:
            self.clear(sr, dry_run=args.dry_run)
        else:
            print("Aborting")

    @staticmethod
    def clear(sr: Subreddit, dry_run=False):
        if dry_run:
            print("Would delete all flair in /r/{}".format(sr.display_name))
        else:
            print("Deleting all flair in /r/{}".format(sr.display_name))
            sr.flair.delete_all()


class Upload(Command):
    def setup_argparse(self, sp: argparse.ArgumentParser):
        sp.add_argument('infile', nargs='?', type=argparse.FileType('r', encoding="UTF-8"), default=sys.stdin)

    def run(self, sr: Subreddit, args):
        self.upload(args.infile, sr, dry_run=args.dry_run)

    @staticmethod
    def upload(infile, sr: Subreddit, has_header=True, dry_run=False):
        if not has_header:
            fieldnames = FLAIR_FIELD_NAMES
        else:
            fieldnames = None
        reader = csv.DictReader(infile, fieldnames=fieldnames, restval='')
        if dry_run:
            for row in reader:
                pprint(row)
        else:
            sr.flair.update(reader)


COMMANDS = [Dump, Upload, Clear, SetTemplates]


class FlairTool:
    def __init__(self):
        parser = argparse.ArgumentParser(description="Flair swiss army knife")
        parser.add_argument('-s', '--site', dest='site', help="Reddit 'site' (praw.ini section) to use")
        parser.add_argument('-v', '--verbose', action="store_true", help="Log network requets")
        parser.add_argument('-n', '--dry-run', action="store_true", help="Prevent any action on reddit being taken "
                                                                         "(other side-effects are not prevented!)")
        parser.add_argument('sr_name', help="Name of subreddit to run on")

        sp = parser.add_subparsers(help="Flair command to run (%s)" % ", ".join([c.__name__ for c in COMMANDS]),
                                   dest='cmd', required=True, metavar='cmd')
        self.parser = parser
        self.commands = {}
        for CmdClass in COMMANDS:
            name = CmdClass.__name__
            cmd_parser = sp.add_parser(name)
            cmd = CmdClass()
            cmd.setup_argparse(cmd_parser)
            self.commands[name] = cmd

    def run(self):
        args = self.parser.parse_args()

        if args.verbose:
            import logging
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)
            for logger_name in ("praw", "prawcore"):
                logger = logging.getLogger(logger_name)
                logger.setLevel(logging.DEBUG)
                logger.addHandler(handler)

        try:
            r = Reddit(args.site)
            ensure_scopes(r, scopes=['read', 'flair', 'modflair', 'structuredstyles'])
        except ClientException:
            traceback.print_exc()
            sys.stderr.write("\n\nOh dear, something broke. Most likely you need to pass the --site "
                             "parameter, set the praw_site environment variable or configure a "
                             "DEFAULT site in your praw.ini\n\n")
            self.parser.print_help()
            sys.exit(1)

        sr = r.subreddit(args.sr_name)

        self.commands[args.cmd].run(sr, args)


def main():
    ft = FlairTool()
    ft.run()


if __name__ == '__main__':
    main()
