[![Build Status](https://travis-ci.org/cburkert/pyGitPrivacy.svg?branch=master)](https://travis-ci.org/cburkert/pyGitPrivacy)

# git-privacy: Keep your coding hours private

Git-privacy redacts author and committer dates to keep your coding hours more
private. You can choose the level of redaction: only remove minutes and seconds
from your dates or even hide day or month.
The original dates are encrypted and stored in the commit message in case you
might need them.


## Installation

+ `pip3 install gitprivacy`

Note: Git-privacy requires Python version 3.5 or later.


## Getting Started

1. Add the following to `.git/config` and adapt it to your needs:

```
[privacy]
	password = <your-password>
	mode = reduce
	pattern = "ms"
	#limit = 9-17
```

2. Choose a strong password. It is used to encrypt your timestamps.
3. Pick a redaction pattern from the following options:
    + M: Sets the month to January
    + d: Sets the day to the first day of the month
    + h: Sets the hour to midnight
    + m: Sets the minute to zero (full hour)
    + s: Sets the seconds to zero (full minute)
4. Set an acceptable timestamp range (`limit`). Outliers are rounded towards
   the set limits, e.g., commits at 17:30 (5:30pm) are set to 17:00. Only full
   hours are currently supported. Omit the limits setting to disable.
5. Execute `git-privacy init`. This sets the necessary Git hooks.


## Usage

### Redaction of New Commits

New commits are automatically redacted if git-privacy is initialised in a repo.
This is achieve via a post-commit hook.

If you want to manually redact the last commit, run:

    git-privacy redate --only-head

### View Unredacted Dates

To view the unredacted commit dates, git-privacy offers a git-log-like listing:

    git-privacy log

### Bulk Re-dating of Commits

To redact and redate all commits of the currently active branch run:

    git-privacy redate

**WARNING:** This will completely rewrite the history and will lead to
diverging commit histories.


## Optional: Timezone Change Warnings

Additionally you may install a pre-commit hook which currently checks if your timezone differs from the last commit.
To do so simply execute:

    git-privacy init --enable-check

