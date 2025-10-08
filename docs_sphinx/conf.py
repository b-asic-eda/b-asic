# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import shutil

project = "B-ASIC"
copyright = "2020-2025, Oscar Gustafsson et al"
author = "Oscar Gustafsson et al"
html_logo = "../logos/logo_tiny.png"

pygments_style = "sphinx"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.inheritance_diagram",
    "sphinx.ext.intersphinx",
    "sphinx_gallery.gen_gallery",
    "numpydoc",  # Needs to be loaded *after* autodoc.
    "sphinx_copybutton",
]
language = "en"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

autodoc_docstring_signature = True

# nitpicky = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "graphviz": ("https://graphviz.readthedocs.io/en/stable/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "networkx": ("https://networkx.org/documentation/stable", None),
    "mplsignal": ("https://mplsignal.readthedocs.io/en/stable/", None),
    "pulp": ("https://coin-or.github.io/pulp/", None),
}

numpydoc_show_class_members = False
# numpydoc_validation_checks = {
#     "all",
#     "ES01",
#     "SA01",
#     "EX01",
#     "RT01",
#     "GL08",
#     "SA04",
#     "RT03",
# }

inheritance_node_attrs = {"fontsize": 16}

graphviz_dot = shutil.which("dot")

html_favicon = "_static/icon_logo.png"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]

# -- Options for sphinx-gallery --
sphinx_gallery_conf = {
    "examples_dirs": "../examples",  # path to your example scripts
    "gallery_dirs": "examples",  # path to where to save gallery generated output
    "plot_gallery": "True",  # sphinx-gallery/913
    "filename_pattern": ".",
    "doc_module": ("b_asic",),
    "reference_url": {"b_asic": None},
    "image_scrapers": (
        #    qtgallery.qtscraper,
        "matplotlib",
    ),
    "reset_modules": (
        #    qtgallery.reset_qapp,
        "matplotlib",
    ),
}
