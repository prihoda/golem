# -*- coding: utf-8 -*-

import os
from setuptools import find_packages, setup

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='golm',
    version='0.9.1-beta',
    packages=find_packages(),
    include_package_data=True,
    license='Apache Software License',
    description='Framework for creating chatbots for Messenger and other platforms.',
    long_description=README,
    url='https://github.com/prihoda/golm',
    author='David Příhoda, Jakub Drdák, Matúš Žilinec',
    author_email='david.prihoda@gmail.com',
    entry_points={
          'console_scripts': [
              'golm = golm.console:main'
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
    install_requires=['django==2.0.3','requests','wit','wheel','redis',
    'pytz','unidecode','emoji','celery==4.0.2','python-dateutil'],
)
