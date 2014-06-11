#!/usr/bin/env python3
"""
SakuraiBot test suite.

Uses a test subreddit and a test user.
Created on 2013-07-17
Author: Wiwiweb

"""

from configparser import ConfigParser
from datetime import datetime
from filecmp import cmp
import logging
from os import remove
from shutil import copy
import sys

import praw
import unittest
import pep8
import requests
from uuid import uuid4

import sakuraibot
from sakuraibot import ExtraPost

CONFIG_FILE = "../cfg/config.ini"
CONFIG_FILE_PRIVATE = "../cfg/config-private.ini"
config = ConfigParser()
config.read([CONFIG_FILE, CONFIG_FILE_PRIVATE])

USER_AGENT = "SakuraiBot test suite"

LAST_POST_FILENAME = 'last-post.txt'
EXTRA_COMMENT_FILENAME = '../res/extra-comment.txt'
PICTURE_MD5_FILENAME = 'last-picture-md5.txt'
LAST_CHAR_FILENAME = 'last-char.txt'

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                    format='%(asctime)s: %(message)s')

imgur_client_id = config['Imgur']['client_id']

unicode_text = ' No \u0CA0_\u0CA0 ;' \
               ' Yes \u0CA0\u203F\u0CA0 \u2026'
long_text = \
    '. By the way this text is very very very very very very very ' \
    'very very very very very very very very very very very very ' \
    'very very very very very very very very very very very very ' \
    'very very very very very very very very very very very long.'


class CodeFormatTests(unittest.TestCase):
    def test_pep8_conformance(self):
        pep8style = pep8.StyleGuide()
        result = pep8style.check_files(['../src/sakuraibot.py',
                                        '../src/__init__.py', 'tests.py'])
        self.assertFalse(result.total_errors, result.messages)


class BasicTests(unittest.TestCase):
    def setUp(self):
        self.sbot = sakuraibot.SakuraiBot(config['Reddit']['test_username'],
                                          config['Reddit']['test_subreddit'],
                                          [config['Reddit']['test_subreddit']],
                                          config['Imgur']['test_album_id'],
                                          LAST_POST_FILENAME,
                                          EXTRA_COMMENT_FILENAME,
                                          PICTURE_MD5_FILENAME,
                                          LAST_CHAR_FILENAME,
                                          debug=True)

    def test_get_new_miiverse_cookie(self):
        cookie = self.sbot.get_new_miiverse_cookie()
        self.assertRegex(cookie, r'^[0-9]{10}[.].{43}$',
                         "Malformed cookie: " + cookie)

    def test_is_new_post_yes(self):
        self.assertTrue(self.sbot.is_new_post(
            '/posts/AYMHAAABAAAYUKk9MS0TYA'))

    def test_is_new_post_no(self):
        self.assertFalse(self.sbot.is_new_post(
            '/posts/AYMHAAABAAD4UV51j0kRvw'))

    def test_get_current_pic_md5(self):
        md5 = self.sbot.get_current_pic_md5()
        self.assertRegexpMatches(md5, r'([a-fA-F\d]{32})',
                                 "Malformed md5: " + md5)

    def test_is_website_new_yes(self):
        md5 = '3c0cb77a45b1215d9d4ef6cda0d89959'
        self.assertTrue(self.sbot.is_website_new(md5))

    def test_is_website_new_no(self):
        md5 = 'ea29d1e00c26ccd3088263f5340be961'
        self.assertFalse(self.sbot.is_website_new(md5))

    def test_get_new_char(self):
        new_char = self.sbot.get_new_char()
        self.assertRegex(new_char.char_id, r'[a-z_]+')
        self.assertRegex(new_char.name, r'[a-zA-Z ]+')
        self.assertTrue(new_char.description == 'New challenger' or
                        new_char.description == 'Veteran fighter')

    def test_set_last_post(self):
        file_before = 'last-post-before.txt'
        file_copy = 'last-post-before-copy.txt'
        copy(file_before, file_copy)
        self.sbot.last_post_filename = file_copy
        self.sbot.set_last_post('/posts/AYMHAAABAABtUV58VKXjyQ')
        self.assertTrue(cmp(file_copy, LAST_POST_FILENAME))
        remove(file_copy)

    def test_update_md5(self):
        md5 = 'ea29d1e00c26ccd3088263f5340be961'
        file_before = 'last-picture-md5-before.txt'
        file_copy = 'last-picture-md5-before-copy.txt'
        copy(file_before, file_copy)
        self.sbot.picture_md5_filename = file_copy
        self.sbot.update_md5(md5)
        self.assertTrue(cmp(file_copy, PICTURE_MD5_FILENAME))
        remove(file_copy)


