""" setup file """
from setuptools import setup, find_packages


with open('README.md') as f:
    README = f.read()

with open('LICENSE') as f:
    LICENSE = f.read()

setup(
    name='gitprivacy',
    version='0.0.1',
    description='Git extension that adds timestamp blurring',
    long_description=README,
    author='Benjamin Brahmer',
    author_email='info@b-brahmer.de',
    url='https://git.b-brahmer.de/Grotax/pyGitPrivacy',
    license=LICENSE,
    packages=find_packages(exclude=('tests', 'docs')),
    entry_points={
        'console_scripts': [
            'git-privacy = gitprivacy.gitprivacy:main'
        ]
    }
)
