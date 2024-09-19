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

import os
import posixpath
import logging
import time
import contextlib  # Import contextlib
from datetime import datetime
from threading import Thread
import dropbox
from watchdog.events import PatternMatchingEventHandler

# Create logger for jplotlib
logger = logging.getLogger(__name__)
# Chunk size dimension
CHUNK_SIZE = 4 * 1024 * 1024
# Ignored pattern
IGNORE_PATTERNS = ["*.swp", "*.goutputstream*"]

class UpDown(Thread, PatternMatchingEventHandler):

    def __init__(self, app_key, app_secret, refresh_token, folder, dropboxignore=".dropboxignore",
                 interval=0.5, overwrite=""):
        Thread.__init__(self)
        PatternMatchingEventHandler.__init__(self, ignore_patterns=IGNORE_PATTERNS)
        self.folder = folder
        self.dropboxignore = dropboxignore
        self.interval = interval
        self.overwrite = overwrite

        if not refresh_token:
            logger.info("Refresh token not set. Calling Dropbox API to generate it.")
            refresh_token = self.get_refresh_token(app_key, app_secret)
            logger.info("Refresh token retrieved: '" + refresh_token + "' (keep it for next run)")
        # Load Dropbox library
        self.dbx = dropbox.Dropbox(app_key=app_key, app_secret=app_secret, oauth2_refresh_token=refresh_token)
        # Load DropboxIgnore list
        self.excludes = self.loadDropboxIgnore()
        # Status initialization
        logger.info(f"Dropbox folder name: {folder}")
        logger.debug(f"Local directory: {folder}")

        # Initialize date components for consistent paths
        self.timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        self.year = datetime.now().strftime('%Y')
        self.month = datetime.now().strftime('%m')

        # Set db_folder to '/year/month/timestamp'
        self.db_folder = posixpath.join('/', self.year, self.month, self.timestamp)

    def get_refresh_token(self, app_key, app_secret):
        auth_flow = dropbox.DropboxOAuth2FlowNoRedirect(app_key, app_secret, token_access_type='offline')
        authorize_url = auth_flow.start()
        logger.info("1. Go to: " + authorize_url)
        logger.info("2. Click \"Allow\" (you might have to log in first).")
        logger.info("3. Copy the authorization code.")
        auth_code = input("Enter the authorization code here: ").strip()
        try:
            oauth_result = auth_flow.finish(auth_code)
        except Exception as e:
            print('Error: %s' % (e,))
            exit(1)
        return oauth_result.refresh_token

    def loadDropboxIgnore(self):
        """Load Dropbox Ignore file and exclude these files from the list."""
        excludes = r'$.'
        path = os.path.join(self.folder, self.dropboxignore)
        ignore_files = []
        if os.path.exists(path) and os.path.isfile(path):
            with open(path, 'r') as f:
                ignore_files = f.read().splitlines()
        if ignore_files:
            # Update exclude list
            excludes = r'|'.join([fnmatch.translate(x) for x in ignore_files]) or r'$.'
            logger.warning(f"Ignore dropbox files: {ignore_files}")
        return excludes

    def normalizePath(self, subfolder, name):
        """Normalize folder for Dropbox synchronization."""
        parts = [self.db_folder, subfolder.replace(os.path.sep, '/'), name]
        path = posixpath.join(*filter(None, parts))
        return path

    def upload(self, fullname, subfolder, name, overwrite=False):
        """Upload a file or directory."""
        # Build the Dropbox path
        path = self.normalizePath(subfolder, name)
        mode = (dropbox.files.WriteMode.overwrite
                if overwrite
                else dropbox.files.WriteMode.add)
        mtime = os.path.getmtime(fullname)

        if os.path.isdir(fullname):
            try:
                res = self.dbx.files_create_folder_v2(path)
                logger.debug(f"Created folder at {path}")
            except dropbox.exceptions.ApiError as err:
                logger.error(f"API ERROR: {err}")
                return None
            return res
        else:
            with open(fullname, 'rb') as f:
                file_size = os.path.getsize(fullname)
                if file_size <= CHUNK_SIZE:
                    data = f.read()
                    with self.stopwatch(f"upload {file_size} bytes"):
                        try:
                            res = self.dbx.files_upload(
                                data, path, mode,
                                client_modified=datetime(*time.gmtime(mtime)[:6]),
                                mute=True
                            )
                            logger.debug(f"Uploaded file to {path}")
                        except dropbox.exceptions.ApiError as err:
                            logger.error(f"API ERROR: {err}")
                            return None
                else:
                    # Handle large files in chunks
                    upload_session_start_result = self.dbx.files_upload_session_start(f.read(CHUNK_SIZE))
                    cursor = dropbox.files.UploadSessionCursor(
                        session_id=upload_session_start_result.session_id,
                        offset=f.tell()
                    )
                    commit = dropbox.files.CommitInfo(path=path)
                    with self.stopwatch(f"upload {file_size} bytes"):
                        while f.tell() < file_size:
                            if (file_size - f.tell()) <= CHUNK_SIZE:
                                try:
                                    res = self.dbx.files_upload_session_finish(
                                        f.read(CHUNK_SIZE), cursor, commit
                                    )
                                    logger.debug(f"Uploaded large file to {path}")
                                except dropbox.exceptions.ApiError as err:
                                    logger.error(f"API ERROR: {err}")
                                    return None
                            else:
                                self.dbx.files_upload_session_append(
                                    f.read(CHUNK_SIZE), cursor.session_id, cursor.offset
                                )
                                cursor.offset = f.tell()
        return res

    @contextlib.contextmanager
    def stopwatch(self, message):
        """Context manager to print how long a block of code took."""
        t0 = time.time()
        try:
            yield
        finally:
            t1 = time.time()
            logger.debug(f"Total elapsed time for {message}: {(t1 - t0):.3f}")

    def on_created(self, event):
        subfolder, name = self.getFolderAndFile(event.src_path)
        if not re.match(self.excludes, name):
            logger.debug(f"Created {name} in folder: \"{subfolder}\"")
            self.upload(event.src_path, subfolder, name)

    def on_modified(self, event):
        if not event.is_directory:
            subfolder, name = self.getFolderAndFile(event.src_path)
            if not re.match(self.excludes, name):
                logger.debug(f"Modified {name} in folder: \"{subfolder}\"")
                self.upload(event.src_path, subfolder, name, overwrite=True)

    def getFolderAndFile(self, src_path):
        abs_path = os.path.dirname(src_path)
        subfolder = os.path.relpath(abs_path, self.folder)
        subfolder = subfolder if subfolder != "." else ""
        name = os.path.basename(src_path)
        return subfolder, name
