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
import contextlib
from datetime import datetime
from threading import Thread
import dropbox

# Create logger for jplotlib
logger = logging.getLogger(__name__)
# Chunk size dimension
CHUNK_SIZE = 4 * 1024 * 1024

class UpDown(Thread):

    def __init__(self, app_key, app_secret, refresh_token, folder, interval=86400):
        Thread.__init__(self)
        self.folder = folder
        self.interval = interval

        if not refresh_token:
            logger.info("Refresh token not set. Calling Dropbox API to generate it.")
            refresh_token = self.get_refresh_token(app_key, app_secret)
            logger.info("Refresh token retrieved: '" + refresh_token + "' (keep it for next run)")
        # Load Dropbox library
        self.dbx = dropbox.Dropbox(app_key=app_key, app_secret=app_secret, oauth2_refresh_token=refresh_token)
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

    def normalizePath(self, subfolder, name):
        """Normalize folder for Dropbox synchronization."""
        parts = [self.db_folder, subfolder.replace(os.path.sep, '/'), name]
        path = posixpath.join(*filter(None, parts))
        return path

    def upload(self, fullname, subfolder, name):
        """Upload a file or directory."""
        # Build the Dropbox path
        path = self.normalizePath(subfolder, name)
        mode = dropbox.files.WriteMode.add
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

    def run(self):
        # List of subfolders to upload
        subfolders = [
            "lnbits",
            "lnd",
            "nocodb",
            "postgres",
            "dashboard"
        ]
        while True:
            logger.info("Starting backup upload")
            for subfolder in subfolders:
                folder_path = os.path.join(self.folder, subfolder)
                for root, dirs, files in os.walk(folder_path):
                    for name in files:
                        fullname = os.path.join(root, name)
                        rel_subfolder = os.path.relpath(root, self.folder)
                        try:
                            self.upload(fullname, rel_subfolder, name)
                        except PermissionError as e:
                            logger.error(f"PermissionError: {e}")
            logger.info("Backup upload completed")
            time.sleep(self.interval)
