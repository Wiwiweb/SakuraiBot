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
import cookielib
from urllib import urlencode
from bs4 import BeautifulSoup
from time import sleep
import datetime
import json

VERSION = "1.2"
USER_AGENT = "SakuraiBot v" + VERSION + " by /u/Wiwiweb for /r/smashbros"
FREQUENCY = 300
SAKURAI_BABBLE = "Sakurai: (laughs)"

REDDIT_PASSWORD_FILENAME = "../res/private/reddit-password.txt"
MIIVERSE_PASSWORD_FILENAME = "../res/private/miiverse-password.txt"
IMGUR_REFRESH_TOKEN_FILENAME = "../res/private/imgur-refresh-token.txt"
IMGUR_CLIENT_SECRET_FILENAME = "../res/private/imgur-client-secret.txt"

IMGUR_CLIENT_ID = "45b2e3810d7d550"
LAST_POST_FILENAME = "../res/last-post.txt"

USERNAME = "SakuraiBot"
MIIVERSE_URL = "https://miiverse.nintendo.net"
MAIN_PATH = "/titles/14866558073037299863/14866558073037300685"
IMGUR_UPLOAD_URL = "https://api.imgur.com/3/image"
IMGUR_REFRESH_URL = "https://api.imgur.com/oauth2/token"
SMASH_DAILY_PIC = "http://www.smashbros.com/update/images/daily.jpg"
NINTENDO_LOGIN_PAGE = "https://id.nintendo.net/oauth/authorize"

if len(sys.argv) > 1 and "--debug" in sys.argv:
    debug = True
    subreddit = "reddit_api_test"
else:
    debug = False
    subreddit = "smashbros"
    
if len(sys.argv) > 1 and "--miiverse" in sys.argv:
    miiverse_main = True
else:
    miiverse_main = False

if debug:
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format='%(asctime)s: %(message)s')
else:
    log_file = datetime.datetime.now().strftime("../logs/sakuraibot_%y-%m-%d.log")
    logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s: %(message)s')

logging.info("--- Starting sakuraibot ---")
    
f = open(REDDIT_PASSWORD_FILENAME, "r")
reddit_password = f.read().strip()
f.close()

f = open(IMGUR_REFRESH_TOKEN_FILENAME, "r")
imgur_token = f.read().strip()
f.close()

f = open(IMGUR_CLIENT_SECRET_FILENAME, "r")
imgur_secret = f.read().strip()
f.close()

f = open(MIIVERSE_PASSWORD_FILENAME, "r")
miiverse_password = f.read().strip()
f.close()


class PostDetails:
    def __init__(self, author, text, picture, video, smashbros_picture):
        self.author = author
        self.text = text
        self.picture = picture
        self.video = video
        self.smashbros_picture = smashbros_picture
    def isTextPost(self):
        return self.picture is None and self.video is None
    def isPicturePost(self):
        return self.picture is not None
    def isVideoPost(self):
        return self.video is not None
    
    
def getNewMiiverseCookie():
    cookies = cookielib.CookieJar()
    urllib2.HTTPCookieProcessor(cookies)
 
    cookies = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookies))
 
    parameters = {"client_id"    :"ead88d8d450f40ada5682060a8885ec0",
                  "response_type":"code",
                  "redirect_uri" :"https://miiverse.nintendo.net/auth/callback",
                  "username"     :"Wiwiweb",
                  "password"     :miiverse_password}
    data = urlencode(parameters)
    req = urllib2.Request(NINTENDO_LOGIN_PAGE, data)
    opener.open(req)
    for cookie in cookies:
        if cookie.name == "ms":
            miiverse_cookie = cookie.value
            break
    return miiverse_cookie 
  
    
def getMiiverseLastPost(miiverse_cookie):
    """Fetches the URL path to the last Miiverse post in the Director's room."""
    req = urllib2.Request(MIIVERSE_URL + MAIN_PATH)
    req.add_header("Cookie", "ms=" + miiverse_cookie)
    page = urllib2.urlopen(req).read()
    soup = BeautifulSoup(page)
    post_url_class = soup.find("div", {"class":"post"})
    if post_url_class is not None:
        post_url = post_url_class.get("data-href")
        logging.info("Last post found: " + post_url)
        return post_url
    elif soup.find("form", {"id":"login_form"}):
        logging.error("ERROR: Could not sign in to Miiverse.")
        quit()
    else:
        raise("Unknown error")
    
    
def isNewPost(post_url):
    """Compares the latest post URL to the ones we already processed, to see if it is new."""
    postf = open(LAST_POST_FILENAME, "r")
    
    # We have to check 50 posts, because sometimes Miiverse will mess up the order and we might think it's a new post even though it's not.
    for _ in range(49): # Only 50 posts on the first page.
        seen_post = postf.readline().strip()
        if seen_post == post_url:
            postf.close()
            logging.info("Post was already posted")
            return False
        elif not seen_post: # No more lines.
            break

    postf.close()
    logging.info("Post is new!")
    return True


def getInfoFromPost(post_url, miiverse_cookie):
    """Fetches author, text and picture URL from the post (and possibly more later)"""
    req = urllib2.Request(MIIVERSE_URL + post_url)
    req.add_header("Cookie", miiverse_cookie)
    page = urllib2.urlopen(req).read()
    soup = BeautifulSoup(page)
    author = soup.find("p", {"class":"user-name"}).find("a").get_text()
    logging.info("Post author: " + author)
    
    text = soup.find("p", {"class":"post-content-text"}).get_text()
    logging.info("Post text: " + text)
    
    screenshot_container = soup.find("div", {"class":"screenshot-container"})
    if screenshot_container == None:
        # Text post
        picture_url = None
        video_url = None
        logging.info("No picture or video found.")
    elif "video" in screenshot_container["class"]:
        # Video post
        picture_url = None
        video_url = soup.find("p", {"class":"url-link"}).find("a").get("href")
        logging.info("Post video: " + video_url)
    else:
        # Picture post
        picture_url = screenshot_container.find("img").get("src")
        video_url = None
        logging.info("Post picture: " + picture_url)
    
    return PostDetails(author, text, picture_url, video_url, None)
    
    
