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

from collections import defaultdict
from datetime import UTC, datetime
from urllib.parse import quote

import requests
from bugzilla.rhbugzilla import RHBugzilla

from .cache import cache
from .models import Project, Ticket, Workflow


class Gatherer:
    def __init__(self, config):
        self.config = config
        self.http = requests.Session()

    @cache.cache_on_arguments()
    def _api_get(self, url):
        response = self.http.get(url)
        response.raise_for_status()
        return response

    def _get_labels(self, ticket):
        return [label["name"] for label in ticket["labels"]]

    def _filter_labels(self, ticket, project: Project):
        return [
            label
            for label in self._get_labels(ticket)
            if label.lower() != project.tag.lower().replace("+", " ")
        ]

    def get_tickets(self, project: Project):
        ...

    def get_workflows(self, project: Project):
        return []


class GitHubGatherer(Gatherer):
    BASE_URL = "https://api.github.com"
    SKIP_WORKFLOWS = [
        "Dependabot Updates",
        "Apply labels when deployed",
    ]

    def __init__(self, config):
        super().__init__(config)
        if "username" in config.get("github", {}) and "api_key" in config.get("github", {}):
            auth = (config["github"]["username"], config["github"]["api_key"])
        else:
            auth = None
        self.http.auth = auth

    def _api_get(self, sub_url):
        url = f"{self.BASE_URL}{sub_url}"
        return super()._api_get(url)

    def get_projects_in_organization(self, org_name):
        url = f"/orgs/{org_name}/repos?sort=full_name"
        for repo in self.all_pages(url):
            if repo["archived"]:
                continue
            yield repo["full_name"]

    def all_pages(self, url, key=None):
        while True:
            response = self._api_get(url)
            response.raise_for_status()
            response_json = response.json()
            if key is not None:
                yield from response_json[key]
            else:
                yield from response_json
            try:
                url = response.links["next"]["url"]
                url = url[len(self.BASE_URL) :]
            except KeyError:
                break

    def _get_labels(self, ticket):
        return [label["name"] for label in ticket["labels"]]

    def get_tickets(self, project: Project):
        url = f"/repos/{project.name}/issues" f"?labels={project.tag}&state=open"
        for ticket in self.all_pages(url):
            yield Ticket(
                id=ticket["number"],
                title=ticket["title"],
                url=ticket["html_url"],
                status=ticket["state"],
                body=ticket["body"],
                assignees=[a["login"] for a in ticket["assignees"]],
                created_at=datetime.fromisoformat(ticket["created_at"]),
                updated_at=datetime.fromisoformat(ticket["updated_at"]),
                labels=self._filter_labels(ticket, project),
            )

    def get_workflows(self, project: Project):
        repo_response = self._api_get(f"/repos/{project.name}")
        repo_response.raise_for_status()
        repo = repo_response.json()
        url = f"/repos/{project.name}/actions/workflows"
        for workflow in self.all_pages(url, "workflows"):
            if workflow["state"] != "active":
                continue
            if workflow["name"] in self.SKIP_WORKFLOWS:
                continue
            if workflow["path"].startswith(".github"):
                workflow_filename = workflow["path"].split("/")[-1]
                # Better badge URL
                workflow[
                    "badge_url"
                ] = f"https://github.com/{project.name}/actions/workflows/{workflow_filename}/badge.svg?branch={repo['default_branch']}"
                # Better HTML URL
                workflow[
                    "html_url"
                ] = f"https://github.com/{project.name}/actions/workflows/{workflow_filename}"
            yield Workflow(
                name=workflow["name"],
                html_url=workflow["html_url"],
                badge_url=workflow["badge_url"],
            )


class PagureGatherer(Gatherer):
    def _get_labels(self, ticket):
        return ticket["tags"]

    def get_tickets(self, project):
        url = f"https://pagure.io/api/0/{project.name}/issues?status=Open&tags={project.tag}"
        response = self._api_get(url)
        for ticket in response.json()["issues"]:
            assignees = [ticket["assignee"]["name"]] if ticket["assignee"] is not None else []
            yield Ticket(
                id=ticket["id"],
                title=ticket["title"],
                url=f"https://pagure.io/{project.name}/issue/{ticket['id']}",
                status=ticket["status"],
                body=ticket["content"],
                created_at=datetime.fromtimestamp(int(ticket["date_created"]), tz=UTC),
                updated_at=datetime.fromtimestamp(int(ticket["last_updated"]), tz=UTC),
                labels=self._filter_labels(ticket, project),
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
    def get_tickets(self):
        """From the Red Hat bugzilla, retrieve all new tickets with keyword
        easyfix or whiteboard trivial.
        """
        easyfixes = self.client.query(
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
        trivials = self.client.query(
            {
                "status_whiteboard": "trivial",
                "status_whiteboard_type": "anywords",
                "query_format": "advanced",
                "bug_status": ["NEW"],
                "classification": "Fedora",
            }
        )
        # print(" {0} trivial bugs retrieved from BZ".format(len(bugbz)))
        result = easyfixes + trivials
        result.sort(key=lambda b: f"{b.component}--{b.id}")
        return result

    def get_components(self):
        bugs = self.get_tickets()
        components = defaultdict(list)
        for bug in bugs:
            components[bug.component].append(bug)
        return components
