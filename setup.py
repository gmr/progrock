import setuptools
import sys

tests_require = ['nose', 'mock']
if sys.version_info < (2, 7, 0):
    tests_require.append('unittest2')

desc = ('A multi-progressbar implementation to complement '
        'multiprocessing.Process')

setuptools.setup(name='progrock',
                 version='0.3.1',
                 description=desc,
                 long_description=open('README.rst').read(),
                 author='Gavin M. Roy',
                 author_email='gavinmroy@gmail.com',
                 keywords='multiprocess progress progressbar curses console',
                 url='http://progrock.readthedocs.org',
                 py_modules=['progrock'],
                 package_data={'': ['LICENSE', 'README.md']},
                 include_package_data=True,
                 license=open('LICENSE').read(),
                 classifiers=['Development Status :: 3 - Alpha',
                              'Environment :: Console',
                              'Environment :: Console :: Curses',
                              'Intended Audience :: Developers',
                              'License :: OSI Approved :: BSD License',
                              'Operating System :: OS Independent',
                              'Programming Language :: Python :: 2',
                              'Programming Language :: Python :: 2.6',
                              'Programming Language :: Python :: 2.7',
                              'Programming Language :: Python :: 3',
                              'Programming Language :: Python :: 3.2',
                              'Programming Language :: Python :: 3.3',
                              'Programming Language :: Python :: 3.4',
                              'Programming Language :: Python :: Implementation :: CPython',
                              'Programming Language :: Python :: Implementation :: PyPy',
                              'Topic :: Software Development :: Libraries'])
