#!/usr/bin/env python3
"""
Main functions of the Reddit bot.

Fetches Miiverse posts by Smash Bros creator Sakurai.
Created on 2013-06-14
Author: Wiwiweb

"""

from base64 import b64encode
from configparser import ConfigParser
from datetime import datetime
import hashlib
from logging import getLogger
from random import randint
from time import sleep

from bs4 import BeautifulSoup
import praw
import requests

CONFIG_FILE = "../cfg/config.ini"
CONFIG_FILE_PRIVATE = "../cfg/config-private.ini"
config = ConfigParser()
config.read([CONFIG_FILE, CONFIG_FILE_PRIVATE])


VERSION = "2.0"
USER_AGENT = "SakuraiBot v" + VERSION + " by /u/Wiwiweb for /r/smashbros"

LAST_PICTURE_MD5_FILENAME = "../res/last-picture-md5.txt"
SAKURAI_BABBLES_FILENAME = "../res/sakurai-babbles.txt"

MIIVERSE_URL = "https://miiverse.nintendo.net"
MIIVERSE_CALLBACK_URL = "https://miiverse.nintendo.net/auth/callback"
MIIVERSE_DEVELOPER_PAGE = "/titles/14866558073037299863/14866558073037300685"
IMGUR_UPLOAD_URL = "https://api.imgur.com/3/image"
IMGUR_REFRESH_URL = "https://api.imgur.com/oauth2/token"
SMASH_DAILY_PIC = "http://www.smashbros.com/update/images/daily.jpg"
NINTENDO_LOGIN_PAGE = "https://id.nintendo.net/oauth/authorize"

