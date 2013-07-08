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
from logging.handlers import TimedRotatingFileHandler
import sys
import urllib2
import cookielib
from urllib import urlencode
from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime
from json import loads
from random import randint
import unicodedata

VERSION = "1.4"
USER_AGENT = "SakuraiBot v" + VERSION + " by /u/Wiwiweb for /r/smashbros"
FREQUENCY = 300

REDDIT_PASSWORD_FILENAME = "../res/private/reddit-password.txt"
MIIVERSE_PASSWORD_FILENAME = "../res/private/miiverse-password.txt"
IMGUR_REFRESH_TOKEN_FILENAME = "../res/private/imgur-refresh-token.txt"
IMGUR_CLIENT_SECRET_FILENAME = "../res/private/imgur-client-secret.txt"

IMGUR_CLIENT_ID = "45b2e3810d7d550"
ID_FLAIR_SSB4 = "d31a17da-d4ad-11e2-a21c-12313d2c1c24"
LAST_POST_FILENAME = "../res/last-post.txt"
SAKURAI_BABBLES_FILENAME = "../res/sakurai-babbles.txt"

USERNAME = "SakuraiBot"
MIIVERSE_USERNAME = "Wiwiweb"
MIIVERSE_URL = "https://miiverse.nintendo.net"
MIIVERSE_CALLBACK_URL = "https://miiverse.nintendo.net/auth/callback"
MIIVERSE_DEVELOPER_PAGE = "/titles/14866558073037299863/14866558073037300685"
IMGUR_UPLOAD_URL = "https://api.imgur.com/3/image"
IMGUR_REFRESH_URL = "https://api.imgur.com/oauth2/token"
SMASH_DAILY_PIC = "http://www.smashbros.com/update/images/daily.jpg"
NINTENDO_LOGIN_PAGE = "https://id.nintendo.net/oauth/authorize"

if len(sys.argv) > 1 and '--debug' in sys.argv:
    debug = True
    subreddit = 'reddit_api_test'
else:
    debug = False
    subreddit = 'smashbros'

if debug:
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                        format='%(asctime)s: %(message)s')
else:
    # Logging
    timed_logger = TimedRotatingFileHandler('../logs/sakuraibot.log',
                                            'midnight')
    timed_logger.setFormatter(logging.Formatter('%(asctime)s: %(message)s'))
    timed_logger.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(timed_logger)

logging.info("--- Starting sakuraibot ---")

if len(sys.argv) > 1 and '--miiverse' in sys.argv:
    miiverse_main = True
    logging.info("Main pic: Miiverse")
else:
    miiverse_main = False
    logging.info("Main pic: smashbros.com")

f = open(REDDIT_PASSWORD_FILENAME, 'r')
reddit_password = f.read().strip()
f.close()

f = open(IMGUR_REFRESH_TOKEN_FILENAME, 'r')
imgur_token = f.read().strip()
f.close()

f = open(IMGUR_CLIENT_SECRET_FILENAME, 'r')
imgur_secret = f.read().strip()
f.close()

f = open(MIIVERSE_PASSWORD_FILENAME, 'r')
miiverse_password = f.read().strip()
f.close()


f = open(SAKURAI_BABBLES_FILENAME, 'r')
sakurai_babbles = []
for line in f:
    sakurai_babbles.append(line.strip())
f.close()


class PostDetails:
    def __init__(self, author, text, picture, video, smashbros_pic):
        self.author = author
        self.text = text
        self.picture = picture
        self.video = video
        self.smashbros_pic = smashbros_pic

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

    parameters = {"client_id":     "ead88d8d450f40ada5682060a8885ec0",
                  "response_type": "code",
                  "redirect_uri":  MIIVERSE_CALLBACK_URL,
                  "username":      MIIVERSE_USERNAME,
                  "password":      miiverse_password}
    data = urlencode(parameters)
    req = urllib2.Request(NINTENDO_LOGIN_PAGE, data)
    opener.open(req)
    for cookie in cookies:
        if cookie.name == 'ms':
            miiverse_cookie = cookie.value
            break
    return miiverse_cookie