class MiiverseTests(unittest.TestCase):
    def setUp(self):
        self.sbot = sakuraibot.SakuraiBot(config['Reddit']['test_username'],
                                          config['Reddit']['test_subreddit'],
                                          [config['Reddit']['test_subreddit']],
                                          config['Imgur']['test_album_id'],
                                          LAST_POST_FILENAME,
                                          EXTRA_COMMENT_FILENAME,
                                          PICTURE_MD5_FILENAME,
                                          LAST_CHAR_FILENAME,
                                          debug=True)
        self.cookie = self.sbot.get_new_miiverse_cookie()

    def test_get_miiverse_last_post(self):
        url = self.sbot.get_miiverse_last_post(self.cookie)
        self.assertRegex(url, r'^/posts/.{22}$',
                         "Malformed URL: " + url)

    def test_get_info_from_post_text(self):
        url = '/posts/AYMHAAABAADOUV51jNwWyg'
        text = ("Hi I'm the director of Super Smash Bros., "
                "Masahiro Sakurai of Sora.\r\n"
                "From now on, I'll be posting on Miiverse, "
                "so I hope you'll look forward to my posts.\r\n"
                "Please note that I won't be able to answer any questions.")
        info = self.sbot.get_info_from_post(url, self.cookie)
        self.assertTrue(info.is_text_post())
        self.assertEqual(info.author, 'Sakurai')
        self.assertTrue(isinstance(info.text, str))  # Not unicode
        self.assertTrue(isinstance(info.author, str))
        self.assertEqual(info.text, text)
        self.assertIsNone(info.picture)
        self.assertIsNone(info.video)
        self.assertIsNone(info.smashbros_pic)
        self.assertFalse(info.extra_posts)

    def test_get_info_from_post_picture(self):
        url = '/posts/AYMHAAABAABtUV58IEIGrA'
        text = ("Mega Man 2 seems to be the most popular,"
                " so many of his moves are from that game.")
        picture = 'https://d3esbfg30x759i.cloudfront.net/ss/zlCfzRAybhUAGnxAWi'

        info = self.sbot.get_info_from_post(url, self.cookie)
        self.assertTrue(info.is_picture_post())
        self.assertEqual(info.author, 'Sakurai')
        self.assertTrue(isinstance(info.text, str))  # Not unicode
        self.assertTrue(isinstance(info.author, str))
        self.assertEqual(info.text, text)
        self.assertEqual(info.picture, picture)
        self.assertIsNone(info.video)
        self.assertIsNone(info.smashbros_pic)
        self.assertFalse(info.extra_posts)

    def test_get_info_from_post_video(self):
        url = '/posts/AYMHAAABAADMUKlXokfF0g'
        text = ("The long-awaited super robot Mega Man joins the battle!\r\n"
                "He fights using the various weapons"
                " he acquired from bosses in past games.")
        video = 'https://www.youtube.com/watch?v=aX2KNyaoNV4'

        info = self.sbot.get_info_from_post(url, self.cookie)
        self.assertTrue(info.is_video_post())
        self.assertEqual(info.author, 'Sakurai')
        self.assertTrue(isinstance(info.text, str))  # Not unicode
        self.assertTrue(isinstance(info.author, str))
        self.assertEqual(info.text, text)
        self.assertIsNone(info.picture)
        self.assertEqual(info.video, video)
        self.assertIsNone(info.smashbros_pic)
        self.assertFalse(info.extra_posts)

    def test_get_info_from_post_extra_picture(self):
        url = '/posts/AYMHAAACAABnUYnYdfxmSw'
        text = ("Pic of the day. "
                "A new stage, Mario Galaxy!!  The pull of gravity "
                "emanates from the center of the planet, "
                "so this will require using brand-new tactics.")
        picture = 'https://d3esbfg30x759i.cloudfront.net/ss/zlCfzRMJy3ooPr5IXd'
        extra_picture = \
            'https://d3esbfg30x759i.cloudfront.net/ss/zlCfzRMJy9APSdORn5'
        extra_text = ("Here's what happens when you stand by the edges. "
                      "Vertical jumps and getting hit upward "
                      "will shoot you up diagonally.")

        info = self.sbot.get_info_from_post(url, self.cookie)
        self.assertTrue(info.is_picture_post())
        self.assertEqual(info.author, 'Sakurai')
        self.assertTrue(isinstance(info.text, str))  # Not unicode
        self.assertTrue(isinstance(info.author, str))
        self.assertEqual(info.text, text)
        self.assertEqual(info.picture, picture)
        self.assertEqual(info.extra_posts[0].author, 'Sakurai')
        self.assertEqual(info.extra_posts[0].picture, extra_picture)
        self.assertEqual(info.extra_posts[0].text, extra_text)
        self.assertIsNone(info.video)
        self.assertIsNone(info.smashbros_pic)

    def test_get_info_from_post_multiple_extra_pictures(self):
        url = '/posts/AYMHAAACAADMUKloUYDezQ'
        text = ("Pic of the day. "
                "Here's some info on the Nintendo 3DS stage "
                "called Super Mario 3D Land! "
                "First, it advances by side-scrolling…")
        picture = 'https://d3esbfg30x759i.cloudfront.net/ss/zlCfzRpCLAEzC-LqC4'

        extra_text1 = ("Then you continue into the valley--it's in 3D Land, "
                       "after all. The protruding stone blocks change "
                       "the angles of the platforms.")
        extra_picture1 = \
            'https://d3esbfg30x759i.cloudfront.net/ss/zlCfzRpCLfEXjgpdwk'
        extra_post1 = ExtraPost('Sakurai', extra_text1, extra_picture1)

        extra_text2 = ("After that, back to side-scrolling. Now it gets "
                       "you moving--you'll have to trot downhill here.")
        extra_picture2 = \
            'https://d3esbfg30x759i.cloudfront.net/ss/zlCfzRpCLsc42ZpA7g'
        extra_post2 = ExtraPost('Sakurai', extra_text2, extra_picture2)

        extra_text3 = ("And finally, you get back on rails to go farther into "
                       "the stage. It takes roughly two minutes to complete a "
                       "lap, and at the end you go into a giant pipe that "
                       "takes you back to the beginning. …I know this "
                       "sequence goes above and beyond a traditional "
                       "Pic of the Day, so consider this a little something "
                       "extra on the side from me.")
        extra_picture3 = \
            'https://d3esbfg30x759i.cloudfront.net/ss/zlCfzRpCMHYUiQh7v1'
        extra_post3 = ExtraPost('Sakurai', extra_text3, extra_picture3)

        extra_posts = [extra_post1, extra_post2, extra_post3]

        info = self.sbot.get_info_from_post(url, self.cookie)
        self.assertTrue(info.is_picture_post())
        self.assertEqual(info.author, 'Sakurai')
        self.assertTrue(isinstance(info.text, str))  # Not unicode
        self.assertTrue(isinstance(info.author, str))
        self.assertEqual(info.text, text)
        self.assertEqual(info.picture, picture)
        for i in range(0, 2):
            self.assertEqual(info.extra_posts[i].author,
                             extra_posts[i].author)
            self.assertEqual(info.extra_posts[i].picture,
                             extra_posts[i].picture)
            self.assertEqual(info.extra_posts[i].text,
                             extra_posts[i].text)
        self.assertIsNone(info.video)
        self.assertIsNone(info.smashbros_pic)


