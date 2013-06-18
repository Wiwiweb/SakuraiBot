#!/usr/bin/python
'''
Created on 2013-06-14
Author: Wiwiweb

Reddit bot to fetch Miiverse posts by Smash Bros creator Sakurai.

Some parts inspired by reddit-xkcdbot's source code.
https://github.com/trisweb/reddit-xkcdbot
'''

import praw
import logging
import sys
import urllib2
from bs4 import BeautifulSoup
from time import sleep
import datetime

VERSION = "1.0"
FREQUENCY = 300
SAKURAI_BABBLE = "Sakurai: (laughs)"

PASSWORD_FILENAME = "../res/private/reddit-password.txt"
COOKIE_FILENAME = "../res/private/miiverse-cookie.txt"
LAST_POST_FILENAME = "../res/last-post.txt"

USERNAME = "SakuraiBot"
MIIVERSE_URL = "https://miiverse.nintendo.net"
MAIN_PATH = "/titles/14866558073037299863/14866558073037300685"

if len(sys.argv) > 1 and sys.argv[1] == "--debug":
    debug = True
    subreddit = "reddit_api_test"
else:
    debug = False
    subreddit = "smashbros"

if debug:
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s: %(message)s')
else:
    logging.basicConfig(filename='sakurai.log', level=logging.INFO, format='%(asctime)s: %(message)s')

logging.info("--- Starting sakuraibot ---")    
    
passf = open(PASSWORD_FILENAME, "r")
password = passf.read().strip()
passf.close()

cookief = open(COOKIE_FILENAME, "r")
cookie = cookief.read().strip()
cookief.close()

class PostDetails:
    def __init__(self, author, text, picture):
        self.author = author
        self.text = text
        self.picture = picture

def getMiiverseLastPost():
    """Fetches the URL path to the last Miiverse post in the Director's room."""
    req = urllib2.Request(MIIVERSE_URL + MAIN_PATH)
    req.add_header("Cookie", cookie)
    page = urllib2.urlopen(req).read()
    soup = BeautifulSoup(page)
    print page
    post_url = soup.find("div", {"class":"post"}).get("data-href")
    logging.info("Last post found: " + post_url)
    return post_url

    
def isNewPost(post_url):
    """Compares the latest post URL to the ones we already processed, to see if it is new."""
    postf = open(LAST_POST_FILENAME, "r")
    last_post = postf.read()
    postf.close()
    if last_post == post_url:
        logging.info("Post was already posted")
        return False
    else:
        logging.info("Post is new!")
        return True


def getInfoFromPost(post_url):
    """Fetches author, text and picture URL from the post (and possibly more later)"""
    req = urllib2.Request(MIIVERSE_URL + post_url)
    req.add_header("Cookie", cookie)
    page = urllib2.urlopen(req).read()
    soup = BeautifulSoup(page)
    
    author = soup.find("p", {"class":"user-name"}).find("a").get_text()
    logging.info("Post author: " + author)
    
    text = soup.find("p", {"class":"post-content-text"}).get_text()
    logging.info("Post text: " + text)
    
    screenshot_container = soup.find("div", {"class":"screenshot-container"})
    if screenshot_container == None:
        picture_url = None
        logging.info("No picture found.")
    else:
        picture_url = screenshot_container.find("img").get("src")
        logging.info("Post picture: " + picture_url)
    
    return PostDetails(author, text, picture_url)
    
def postToReddit(post_details):
    """Posts the new Miiverse post to /r/smashbros"""
    user_agent = "SakuraiBot v" + VERSION + " by /u/Wiwiweb"
    r = praw.Reddit(user_agent=user_agent)
    r.login(USERNAME, password)
    logging.info("Logged into Reddit.")
    
    title = "New " + post_details.author + " post! \"" + post_details.text + "\""
    if post_details.picture == None:
        # Self post
        title = "New " + post_details.author + " post! (" + datetime.datetime.now().strftime("%y-%m-%d") + ") \"" + post_details.text + "\" (No picture)"
        submission = r.submit(subreddit, title, text=SAKURAI_BABBLE)
        logging.info("New self-post posted! " + submission.short_link)
    else:
        # Link post
        title = "New " + post_details.author + " picture! \"" + post_details.text + "\""
        submission = r.submit(subreddit, title, url=post_details.picture)
        logging.info("New submission posted!" + submission.short_link)


def setLastPost(post_url):
    """Replaces the last post remembered with the argument."""
    postf = open(LAST_POST_FILENAME, "w")
    postf.write(post_url)
    postf.close()

    

# Main loop
try:
    while True:
        try:
            
            logging.info("Starting the cycle again.")
            post_url = getMiiverseLastPost()
            if isNewPost(post_url):
                post_details = getInfoFromPost(post_url)
                postToReddit(post_details)
                if not debug:
                    setLastPost(post_url)
            
            if debug:
                quit()
        except urllib2.HTTPError as e:
            logging.error("ERROR: HTTPError code " + e.code + " encountered while making request - sleeping another iteration and retrying.")
        except urllib2.URLError as e:
            logging.info("URLError: " + e.reason + ". Sleeping another iteration and retrying.")
        except Exception as e:
            logging.info("Unknown error: " + str(e) + ". Sleeping another iteration and retrying.")
        sleep(FREQUENCY)
        
except (KeyboardInterrupt):
    logging.info("Keyboard interrupt detected, shutting down Sakuraibot.")
    quit()
