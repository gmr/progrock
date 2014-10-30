#!/usr/bin/env python
from progrock import __version__
needs_sphinx = '1.0'
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinxcontrib.httpdomain',
]
templates_path = []
source_suffix = '.rst'
master_doc = 'index'
project = 'progrock'
copyright = 'Gavin M. Roy'
version = '.'.join(__version__.split('.')[0:1])
release = __version__
intersphinx_mapping = {
    'python': ('https://docs.python.org/', None),
}
