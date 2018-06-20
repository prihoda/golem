# -*- coding: utf-8 -*-

import os
from setuptools import find_packages, setup

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='django-golem',
    version='0.90-beta1',
    packages=find_packages(),
    include_package_data=True,
    license='Apache Software License',
    description='Framework for creating stateful chatbots on Django.',
    long_description=README,
    url='https://github.com/prihoda/golem',
    author='David Příhoda, Jakub Drdák, Matúš Žilinec',
    author_email='david.prihoda@gmail.com',
    entry_points={
          'console_scripts': [
              'golem-admin = golem.core.admin:main',
              'golm = golem.management.golm:main'
          ]
      },
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    install_requires=['django', 'networkx', 'requests', 'six', 'sqlparse', 'wit==4.3.0', 'wheel', 'redis',
                      'pytz', 'unidecode', 'emoji', 'elasticsearch', 'celery', 'python-dateutil'],
)
