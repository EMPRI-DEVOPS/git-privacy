#!/usr/bin/python3

import subprocess as sp
import argparse
import sys
import os
import uuid
import random
import string
import requests
from bs4 import BeautifulSoup


PARSER = argparse.ArgumentParser()
PARSER.add_argument("-n", metavar="Number of commits", dest="commits",
                    help="-n 1-99",
                    required=True)
ARGS = PARSER.parse_args()

def main():
    if int(ARGS.commits) > 99:
        sys.exit(1)
    elif int(ARGS.commits) < 1:
        sys.exit(1)
    else:
        current_working_directory = os.getcwd()
        for i in range(int(ARGS.commits)):
            file_name = current_working_directory+'/'+str(uuid.uuid4())
            with open(file_name, 'w+') as file:
                file.write(''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randrange(1,100,1))))
            sp.check_call(["git", "add", "."])
            result = requests.get('http://www.whatthecommit.com/')
            soup = BeautifulSoup(result.content, 'html5lib')
            div = soup.find(id="content")
            message = div.findAll('p')[0].getText().rstrip()
            sp.check_call(["git", "commit", "-m", "{}".format(message)])


if __name__ == '__main__':
    main()