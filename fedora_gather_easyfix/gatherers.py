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

import datetime
from collections import defaultdict
from urllib.parse import quote

import requests
from bugzilla.rhbugzilla import RHBugzilla

from .cache import cache
from .models import Project, Ticket


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
    def __init__(self, config):
        super().__init__(config)
        self.client = RHBugzilla(url="https://bugzilla.redhat.com/xmlrpc.cgi", cookiefile=None)

    @cache.cache_on_arguments()
    def get_easyfixes(self):
        """From the Red Hat bugzilla, retrieve all new tickets with keyword
        easyfix or whiteboard trivial.
        """
        return self.client.query(
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
        return self.client.query(
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

    def get_components(self):
        bugs = self.get_tickets()
        components = defaultdict(list)
        for bug in bugs:
            components[bug.component].append(bug)
        return components
