# GNU Lesser General Public License v3.0 only
# Copyright (C) 2020 Artefact
# licence-information@artefact.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""Summary
"""
from typing import List

import os

from commands.upload_file import upload_file
from inotify_simple import INotify, flags, Event
from loguru import logger

import config


class FileWatcher:

    """Summary

    Attributes:
        directories (dict): Description
        inotify (INotify): Description
        watch_descriptors (dict): Description
        watched_flags (int): Description
    """

    def __init__(self):
        """Summary
        """
        self.inotify = INotify()
        self.watched_flags = flags.CREATE | flags.MOVED_TO | flags.ISDIR
        self.directories = {}
        self.watch_descriptors = {}
        watch_descriptor = self.inotify.add_watch(config.APP_LANDING_INGEST_DIR, self.watched_flags)
        self.directories[watch_descriptor] = config.APP_LANDING_INGEST_DIR
        self.watch_descriptors[self.directories[watch_descriptor]] = watch_descriptor
        logger.info("Watching ingestion folder")

        while True:
            events = self.inotify.read(read_delay=1000)
            all_events = self.get_all_events(events)
            for event in all_events:
                path = os.path.join(self.directories[event.wd], event.name)
                upload_file(path)
                os.remove(path)
            self.delete_folders_if_empty(config.APP_LANDING_INGEST_DIR)

    def delete_folders_if_empty(self, dirname: str):
        """Summary

        Args:
            dirname (str): Description
        """
        for root, dirs, _ in os.walk(dirname, topdown=False):
            for name in dirs:
                dir_path = os.path.join(root, name)
                if not os.listdir(dir_path):  # An empty list is False
                    self.inotify.rm_watch(self.watch_descriptors[os.path.join(root, name)])
                    del self.directories[self.watch_descriptors[os.path.join(root, name)]]
                    del self.watch_descriptors[os.path.join(root, name)]
                    os.rmdir(os.path.join(root, name))

    def get_all_events(self, events: List[Event]):
        """Summary

        Args:
            events (List[Event]): Description

        Returns:
            List[Event]: Description
        """
        logger.info(f"Initial events: {events}")
        all_events = []
        for event in events:
            is_dir = False
            deleted = False
            for flag in flags.from_mask(event.mask):
                if flag == flag.ISDIR:
                    is_dir = True
                if flag in (flag.DELETE, flag.IGNORED):
                    deleted = True
            if is_dir and not deleted:
                watch_descriptor = self.inotify.add_watch(
                    os.path.join(config.APP_LANDING_INGEST_DIR, event.name),
                    self.watched_flags
                )
                self.directories[watch_descriptor] = os.path.join(
                    config.APP_LANDING_INGEST_DIR,
                    event.name
                )
                self.watch_descriptors[self.directories[watch_descriptor]] = watch_descriptor
                all_events = self.check_subfolders(watch_descriptor, all_events)
            elif not deleted:
                all_events += [event]
                logger.info(
                    f"Adding event for file : "
                    f"{self.directories[event.wd]}/{event.name}"
                )
            else:
                continue
        logger.info(f"All events : {all_events}")
        return all_events

    def check_subfolders(self, watch_descriptor: int, all_events: List[Event]):
        """Summary

        Args:
            watch_descriptor (int): Description
            all_events (List[Event]): Description

        Returns:
            List[Event]: Description
        """
        for root, folders, files in os.walk(self.directories[watch_descriptor]):
            for folder in folders:
                watch_descriptor = self.inotify.add_watch(
                    os.path.join(root, folder),
                    self.watched_flags
                )
                self.directories[watch_descriptor] = os.path.join(root, folder)
                self.watch_descriptors[self.directories[watch_descriptor]] = watch_descriptor
            for file in files:
                all_events += [
                    Event(
                        wd=self.watch_descriptors[root],
                        mask=256,
                        cookie=0,
                        name=file)
                ]
                logger.info(f"Adding untracked event for file : {root}/{file}")
        return all_events


def watch_ingest_folder():
    """Summary
    """
    FileWatcher()
