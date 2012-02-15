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

import xmlrpclib

PROJECTS = { 'fedora-infrastructure' : 'easyfix',
            'tgcaptcha2' : 'easyfix',
            'fas' : 'easyfix',
          }

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
    for project in PROJECTS.keys():
        print 'Project: %s' % project
        for ticket in get_open_tickets_for_keyword(project,
            PROJECTS[project]):
            info = ticket[3]
            print """#%s  - %s
   status: %s - type: %s
   https://fedorahosted.org/%s/ticket/%s""" %( ticket[0],info['summary'],
            info['status'], info['type'], project, ticket[0])
        print ''


if __name__ == '__main__':
    main()