REDDIT_TITLE_LIMIT = 300
IMGUR_TITLE_LIMIT = 128

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
    def __init__(self, username, subreddit, imgur_album,
                 last_post_filename,
                 extra_comment_filename,
                 picture_md5_filename,
                 logger=getLogger(), debug=False):
        self.username = username
        self.subreddit = subreddit
        self.imgur_album = imgur_album
        self.last_post_filename = last_post_filename
        self.extra_comment_filename = extra_comment_filename
        self.picture_md5_filename = picture_md5_filename
        self.logger = logger
        self.debug = debug
        self.dont_retry = False

    def get_new_miiverse_cookie(self):
        parameters = {'client_id': 'ead88d8d450f40ada5682060a8885ec0',
                      'response_type': 'code',
                      'redirect_uri': MIIVERSE_CALLBACK_URL,
                      'username': config['Miiverse']['username'],
                      'password': config['Passwords']['miiverse']}
        self.logger.debug("Parameters: " + str(parameters))
        req = requests.post(NINTENDO_LOGIN_PAGE, data=parameters)
        miiverse_cookie = req.history[1].cookies['ms']
        if miiverse_cookie is None:
            self.logger.debug("Page: " + req.text)
            self.logger.debug("History: " + req.history)
            raise Exception("Couldn't retrieve miiverse cookie.")
        return miiverse_cookie

    def get_miiverse_last_post(self, miiverse_cookie):
        """Fetch the URL path to the last Miiverse post."""
        cookies = {'ms': miiverse_cookie}
        req = requests.get(MIIVERSE_URL + MIIVERSE_DEVELOPER_PAGE,
                           cookies=cookies)
        soup = BeautifulSoup(req.text)
        post_url_class = soup.find('div', class_='post')
        if post_url_class is not None:
            post_url = post_url_class.get('data-href')
            self.logger.info("Last post found: " + post_url)
            return post_url
        elif soup.find('form', {'id': 'login_form'}):
            self.logger.error("ERROR: Could not sign in to Miiverse."
                              " Shutting down.")
            quit()
        else:
            self.logger.debug("Page: " + req.text)
            raise Exception("Couldn't retrieve miiverse info.")

    def is_new_post(self, post_url):
        """Compare the latest post URL to the ones we already processed."""
        postf = open(self.last_post_filename, 'r')

        # We have to check 50 posts, because sometimes Miiverse will mess up
        # the order and we might think it's a new post even though it's not.
        for _ in range(49):  # Only 50 posts on the first page.
            seen_post = postf.readline().strip()
            if seen_post == post_url:
                postf.close()
                self.logger.info("Post was already posted")
                return False
            elif not seen_post:  # No more lines.
                break

        postf.close()
        self.logger.info("Post is new!")
        return True

    def get_current_pic_md5(self):
        """Get the md5 of the current smashbros.com pic."""
        req = requests.get(SMASH_DAILY_PIC)
        md5 = hashlib.md5()
        md5.update(req.content)
        current_md5 = md5.hexdigest()
        self.logger.debug("Current pic md5: " + current_md5)
        return current_md5

    def is_website_new(self, current_md5):
        """Compare the smashbros pic md5 to the last md5 posted."""
        f = open(self.picture_md5_filename, 'r')
        last_md5 = f.read().strip()
        f.close()

        if current_md5 == last_md5:
            self.logger.info("Same website picture as before.")
            return False
        else:
            self.logger.info("Website picture has changed!")
            return True

    def get_info_from_post(self, post_url, miiverse_cookie):
        """Fetch author, text and picture URL from the post."""
        cookies = {'ms': miiverse_cookie}
        req = requests.get(MIIVERSE_URL + post_url, cookies=cookies)
        soup = BeautifulSoup(req.text)

        author = soup.find('p', class_='user-name').find('a').get_text()
        self.logger.info("Post author: " + author)

        text = soup.find('p', class_='post-content-text') \
            .get_text().strip()
        self.logger.debug("Text of type: " + str(type(text)))
        self.logger.info("Post text: " + text)

        screenshot_container = soup.find('div', class_='screenshot-container')
        if screenshot_container is None:
            # Text post
            picture_url = None
            video_url = None
            self.logger.info("No picture or video found.")
        elif 'video' in screenshot_container['class']:
            # Video post
            picture_url = None
            video_url = soup.find('p', class_='url-link') \
                .find('a').get('href')
            self.logger.info("Post video: " + video_url)
        else:
            # Picture post
            picture_url = screenshot_container.find('img').get('src')
            video_url = None
            self.logger.info("Post picture: " + picture_url)

        return PostDetails(author, text, picture_url, video_url, None)

    def upload_to_imgur(self, post_details):
        """Upload the picture to imgur and returns the link."""

        # Get image base64 data
        # We could send the url to imgur directly
        # but sometimes imgur will not see the same image
        req = requests.get(SMASH_DAILY_PIC)
        pic_base64 = b64encode(req.content)

        retries = 5
        picture_url = ''

        # Request new access token
        imgur_access_token = ''
        while True:
            try:
                parameters = {'refresh_token':
                              config['Passwords']['imgur_refresh_token'],
                              'client_id': config['Imgur']['client_id'],
                              'client_secret':
                              config['Passwords']['imgur_client_secret'],
                              'grant_type': 'refresh_token'}
                self.logger.debug("Token request parameters: "
                                  + str(parameters))
                req = requests.post(IMGUR_REFRESH_URL, data=parameters)
                imgur_access_token = req.json()['access_token']
                break
            except requests.HTTPError as e:
                retries -= 1
                if retries == 0:
                    raise
                else:
                    self.logger.error(
                        "ERROR: HTTPError: " + str(e.response.status_code) +
                        ". Retrying imgur upload" + retries +
                        " more times.")
                    sleep(2)
                    continue

        # Upload picture
        while True:
            try:
                title = post_details.text
                description = ''
                if len(title) > IMGUR_TITLE_LIMIT:
                    too_long = ' [...]'
                    allowed_text_length = IMGUR_TITLE_LIMIT - len(too_long)
                    while len(title) > allowed_text_length:
                        title = title.rsplit(' ', 1)[0]  # Remove last word
                    title += too_long
                    description = post_details.text
                parameters = {'image': pic_base64,
                              'title': title,
                              'album_id': self.imgur_album,
                              'description': description,
                              'type': 'base64'}
                self.logger.debug("Upload request parameters: "
                                  + str(parameters))
                headers = {'Authorization': 'Bearer ' + imgur_access_token}
                req = requests.post(IMGUR_UPLOAD_URL, data=parameters,
                                    headers=headers)

                picture_url = req.json()['data']['link']
                self.logger.info("Uploaded to imgur! " + picture_url)
                break
            except requests.HTTPError as e:
                retries -= 1
                if retries == 0:
                    raise e
                else:
                    self.logger.error(
                        "ERROR: HTTPError: " + str(e.response.status_code) +
                        ". Retrying.")
                    sleep(2)
                    continue

        return picture_url

    def get_random_babble(self):
        """Get a random funny Sakurai-esque quote."""
        rint = randint(0, len(sakurai_babbles) - 1)
        return sakurai_babbles[rint]

    def post_to_reddit(self, post_details):
        """Post the Miiverse post to subreddit and returns the submission."""
        r = praw.Reddit(user_agent=USER_AGENT)
        r.login(self.username, config['Passwords']['reddit'])
        self.logger.info("Logged into Reddit.")

        date = datetime.now().strftime('%y-%m-%d')
        author = post_details.author
        title_format = "New " + author + " {type}! (" + \
                       date + ") {text}{extra}"
        text_too_long = False
        text_post = False
        extra = ''
        url = ''
        submission = None
        if post_details.picture is None and post_details.video is None:
            # Self post
            text_post = True
            post_type = "post"
            extra = " (No picture)"
        else:
            if post_details.video is None:
                # Picture post
                post_type = "picture"
                url = post_details.smashbros_pic
            else:
                # Video post
                post_type = "video"
                url = post_details.video

        text = '"' + post_details.text + '"'
        title = title_format.format(type=post_type, text=text, extra=extra)
        self.logger.debug("Title: " + title)
        self.logger.debug("Title length: " + str(len(title)))
        self.logger.debug("Encoded title length : " +
                          str(len(title.encode('utf-8'))))
        if len(title) > REDDIT_TITLE_LIMIT:
            if text_post:
                too_long_type = "post"
            else:
                too_long_type = "comment"
            too_long = ' [...]" (Text too long! See {})'.format(too_long_type)

            allowed_text_length = \
                len(text) \
                - (len(title) - REDDIT_TITLE_LIMIT) \
                - len(too_long)
            while len(text) > allowed_text_length:
                text = text.rsplit(' ', 1)[0]  # Remove last word
            text += too_long
            title = title_format.format(type=post_type,
                                        text=text,
                                        extra=extra)
            text_too_long = True

        if not text_post:
            self.dont_retry = True
            submission = r.submit(self.subreddit, title, url=url)
            self.logger.info("New submission posted! " + submission.short_link)

        # Additional comment
        comment = '{full_text} \n\n' \
                  '{original_picture} {album_link} \n\n' \
                  '{extra_comment}'
        if text_too_long:
            # Reddit formatting
            reddit_text = post_details.text.replace("\r\n", "  \n")
            full_text = "Full text:  \n>" + reddit_text
            self.logger.info("Text too long. Added to comment.")
        else:
            full_text = ''
        if post_details.picture is not None:
            original_picture = ("[Original Miiverse picture]("
                                + post_details.picture + ") |")
        else:
            original_picture = ''
        album_link = ("[Pic of the Day album](http://imgur.com/a/"
                      + self.imgur_album + ")")
        f = open(self.extra_comment_filename, 'a+')
        extra_comment = f.read().strip()
        if not self.debug:
            f.truncate(0)  # Erase file
        f.close()

        comment = comment.format(full_text=full_text,
                                 original_picture=original_picture,
                                 album_link=album_link,
                                 extra_comment=extra_comment)
        comment = comment.strip()

        if text_post:
            self.dont_retry = True
            if comment != '':
                submission = r.submit(self.subreddit, title, text=comment)
                self.logger.info("New self-post posted with extra text! "
                                 + submission.short_link)
            else:
                babble = self.get_random_babble()
                submission = r.submit(self.subreddit, title, text=babble)
                self.logger.info("New self-post posted with no extra text! "
                                 + submission.short_link)
        else:
            if comment != '':
                submission.add_comment(comment)
                self.logger.info("Comment posted.")
            else:
                self.logger.info("No comment posted.")

        # Adding flair
        r.select_flair(submission, config['Reddit']['ssb4_flair'])
        self.logger.info("Tagged as SSB4.")

        return r.get_submission(submission_id=submission.id, comment_limit=1)

    def set_last_post(self, post_url):
        """Add the post URL to the top of the last-post.txt file."""
        postf = open(self.last_post_filename, 'r+')
        old = postf.read()
        postf.seek(0)
        postf.write(post_url + "\n" + old)
        postf.close()
        self.logger.info("New post remembered.")

    def update_md5(self, current_md5):
        """Update the md5 in the last-picture-md5.txt file."""
        postf = open(self.picture_md5_filename, 'w')
        postf.write(current_md5)
        postf.close()
        self.logger.info("Md5 updated.")

    def bot_cycle(self):
        self.logger.debug("Entering get_new_miiverse_cookie()")
        miiverse_cookie = self.get_new_miiverse_cookie()
        self.logger.debug("Entering get_miiverse_last_post()")
        post_url = self.get_miiverse_last_post(miiverse_cookie)

        self.logger.debug("Entering is_new_post()")
        if self.is_new_post(post_url) or self.debug:
            self.logger.debug("Entering get_current_pic_md5()")
            current_md5 = self.get_current_pic_md5()

            self.logger.debug("Entering is_website_new()")
            if self.is_website_new(current_md5) or self.debug:

                self.logger.debug("Entering get_info_from_post()")
                post_details = self.get_info_from_post(post_url,
                                                       miiverse_cookie)

                if post_details.is_picture_post():
                    self.logger.debug("Entering upload_to_imgur()")
                    post_details.smashbros_pic = \
                        self.upload_to_imgur(post_details)
                self.logger.debug("Entering post_to_reddit()")
                self.post_to_reddit(post_details)
                if not self.debug:
                    self.logger.debug("Entering set_last_post()")
                    self.set_last_post(post_url)
                    self.logger.debug("Entering update_md5()")
                    self.update_md5(current_md5)
