#!/usr/bin/python -tt
#-*- coding: utf-8 -*-

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

import re
import fedora.client
import xmlrpclib


class MediaWiki(fedora.client.Wiki):
    """ Mediawiki class.
    Handles interaction with the Mediawiki.
    Code stollen from cnucnu:
    http://fedorapeople.org/gitweb?p=till/public_git/cnucnu.git;a=summary
    """

    def __init__(self, base_url='https://fedoraproject.org/w/', *args, **kw):
        """ Instanciate a Mediawiki client.
        """
        super(MediaWiki, self).__init__(base_url, *args, **kw)

    def json_request(self, method="api.php", req_params=None, auth=False, **kwargs):
        """ Perform a json request to retrieve the content of a page.
        """
        if req_params:
            req_params["format"] = "json"

        data =  self.send_request(method, req_params, auth, **kwargs)

        if 'error' in data:
            raise Exception(data['error']['info'])
        return data

    def get_pagesource(self, titles):
        """ Retrieve the content of a given page from Mediawiki.
        :arg titles, the title of the page to return
        """
        data = self.json_request(req_params={
                'action' : 'query',
                'titles' : titles,
                'prop'   : 'revisions',
                'rvprop' : 'content'
                }
                )
        return data['query']['pages'].popitem()[1]['revisions'][0]['*']


def gather_project():
    """ Retrieve all the projects which have subscribe to this idea.
    """
    wiki = MediaWiki(base_url='https://fedoraproject.org/w/')
    page = wiki.get_pagesource("User:Pingou/easyfix")
    projects = {}
    for row in page.split('\n'):
        regex = re.search(' \* (\w*) (\w*)( \w*)?', row)
        if regex:
            projects[regex.group(1)] = (regex.group(2), regex.group(3))
    return projects


def get_open_tickets_for_keyword(project, keyword):
    tickets = []
    try:
        server = xmlrpclib.ServerProxy('https://fedorahosted.org/%s/rpc' % project)
        query = 'status=assigned&status=new&status=reopened&keywords=~%s' % keyword
        for ticket in server.ticket.query(query):
            tickets.append(server.ticket.get(ticket))
    except xmlrpclib.Error, err:
        print '   Could not retrieve information for project: %s' % project
        print '   Error: %s' % err
    return tickets


def main():
    """ For each project defined in PROJECTS, gather the tickets
    containing the provided keyword.
    """
    projects = gather_project()
    for project in projects.keys():
        print 'Project: %s' % project
        for ticket in get_open_tickets_for_keyword(project,
            projects[project][0]):
            info = ticket[3]
            print """#%s  - %s
   status: %s - type: %s - component: %s
   https://fedorahosted.org/%s/ticket/%s
   Contact person: %s@fedoraproject.org""" %( ticket[0],info['summary'],
            info['status'], info['type'], info['component'], project,
            ticket[0], projects[project][1])
        print ''


if __name__ == '__main__':
    main()
