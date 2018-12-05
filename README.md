# pyGitPrivacy

## Dependencies

You need to install:

`python3 python3-pip`

Installed by setup:

- gitpython
- colorama
- progressbar2
- cryptography

## Installation

+ clone the repository and change directory
+ `sudo pip3 install .`

Copy `post-commit` to `yourRepo/.git/hooks/` (make sure that it is executable)

Edit your `yourRepo/.git/config` and add the following:

```
[privacy]
        password = 123456
        mode = reduce
        pattern = "h,s"
        limit = 16-20
        database_path = /path/to/your/database.db
```
+ password -> your password
+ mode
    + simple -> adds 1 hour to the last commit (not recommended)
    + average -> also not recommended check code if interested
    + reduce -> accuracy of the timestamp is reduced by replacing the values defined by `pattern`
+ pattern
    + y = Year
    + M = Month
    + d = day
    + h = hour
    + m = minute
    + s = second
+ limit -> ensure that commits are placed in a certain time frame
+ database_path -> path to your database

The post-commit will disable itself to prevent a loop this will trigger git to warn you that the hook was ignored.
To disable that add the following:
```
[advice]
        ignoredHook = false
```

## Optional

Additionally you may install a pre-commit hook which currently checks if your timezone differs from the last commit.

Copy `doc/pre-commit` to `your/repo/.git/hooks`

## Commands

Intended for manual use:

```
git-privacy -log       # git log like function
git-privacy -clean     # Removes commits from the DB that no longer exist in your repository
git-privacy -anonymize # Changes dates on each commit in your repository
```