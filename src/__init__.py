#!/usr/bin/env python3
"""
Initialises and runs the bot in a loop.

Created on 2013-07-24
Author: Wiwiweb

"""

from configparser import ConfigParser
import logging
import smtplib
import sys
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
from time import sleep

import requests

from sakuraibot import SakuraiBot


CONFIG_FILE = "../cfg/config.ini"
CONFIG_FILE_PRIVATE = "../cfg/config-private.ini"
config = ConfigParser()
config.read([CONFIG_FILE, CONFIG_FILE_PRIVATE])


# -------------------------------------------------
# Main loop
# -------------------------------------------------

if len(sys.argv) > 1 and '--debug' in sys.argv:
    debug = True
    username = config['Reddit']['test_username']
    subreddit = config['Reddit']['test_subreddit']
    imgur_album_id = config['Imgur']['test_album_id']
    other_subreddits = list(config['Reddit']['test_subreddit'])
else:
    debug = False
    username = config['Reddit']['username']
    subreddit = config['Reddit']['subreddit']
    imgur_album_id = config['Imgur']['album_id']
    other_subreddits = config['Passwords']['new_char_subreddits'].split(', ')

root_logger = logging.getLogger()
if debug:
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                        format='%(asctime)s: %(message)s')
else:
    # Logging
    timed_handler = TimedRotatingFileHandler(config['Files']['logfile'],
                                             'midnight')
    timed_handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s'))
    timed_handler.setLevel(logging.INFO)
    debug_handler = RotatingFileHandler(config['Files']['debug_logfile'],
                                        maxBytes=102400,
                                        backupCount=1)
    debug_handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s'))
    debug_handler.setLevel(logging.DEBUG)
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(timed_handler)
    root_logger.addHandler(debug_handler)

if len(sys.argv) > 1 and '--miiverse' in sys.argv:
    miiverse_main = True
    logging.info("Main pic: Miiverse")
else:
    miiverse_main = False
    logging.info("Main pic: smashbros.com")


def send_alert_mail():
    message = ("From: Script Alert: SakuraiBot <" +
               config['Mail']['sender_address'] + ">\n" +
               "Subject: SakuraiBot stopped unexpectedly!\n\n")
    f = open(config['Files']['debug_logfile'], 'r')
    log_content = f.read()
    f.close()
    message += log_content
    try:
        smtp = smtplib.SMTP(config['Mail']['smtp_host'])
        smtp.starttls()
        logging.debug(config['Mail']['sender_address'])
        logging.debug(config['Passwords']['mail'])
        smtp.login(config['Mail']['sender_address'],
                   config['Passwords']['mail'])
        smtp.sendmail(config['Mail']['sender_address'],
                      config['Mail']['address'], message)
        logging.info("Alert email sent.")
    except smtplib.SMTPException as e:
        logging.error("ERROR: Couldn't send alert email: " + str(e))


global_retries = 5


def retry_or_die(dont_retry):
    global global_retries
    if global_retries == 0 or dont_retry:
        logging.error("ERROR: Shutting down SakuraiBot.")
        send_alert_mail()
        quit()
    else:
        global_retries -= 1
        logging.error("ERROR: Sleeping another cycle and retrying "
                      + str(global_retries) + " more times.")


if __name__ == '__main__':
    logging.info("--- Starting sakuraibot ---")
    sbot = SakuraiBot(username, subreddit, other_subreddits, imgur_album_id,
                      config['Files']['last_post'],
                      config['Files']['extra_comment'],
                      config['Files']['picture_md5'],
                      config['Files']['last_char'],
                      debug=debug)
    try:
        while True:
            try:
                logging.info("Starting the cycle again.")
                sbot.bot_cycle()
                logging.debug("End of cycle.")
                if debug:  # Don't loop in debug
                    quit()
                global_retries = 5
                sbot.dont_retry = False

            except requests.HTTPError as e:
                logging.exception(
                    "ERROR: HTTPError code " + str(e.response.status_code) +
                    " encountered while making request.")
                retry_or_die(sbot.dont_retry)
            except Exception as e:
                logging.exception("ERROR: Unknown error: " + str(e))
                retry_or_die(sbot.dont_retry)

            sleep(int(config['Main']['frequency']))

    except KeyboardInterrupt:
        logging.info("Keyboard interrupt detected, shutting down Sakuraibot.")
        quit()
