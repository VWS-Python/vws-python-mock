#!/usr/bin/env python3
"""
Configuration for Sphinx.
"""

import importlib.metadata

from packaging.specifiers import SpecifierSet

project = "VWS-Python-Mock"
author = "Adam Dangoor"

extensions = [
    "sphinx_copybutton",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx_paramlinks",
    "sphinx_substitution_extensions",
    "sphinxcontrib.spelling",
    "sphinxcontrib.autohttp.flask",
    "sphinx_toolbox.more_autodoc.autoprotocol",
    "enum_tools.autoenum",
]

templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"

project_copyright = f"%Y, {author}"

# Exclude the prompt from copied code with sphinx_copybutton.
# https://sphinx-copybutton.readthedocs.io/en/latest/use.html#automatic-exclusion-of-prompts-from-the-copies.
copybutton_exclude = ".linenos, .gp"

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# Use ``importlib.metadata.version`` as per
# https://setuptools-scm.readthedocs.io/en/latest/usage/#usage-from-sphinx.
version = importlib.metadata.version(distribution_name=project)
# This method of getting the release from the version goes hand in hand with
# the ``post-release`` versioning scheme chosen in the ``setuptools-scm``
# configuration.
release = version.split(sep=".post")[0]


project_metadata = importlib.metadata.metadata(distribution_name=project)
requires_python = project_metadata["Requires-Python"]
specifiers = SpecifierSet(specifiers=requires_python)
(specifier,) = specifiers
if specifier.operator != ">=":
    msg = (
        f"We only support '>=' for Requires-Python, got {specifier.operator}."
    )
    raise ValueError(msg)
minimum_python_version = specifier.version

language = "en"

# The name of the syntax highlighting style to use.
pygments_style = "sphinx"

# Output file base name for HTML help builder.
htmlhelp_basename = "VWSPYTHONMOCKdoc"
autoclass_content = "init"
intersphinx_mapping = {
    "python": (f"https://docs.python.org/{minimum_python_version}", None),
    "docker": ("https://docker-py.readthedocs.io/en/stable", None),
}
nitpicky = True
warning_is_error = True

html_theme = "furo"
html_title = project
html_show_copyright = False
html_show_sphinx = False
html_show_sourcelink = False
html_theme_options = {
    "sidebar_hide_name": False,
}

# Retry link checking to avoid transient network errors.
linkcheck_retries = 5

spelling_word_list_filename = "../../spelling_private_dict.txt"

autodoc_member_order = "bysource"

rst_prolog = f"""
.. |project| replace:: {project}
.. |release| replace:: {release}
.. |minimum-python-version| replace:: {minimum_python_version}
.. |github-owner| replace:: VWS-Python
.. |github-repository| replace:: vws-python-mock
"""
