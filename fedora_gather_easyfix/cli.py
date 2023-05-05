import argparse
import logging
import tomllib

from .cache import cache
from .output import generate_output
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

    cache.configure(**config["cache"])
    project_groups = get_projects(config)
    # Filter out groups where no project has a ticket
    project_groups = {
        groupname: projects
        for groupname, projects in project_groups.items()
        if sum(len(p.tickets) for p in projects) > 0
    }

    # print("Gathering Bugzilla tickets")
    # bz_gatherer = BugzillaGatherer(config)
    # bz_components = bz_gatherer.get_components()

    # generate_output(config, project_groups, bz_components)
    generate_output(config, project_groups, {})