def getMiiverseLastPost(miiverse_cookie):
    """Fetch the URL path to the last Miiverse post in the Director's room."""
    req = urllib2.Request(MIIVERSE_URL + MIIVERSE_DEVELOPER_PAGE)
    req.add_header("Cookie", "ms=" + miiverse_cookie)
    page = urllib2.urlopen(req).read()
    soup = BeautifulSoup(page)
    post_url_class = soup.find("div", {"class": "post"})
    if post_url_class is not None:
        post_url = post_url_class.get("data-href")
        logging.info("Last post found: " + post_url)
        return post_url
    elif soup.find("form", {"id": "login_form"}):
        logging.error("ERROR: Could not sign in to Miiverse. Shutting down.")
        quit()
    else:
        raise("Unknown error")


def isNewPost(post_url):
    """Compare the latest post URL to the ones we already processed."""
    postf = open(LAST_POST_FILENAME, 'r')

    # We have to check 50 posts, because sometimes Miiverse will mess up the
    # order and we might think it's a new post even though it's not.
    for _ in range(49):  # Only 50 posts on the first page.
        seen_post = postf.readline().strip()
        if seen_post == post_url:
            postf.close()
            logging.info("Post was already posted")
            return False
        elif not seen_post:  # No more lines.
            break

    postf.close()
    logging.info("Post is new!")
    return True


def getInfoFromPost(post_url, miiverse_cookie):
    """Fetch author, text and picture URL from the post."""
    req = urllib2.Request(MIIVERSE_URL + post_url)
    req.add_header("Cookie", "ms=" + miiverse_cookie)
    page = urllib2.urlopen(req).read()
    soup = BeautifulSoup(page)

    author = soup.find("p", {"class": "user-name"}).find("a").get_text()
    logging.info("Post author: " + author)

    text = soup.find("p", {"class": "post-content-text"}).get_text().strip()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore')
    logging.info("Post text: " + text)

    screenshot_container = soup.find("div", {"class": "screenshot-container"})
    if screenshot_container is None:
        # Text post
        picture_url = None
        video_url = None
        logging.info("No picture or video found.")
    elif "video" in screenshot_container["class"]:
        # Video post
        picture_url = None
        video_url = soup.find("p", {"class": "url-link"}).find("a").get("href")
        logging.info("Post video: " + video_url)
    else:
        # Picture post
        picture_url = screenshot_container.find("img").get("src")
        video_url = None
        logging.info("Post picture: " + picture_url)

    return PostDetails(author, text, picture_url, video_url, None)


def uploadToImgur(post_details):
    """Upload the picture to imgur and returns the link."""

    # Request new access token
    parameters = {"refresh_token": imgur_token,
                  "client_id":     IMGUR_CLIENT_ID,
                  "client_secret": imgur_secret,
                  "grant_type":    "refresh_token"}
    data = urlencode(parameters)
    req = urllib2.Request(IMGUR_REFRESH_URL, data)
    json_resp = loads(urllib2.urlopen(req).read())
    imgur_access_token = json_resp["access_token"]

    # Upload picture
    parameters = {"image": SMASH_DAILY_PIC,
                  "title": post_details.text,
                  "type":  "URL"}
    data = urlencode(parameters)
    req = urllib2.Request(IMGUR_UPLOAD_URL, data)
    req.add_header("Authorization", "Bearer " + imgur_access_token)
    json_resp = loads(urllib2.urlopen(req).read())

    picture_url = json_resp["data"]["link"]
    logging.info("Uploaded to imgur! " + picture_url)
    return picture_url


def getRandomBabble():
    """Get a random funny Sakurai-esque quote."""
    rint = randint(0, len(sakurai_babbles) - 1)
    return sakurai_babbles[rint]


