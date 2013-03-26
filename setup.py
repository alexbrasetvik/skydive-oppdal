import os
import sys

from setuptools import setup, find_packages


setup(
    name = 'freefly',
    author = 'NTNU Fallskjermklubb',
    author_email = 'alex@brasetvik.com',
    url = 'http://www.skydiveoppdal.no',
    description = 'Freefly',
    zip_safe=False,

    entry_points = dict(
    ),

    install_requires = [
        'piped>=0.5.3', 'piped.contrib.database>=0.5.2', 'piped.contrib.validation', 'piped.contrib.cyclone>=0.4.3',
        'sqlalchemy',
    ]
)
