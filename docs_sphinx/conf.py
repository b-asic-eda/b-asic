# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import shutil

project = 'B-ASIC'
copyright = '2020-2022, Oscar Gustafsson et al'
author = 'Oscar Gustafsson et al'
html_logo = "../logo_tiny.png"

pygments_style = 'sphinx'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.inheritance_diagram',
    'sphinx.ext.intersphinx',
    'numpydoc',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

autodoc_docstring_signature = True

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
}

numpydoc_show_class_members = False

inheritance_node_attrs = dict(fontsize=16)

graphviz_dot = shutil.which('dot')

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']
