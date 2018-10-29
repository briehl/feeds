from ..base import BaseFeed
from feeds.activity.notification import Notification
from feeds.storage.mongodb.activity_storage import MongoActivityStorage
from feeds.storage.mongodb.timeline_storage import MongoTimelineStorage
from cachetools import TTLCache
import logging


class NotificationFeed(BaseFeed):
    def __init__(self, user_id):
        self.user_id = user_id
        self.timeline_storage = MongoTimelineStorage(self.user_id)
        self.activity_storage = MongoActivityStorage()
        self.timeline = None
        self.cache = TTLCache(1000, 600)

    def _update_timeline(self):
        """
        Updates a local user timeline cache. This is a list of activity ids
        that are used for fetching from activity storage (for now). Sorted
        by newest first.

        TODO: add metadata to timeline storage - type and verb, first.
        """
        logging.getLogger(__name__).info('Fetching timeline for ' + self.user_id)
        self.timeline = self.timeline_storage.get_timeline()

    def get_notifications(self, count=10, user_view=False):
        activities = self.get_activities(count=count)
        if user_view:
            ret_list = list()
            for act in activities:
                ret_list.append(act.user_view())
            return ret_list
        else:
            return activities

    def get_activities(self, count=10):
        """
        Returns a selection of activities.
        :param count: Maximum number of Notifications to return (default 10)
        """
        # steps.
        # 0. If in cache, return them.  <-- later
        # 1. Get storage adapter.
        # 2. Query it for recent activities from this user.
        # 3. Cache them here.
        # 4. Return them.
        if count < 1 or not isinstance(count, int):
            raise ValueError('Count must be an integer > 0')
        serial_notes = self.timeline_storage.get_timeline(count=count)
        note_list = [Notification.from_dict(note) for note in serial_notes]
        return note_list

    def mark_activities(self, activity_ids, seen=False):
        """
        Marks the given list of activities as either seen (True) or unseen (False).
        If the owner of this feed is not on the users list for an activity, nothing is
        changed for that activity.
        """
        if seen:
            self.activity_storage.set_seen(activity_ids, self.user_id)
        else:
            self.activity_storage.set_unseen(activity_ids, self.user_id)

    def add_notification(self, note):
        return self.add_activity(note)

    def add_activity(self, note):
        """
        Adds an activity to this user's feed
        """
        self.activity_storage.add_to_storage(note, [self.user_id])