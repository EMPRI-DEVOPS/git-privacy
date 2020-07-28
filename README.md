[![Latest version on PyPI](https://img.shields.io/pypi/v/gitprivacy.svg)](https://pypi.org/project/gitprivacy/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/gitprivacy.svg)](https://pypi.org/project/gitprivacy/)
[![Build Status](https://travis-ci.org/EMPRI-DEVOPS/git-privacy.svg?branch=master)](https://travis-ci.org/EMPRI-DEVOPS/git-privacy)

# `git-privacy`: Keep your coding hours private

`git-privacy` redacts author and committer dates to keep your coding hours more
private. You can choose the level of redaction: only remove minutes and seconds
from your dates or even hide day or month.
The original dates are encrypted and stored in the commit message in case you
might need them.


## Installation

`git-privacy` can be easily installed via pip:

    $ pip3 install gitprivacy

_Note: `git-privacy` requires Python version 3.6 or later and Git version 2.22.0 or later._


## Getting Started

You can either setup `git-privacy` separately for selected Git repositories or
globally so that each new Git repo automatically uses `git-privacy` from the
beginning.

To setup `git-privacy` for a _single Git repository_ do the following:

1. Initialise `git-privacy`, which sets the necessary hooks.

       $ git-privacy init

2. Set a redaction pattern from the following options:
      - M: Sets the month to January
      - d: Sets the day to the first day of the month
      - h: Sets the hour to midnight
      - m: Sets the minute to zero (full hour)
      - s: Sets the seconds to zero (full minute)


       $ git config privacy.pattern <pattern>

   For example:

       $ git config privacy.pattern hms

3. Set an encryption key if you want to preserve the original timestamps in
   encrypted form in the commit message.
   If no key is set, only the reduced timestamp will remain.

       $ git-privacy keys --init

   For more information about managing encryption keys see `git-privacy keys -h`.

4. Use Git as normal ;-)

To setup `git-privacy` _globally for all new repositories_ do the following:

1. Initialise `git-privacy` to set the necessary hooks globally (in a Git
   template directory).

       $ git-privacy init --global

2. Set a global redaction pattern from the following options:
      - M: Sets the month to January
      - d: Sets the day to the first day of the month
      - h: Sets the hour to midnight
      - m: Sets the minute to zero (full hour)
      - s: Sets the seconds to zero (full minute)


       $ git config --global privacy.pattern <pattern>

   For example:

       $ git config --global privacy.pattern hms

3. Use Git to init or clone repos as usual and `git-privacy` will redact
   timestamps for you :-)

4. **Per individual repo:** Set an encryption key if you want to preserve the original timestamps in
   encrypted form in the commit message.
   If no key is set, only the reduced timestamp will remain.

       $ git-privacy keys --init

   For more information about managing encryption keys see `git-privacy keys -h`.

For an overview of further features and options read the following sections.


## Usage

### Redaction of New Commits

New commits are automatically redacted if `git-privacy` is initialised in a repo.
This is achieved via a post-commit hook.

If you want to manually redact the last commit, run:

    $ git-privacy redate --only-head

### Bulk Re-dating of Commits

To redact and redate all commits of the currently active branch run:

    $ git-privacy redate

***Warning: This will likely rewrite the Git history and might lead to
diverging commit histories.
See [A Warning about Git History Rewriting](#a-warning-about-git-history-rewriting).***

_Note: `git-privacy` warns you if you attempt to redate commits that have
already been pushed to a remote. However, you can force it to do so anyway._

#### Re-dating of Commits from a Startpoint

You can also limit the redate to all commits that succeed a given startpoint:

    $ git-privacy redate <startpoint>

This will redate all commits in the range `<startpoint>..HEAD` (see git rev-list for syntax details).

For example, you can use this to redate all commits of a branch since it has been branched off from `master` by invoking:

    $ git-privacy redate master

### View Unredacted Dates

To view the unredacted commit dates, `git-privacy` offers a git-log-like listing:

    $ git-privacy log

_Note: Unredacted dates are only preserved if you set an encryption key
which allows `git-privacy` to store the encrypted dates in the commit
message._

### Redate after Rebases and other Rewrites
Some Git operations like `git rebase` or `git commit --amend` rewrite existing
commits. Consequently, a new commit date is set for those commit.
`git-privacy` takes notice of such rewrites via a `post-rewrite` hook, logs
them and alerts you that unredated commit dates have been introduced to the
repository, as shown in the following example:

    $ git rebase -i HEAD~2
    Rebasing (1/2)
    Rebasing (2/2)
    A rewrite may have inserted unredacted committer dates.
    To apply date redaction on these dates run

    git-privacy redate-rewrites

    Warning: This alters your Git history.
    Successfully rebased and updated refs/heads/master.

To redate the rewritten commits run, as mentioned:

    $ git-privacy redate-rewrites

***Warning: This will rewrite the Git history again and can lead to
diverging commit histories.
See [A Warning about Git History Rewriting](#a-warning-about-git-history-rewriting).***


### Time Zone Change Warnings

Git commit dates include your current system time zone. These time zones might
leak information about your travel activities.
`git-privacy` warns you about any changes in your system time zone since your last commit.
By default, this is just a warning.
You can set `git-privacy` to prevent commits with changed time zone by running

    $ git-privacy init --timezone-change=abort

or by setting the `privacy.ignoreTimezone` switch in the Git config to `False`.


### Email Address Redaction

Imagine you want to publish a repository which contains some contributor's private email addresses.
`git-privacy` makes it easy to redact such addresses:

    $ git-privacy redact-email john@example.com paul@example.net

You can also specify individual substitutes:

    $ git-privacy redact-email john@example.com:john@bigfirm.invalid

Or, you can use your GitHub username and GitHub's [noreply addresses](https://help.github.com/en/articles/about-commit-email-addresses) to still have your commit associated to your account and get credit:

    $ git-privacy redact-email -g john@example.com:john


## Configuration Options

`git-privacy` takes the following configuration options via [git-config](https://git-scm.com/docs/git-config).

### `privacy.ignoreTimezone`

If true, `git-privacy` will only warn you if your timezone has changed since
your last commit. If false, it will abort the commit. Default is true.

_Note: This requires that the `pre-commit` hook is set by `git-privacy init`_.

### `privacy.limit`
If set, redacted timestamps will be rounded towards the given interval.
The format is `hh-hh` where `hh` is a value between 0 and 24.

Example: `limit = 9-17` means that commits at 17:30 (5:30pm) are set to 17:00.
By default limits are disabled.

### `privacy.mode`
Currently, only the `reduce` mode is supported. Default is `reduce`.

### `privacy.password`
_**Deprecated**: Since version 2.0, `git-privacy` uses key files to encrypt
dates and will automatically migrate from passwords to the new format._

This specifies the password used to encrypt the original timestamps.
If no password is given, original timestamps will not be preserved.

### `privacy.pattern`
This option specifies the extend of the timestamp reduction applied by
`git-privacy`. The reduction pattern is a string that can comprise the following characters:

| Character | Meaning |
| :-------- | :------ |
| M | Sets the month to January |
| d | Sets the day to the first day of the month |
| h | Sets the hour to midnight |
| m | Sets the minute to zero (full hour) |
| s | Sets the seconds to zero (full minute) |

If no pattern is specified, `git-privacy` will abort.

### `privacy.replacements`

If true, `git-privacy` creates a replacement mapping ([git-replace(1)](https://git-scm.com/docs/git-replace))
for each commit that is rewritten by a redate. Default is false.

### `privacy.salt`
_**Deprecated**: Since version 2.0, `git-privacy` uses key files to encrypt
dates and will automatically migrate to the new format._

This is an auto-generated value created by `git-privacy` if `password` is set
by the user. It should not be altered by the user.


## A Warning about Git History Rewriting

Author and committer timestamps are part of the commit object and therefore part of
the input that determines the commit hash (the commit's SHA1 value).
Consequently, every modification to a timestamp changes the commit hash.
And since Git uses hash chains, it also changes all commits that build an that
commit, i.e., that have it as an ancestor.

Example: Consider the commit sequence `a<-b<-c`. If you now redate `b`,
`c` will also be rewritten under a new commit hash resulting into: `a<-b'<-c'`.
If `b` and `c` were just commits in your local repository, you're probably
fine. But if `b` or `c` have been shared with other developers (e.g., by
pushing to a remote), your histories have diverged and you can no longer easily
merge changes from remote.
Do not force-push unless you absolutely know what you are doing!

To avoid diverging histories `git-privacy` rejects redates of commits that
are part of any known remote branch.
But you can still run into locally diverging histories, e.g., if you redate
after you have branched of a branch for a feature development.
So keep this in mind when calling `git-privacy redate` manually.
Using the automatic redating of new commits by the `post-commit` hook or by the
`--only-head` option should be safe for standard setups.
