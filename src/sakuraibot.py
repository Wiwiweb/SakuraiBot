#!/usr/bin/env python3
"""
Main functions of the Reddit bot.

Fetches Miiverse posts by Smash Bros creator Sakurai.
Created on 2013-06-14
Author: Wiwiweb

"""

from base64 import b64encode
import collections
from configparser import ConfigParser
from datetime import datetime
import hashlib
from logging import getLogger
import os
from random import randint
import re
from time import sleep
from uuid import uuid4

from bs4 import BeautifulSoup
import lurklib
import praw
import requests


CONFIG_FILE = "../cfg/config.ini"
CONFIG_FILE_PRIVATE = "../cfg/config-private.ini"
config = ConfigParser()
config.read([CONFIG_FILE, CONFIG_FILE_PRIVATE])

VERSION = "2.5"
USER_AGENT = "SakuraiBot v" + VERSION + " by /u/Wiwiweb for /r/smashbros"

LAST_PICTURE_MD5_FILENAME = "../res/last-picture-md5.txt"
LAST_CHAR_FILENAME = "../res/last-char.txt"
SAKURAI_BABBLES_FILENAME = "../res/sakurai-babbles.txt"

MIIVERSE_URL = "https://miiverse.nintendo.net"
MIIVERSE_CALLBACK_URL = "https://miiverse.nintendo.net/auth/callback"
MIIVERSE_DEV_PAGE = "/titles/14866558073037299863/14866558073037300685"
MIIVERSE_DEV_PAGE_JP = "/titles/14866558073037273112/14866558073037275469"
NINTENDO_LOGIN_PAGE = "https://id.nintendo.net/oauth/authorize"
SMASH_WEBPAGE = "http://www.smashbros.com/en-uk/"
SMASH_NEWS_PAGE = "http://www.smashbros.com/data/en-uk/news.json"
SMASH_CHARACTER_PAGE = "http://www.smashbros.com/en-uk/characters/{}.html"
SMASH_DAILY_PIC = "http://www.smashbros.com/update/images/daily-en.jpg"
IMGUR_UPLOAD_URL = "https://api.imgur.com/3/image"
IMGUR_REFRESH_URL = "https://api.imgur.com/oauth2/token"
IMGUR_SIGNIN_URL = "https://imgur.com/signin"
IMGUR_REARRANGE_URL = "http://imgur.com/ajaxalbums/rearrange/{}"
IMGUR_ALBUM_IMAGES_URL = "https://api.imgur.com/3/album/{}/images"

NEW_CHAR_REGEX = r'The introduction for (.+), (.+), is now available\.'
YOUTUBE_REGEX = \
    r'https://www\.youtube\.com/embed/(.{11})\?rel=0&modestbranding=1'

REDDIT_TITLE_LIMIT = 300
IMGUR_TITLE_LIMIT = 128

f = open(SAKURAI_BABBLES_FILENAME, 'r')
sakurai_babbles = []
for babble in f:
    sakurai_babbles.append(babble.strip())
f.close()


class PostDetails:
    def __init__(self, author, text, picture, video, smashbros_pic=None,
                 extra_posts=None):
        self.author = author
        self.text = text
        self.picture = picture
        self.video = video
        self.smashbros_pic = smashbros_pic
        if extra_posts is None:
            self.extra_posts = []
        else:
            self.extra_posts = extra_posts

    def is_text_post(self):
        return self.picture is None and self.video is None

    def is_picture_post(self):
        return self.picture is not None

    def is_video_post(self):
        return self.video is not None


# Cannot be a namedtuple because it must stay mutable when uploading to imgur
class ExtraPost:
    def __init__(self, author, text, picture):
        self.author = author
        self.text = text
        self.picture = picture


CharDetails = collections.namedtuple('CharDetails', 'char_id name description')


