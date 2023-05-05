import argparse
import datetime
import logging
import os
import tomllib
from itertools import chain
from shutil import copytree

from jinja2 import Template

from .cache import cache
from .gatherers import BugzillaGatherer
from .watch import get_projects


def parse_arguments():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("-c", "--config", default="config.toml", help="configuration file")
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
