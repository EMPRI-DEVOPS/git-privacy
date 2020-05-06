from setuptools import setup, find_packages


with open('README.md') as f:
    README = f.read()

setup(
    name='gitprivacy',
    version='1.4.1',
    description='Git wrapper redacting author and committer dates.',
    long_description=README,
    long_description_content_type="text/markdown",
    keywords=["git", "privacy", "timestamps"],
    maintainer='Christian Burkert',
    maintainer_email='gitprivacy@cburkert.de',
    url='https://github.com/EMPRI-DEVOPS/git-privacy',
    license="BSD",
    packages=find_packages(exclude=('tests', 'docs')),
    include_package_data=True,
    python_requires='>=3.6',
    install_requires=[
        'click>=7',
        'gitpython',
        'pynacl',
    ],
    entry_points={
        'console_scripts': [
            'git-privacy = gitprivacy.gitprivacy:cli'
        ]
    },
    classifiers=[
        "Topic :: Software Development :: Version Control :: Git",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
)
