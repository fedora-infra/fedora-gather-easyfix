#!/usr/bin/env python -tt
# -*- coding: utf-8 -*-

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
import re
from collections import defaultdict
from dataclasses import dataclass, field
from importlib import metadata
from itertools import chain
from shutil import copytree
from urllib.parse import quote

import mwclient
import requests
import tomllib
from bugzilla.rhbugzilla import RHBugzilla
from dogpile.cache import make_region
from jinja2 import Template

from .cache import cache

__version__ = metadata.version("fedora-gather-easyfix")


class MediaWikiException(Exception):
    """MediaWikiException class.
    Exception class generated when something has gone wrong while
    querying the MediaWiki instance of the project.
    """

    pass


class MediaWiki:
    """Mediawiki class.
    Handles interaction with the Mediawiki.
    """

    def __init__(self, base_url):
        """Instanciate a Mediawiki client.
        :arg base_url: site url of the mediawiki to query.
        """
        self.site = mwclient.Site(base_url)

    def get_pagesource(self, title):
        """Retrieve the content of a given page from Mediawiki.
        :arg title, the title of the page to return
        """
        return self.site.pages[title].text()


@dataclass
class Project:
    """Simple object representation of a project."""

    name: str
    site: str
    owner: str
    tag: str
    tickets: list[str] = field(default_factory=list)
    description: str | None = None

    @property
    def url(self):
        if self.site == "github":
            return f"https://github.com/{self.name}/"
        if self.site == "pagure.io":
            return f"https://pagure.io/{self.name}/"
        if self.site == "gitlab.com":
            return f"https://gitlab.com/{self.name}/"

    @property
    def email(self):
        if "@" in self.owner:
            return self.owner
        else:
            return f"{self.owner}@fedoraproject.org"

    @property
    def group(self):
        if "/" not in self.name:
            return None
        return self.name.split("/")[0]

    @property
    def repo_name(self):
        if "/" not in self.name:
            return self.name
        return self.name.split("/", 1)[1]


@dataclass
class Ticket:
    """Simple object representation of a ticket."""

    id: str
    url: str
    title: str
    status: str
    created_at: str
    updated_at: str
    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    type: str = ""
    component: str = ""


class Gatherer:
    def __init__(self, config):
        self.config = config
        self.http = requests.Session()

    @cache.cache_on_arguments()
    def _api_get(self, url):
        response = self.http.get(url)
        response.raise_for_status()
        return response

    def get_tickets(self, project: Project):
        ...


class GitHubGatherer(Gatherer):
    def __init__(self, config):
        super().__init__(config)
        if "username" in config.get("github", {}) and "api_key" in config.get(
            "github", {}
        ):
            auth = (config["github"]["username"], config["github"]["api_key"])
        else:
            auth = None
        self.http.auth = auth

    def get_projects_in_organization(self, org_name):
        url = f"https://api.github.com/orgs/{org_name}/repos?sort=full_name"
        for repo in self.all_pages(url):
            if repo["archived"]:
                continue
            yield repo["full_name"]

    def all_pages(self, url):
        while True:
            response = self._api_get(url)
            yield from response.json()
            try:
                url = response.links["next"]["url"]
            except KeyError:
                break

    def get_tickets(self, project):
        url = (
            f"https://api.github.com/repos/{project.name}/issues"
            f"?labels={project.tag}&state=open"
        )
        response = self.http.get(url)
        response.raise_for_status()
        for ticket in self.all_pages(url):
            labels = [
                label["name"]
                for label in ticket["labels"]
                if label["name"].lower() != project.tag.lower()
            ]
            yield Ticket(
                id=ticket["number"],
                title=ticket["title"],
                url=ticket["html_url"],
                status=ticket["state"],
                assignees=ticket["assignees"],
                created_at=ticket["created_at"],
                updated_at=ticket["updated_at"],
                labels=labels,
            )


class PagureGatherer(Gatherer):
    def get_tickets(self, project):
        url = f"https://pagure.io/api/0/{project.name}/issues?status=Open&tags={project.tag}"
        response = self._api_get(url)
        for ticket in response.json()["issues"]:
            assignees = (
                [ticket["assignee"]["name"]] if ticket["assignee"] is not None else []
            )
            labels = [
                tag for tag in ticket["tags"] if tag.lower() != project.tag.lower()
            ]
            yield Ticket(
                id=ticket["id"],
                title=ticket["title"],
                url=f"https://pagure.io/{project.name}/issue/{ticket['id']}",
                status=ticket["status"],
                created_at=datetime.datetime.utcfromtimestamp(
                    int(ticket["date_created"])
                ),
                updated_at=datetime.datetime.utcfromtimestamp(
                    int(ticket["last_updated"])
                ),
                labels=labels,
                assignees=assignees,
            )


