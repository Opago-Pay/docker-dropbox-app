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
import datetime  # Added this line
# Package imports
from dbsync import UpDown

# Create logger for jplotlib
logger = logging.getLogger(__name__)


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def main():
    """Main program.

    Parse command line, then iterate over files and directories under
    rootdir and upload all files.  Skips some temporary files and
    directories, and avoids duplicate uploads by comparing size and
    mtime with the server.
    """

    parser = argparse.ArgumentParser(description='Sync ~/dropbox to Dropbox')
    parser.add_argument('--rootdir',
                        default=os.environ['DROPBOX_ROOTDIR'] if "DROPBOX_ROOTDIR" in os.environ else "~/Downloads",
                        help='Local directory to upload')
    parser.add_argument('--folder', '-f',
                        default=os.environ['DROPBOX_FOLDER'] if "DROPBOX_FOLDER" in os.environ else "",
                        help='Folder name in your Dropbox')
    parser.add_argument('--appKey', default=os.environ['DROPBOX_APP_KEY'] if "DROPBOX_APP_KEY" in os.environ else "",
                        help='Application key')
    parser.add_argument('--appSecret',
                        default=os.environ['DROPBOX_APP_SECRET'] if "DROPBOX_APP_SECRET" in os.environ else "",
                        help='Application secret')
    parser.add_argument('--refreshToken',
                        default=os.environ['DROPBOX_REFRESH_TOKEN'] if "DROPBOX_REFRESH_TOKEN" in os.environ else "",
                        help='Refresh token')
    parser.add_argument('--interval', '-i',
                        default=int(os.environ['DROPBOX_INTERVAL']) if "DROPBOX_INTERVAL" in os.environ else 10,
                        help='Interval to sync from dropbox')
    parser.add_argument('--fromDropbox', action='store_true',
                        help='Direction to synchronize Dropbox')
    parser.add_argument('--fromLocal', action='store_true',
                        help='Direction to synchronize Dropbox')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show all Take default answer on all questions')
    # Parser arguments
    args = parser.parse_args()
    # Initialize loggger
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format='%(name)s - %(levelname)s - %(message)s')
    # Check token
    if not (args.appKey and args.appSecret):
        print(f"{bcolors.FAIL}app key and app secret must be set{bcolors.ENDC}")
        sys.exit(2)

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

    # Set dbfolder to args.folder
    folder = args.folder

    # Start updown sync with refresh token, designed for long living
    updown = UpDown(args.appKey, args.appSecret, args.refreshToken, folder, rootdir, interval=args.interval,
                    overwrite=overwrite)

    # Run observer
    logger.info("Server started")
    updown.start()
    # Run loop
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.debug("Keyboard interrupt")
    # Stop server
    updown.stop()


if __name__ == '__main__':
    main()
# EOF

