"""Cyberjunky's 3Commas bot helpers."""
import json
import logging
import os
import queue
import threading
import time
from logging.handlers import TimedRotatingFileHandler as _TimedRotatingFileHandler

import apprise
from apprise import NotifyFormat

class NotificationHandler:
    """Notification class."""

    def __init__(self, program, enabled=False, notify_urls=None):
        self.program = program
        self.message = ""

        if enabled and notify_urls:
            self.apobj = apprise.Apprise()
            urls = json.loads(notify_urls)
            for url in urls:
                self.apobj.add(url)
            self.queue = queue.Queue()
            self.start_worker()
            self.enabled = True
        else:
            self.enabled = False

    def start_worker(self):
        """Start notification worker."""
        threading.Thread(target=self.process_queue, daemon=True).start()

    def process_queue(self):
        """Process the queue."""
        while True:
            message, attachments = self.queue.get()
            if attachments:
                self.apobj.notify(body=message, attach=attachments, body_format=NotifyFormat.TEXT)
            else:
                self.apobj.notify(body=message, body_format=NotifyFormat.TEXT)
            self.queue.task_done()

    def queue_notification(self, message):
        """Queue notification messages."""
        if self.enabled:
            message.encode(encoding = 'UTF-8', errors = 'strict')
            self.message += f"{message}\r\n \r\n"

    def send_notification(self):
        """Send the notification messages if there are any."""
        if self.enabled and self.message:
            msg = f"[3C Cyber Bot-Helper {self.program}]\r\n \r\n" + self.message
            self.queue.put((msg, []))
            self.message = ""


class TimedRotatingFileHandler(_TimedRotatingFileHandler):
    """Override original code to fix bug with not deleting old logfiles."""

    def __init__(self, filename="", when="midnight", interval=1, backupCount=7, encoding='utf-8'):
        super().__init__(
            filename=filename,
            when=when,
            interval=int(interval),
            backupCount=int(backupCount),
            encoding=encoding
        )

    def getFilesToDelete(self):
        """Find all logfiles present."""
        dirname, basename = os.path.split(self.baseFilename)
        filenames = os.listdir(dirname)
        result = []
        prefix = basename + "."
        plen = len(prefix)
        for filename in filenames:
            if filename[:plen] == prefix:
                suffix = filename[plen:]
                if self.extMatch.match(suffix):
                    result.append(os.path.join(dirname, filename))
        result.sort()
        if len(result) < self.backupCount:
            result = []
        else:
            result = result[: len(result) - self.backupCount]
        return result

    def doRollover(self):
        """Delete old logfiles but keep latest backupCount amount."""
        super().doRollover()
        self.close()
        timetuple = time.localtime(time.time())
        dfn = self.baseFilename + "." + time.strftime(self.suffix, timetuple)

        if os.path.exists(dfn):
            os.remove(dfn)

        os.rename(self.baseFilename, dfn)

        if self.backupCount > 0:
            for oldlog in self.getFilesToDelete():
                os.remove(oldlog)

        self.stream = open(self.baseFilename, "w")

        currenttime = int(time.time())
        newrolloverat = self.computeRollover(currenttime)
        while newrolloverat <= currenttime:
            newrolloverat = newrolloverat + self.interval

        self.rolloverAt = newrolloverat


class Logger:
    """Logger class."""

    my_logger = None

    def __init__(
        self,
        datadir,
        program,
        notificationhandler,
        logstokeep,
        debug_enabled,
        notify_enabled,
    ):
        """Logger init."""
        self.my_logger = logging.getLogger()
        self.datadir = datadir
        self.program = program
        self.notify_enabled = notify_enabled
        self.notificationhandler = notificationhandler

        if debug_enabled:
            self.my_logger.setLevel(logging.DEBUG)
            self.my_logger.propagate = False
        else:
            self.my_logger.setLevel(logging.INFO)
            self.my_logger.propagate = False

        date_fmt = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(
            f"%(asctime)s - {program} - %(levelname)s - %(message)s", date_fmt
        )
        console_formatter = logging.Formatter(
            f"%(asctime)s - {program} - %(levelname)s - %(message)s", date_fmt
        )
        # Create directory if not exists
        if not os.path.exists(f"{self.datadir}/logs"):
            os.makedirs(f"{self.datadir}/logs")

        # Log to file and rotate if needed
        file_handle = TimedRotatingFileHandler(
            filename=f"{self.datadir}/logs/{self.program}.log", backupCount=logstokeep, encoding='utf-8'
        )
        file_handle.setFormatter(formatter)
        self.my_logger.addHandler(file_handle)

        # Log to console
        console_handle = logging.StreamHandler()
        if debug_enabled:
            console_handle.setLevel(logging.DEBUG)
        else:
            console_handle.setLevel(logging.INFO)
        console_handle.setFormatter(console_formatter)
        self.my_logger.addHandler(console_handle)

        self.info(f"3C Cyber Bot-Helper {program}")
        self.info("Started on %s" % time.strftime("%A %H:%M:%S %Y-%m-%d"))

        if self.notify_enabled:
            self.info("Notifications are enabled")
        else:
            self.info("Notifications are disabled")

    def log(self, message, level="info"):
        """Call the log levels."""
        if level == "info":
            self.my_logger.info(message)
        elif level == "warning":
            self.my_logger.warning(message)
        elif level == "error":
            self.my_logger.error(message)
        elif level == "debug":
            self.my_logger.debug(message)

    def info(self, message, notify=False):
        """Info level."""
        self.log(message, "info")
        if self.notify_enabled and notify:
            self.notificationhandler.queue_notification(message)

    def warning(self, message, notify=True):
        """Warning level."""
        self.log(message, "warning")
        if self.notify_enabled and notify:
            self.notificationhandler.queue_notification(message)

    def error(self, message, notify=True):
        """Error level."""
        self.log(message, "error")
        if self.notify_enabled and notify:
            self.notificationhandler.queue_notification(message)

    def debug(self, message, notify=False):
        """Debug level."""
        self.log(message, "debug")
        if self.notify_enabled and notify:
            self.notificationhandler.queue_notification(message)
