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

IMGUR_CLIENT_ID = '45b2e3810d7d550'
ID_FLAIR_SSB4 = 'd31a17da-d4ad-11e2-a21c-12313d2c1c24'
LAST_POST_FILENAME = "../res/last-post.txt"
SAKURAI_BABBLES_FILENAME = "../res/sakurai-babbles.txt"
EXTRA_COMMENT_FILENAME = "../res/extra-comment.txt"

USERNAME = 'SakuraiBot'
MIIVERSE_USERNAME = 'Wiwiweb'
MIIVERSE_URL = "https://miiverse.nintendo.net"
MIIVERSE_CALLBACK_URL = "https://miiverse.nintendo.net/auth/callback"
MIIVERSE_DEVELOPER_PAGE = "/titles/14866558073037299863/14866558073037300685"
IMGUR_UPLOAD_URL = "https://api.imgur.com/3/image"
IMGUR_REFRESH_URL = "https://api.imgur.com/oauth2/token"
IMGUR_ALBUM_ID = '8KnTr'
SMASH_DAILY_PIC = "http://www.smashbros.com/update/images/daily.jpg"
NINTENDO_LOGIN_PAGE = "https://id.nintendo.net/oauth/authorize"

if len(sys.argv) > 1 and '--debug' in sys.argv:
    debug = True
    subreddit = 'SakuraiBot_test'
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

    def is_text_post(self):
        return self.picture is None and self.video is None

    def is_picture_post(self):
        return self.picture is not None

    def is_video_post(self):
        return self.video is not None

