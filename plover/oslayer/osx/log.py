import logging

import objc

from plover import log

NSUserNotification = objc.lookUpClass("NSUserNotification")
NSUserNotificationCenter = objc.lookUpClass("NSUserNotificationCenter")
NSObject = objc.lookUpClass("NSObject")


class NotificationHandler(logging.Handler):
    """Handler using OS X Notification Center to show messages."""

    def __init__(self):
        super().__init__()
        self.setLevel(log.WARNING)
        self.setFormatter(log.NoExceptionTracebackFormatter("%(message)s"))

        self.notification_center = (
            NSUserNotificationCenter.defaultUserNotificationCenter()
        )
        if self.notification_center is None:
            print(
                "no notification center available (e.g. when running from source); not showing notifications"
            )
            self.always_present_delegator = None
        else:
            self.always_present_delegator = AlwaysPresentNSDelegator.alloc().init()

    def handle(self, record):
        if self.notification_center is None:
            # not showing notifications
            return

        # Notification Center has no levels or timeouts.
        notification = NSUserNotification.alloc().init()

        notification.setTitle_(record.levelname.title())
        notification.setInformativeText_(self.format(record))

        self.notification_center.setDelegate_(self.always_present_delegator)
        self.notification_center.deliverNotification_(notification)


class AlwaysPresentNSDelegator(NSObject):
    """
    Custom delegator to force presenting even if Plover is in the foreground.
    """

    def userNotificationCenter_didActivateNotification_(self, ns, note):
        # Do nothing
        return

    def userNotificationCenter_shouldPresentNotification_(self, ns, note):
        # Force notification, even if frontmost application.
        return True
