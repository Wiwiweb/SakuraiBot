#!/usr/bin/env python3

import logging
from logging.handlers import RotatingFileHandler
import smtplib
import subprocess
from time import sleep

LOG_FILE_DEBUG = "../logs/statuscheck.log"
MAIL_ADDRESS = "sakuraibotalert@gmail.com"
SENDER_MAIL_ADDRESS = "sakuraibotalert@gmail.com"
SMTP_HOST = "smtp.gmail.com:587"
MAIL_PASSWORD_FILENAME = "../res/private/mail-password.txt"

f = open(MAIL_PASSWORD_FILENAME, 'r')
mail_password = f.read().strip()
f.close()

root_logger = logging.getLogger()
debug_handler = RotatingFileHandler(LOG_FILE_DEBUG, maxBytes=102400,
                                    backupCount=1)
debug_handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s'))
debug_handler.setLevel(logging.DEBUG)
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(debug_handler)


def send_alert_mail():
    message = ("From: Script Alert: SakuraiBot <" + MAIL_ADDRESS + ">\n" +
               "Subject: SakuraiBot stopped unexpectedly! " +
               "(checkstatus.sh)\n\n")
    f = open(LOG_FILE_DEBUG, 'r')
    log_content = f.read()
    f.close()
    message += log_content
    try:
        smtp = smtplib.SMTP(SMTP_HOST)
        smtp.starttls()
        logging.debug(MAIL_ADDRESS)
        logging.debug(mail_password)
        smtp.login(MAIL_ADDRESS, mail_password)
        smtp.sendmail(MAIL_ADDRESS, MAIL_ADDRESS, message)
        logging.info("Alert email sent.")
    except smtplib.SMTPException as e:
        logging.error("ERROR: Couldn't send alert email: " + str(e))

if __name__ == '__main__':
    while True:
        ps = subprocess.Popen(
            "ps -eo cmd,etime | grep '__init__.py' | grep -v grep | awk '{print("
            "$3)}'",
            shell=True, stdout=subprocess.PIPE)
        output = ps.stdout.read()
        ps.stdout.close()
        ps.wait()

        if output == "":
            logging.error("SakuraiBot stopped!")
            send_alert_mail()
            quit()
        else:
            logging.info("SakuraiBot running. Uptime: " + output)

        sleep(30)
