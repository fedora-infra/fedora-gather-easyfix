#!/usr/bin/env python
"""
Setup script
"""

from distutils.core import setup
from gather_easyfix import __version__

setup(
    name = 'fedora-gather-easyfix',
    description = 'Gather easyfix tickets accross fedorahosted projects',
    description_long = '''
The aims of this project is to offer a simple overview of where help is needed for people coming to Fedora.

There are a number of project hosted on  fedorahosted.org which are participating in this process by marking tickets as 'easyfix'. fedora-gather-easyfix find them and gather them in a single place.

A new contributor can thus consult this page and find a place/task she/he would like to help with, contact the person in charge and get started.
''',
    data_files = [('/etc/fedora-gather-easyfix/', [ 'template.html' ] ),
            ('/usr/share/fedora-gather-easyfix/css/', ['css/jquery-ui-1.8.17.custom.css']),
            ('/usr/share/fedora-gather-easyfix/js/', ['js/jquery-1.7.1.js',
                        'js/jquery-1.7.1.min.js', 'js/jquery.ui.core.js', 'js/jquery.ui.tabs.js',
								'js/jquery.ui.widget.js'])],
    version = __version__,
    author = 'Pierre-Yves Chibon',
    author_email = 'pingou@pingoured.fr',
    maintainer = 'Pierre-Yves Chibon',
    maintainer_email = 'pingou@pingoured.fr',
    license = 'GPLv2+',
    download_url = '',
    url = 'https://fedorahosted.org/fedora-gather-easyfix/',
    scripts=['gather_easyfix.py'],
    )