def uploadToImgur(post_details):
    """Uploads the picture to imgur and returns the link."""
    
    # Request new access token
    parameters = {"refresh_token":imgur_token,
                  "client_id"    :IMGUR_CLIENT_ID,
                  "client_secret":imgur_secret,
                  "grant_type"   :"refresh_token"}
    data = urlencode(parameters)
    req = urllib2.Request(IMGUR_REFRESH_URL, data)
    json_resp = json.loads(urllib2.urlopen(req).read())
    imgur_access_token = json_resp["access_token"]

    # Upload picture
    parameters = {"image":SMASH_DAILY_PIC,
                  "title":post_details.text,
                  "type" :"URL"}
    data = urlencode(parameters)
    req = urllib2.Request(IMGUR_UPLOAD_URL, data)
    req.add_header("Authorization", "Bearer " + imgur_access_token)
    json_resp = json.loads(urllib2.urlopen(req).read())
    
    picture_url = json_resp["data"]["link"]
    logging.info("Uploaded to imgur! " + picture_url)
    return picture_url

    
def postToReddit(post_details):
    """Posts the new Miiverse post to /r/smashbros"""
    r = praw.Reddit(user_agent=USER_AGENT)
    r.login(USERNAME, reddit_password)
    logging.info("Logged into Reddit.")
    
    date = datetime.datetime.now().strftime("%y-%m-%d")
    text_too_long = False
    text_post = False
    if post_details.picture == None:
        # Self post
        text_post = True
        title = "New " + post_details.author + " post! (" + date + ") \"" + post_details.text + "\" (No picture)"
        if len(title) > 300:
            title = "New " + post_details.author + " post! (" + date + ") (Text too long! See comments) (No picture)"
            text_too_long = True
    else:
        # Link post
        if post_details.video == None:
            title = "New " + post_details.author + " picture! (" + date + ") \"" + post_details.text + "\""
            if len(title) > 300:
                title = "New " + post_details.author + " picture! (" + date + ") (Text too long! See post)"
                text_too_long = True
            if miiverse_main:
                submission = r.submit(subreddit, title, url=post_details.picture)
            else:
                submission = r.submit(subreddit, title, url=post_details.smashbros_picture)
        else:
            title = "New " + post_details.author + " video! (" + date + ") \"" + post_details.text + "\""
            if len(title) > 300:
                title = "New " + post_details.author + " video! (" + date + ") (Text too long! See comments)"
                text_too_long = True
            submission = r.submit(subreddit, title, url=post_details.video)
        logging.info("New submission posted! " + submission.short_link)
        
    # Additional comment
    comment = ""
    if text_too_long:
        comment += "Full text:  \n>" + post_details.text.replace("\r\n", "  \n") # Reddit formatting
        logging.info("Text too long. Added to comment.")
    if post_details.smashbros_picture is not None:
        if comment is not "":
            comment += "\\n\\n"
        if miiverse_main:
            comment += "[Original Miiverse picture](" + post_details.picture + ")"
        else:
            comment += "[Smashbros.com image (Slightly higher quality)](" + post_details.smashbros_picture + ")"
        
    if text_post:
        if comment is not "":
            submission = r.submit(subreddit, title, text=comment)
            logging.info("New self-post posted with extra text! " + submission.short_link)
        else:
            submission = r.submit(subreddit, title, text=SAKURAI_BABBLE)
            logging.info("New self-post posted with no extra text! " + submission.short_link)
    else:
        if comment is not "":
            submission.add_comment(comment)
            logging.info("Comment posted.")
        else:
            logging.info("No comment posted.")
   

def setLastPost(post_url):
    """Adds the last post remembered with the argument."""
    postf = open(LAST_POST_FILENAME, "r+")
    old = postf.read()
    postf.seek(0)
    postf.write(post_url + "\n" + old)
    postf.close()
    logging.info("New post remembered.")

    

# Main loop
try:
    while True:
        try:
            log_file = datetime.datetime.now().strftime("../logs/toto.log")
            logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s: %(message)s')
            
            logging.info("Starting the cycle again.")
            miiverse_cookie = getNewMiiverseCookie()
            post_url = getMiiverseLastPost(miiverse_cookie)
            if isNewPost(post_url):
                post_details = getInfoFromPost(post_url, miiverse_cookie)
                if post_details.isPicturePost():
                    post_details.smashbros_picture = uploadToImgur(post_details)
                postToReddit(post_details)
                if not debug:
                    setLastPost(post_url)
                     
            if debug: # Don't loop
                quit()
        except urllib2.HTTPError as e:
            logging.error("ERROR: HTTPError code " + e.code + " encountered while making request - sleeping another iteration and retrying.")
        except urllib2.URLError as e:
            logging.info("ERROR: URLError: " + e.reason + ". Sleeping another iteration and retrying.")
        except Exception as e:
            logging.info("ERROR: Unknown error: " + str(e) + ". Sleeping another iteration and retrying.")
                    
        sleep(FREQUENCY)
        log_file = datetime.datetime.now().strftime("../logs/sakuraibot_%y-%m-%d.log")
        logging.basicConfig(filename=log_file)
        
except (KeyboardInterrupt):
    logging.info("Keyboard interrupt detected, shutting down Sakuraibot.")
    quit()