class SakuraiBot:
    def __init__(self, username, subreddit, other_subreddits, imgur_album,
                 last_post_filename,
                 extra_comment_filename,
                 picture_md5_filename,
                 last_char_filename,
                 logger=getLogger(), miiverse_main=False, debug=False):
        self.username = username
        self.subreddit = subreddit
        self.other_subreddits = other_subreddits
        self.imgur_album = imgur_album
        self.last_post_filename = last_post_filename
        self.extra_comment_filename = extra_comment_filename
        self.picture_md5_filename = picture_md5_filename
        self.last_char_filename = last_char_filename
        self.logger = logger
        self.miiverse_main = miiverse_main
        self.debug = debug
        self.dont_retry = False

    def get_new_miiverse_cookie(self):
        parameters = {'client_id': 'ead88d8d450f40ada5682060a8885ec0',
                      'response_type': 'code',
                      'redirect_uri': MIIVERSE_CALLBACK_URL,
                      'username': config['Miiverse']['username'],
                      'password': config['Passwords']['miiverse']}
        self.logger.debug("Parameters: " + str(parameters))
        # For some reason the nintendo id certificate fails now
        # It works fine in my browser but python and curl don't like it
        # I'll bypass the verification for now
        req = requests.post(NINTENDO_LOGIN_PAGE, data=parameters, verify=False)
        if len(req.history) < 2:
            self.logger.debug("Page: " + req.text)
            raise Exception("Couldn't retrieve miiverse cookie.")
        miiverse_cookie = req.history[1].cookies.get('ms')
        if miiverse_cookie is None:
            self.logger.debug("Page: " + req.text)
            self.logger.debug("History: ".join(req.history))
            raise Exception("Couldn't retrieve miiverse cookie.")
        return miiverse_cookie

    def get_miiverse_last_post(self, miiverse_cookie, japanese=False):
        """Fetch the URL path to the last Miiverse post."""
        cookies = {'ms': miiverse_cookie}
        if japanese:
            dev_page = MIIVERSE_DEV_PAGE_JP
        else:
            dev_page = MIIVERSE_DEV_PAGE
        req = requests.get(MIIVERSE_URL + dev_page,
                           cookies=cookies)
        soup = BeautifulSoup(req.text)
        post_url_class = soup.find('div', class_='post')
        if post_url_class is not None:
            post_url = post_url_class.get('data-href')
            self.logger.info("Last post found: " + post_url)
            return post_url
        elif soup.find('form', {'id': 'login_form'}):
            raise Exception("ERROR: Could not sign in to Miiverse."
                            " Shutting down.")
        else:
            self.logger.debug("Page: " + req.text)
            raise Exception("Couldn't retrieve miiverse info.")

    def is_new_post(self, post_url):
        """Compare the latest post URL to the ones we already processed."""
        postf = open(self.last_post_filename, 'r')
        lines = postf.readlines()
        postf.close()

        # We have to check all posts, because sometimes Miiverse will mess up
        # the order and we might think it's a new post even though it's not.
        # Apparently it's not limited to the first page, so 50 isn't enough.
        for line in lines:
            seen_post = line.strip()
            if seen_post == post_url:
                self.logger.info("Post was already posted")
                return False
            elif not seen_post:  # No more lines.
                break

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
        self.logger.debug("last_md5: " + last_md5)

        if current_md5 == last_md5:
            self.logger.info("Same website picture as before.")
            return False
        else:
            self.logger.info("Website picture has changed!")
            return True

    def get_new_char(self):
        req = requests.get(SMASH_NEWS_PAGE)
        news = req.json()['news']
        for single_news in news:
            match = re.match(NEW_CHAR_REGEX, single_news['content'])
            if match:
                last_char_news = single_news
                break
        else:
            return None
        self.logger.debug("Last news post: " + last_char_news['content'])
        self.logger.debug("Last news href: " + last_char_news['href'])
        char_id = last_char_news['href'][17:-5]
        file = open(self.last_char_filename, 'r')
        last_char = file.read().strip()
        file.close()
        self.logger.debug("Char id: " + char_id)
        self.logger.debug("Last char: " + last_char)
        if char_id != last_char:
            # We've got a new char, get info
            char_name = match.group(2)
            self.logger.info("New character announced!")
            self.logger.info("Char name: " + char_name)
            if re.search(r'veteran', match.group(1)):
                char_description = 'Veteran fighter'
            else:
                char_description = 'New challenger'
            self.logger.debug("Char description: " + char_description)
            return CharDetails(char_id, char_name, char_description)
        return None

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

        screenshot_containers = \
            soup.find_all('div', class_='screenshot-container')
        if not screenshot_containers:
            # Text post
            picture_url = None
            video_url = None
            self.logger.info("No picture or video found.")
        else:
            image = None
            for item in screenshot_containers:
                image = item.find('img')
                if image:
                    break

            if image:
                # Picture post
                picture_url = image.get('src')
                video_url = None
                self.logger.info("Post picture: " + picture_url)
            else:
                # Video post and nothing else
                picture_url = None
                # If there's multiple videos (not that it even happened)
                # we'll take the first one
                embed_url = screenshot_containers[0].find('iframe').get('src')
                video_id = re.match(YOUTUBE_REGEX, embed_url).group(1)
                video_url = 'https://www.youtube.com/watch?v=' + video_id
                self.logger.info("Post video: " + video_url)

        # Check for extra image in comments
        extra_posts_soup = soup.find_all('li', class_='official-user')
        extra_posts = []
        if extra_posts_soup:
            for extra_post in extra_posts_soup:
                self.logger.info("Found an extra post!")
                extra_author = extra_post.find('p', class_='user-name') \
                    .find('a').get_text()
                self.logger.info("Extra post author: " + extra_author)
                extra_text = \
                    extra_post.find('p', class_='reply-content-text') \
                    .get_text().strip()
                self.logger.info("Extra post text: " + extra_text)
                extra_screenshot_container = \
                    extra_post.find('div', class_='screenshot-container')
                if extra_screenshot_container is not None:
                    extra_picture = \
                        extra_screenshot_container.find('img').get('src')
                    self.logger.info("Extra picture: " + extra_picture)
                else:
                    self.logger.info("No extra picture.")
                    extra_picture = None
                extra_posts.append(
                    ExtraPost(extra_author, extra_text, extra_picture))
        else:
            self.logger.info("No extra post found.")

        return PostDetails(author, text, picture_url, video_url, None,
                           extra_posts)

    def upload_to_imgur(self, post_details, website_give_up=False):
        """Upload the picture to imgur and returns the link."""

        # Get image base64 data
        # We could send the url to imgur directly
        # but sometimes imgur will not see the same image
        if not website_give_up:
            picture = SMASH_DAILY_PIC
        else:
            picture = post_details.picture
        req = requests.get(picture)
        pic_base64 = b64encode(req.content)

        retries = 5
        picture_url = ''

        # Request new access token
        imgur_access_token = ''
        while True:
            try:
                parameters = \
                    {'refresh_token': config['Passwords'][
                        'imgur_refresh_token'],
                     'client_id': config['Imgur']['client_id'],
                     'client_secret': config['Passwords'][
                         'imgur_client_secret'],
                     'grant_type': 'refresh_token'}
                self.logger.debug("Token request parameters: "
                                  + str(parameters))
                req = requests.post(IMGUR_REFRESH_URL, data=parameters)
                try:
                    imgur_access_token = req.json()['access_token']
                except KeyError as e:
                    self.logger.error(
                        "ERROR: Couldn't retrieve imgur access token.")
                    self.logger.error("JSON: " + str(req.json()))
                    raise e
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

        # Get previous album order
        headers = {'Authorization': 'Bearer ' + imgur_access_token}
        req = requests.get(IMGUR_ALBUM_IMAGES_URL.format(self.imgur_album),
                           headers=headers)
        album_order = ''
        for img in req.json()['data']:
            album_order += img['id'] + ','
        album_order = album_order[:-1]
        self.logger.debug('Old album order: ' + album_order)
        new_img_ids = ''

        # Upload picture
        title = post_details.text
        description = ''
        if len(title) > IMGUR_TITLE_LIMIT:
            too_long = ' [...]'
            allowed_text_length = IMGUR_TITLE_LIMIT - len(too_long)
            while len(title) > allowed_text_length:
                title = title.rsplit(' ', 1)[0]  # Remove last word
            title += too_long
            description = post_details.text
        # HTTPError retry loop
        while True:
            try:
                parameters = {'image': pic_base64,
                              'title': title,
                              'description': description,
                              'album_id': self.imgur_album,
                              'type': 'base64'}
                self.logger.debug("Image upload parameters: "
                                  + str(parameters))
                headers = {'Authorization': 'Bearer ' + imgur_access_token}
                req = requests.post(IMGUR_UPLOAD_URL, data=parameters,
                                    headers=headers)

                try:
                    picture_url = req.json()['data']['link']
                except KeyError as e:
                    self.logger.error("ERROR: JSON key error "
                                      "during image upload")
                    self.logger.error("JSON: " + str(req.json()))
                    raise e
                new_img_ids = picture_url[-11:-4]
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

        # Upload extra pictures if there's any
        for extra_post in post_details.extra_posts:
            if extra_post.picture:
                title = extra_post.text
                description = ''
                if len(title) > IMGUR_TITLE_LIMIT:
                    too_long = ' [...]'
                    allowed_text_length = IMGUR_TITLE_LIMIT - len(too_long)
                    while len(title) > allowed_text_length:
                        title = title.rsplit(' ', 1)[0]  # Remove last word
                    title += too_long
                    description = extra_post.text
                # HTTPError retry loop
                while True:
                    try:
                        parameters = {'image': extra_post.picture,
                                      'title': title,
                                      'description': description,
                                      'album_id': self.imgur_album,
                                      'type': 'URL'}
                        self.logger.debug("Extra image upload parameters: "
                                          + str(parameters))
                        headers = {'Authorization': 'Bearer ' +
                                                    imgur_access_token}
                        req = requests.post(IMGUR_UPLOAD_URL, data=parameters,
                                            headers=headers)

                        try:
                            extra_picture_url = req.json()['data']['link']
                        except KeyError as e:
                            self.logger.error("ERROR: JSON key error "
                                              "during extra image upload")
                            self.logger.error("JSON: " + str(req.json()))
                            raise e
                        new_img_ids = \
                            extra_picture_url[-11:-4] + ',' + new_img_ids
                        extra_post.picture = extra_picture_url
                        self.logger.info("Uploaded to imgur! " +
                                         extra_picture_url)
                        break
                    except requests.HTTPError as e:
                        retries -= 1
                        if retries == 0:
                            raise e
                        else:
                            self.logger.error(
                                "ERROR: HTTPError: " +
                                str(e.response.status_code) +
                                ". Retrying.")
                            sleep(2)
                            continue

        self.logger.info("New image ids: " + new_img_ids)

        # Rearrange newest picture to be first of the album
        # No API call for this...
        # Time to do it the PRO MLG WAY

        # Get Imgur session cookie
        parameters = {'username': config['Imgur']['username'],
                      'password': config['Passwords']['imgur']}
        self.logger.debug("Parameters: " + str(parameters))

        # Trust me bro, I'm totally not a Python script
        headers = {'User-Agent': 'runscope/0.1'}

        req = requests.post(IMGUR_SIGNIN_URL, data=parameters, headers=headers,
                            allow_redirects=False)
        imgur_cookie = req.cookies.get('IMGURSESSION')

        if imgur_cookie is None:
            self.logger.error("ERROR: Couldn't retrieve Imgur cookie.")
            self.logger.error("Page: " + req.text)
        else:
            self.logger.debug("imgur_cookie: " + imgur_cookie)
            new_album_order = new_img_ids + ',' + album_order
            self.logger.debug("New album order: " + new_album_order)

            # Use cookie to rearrange album
            cookies = {'IMGURSESSION': imgur_cookie}
            parameters = {'order': new_album_order}
            self.logger.debug("Parameters: " + str(parameters))
            req = requests.post(
                IMGUR_REARRANGE_URL.format(self.imgur_album), data=parameters,
                cookies=cookies)
            if req.text:
                raise Exception(
                    "ERROR: Could not rearrange Imgur album: " + req.text)

        return picture_url

    def get_random_babble(self):
        """Get a random funny Sakurai-esque quote."""
        rint = randint(0, len(sakurai_babbles) - 1)
        return sakurai_babbles[rint]

    def post_to_reddit(self, post_details, new_char=None,
                       post_url=None, post_url_jp=None,
                       website_give_up=False):
        """Post the Miiverse post to subreddit and returns the submission."""
        r = praw.Reddit(user_agent=USER_AGENT)
        r.login(self.username, config['Passwords']['reddit'])
        self.logger.info("Logged into Reddit.")

        date_format = config['Main']['date_format']
        date = datetime.utcnow().strftime(date_format)
        author = post_details.author
        if new_char:
            title_format = "" + new_char.description + " approaching! (" + \
                           date + ") {text}{extra}"
        else:
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

            # allowed_text_length =
            # length of text - the number of chars we must remove
            # - the length of the text we add at the end
            allowed_text_length = \
                len(text) \
                - (len(title) - REDDIT_TITLE_LIMIT) \
                - len(too_long)
            self.logger.debug("allowed_text_length: " +
                              str(allowed_text_length))
            while len(text) > allowed_text_length:
                text = text.rsplit(' ', 1)[0]  # Remove last word
            text += too_long
            title = title_format.format(type=post_type,
                                        text=text,
                                        extra=extra)
            text_too_long = True

        if not text_post:
            self.dont_retry = True
            try:
                submission = r.submit(self.subreddit, title, url=url)
                self.logger.info(
                    "New submission posted! " + submission.short_link)
            except praw.errors.AlreadySubmitted:
                self.logger.info("Submission already posted. Changing url.")
                if '?' in url:
                    url = url + '&unique=' + str(uuid4())
                else:
                    url = url + '?unique=' + str(uuid4())
                submission = r.submit(self.subreddit, title, url=url)
                self.logger.info(
                    "New submission posted! " + submission.short_link)

        # Additional comment
        comment = '{full_text}\n\n' \
                  '{website_give_up_text}\n\n' \
                  '{original_picture} {album_link}\n\n' \
                  '{miiverse_links}\n\n' \
                  '{new_char}\n\n' \
                  '{bonus_posts}\n\n' \
                  '{extra_comment}'
        full_text = ''
        if text_too_long:
            # Reddit formatting
            reddit_text = post_details.text.replace("\r\n", "  \n")
            full_text = "Full text:  \n>" + reddit_text
            self.logger.info("Text too long. Added to comment.")

        website_give_up_text = ''
        if website_give_up and not self.miiverse_main:
            website_give_up_text = \
                ("The Smash Bros website did not update in time, "
                 "so today's link is the lower-quality Miiverse picture. "
                 "The high quality picture will eventually appear "
                 "[here.]({})".format(SMASH_DAILY_PIC))

        original_picture = ''
        if post_details.picture:
            original_picture = ("[Original Miiverse picture]("
                                + post_details.picture + ") |")

        album_link = ("[Pic of the Day album](http://imgur.com/a/"
                      + self.imgur_album + ")")
        self.logger.info("filename: " + self.extra_comment_filename)
        f = open(self.extra_comment_filename, 'r+')
        extra_comment = f.read().strip()
        if len(extra_comment) > 0:
            extra_comment = "***** \n\n" + extra_comment
            self.logger.info("comment: " + extra_comment)
        if not self.debug:
            f.truncate(0)  # Erase file
        f.close()

        if post_url and post_url_jp:
            miiverse_links = "[Miiverse post]({}) | " \
                             "[Miiverse Japanese post]({})" \
                .format(MIIVERSE_URL + post_url, MIIVERSE_URL + post_url_jp)
        else:
            miiverse_links = ''

        new_char_text = ''
        if new_char:
            new_char_text = (
                "**[{description} approaching! {name} joins the battle!]"
                "({url})**"
                .format(description=new_char.description,
                        name=new_char.name,
                        url=SMASH_CHARACTER_PAGE.format(new_char.char_id)))

        bonus_posts = ''
        previous_author = ''
        for extra_post in post_details.extra_posts:
            extra_text = extra_post.text.replace("\r\n", "  \n")
            if extra_post.author != previous_author:
                bonus_posts += \
                    "**Extra {author} post in Miiverse's comments!**  \n" \
                    .format(author=extra_post.author)
            bonus_posts += ">{text}".format(text=extra_text)
            if extra_post.picture:
                bonus_posts += "\n\n[Extra picture]({})\n\n" \
                    .format(extra_post.picture)
            previous_author = extra_post.author

        comment = comment.format(full_text=full_text,
                                 website_give_up_text=website_give_up_text,
                                 original_picture=original_picture,
                                 album_link=album_link,
                                 miiverse_links=miiverse_links,
                                 bonus_posts=bonus_posts,
                                 extra_comment=extra_comment,
                                 new_char=new_char_text)
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
                self.logger.info(comment)
                submission.add_comment(comment)
                self.logger.info("Comment posted.")
            else:
                self.logger.info("No comment posted.")

        # Adding flair
        r.select_flair(submission, config['Reddit']['ssb4_flair'])
        self.logger.info("Tagged as SSB4.")

        return submission

    def post_to_other_subreddits(self, new_char, rsmashbros_url):
        """Post new character announcements in other subreddits."""
        r = praw.Reddit(user_agent=USER_AGENT)
        r.login(self.username, config['Passwords']['reddit'])
        self.logger.info("Logged into Reddit.")

        title = "{description} approaching! " \
                "{name} confirmed for Super Smash Bros. 4!" \
            .format(name=new_char.name, description=new_char.description)

        comment = "[An album of all previous daily SSB4 pictures posted by " \
                  "Sakurai.](http://imgur.com/a/{album})\n\n" \
                  "If you are interested in SSB4 news, " \
                  "join us at /r/smashbros " \
                  "where we discuss every daily picture. [\({name} " \
                  "/r/smashbros discussion thread.\)]({url})" \
            .format(album=self.imgur_album, name=new_char.name,
                    url=rsmashbros_url)

        for subreddit in self.other_subreddits:
            while True:
                try:
                    submission = r.submit(subreddit, title,
                                          url=SMASH_CHARACTER_PAGE
                                          .format(new_char.char_id))
                    self.logger.info(
                        "New submission posted to /r/" + subreddit + "! " +
                        submission.short_link)
                    submission.add_comment(comment)
                    self.logger.info(
                        "Comment posted  to /r/" + subreddit + ".")
                    break
                except praw.errors.RateLimitExceeded as e:
                    self.logger.error(e)
                    self.logger.info("Waiting 2 minutes.")
                    sleep(120)

    def set_last_post(self, post_url):
        """Add the post URL to the top of the last-post.txt file."""
        postf = open(self.last_post_filename, 'r+')
        old = postf.read()
        postf.seek(0)
        postf.write(post_url + "\n" + old)
        postf.close()
        self.logger.info("New post remembered.")

    def set_last_char(self, new_char_id):
        """Add the char id to the last-char.txt file."""
        postf = open(self.last_char_filename, 'w')
        postf.write(new_char_id)
        postf.close()
        self.logger.info("New char remembered.")

    def update_md5(self, current_md5):
        """Update the md5 in the last-picture-md5.txt file."""
        postf = open(self.picture_md5_filename, 'w')
        postf.write(current_md5)
        postf.close()
        self.logger.info("Md5 updated.")

    def post_to_irc(self, post_details, reddit_url):
        """Post a message to IRC with the new Sakurai post details."""
        server = config['IRC']['server']
        channel = '#' + config['IRC']['channel']
        nick = config['IRC']['nickname']
        nicks = (nick, nick + '_', nick + '__')
        self.logger.debug("server = " + server)
        self.logger.debug("channel = " + channel)
        self.logger.debug("nicks = " + str(nicks))
        irc_client = lurklib.Client(server=server, nick=nicks, tls=False)
        self.logger.debug("Logged in to the IRC server")
        self.logger.debug("irc_client = " + str(irc_client))
        sleep(30)
        self.logger.debug("Slept")
        irc_client.join_(channel)
        self.logger.debug("Joined channel")
        irc_client.privmsg(channel, 'New Sakurai post! - ' + reddit_url)
        message = '"' + post_details.text + '"'
        if len(message) <= 512:
            irc_client.privmsg(channel, message)
            self.logger.info("IRC Message posted")
        else:
            message = '"' + post_details.text[:472] + \
                      ' [...]" (Text too long! See the link.)'
            irc_client.privmsg(channel, message)
            self.logger.info("Shorten IRC Message posted")

        irc_client.quit()

    def bot_cycle(self):
        """Main loop of the bot."""
        self.logger.debug("Entering get_new_miiverse_cookie()")
        miiverse_cookie = self.get_new_miiverse_cookie()
        self.logger.debug("Entering get_miiverse_last_post()")
        post_url = self.get_miiverse_last_post(miiverse_cookie)

        waiting_file = config['Files']['waiting_on_website']
        self.logger.debug("Entering is_new_post()")
        if self.is_new_post(post_url) or self.debug:

            self.logger.debug("Entering get_info_from_post()")
            post_details = self.get_info_from_post(post_url,
                                                   miiverse_cookie)

            website_give_up = False
            if post_details.is_picture_post():
                self.logger.debug("Entering get_current_pic_md5()")
                current_md5 = self.get_current_pic_md5()

                if not self.miiverse_main:
                    self.logger.debug("Entering is_website_new() loop")
                    website_tries = \
                        int(config['Main']['website_not_new_tries'])
                    website_loop_retries = website_tries

                    while not self.is_website_new(current_md5) \
                            and not self.debug:
                        website_loop_retries -= 1
                        current_md5 = self.get_current_pic_md5()
                        if website_loop_retries <= 0:
                            self.logger.warn(
                                "Checked website picture {} times."
                                " Giving up.".format(website_tries))
                            website_give_up = True
                            # Create a flag to keep checking the website pic
                            open(waiting_file, 'a').close()
                            self.logger.warn("Created waiting_on_website.")
                            break
                        sleep(int(config['Main']['sleep_on_website_not_new']))
                else:
                    self.logger.info("Miiverse is set as main picture,"
                                     " did not check website")
                    website_give_up = True

                self.logger.debug("Entering upload_to_imgur()")
                post_details.smashbros_pic = \
                    self.upload_to_imgur(post_details, website_give_up)

                if not self.debug:
                    self.logger.debug("Entering update_md5()")
                    self.update_md5(current_md5)

            self.logger.debug("Entering get_new_char()")
            new_char = self.get_new_char()

            post_url_jp = self.get_miiverse_last_post(miiverse_cookie, True)

            self.logger.debug("Entering post_to_reddit()")
            reddit_url = self.post_to_reddit(post_details, new_char,
                                             post_url, post_url_jp,
                                             website_give_up).short_link

            if not self.debug:
                self.logger.debug("Entering set_last_post()")
                self.set_last_post(post_url)
                if new_char:
                    self.logger.debug("Entering post_to_other_subreddits()")
                    self.post_to_other_subreddits(new_char, reddit_url)
                    self.logger.debug("Entering set_last_char()")
                    self.set_last_char(new_char.char_id)
                self.logger.debug("Entering post_to_irc()")
                self.post_to_irc(post_details, reddit_url)

        # If the previous post did not get a website pic,
        # we don't want to think the new website pic is for the next post.
        # We need to update it ASAP.
        elif os.path.isfile(waiting_file):
            self.logger.debug("Entering get_current_pic_md5()")
            current_md5 = self.get_current_pic_md5()
            if self.is_website_new(current_md5):
                self.logger.info("MD5 from last post was found.")
                self.logger.debug("Entering update_md5()")
                self.update_md5(current_md5)
                os.remove(waiting_file)