class ImgurTests(unittest.TestCase):
    def setUp(self):
        self.sbot = sakuraibot.SakuraiBot(config['Reddit']['test_username'],
                                          config['Reddit']['test_subreddit'],
                                          [config['Reddit']['test_subreddit']],
                                          config['Imgur']['test_album_id'],
                                          LAST_POST_FILENAME,
                                          EXTRA_COMMENT_FILENAME,
                                          PICTURE_MD5_FILENAME,
                                          LAST_CHAR_FILENAME,
                                          debug=True)
        self.picture = 'http://i.imgur.com/uQIRrD2.gif'

    def test_upload_to_imgur(self):
        unique_text = str(uuid4()) + unicode_text
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              self.picture, None, None)
        picture_url = self.sbot.upload_to_imgur(post_details)
        picture_id = picture_url[-11:-4]

        headers = {'Authorization': 'Client-ID ' + imgur_client_id}
        req = requests.get('https://api.imgur.com/3/image/' + picture_id,
                           headers=headers)
        logging.debug("Image Json Response: " + req.text)
        id_json = req.json()['data']['id']
        self.assertEqual(picture_id, id_json)
        title_json = req.json()['data']['title']
        self.assertEqual(unique_text, title_json)
        description_json = req.json()['data']['description']
        self.assertIsNone(description_json)

        headers = {'Authorization': 'Client-ID ' + imgur_client_id}
        req = requests.get('https://api.imgur.com/3/album/' +
                           config['Imgur']['test_album_id'],
                           headers=headers)
        logging.debug("Album Json Response: " + req.text)
        album_id_json = req.json()['data']['id']
        self.assertEqual(config['Imgur']['test_album_id'], album_id_json)
        # Test if the new picture is first
        picture_id_json = req.json()['data']['images'][0]['id']
        self.assertEqual(picture_id, picture_id_json)

    def test_upload_to_imgur_long(self):
        unique_text = str(uuid4()) + unicode_text + long_text
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              self.picture, None, None)
        picture_url = self.sbot.upload_to_imgur(post_details)
        picture_id = picture_url[19:-4]

        headers = {'Authorization': 'Client-ID ' + imgur_client_id}
        req = requests.get('https://api.imgur.com/3/image/' + picture_id,
                           headers=headers)
        logging.debug("Image Json Response: " + req.text)
        id_json = req.json()['data']['id']
        self.assertEqual(picture_id, id_json)
        title_json = req.json()['data']['title']
        alt_title = unique_text.rsplit(' ', 35)[0] + ' [...]'
        self.assertEqual(alt_title, title_json)
        description_json = req.json()['data']['description']
        self.assertEqual(unique_text, description_json)


