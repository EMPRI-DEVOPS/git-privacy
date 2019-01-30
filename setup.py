from setuptools import setup, find_packages


with open('README.md') as f:
    README = f.read()

with open('LICENSE') as f:
    LICENSE = f.read()

setup(
    name='gitprivacy',
    version='1.1.0',
    description='Git extension that adds timestamp blurring',
    long_description=README,
    maintainer='Christian Burkert',
    author_email='gitprivacy@cburkert.de',
    url='https://github.com/cburkert/pyGitPrivacy',
    license=LICENSE,
    packages=find_packages(exclude=('tests', 'docs')),
    include_package_data=True,
    python_requires='>=3.5',
    install_requires=[
        'gitpython',
        'colorama',
        'progressbar2',
        'pynacl',
    ],
    entry_points={
        'console_scripts': [
            'git-privacy = gitprivacy.gitprivacy:main'
        ]
    }
)
