import re
from collections import defaultdict

import mwclient

from .gatherers import GitHubGatherer, GitLabGatherer, PagureGatherer
from .models import Project


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


def gather_project_from_wiki(url):
    """Retrieve all the projects which have subscribed to this idea."""
    print("Getting repositories from MediaWiki")
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
