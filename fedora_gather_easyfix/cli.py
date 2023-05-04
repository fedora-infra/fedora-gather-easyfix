#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
The idea of this program is to gather tickets from different project
which are marked as 'easyfix' (or any other keyword for that matter).

This version is a simple proof of concept, eventually it should be
converted to an html page and this script run by a cron job of some sort.

The different project to suscribe by email or a git repo or a page on
the wiki. To be sorted out...
"""

import argparse
import datetime
import logging
import os
from itertools import chain
from shutil import copytree

import tomllib
from jinja2 import Template

from .cache import cache
from .gatherers import BugzillaGatherer
from .watch import get_projects


def parse_arguments():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "-c", "--config", default="config.toml", help="configuration file"
    )
    return parser.parse_args()


def main():
    """For each projects which have suscribed in the correct place
    (fedoraproject wiki page), gather all the tickets containing the
    provided keyword.
    """

    args = parse_arguments()
    with open(args.config, "rb") as fh:
        config = tomllib.load(fh)

    logging.basicConfig()
    # logger.setLevel(logging.DEBUG)

    if not os.path.exists(config["template"]):
        print("Template not found")
        return 1

    cache.configure(**config["cache"])
    project_groups = get_projects(config)
    # Filter out groups where no project has a ticket
    project_groups = {
        groupname: projects
        for groupname, projects in project_groups.items()
        if sum(len(p.tickets) for p in projects) > 0
    }
    projects = chain(*project_groups.values())

    print("Gathering Bugzilla tickets")
    bz_gatherer = BugzillaGatherer(config)
    bz_components = bz_gatherer.get_components()
    bz_tickets = chain(*bz_components.values())

    copytree("static", os.path.join(config["output"], "static"), dirs_exist_ok=True)

    try:
        with open(config["template"]) as fh:
            template = Template(fh.read())
        html = template.render(
            project_groups=project_groups,
            bz_components=bz_components,
            ticket_num=sum(len(p.tickets) for p in projects),
            bz_num=len(list(bz_tickets)),
            date=datetime.datetime.now().strftime("%a %b %d %Y %H:%M"),
        )
        with open(os.path.join(config["output"], "index.html"), "w") as fh:
            fh.write(html)
    except OSError as err:
        print("ERROR: %s" % err)
