import os
from datetime import UTC, datetime, timedelta
from itertools import chain
from shutil import copytree

from jinja2 import Environment, PackageLoader


def is_older_than(dt, days):
    return dt < (datetime.now(tz=UTC) - timedelta(days=days))


def generate_output(config, project_groups, bz_components):
    print("Generating output")

    projects = chain(*project_groups.values())
    bz_tickets = chain(*bz_components.values())

    copytree("static", os.path.join(config["output"], "static"), dirs_exist_ok=True)

    environment = Environment(autoescape=True, loader=PackageLoader("fedora_gather_easyfix"))
    environment.tests["older_than"] = is_older_than
    template = environment.get_template("main.html")
    html = template.render(
        project_groups=project_groups,
        bz_components=bz_components,
        ticket_num=sum(len(p.tickets) for p in projects),
        bz_num=len(list(bz_tickets)),
        now=datetime.now().strftime("%a %b %d %Y %H:%M"),
        config=config,
    )
    with open(os.path.join(config["output"], "index.html"), "w") as fh:
        fh.write(html)
