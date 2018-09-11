#!/usr/bin/python3
# EASY-INSTALL-ENTRY-SCRIPT: 'gitprivacy==0.0.1','console_scripts','git-privacy'
__requires__ = 'gitprivacy==0.0.1'
import re
import sys
from pkg_resources import load_entry_point

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(
        load_entry_point('gitprivacy==0.0.1', 'console_scripts', 'git-privacy')()
    )
