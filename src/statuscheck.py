#!/usr/bin/env python3

from configparser import ConfigParser
import logging
from logging.handlers import RotatingFileHandler
import smtplib
import subprocess
from time import sleep


LOG_FILE_DEBUG = "../logs/statuscheck.log"

CONFIG_FILE = "../cfg/config.ini"
CONFIG_FILE_PRIVATE = "../cfg/config-private.ini"
config = ConfigParser()
config.read([CONFIG_FILE, CONFIG_FILE_PRIVATE])

root_logger = logging.getLogger()
debug_handler = RotatingFileHandler(LOG_FILE_DEBUG, maxBytes=102400,
                                    backupCount=1)
debug_handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s'))
debug_handler.setLevel(logging.DEBUG)
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(debug_handler)


def send_alert_mail():
    message = ("From: Script Alert: SakuraiBot <" +
               config['Mail']['sender_address'] + ">\n" +
               "Subject: SakuraiBot stopped unexpectedly! " +
               "(checkstatus.sh)\n\n")
    f = open(LOG_FILE_DEBUG, 'r')
    log_content = f.read()
    f.close()
    message += log_content
    try:
        smtp = smtplib.SMTP(config['Mail']['smtp_host'])
        smtp.starttls()
        logging.debug(config['Mail']['sender_address'])
        smtp.login(config['Mail']['sender_address'],
                   config['Passwords']['mail'])
        smtp.sendmail(config['Mail']['sender_address'],
                      config['Mail']['address'], message)
        logging.info("Alert email sent.")
    except smtplib.SMTPException as e:
        logging.error("ERROR: Couldn't send alert email: " + str(e))


if __name__ == '__main__':

    logging.info("Statuscheck started.")
    while True:
        cmd = 'ps -eo cmd | grep "__[i]nit__.py"'

        output = subprocess.check_output(cmd, shell=True).decode().strip()

        if output == "":
            logging.error("SakuraiBot stopped!")
            send_alert_mail()
            quit()

        sleep(30)
