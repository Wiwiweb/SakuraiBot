#!/usr/bin/python
"""
Created on 2013-07-24
Author: Wiwiweb

Initialises and runs the bot in a loop.

"""

from sakuraibot import SakuraiBot
import logging
import sys
import urllib2
from logging.handlers import TimedRotatingFileHandler
from time import sleep

FREQUENCY = 300

LOG_FILE = "../logs/sakuraibot.log"
LAST_POST_FILENAME = "../res/last-post.txt"
EXTRA_COMMENT_FILENAME = "../res/extra-comment.txt"

# -------------------------------------------------
# Main loop
# -------------------------------------------------

if len(sys.argv) > 1 and '--debug' in sys.argv:
    debug = True
    username = 'SakuraiBot_test'
    subreddit = 'SakuraiBot_test'
    imgur_album_id = 'ugL4N'
else:
    debug = False
    username = 'SakuraiBot'
    subreddit = 'smashbros'
    imgur_album_id = '8KnTr'

root_logger = logging.getLogger()
if debug:
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                        format='%(asctime)s: %(message)s')
else:
    # Logging
    timed_logger = TimedRotatingFileHandler(LOG_FILE, 'midnight')
    timed_logger.setFormatter(logging.Formatter('%(asctime)s: %(message)s'))
    timed_logger.setLevel(logging.INFO)
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(timed_logger)

retry_on_error = True

if len(sys.argv) > 1 and '--miiverse' in sys.argv:
    miiverse_main = True
    logging.info("Main pic: Miiverse")
else:
    miiverse_main = False
    logging.info("Main pic: smashbros.com")


def retry_or_die():
    if not retry_on_error:
        logging.error("ERROR: Shutting down SakuraiBot.")
        quit()
    else:
        logging.error("ERROR: Sleeping another cycle and retrying.")

if __name__ == '__main__':
    logging.info("--- Starting sakuraibot ---")
    sbot = SakuraiBot(username, subreddit, imgur_album_id,
                      LAST_POST_FILENAME, EXTRA_COMMENT_FILENAME,
                      debug=debug)
    try:
        while True:
            try:
                logging.info("Starting the cycle again.")
                sbot.bot_cycle()
                if debug:  # Don't loop in debug
                    quit()

            except urllib2.HTTPError as e:
                logging.error("ERROR: HTTPError code " + str(e.code) +
                              " encountered while making request.")
                retry_or_die()
            except urllib2.URLError as e:
                logging.error("ERROR: URLError: " + str(e.reason))
                retry_or_die()
            except Exception as e:
                logging.error("ERROR: Unknown error: " + str(e))
                retry_or_die()

            sleep(FREQUENCY)

    except KeyboardInterrupt:
        logging.info("Keyboard interrupt detected, shutting down Sakuraibot.")
        quit()
