# -*- coding: UTF-8 -*-
# This file is part of the jetson_stats package (https://github.com/rbonghi/docker-dropbox-app or http://rnext.it).
# Copyright (c) 2020 Raffaello Bonghi.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import logging
import argparse
import sys
import os
import time
import datetime  # Add this line
# Package imports
from dbsync import UpDown

# ...

def main():
    # ...
    # Check folders
    folder = args.folder
    rootdir = os.path.expanduser(args.rootdir)
    if not os.path.exists(rootdir):
        print(f"{bcolors.FAIL}{rootdir} does not exist on your filesystem{bcolors.ENDC}")
        sys.exit(1)
    elif not os.path.isdir(rootdir):
        print(f"{bcolors.FAIL}{rootdir} is not a folder on your filesystem{bcolors.ENDC}")
        sys.exit(1)
    # Configure type of overwrite
    if args.fromDropbox:
        overwrite = "dropbox"
    elif args.fromLocal:
        overwrite = "host"
    else:
        overwrite = ""

    # Add timestamp subfolder
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder = os.path.join(folder, timestamp)

    # Start updown sync with refresh token, designed for long living
    updown = UpDown(args.appKey, args.appSecret, args.refreshToken, folder, rootdir, interval=args.interval,
                    overwrite=overwrite)

    # ...

if __name__ == '__main__':
    main()
