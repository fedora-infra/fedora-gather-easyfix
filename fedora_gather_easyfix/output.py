import os
from datetime import UTC, datetime, timedelta
from itertools import chain
from shutil import copytree

from jinja2 import Environment, PackageLoader


def is_older_than(dt, days):
    return dt < (datetime.now(tz=UTC) - timedelta(days=days))


class Generator:
    def __init__(self, config):
        self.config = config
        self.environment = Environment(
            autoescape=True, loader=PackageLoader("fedora_gather_easyfix")
        )
        self.environment.tests["older_than"] = is_older_than

    def _filter_empty_list(self, project_groups, attribute):
        return {
            groupname: projects
            for groupname, projects in project_groups.items()
            if sum(len(getattr(p, attribute, [])) for p in projects) > 0
        }

    def copy_static(self):
        copytree("static", os.path.join(self.config["output"], "static"), dirs_exist_ok=True)

    def generate_output(self, project_groups, bz_components):
        print("Generating output")
        # Filter out groups where no project has a ticket
        _project_groups = self._filter_empty_list(project_groups, "tickets")
        projects = chain(*_project_groups.values())
        bz_tickets = chain(*bz_components.values())

        template = self.environment.get_template("main.html")
        html = template.render(
            project_groups=_project_groups,
            bz_components=bz_components,
            ticket_num=sum(len(p.tickets) for p in projects),
            bz_num=len(list(bz_tickets)),
            now=datetime.now().strftime("%a %b %d %Y %H:%M"),
            config=self.config,
        )
        with open(os.path.join(self.config["output"], "index.html"), "w") as fh:
            fh.write(html)

    def generate_ci_output(self, project_groups):
        print("Generating CI output")
        # Filter out groups where no project has a workflow
        _project_groups = self._filter_empty_list(project_groups, "workflows")
        template = self.environment.get_template("ci-status.html")
        html = template.render(
            project_groups=_project_groups,
            now=datetime.now().strftime("%a %b %d %Y %H:%M"),
            config=self.config,
        )
        with open(os.path.join(self.config["output"], "ci-status.html"), "w") as fh:
            fh.write(html)