def postToReddit(post_details):
    """Post the new Miiverse post to /r/smashbros."""
    r = praw.Reddit(user_agent=USER_AGENT)
    r.login(USERNAME, reddit_password)
    logging.info("Logged into Reddit.")

    date = datetime.now().strftime("%y-%m-%d")
    text_too_long = False
    text_post = False
    if post_details.picture is None:
        # Self post
        text_post = True
        title = ("New " + post_details.author + " post! (" + date + ") \""
                 + post_details.text + "\" (No picture)")
        if len(title) > 300:
            title = ("New " + post_details.author + " post! (" + date
                     + ") (Text too long! See post) (No picture)")
            text_too_long = True
    else:
        # Link post
        if post_details.video is None:
            title = ("New " + post_details.author + " picture! ("
                     + date + ") \"" + post_details.text + "\"")
            if len(title) > 300:
                title = ("New " + post_details.author + " picture! ("
                         + date + ") (Text too long! See comments)")
                text_too_long = True
            if miiverse_main:
                submission = r.submit(subreddit, title,
                                      url=post_details.picture)
            else:
                submission = r.submit(subreddit, title,
                                      url=post_details.smashbros_pic)
        else:
            title = ("New " + post_details.author + " video! ("
                     + date + ") \"" + post_details.text + "\"")
            if len(title) > 300:
                title = ("New " + post_details.author + " video! ("
                         + date + ") (Text too long! See comments)")
                text_too_long = True
            submission = r.submit(subreddit, title, url=post_details.video)
        logging.info("New submission posted! " + submission.short_link)

    # Adding flair
    # Temporary hack while PRAW gets updated
    data = {'flair_template_id': ID_FLAIR_SSB4,
            'link':              submission.fullname,
            'name':              submission.fullname}
    r.config.API_PATHS['select_flair'] = 'api/selectflair/'
    r.request_json(r.config['select_flair'], data=data)
    logging.info("Tagged as SSB4.")

    # Additional comment
    comment = ""
    if text_too_long:
        # Reddit formatting
        reddit_text = post_details.text.replace("\r\n", "  \n")
        comment += "Full text:  \n>" + reddit_text
        logging.info("Text too long. Added to comment.")
    if post_details.smashbros_pic is not None:
        if comment is not "":
            comment += "\\n\\n"
        if miiverse_main:
            comment += ("[Smashbros.com image (Slightly higher quality)]("
                        + post_details.smashbros_pic + ")")
        else:
            comment += ("[Original Miiverse picture]("
                        + post_details.picture + ")")

    if text_post:
        if comment is not "":
            submission = r.submit(subreddit, title, text=comment)
            logging.info("New self-post posted with extra text! "
                         + submission.short_link)
        else:
            babble = getRandomBabble()
            submission = r.submit(subreddit, title, text=babble)
            logging.info("New self-post posted with no extra text! "
                         + submission.short_link)
    else:
        if comment is not "":
            submission.add_comment(comment)
            logging.info("Comment posted.")
        else:
            logging.info("No comment posted.")


def setLastPost(post_url):
    """Add the last post to the top of the remembered posts file."""
    postf = open(LAST_POST_FILENAME, "r+")
    old = postf.read()
    postf.seek(0)
    postf.write(post_url + "\n" + old)
    postf.close()
    logging.info("New post remembered.")


# -------------------------------------------------
# Main loop
# -------------------------------------------------
try:
    while True:
        try:
            logging.info("Starting the cycle again.")
            miiverse_cookie = getNewMiiverseCookie()
            post_url = getMiiverseLastPost(miiverse_cookie)
            if isNewPost(post_url):
                post_details = getInfoFromPost(post_url, miiverse_cookie)
                if post_details.isPicturePost():
                    post_details.smashbros_pic = uploadToImgur(post_details)
                postToReddit(post_details)
                if not debug:
                    setLastPost(post_url)

            if debug:  # Don't loop in debug
                quit()
        except urllib2.HTTPError as e:
            logging.error("ERROR: HTTPError code " + e.code +
                          " encountered while making request "
                          "- sleeping another iteration and retrying.")
        except urllib2.URLError as e:
            logging.info("ERROR: URLError: " + str(e.reason)
                         + ". Sleeping another iteration and retrying.")
        except Exception as e:
            logging.info("ERROR: Unknown error: " + str(e)
                         + ". Sleeping another iteration and retrying.")

        sleep(FREQUENCY)

except (KeyboardInterrupt):
    logging.info("Keyboard interrupt detected, shutting down Sakuraibot.")
    quit()