class RedditTests(unittest.TestCase):
    def setUp(self):
        self.sbot = sakuraibot.SakuraiBot(config['Reddit']['test_username'],
                                          config['Reddit']['test_subreddit'],
                                          [config['Reddit']['test_subreddit']],
                                          config['Imgur']['test_album_id'],
                                          LAST_POST_FILENAME,
                                          EXTRA_COMMENT_FILENAME,
                                          PICTURE_MD5_FILENAME,
                                          LAST_CHAR_FILENAME,
                                          debug=True)
        self.r = praw.Reddit(user_agent=USER_AGENT)
        self.r.login(config['Reddit']['test_username'],
                     config['Passwords']['reddit'])
        self.subreddit = self.r.get_subreddit(
            config['Reddit']['test_subreddit'])
        self.r.config.cache_timeout = 0

    def test_post_to_reddit_text(self):
        unique_text = 'Text test: ' + str(uuid4()) + \
                      unicode_text
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              None, None, None)
        submission = self.sbot.post_to_reddit(post_details, None)
        self.assertEqual(submission,
                         next(self.subreddit.get_new(limit=1)))
        self.assertEqual(submission,
                         next(self.r.user.get_submitted(limit=1)))
        date = datetime.utcnow().strftime(config['Main']['date_format'])
        title = 'New Pug post! (' + date + ') "' \
                + unique_text + '" (No picture)'
        self.assertEqual(title, submission.title)
        # TODO test comment

    def test_post_to_reddit_text_long(self):
        unique_text = 'Long text test: ' + str(uuid4()) + \
                      unicode_text + long_text
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              None, None, None)
        submission = self.sbot.post_to_reddit(post_details, None)
        self.assertEqual(submission,
                         next(self.subreddit.get_new(limit=1)))
        self.assertEqual(submission,
                         next(self.r.user.get_submitted(limit=1)))
        date = datetime.utcnow().strftime(config['Main']['date_format'])
        title = 'New Pug post! (' + date + ') "' + \
                unique_text.rsplit(' ', 16)[0] + \
                ' [...]" (Text too long! See post) (No picture)'
        self.assertEqual(title, submission.title)
        self.assertTrue(unique_text in submission.selftext)

    def test_post_to_reddit_picture(self):
        unique = uuid4()
        picture = 'http://i.imgur.com/uQIRrD2.gif?unique=' + str(unique)
        unique_text = 'Picture test: ' + str(unique) + \
                      unicode_text
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              picture, None, picture)
        submission = self.sbot.post_to_reddit(post_details, None)
        self.assertEqual(submission,
                         next(self.subreddit.get_new(limit=1)))
        self.assertEqual(submission,
                         next(self.r.user.get_submitted(limit=1)))
        date = datetime.utcnow().strftime(config['Main']['date_format'])
        title = 'New Pug picture! (' + date + ') "' + unique_text + '"'
        self.assertEqual(title, submission.title)
        self.assertEqual(picture, submission.url)
        # TODO test comment

    def test_post_to_reddit_picture_long(self):
        unique = uuid4()
        picture = 'http://i.imgur.com/uQIRrD2.gif?unique=' + str(unique)
        unique_text = 'Long Picture test: ' + str(unique) + \
                      unicode_text + long_text
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              picture, None, picture)
        submission = self.sbot.post_to_reddit(post_details, None)
        self.assertEqual(submission,
                         next(self.subreddit.get_new(limit=1)))
        self.assertEqual(submission,
                         next(self.r.user.get_submitted(limit=1)))
        date = datetime.utcnow().strftime(config['Main']['date_format'])
        title = 'New Pug picture! (' + date + ') "' + \
                unique_text.rsplit(' ', 16)[0] + \
                ' [...]" (Text too long! See comment)'
        self.assertEqual(title, submission.title)
        self.assertEqual(picture, submission.url)
        # Reload comments
        submission = next(self.subreddit.get_new(limit=1))
        comment = submission.comments[0].body
        self.assertTrue(unique_text in comment)

    def test_post_to_reddit_extra_pictures(self):
        unique = uuid4()
        picture = 'http://i.imgur.com/uQIRrD2.gif?unique=' + str(unique)
        unique_text = 'Picture test: ' + str(unique) + \
                      unicode_text

        unique_extra_text1 = 'Extra text 1 test: ' + str(unique) + \
            unicode_text
        extra_post1 = ExtraPost('Pug1', unique_extra_text1, picture)
        unique_extra_text2 = 'Extra text 2 test: ' + str(unique) + \
            unicode_text
        extra_post2 = ExtraPost('Pug2', unique_extra_text2, picture)
        unique_extra_text3 = 'Extra text 3 test: ' + str(unique) + \
            unicode_text
        extra_post3 = ExtraPost('Pug2', unique_extra_text3, picture)

        extra_posts = [extra_post1, extra_post2, extra_post3]

        post_details = \
            sakuraibot.PostDetails('Pug', unique_text,
                                   picture, None, picture, extra_posts)
        submission = self.sbot.post_to_reddit(post_details, None)
        self.assertEqual(submission,
                         next(self.subreddit.get_new(limit=1)))
        self.assertEqual(submission,
                         next(self.r.user.get_submitted(limit=1)))
        date = datetime.utcnow().strftime(config['Main']['date_format'])
        title = 'New Pug picture! (' + date + ') "' + unique_text + '"'
        self.assertEqual(title, submission.title)
        self.assertEqual(picture, submission.url)
        # Reload comments
        submission = next(self.subreddit.get_new(limit=1))
        comment = submission.comments[0].body
        self.assertTrue("Extra Pug1 post in Miiverse's comments!" in comment)
        self.assertTrue("Extra Pug2 post in Miiverse's comments!" in comment)
        self.assertTrue(comment.count('Pug2') == 1)
        self.assertTrue(unique_extra_text1 in comment)
        self.assertTrue(unique_extra_text2 in comment)
        self.assertTrue(unique_extra_text3 in comment)
        self.assertTrue(picture in comment)

    def test_post_to_reddit_video(self):
        unique = uuid4()
        video = 'http://www.youtube.com/watch?v=7anpvGqQxwI?unique=' \
                + str(unique)
        unique_text = 'Video test: ' + str(unique) + \
                      unicode_text
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              None, video, None)
        submission = self.sbot.post_to_reddit(post_details, None)
        self.assertEqual(submission,
                         next(self.subreddit.get_new(limit=1)))
        self.assertEqual(submission,
                         next(self.r.user.get_submitted(limit=1)))
        date = datetime.utcnow().strftime(config['Main']['date_format'])
        title = 'New Pug video! (' + date + ') "' + unique_text + '"'
        self.assertEqual(title, submission.title)
        self.assertEqual(video, submission.url)
        # TODO test comment

    def test_post_to_reddit_character(self):
        unique = uuid4()
        picture = 'http://i.imgur.com/uQIRrD2.gif?unique=' + str(unique)
        unique_text = 'Character test: ' + str(unique) + \
                      unicode_text
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              picture, None, picture)
        new_char = sakuraibot.CharDetails('pug', 'Pug', 'New challenger')
        submission = self.sbot.post_to_reddit(post_details, new_char)
        self.assertEqual(submission,
                         next(self.subreddit.get_new(limit=1)))
        self.assertEqual(submission,
                         next(self.r.user.get_submitted(limit=1)))
        date = datetime.utcnow().strftime(config['Main']['date_format'])
        title = 'New challenger approaching! (' + date + ') "' + unique_text \
                + '"'
        self.assertEqual(title, submission.title)
        self.assertEqual(picture, submission.url)
        # TODO test comment

    def test_post_to_other_subreddits(self):
        unique = uuid4()
        name = 'pug' + str(unique)
        new_char = sakuraibot.CharDetails(name, 'Pug', 'New challenger')
        url = 'http://google.com'
        self.sbot.post_to_other_subreddits(new_char, url)
        title = "New challenger approaching!" \
                " Pug confirmed for Super Smash Bros. 4!"
        smash_url = "http://www.smashbros.com/en-uk/characters/{}.html" \
            .format(name)
        submission = next(self.subreddit.get_new(limit=1))
        self.assertEqual(title, submission.title)
        self.assertEqual(smash_url, submission.url)


class CompleteTests(unittest.TestCase):
    def setUp(self):
        self.sbot = sakuraibot.SakuraiBot(config['Reddit']['test_username'],
                                          config['Reddit']['test_subreddit'],
                                          [config['Reddit']['test_subreddit']],
                                          config['Imgur']['test_album_id'],
                                          LAST_POST_FILENAME,
                                          EXTRA_COMMENT_FILENAME,
                                          PICTURE_MD5_FILENAME,
                                          LAST_CHAR_FILENAME,
                                          debug=True)

    def test_bot_cycle(self):
        self.sbot.bot_cycle()
        # TODO: asserts


if __name__ == '__main__':
    unittest.main()