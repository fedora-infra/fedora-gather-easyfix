import argparse
import logging
import tomllib

# import vcr
from .cache import cache
from .output import Generator
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

    # with vcr.use_cassette("cassette.yml"):
    #     project_groups = get_projects(config)
    project_groups = get_projects(config)

    # print("Gathering Bugzilla tickets")
    # bz_gatherer = BugzillaGatherer(config)
    # bz_components = bz_gatherer.get_components()

    # generate_output(config, project_groups, bz_components)
    generator = Generator(config)
    generator.copy_static()
    generator.generate_output(project_groups, {})
    generator.generate_ci_output(project_groups)