class GitLabGatherer(Gatherer):
    def get_tickets(self, project):
        # https://docs.gitlab.com/ee/api/issues.html#list-project-issues
        quoted_name = quote(project.name, safe="")
        url = f"https://gitlab.com/api/v4/projects/{quoted_name}/issues?state=opened&labels={project.tag}"
        response = self._api_get(url)
        for ticket in response.json():
            yield Ticket(
                id=ticket["id"],
                title=ticket["title"],
                url=ticket["web_url"],
                status=ticket["state"],
            )


class BugzillaGatherer(Gatherer):
    @cache.cache_on_arguments()
    def get_easyfixes(self):
        """From the Red Hat bugzilla, retrieve all new tickets with keyword
        easyfix or whiteboard trivial.
        """
        return bzclient.query(
            {
                "f1": "keywords",
                "o1": "allwords",
                "v1": "easyfix",
                "query_format": "advanced",
                "bug_status": ["NEW"],
                "classification": "Fedora",
            }
        )
        # print(" {0} easyfix bugs retrieved from BZ".format(len(bugbz_easyfix)))

    @cache.cache_on_arguments()
    def get_trivials(self):
        return bzclient.query(
            {
                "status_whiteboard": "trivial",
                "status_whiteboard_type": "anywords",
                "query_format": "advanced",
                "bug_status": ["NEW"],
                "classification": "Fedora",
            }
        )
        # print(" {0} trivial bugs retrieved from BZ".format(len(bugbz)))

    def get_tickets(self):
        result = self.get_easyfixes() + self.get_trivials()
        result.sort(key=lambda b: f"{b.component}--{b.id}")
        return result


def gather_project_from_wiki(url):
    """Retrieve all the projects which have subscribed to this idea."""
    wiki = MediaWiki(url)
    page = wiki.get_pagesource("Easyfix")
    projects = []
    for row in page.split("\n"):
        match = re.search(r" \* ([^ ]*) ([^ ]*)( [^ ]*)?", row)
        if match:
            site, name = match.group(1).split(":", 1)
            project = Project(
                name=name,
                site=site,
                tag=match.group(2),
                owner=match.group(3),
            )
            projects.append(project)
    return projects


def gather_project_from_file(filename):
    """Retrieve all the projects which have subscribed to this idea."""
    projects = []
    with open(filename) as fh:
        for line in fh:
            match = re.search("^([^ ]*) ([^ ]*)( [^ ]*)?$", line)
            if match is None:
                continue
            site, name = match.group(1).split(":", 1)
            project = Project(
                name=name,
                site=site,
                tag=match.group(2),
                owner=match.group(3).strip(),
            )
            projects.append(project)
    return projects


def gather_projects(config):
    if config["repo_source"] == "file":
        projects = gather_project_from_file(config["repo_list"])
    elif config["repo_source"] == "wiki":
        projects = gather_project_from_wiki(config["wiki_url"])
    else:
        raise ValueError("Invalid repo_source")

    gh_gatherer = GitHubGatherer(config)

    for project in projects:
        if project.site == "github" and "/" not in project.name:
            # it's an org, resolve
            print(f"Gathering projects in {project.name}")
            for repo_name in gh_gatherer.get_projects_in_organization(project.name):
                yield Project(
                    name=repo_name,
                    site=project.site,
                    tag=project.tag,
                    owner=project.owner,
                )
        else:
            yield project


def get_projects(config):
    gh_gatherer = GitHubGatherer(config)
    p_gatherer = PagureGatherer(config)
    gl_gatherer = GitLabGatherer(config)
    projects = list(gather_projects(config))
    project_groups = defaultdict(list)
    for project in projects:
        project_groups[project.group].append(project)
        print(f"Gathering tickets for {project.name}")
        if project.site == "github":
            project.tickets = list(gh_gatherer.get_tickets(project))
        elif project.site == "pagure.io":
            project.tickets = list(p_gatherer.get_tickets(project))
        elif project.site == "gitlab.com":
            project.tickets = list(gl_gatherer.get_tickets(project))
    return project_groups


def get_bugzilla_components(config):
    bz_gatherer = BugzillaGatherer(config)
    bugs = bz_gatherer.get_tickets()
    components = defaultdict(list)
    for bug in bugs:
        components[bug.component].append(bug)
    return components


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
    except IOError as err:
        print("ERROR: %s" % err)


if __name__ == "__main__":
    main()