class SakuraiBot:
    def __init__(self, last_post_filename, extra_comment_filename):
        self.last_post_filename = last_post_filename
        self.extra_comment_filename = extra_comment_filename

    def get_new_miiverse_cookie(self):
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
    
    
    def get_miiverse_last_post(self, miiverse_cookie):
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
    
    
    def is_new_post(self, post_url):
        """Compare the latest post URL to the ones we already processed."""
        postf = open(self.last_post_filename, 'r')
    
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
    
    
    def get_info_from_post(self, post_url, miiverse_cookie):
        """Fetch author, text and picture URL from the post."""
        req = urllib2.Request(MIIVERSE_URL + post_url)
        req.add_header('Cookie', 'ms=' + miiverse_cookie)
        page = urllib2.urlopen(req).read()
        soup = BeautifulSoup(page)
    
        author = soup.find('p', {'class': 'user-name'}).find('a').get_text()
        logging.info("Post author: " + author)
    
        text = soup.find('p', {'class': 'post-content-text'}).get_text().strip()
        logging.info("Post text: " + text)
    
        screenshot_container = soup.find('div', {'class': 'screenshot-container'})
        if screenshot_container is None:
            # Text post
            picture_url = None
            video_url = None
            logging.info("No picture or video found.")
        elif 'video' in screenshot_container['class']:
            # Video post
            picture_url = None
            video_url = soup.find('p', {'class': 'url-link'}).find('a').get('href')
            logging.info("Post video: " + video_url)
        else:
            # Picture post
            picture_url = screenshot_container.find('img').get('src')
            video_url = None
            logging.info("Post picture: " + picture_url)
    
        return PostDetails(author, text, picture_url, video_url, None)
    
    
    def upload_to_imgur(self, post_details, album_id):
        """Upload the picture to imgur and returns the link."""
    
        # Request new access token
        parameters = {'refresh_token': imgur_token,
                      'client_id':     IMGUR_CLIENT_ID,
                      'client_secret': imgur_secret,
                      'grant_type':    'refresh_token'}
        data = urlencode(parameters)
        req = urllib2.Request(IMGUR_REFRESH_URL, data)
        json_resp = loads(urllib2.urlopen(req).read())
        imgur_access_token = json_resp['access_token']
    
        # Upload picture
        parameters = {'image': SMASH_DAILY_PIC,
                      'title': post_details.text,
                      'album_id': album_id,
                      'type':  'URL'}
        data = urlencode(parameters)
        req = urllib2.Request(IMGUR_UPLOAD_URL, data)
        req.add_header('Authorization', 'Bearer ' + imgur_access_token)
        json_resp = loads(urllib2.urlopen(req).read())
    
        picture_url = json_resp['data']['link']
        logging.info("Uploaded to imgur! " + picture_url)
        return picture_url
    
    
    def get_random_babble(self):
        """Get a random funny Sakurai-esque quote."""
        rint = randint(0, len(sakurai_babbles) - 1)
        return sakurai_babbles[rint]
    
    
    def post_to_reddit(self, post_details, subreddit, username, password):
        """Post the new Miiverse post to /r/smashbros and returns the submission."""
        r = praw.Reddit(user_agent=USER_AGENT)
        r.login(username, password)
        logging.info("Logged into Reddit.")
    
        date = datetime.now().strftime('%y-%m-%d')
        author = post_details.author
        title_format = "New " + author + " {type}! (" + date + ") {text}{extra}"
        text_too_long = False
        text_post = False
        extra = ''
        if post_details.picture is None:
            # Self post
            text_post = True
            post_type = "post"
            extra = " (No picture)"
        else:
            if post_details.video is None:
                # Picture post
                post_type = "picture"
                if miiverse_main:
                    url = post_details.picture
                else:
                    url = post_details.smashbros_pic
            else:
                # Video post
                post_type = "video"
                url = post_details.video
    
        text = '"' + post_details.text + '"'
        title = title_format.format(type=post_type, text=text, extra=extra)
        if len(title) > 300:
            if text_post:
                too_long_type = "post"
            else:
                too_long_type = "comment"
            too_long = "(Text too long! See {})".format(too_long_type)
            title = title_format.format(type=post_type, text=too_long, extra=extra)
            text_too_long = True
    
        if not text_post:
            submission = r.submit(subreddit, title, url=url)
            logging.info("New submission posted! " + submission.short_link)
    
        # Additional comment
        comment = ''
        if text_too_long:
            # Reddit formatting
            reddit_text = post_details.text.replace("\r\n", "  \n")
            comment += "Full text:  \n>" + reddit_text
            logging.info("Text too long. Added to comment.")
        if post_details.smashbros_pic is not None:
            if comment != '':
                comment += "\n\n"
            if miiverse_main:
                comment += ("[Smashbros.com image (Slightly higher quality)]("
                            + post_details.smashbros_pic + ")")
            else:
                comment += ("[Original Miiverse picture]("
                            + post_details.picture + ")")
        f = open(EXTRA_COMMENT_FILENAME, 'a+')
        extra_comment = f.read().strip()
        if extra_comment != '':
            if comment != '':
                comment += "\n\n"
            comment += extra_comment
            if not debug:
                f.truncate(0)  # Erase file
        f.close()
    
        if text_post:
            if comment != '':
                submission = r.submit(subreddit, title, text=comment)
                logging.info("New self-post posted with extra text! "
                             + submission.short_link)
            else:
                babble = self.get_random_babble()
                submission = r.submit(subreddit, title, text=babble)
                logging.info("New self-post posted with no extra text! "
                             + submission.short_link)
        else:
            if comment != '':
                submission.add_comment(comment)
                logging.info("Comment posted.")
            else:
                logging.info("No comment posted.")
    
        # Adding flair
        # Temporary hack while PRAW gets updated
        data = {'flair_template_id': ID_FLAIR_SSB4,
                'link':              submission.fullname,
                'name':              submission.fullname}
        r.config.API_PATHS['select_flair'] = 'api/selectflair/'
        r.request_json(r.config['select_flair'], data=data)
        logging.info("Tagged as SSB4.")

        return submission
    
    
    def set_last_post(self, post_url):
        """Add the last post to the top of the remembered posts file."""
        postf = open(self.last_post_filename, "r+")
        old = postf.read()
        postf.seek(0)
        postf.write(post_url + "\n" + old)
        postf.close()
        logging.info("New post remembered.")


# -------------------------------------------------
# Main loop
# -------------------------------------------------
if __name__=='__main__':
    try:
        while True:
            try:
                logging.info("Starting the cycle again.")
                sbot = SakuraiBot(LAST_POST_FILENAME, EXTRA_COMMENT_FILENAME)
                miiverse_cookie = sbot.get_new_miiverse_cookie()
                post_url = sbot.get_miiverse_last_post(miiverse_cookie)
                if sbot.is_new_post(post_url) or debug:
                    post_details = sbot.get_info_from_post(post_url, miiverse_cookie)
                    if post_details.is_picture_post():
                        post_details.smashbros_pic = sbot.upload_to_imgur(post_details, IMGUR_ALBUM_ID)
                    sbot.post_to_reddit(post_details, USERNAME, reddit_password)
                    if not debug:
                        sbot.setLastPost(post_url)
    
                if debug:  # Don't loop in debug
                    quit()
            except urllib2.HTTPError as e:
                logging.error("ERROR: HTTPError code " + str(e.code) +
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
