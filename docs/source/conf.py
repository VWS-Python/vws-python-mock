#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration for Sphinx.
"""

# pylint: disable=invalid-name

import datetime

from pkg_resources import get_distribution

project = 'VWS-Python-Mock'
author = 'Adam Dangoor'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx_autodoc_typehints',
    'sphinx_paramlinks',
    'sphinx-prompt',
    'sphinx_substitution_extensions',
    'sphinxcontrib.spelling',
    'sphinxcontrib.autohttp.flask',
]

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'

year = datetime.datetime.now().year
copyright = f'{year}, {author}'  # pylint: disable=redefined-builtin

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# Use ``pkg_resources`` as per
# https://github.com/pypa/setuptools_scm#usage-from-sphinx.
version = get_distribution(project).version
_month, _day, _year, *_ = version.split('.')
release = f'{_month}.{_day}.{_year}'

language = None

# The name of the syntax highlighting style to use.
pygments_style = 'sphinx'
html_theme = 'alabaster'

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
#
# This is required for the alabaster theme
# refs: https://alabaster.readthedocs.io/en/latest/installation.html#sidebars
html_sidebars = {
    '**': [
        'relations.html',  # needs 'show_related': True theme option to display
        'searchbox.html',
    ],
}

# Output file base name for HTML help builder.
htmlhelp_basename = 'VWSPYTHONMOCKdoc'
autoclass_content = 'init'
intersphinx_mapping = {
    'python': ('https://docs.python.org/3.9', None),
    'docker': ('https://docker-py.readthedocs.io/en/stable', None),
}
nitpicky = True
warning_is_error = True
nitpick_ignore = [
    ('py:exc', 'RetryError'),
    # See https://bugs.python.org/issue31024 for why Sphinx cannot find this.
    ('py:class', 'typing.Tuple'),
    ('py:class', 'typing.Optional'),
    ('py:class', '_io.BytesIO'),
    ('py:class', 'docker.types.services.Mount'),
    ('py:exc', 'requests.exceptions.MissingSchema'),
    ('http:obj', 'string'),
]

html_show_copyright = False
html_show_sphinx = False
html_show_sourcelink = False

html_theme_options = {
    'show_powered_by': 'false',
}

html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'searchbox.html',
    ],
}

# Don't check anchors because many websites use #! for AJAX magic
# http://sphinx-doc.org/config.html#confval-linkcheck_anchors
linkcheck_anchors = False
# Retry link checking to avoid transient network errors.
linkcheck_retries = 5
linkcheck_ignore = [
    # Requires login.
    r'https://developer.vuforia.com/targetmanager',
]

spelling_word_list_filename = '../../spelling_private_dict.txt'

autodoc_member_order = 'bysource'

rst_prolog = f"""
.. |project| replace:: {project}
.. |release| replace:: {release}
.. |github-owner| replace:: VWS-Python
.. |github-repository| replace:: vws-python-mock
"""
