#!/usr/bin/python
'''
Created on 2013-07-17
Author: Wiwiweb

SakuraiBot test suite
'''

import unittest
import pep8
import pep257
import sakuraibot
import urllib2
import uuid
import praw
import logging
import sys
from time import sleep
from datetime import datetime
from json import loads
from shutil import copy
from filecmp import cmp
from os import remove, path
from sys import modules

USERNAME = 'SakuraiBot_test'
SUBREDDIT = 'SakuraiBot_test'
IMGUR_ALBUM_ID = 'ugL4N'
USER_AGENT = "SakuraiBot test suite"


REDDIT_PASSWORD_FILENAME = '../res/private/reddit-password.txt'
LAST_POST_FILENAME = 'last-post.txt'
EXTRA_COMMENT_FILENAME = 'extra-comment.txt'
PICTURE_MD5_FILENAME = 'last-picture-md5.txt'
IMGUR_CLIENT_ID = '45b2e3810d7d550'
REDDIT_PASSWORD = sakuraibot.reddit_password

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                    format='%(asctime)s: %(message)s')


class CodeFormatTests(unittest.TestCase):

    def test_pep8_conformance(self):
        pep8style = pep8.StyleGuide(quiet=True)
        result = pep8style.check_files(['../src/sakuraibot.py',
                                        '../src/__init__.py', 'tests.py'])
        self.assertFalse(result.total_errors, result.messages)

    def test_pep257_conformance(self):
        result = pep257.check_files(['../src/sakuraibot.py',
                                     '../src/__init__.py', 'tests.py'])
        self.assertFalse(result)


class BasicTests(unittest.TestCase):

    def setUp(self):
        self.sbot = sakuraibot.SakuraiBot(USERNAME, SUBREDDIT, IMGUR_ALBUM_ID,
                                          LAST_POST_FILENAME,
                                          EXTRA_COMMENT_FILENAME,
                                          PICTURE_MD5_FILENAME,
                                          debug=True)

    def test_get_new_miiverse_cookie(self):
        cookie = self.sbot.get_new_miiverse_cookie()
        self.assertRegexpMatches(cookie, r'^[0-9]{10}[.].{43}$',
                                 "Malformed cookie: " + cookie)

    def test_is_new_post_yes(self):
        self.assertTrue(self.
                        sbot.is_new_post('/posts/AYMHAAABAAAYUKk9MS0TYA'))

    def test_is_new_post_no(self):
        self.assertFalse(self.
                         sbot.is_new_post('/posts/AYMHAAABAAD4UV51j0kRvw'))

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
        self.sbot = sakuraibot.SakuraiBot(USERNAME, SUBREDDIT, IMGUR_ALBUM_ID,
                                          LAST_POST_FILENAME,
                                          EXTRA_COMMENT_FILENAME,
                                          PICTURE_MD5_FILENAME,
                                          debug=True)
        self.cookie = self.sbot.get_new_miiverse_cookie()

    def test_get_miiverse_last_post(self):
        url = self.sbot.get_miiverse_last_post(self.cookie)
        self.assertRegexpMatches(url, r'^/posts/.{22}$',
                                 "Malformed URL: " + url)

    def test_get_info_from_post_text(self):
        url = '/posts/AYMHAAABAADOUV51jNwWyg'
        text = ("Hi I'm the director of Super Smash Bros.,"
                " Masahiro Sakurai of Sora.\r\n"
                "From now on, I'll be posting on Miiverse, "
                "so I hope you'll look forward to my posts.\r\n"
                "Please note that I won't be able to answer any questions.")
        text = unicode(text)
        info = self.sbot.get_info_from_post(url, self.cookie)
        self.assertTrue(info.is_text_post())
        self.assertEqual(info.author, 'Sakurai')
        self.assertTrue(isinstance(info.text, str))  # Not unicode
        self.assertTrue(isinstance(info.author, str))
        self.assertEqual(info.text, text)
        self.assertIsNone(info.picture)
        self.assertIsNone(info.video)
        self.assertIsNone(info.smashbros_pic)

    def test_get_info_from_post_picture(self):
        url = '/posts/AYMHAAABAABtUV58IEIGrA'
        text = unicode("Mega Man 2 seems to be the most popular,"
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

    def test_get_info_from_post_video(self):
        url = '/posts/AYMHAAABAADMUKlXokfF0g'
        text = ("The long-awaited super robot Mega Man joins the battle!\r\n"
                "He fights using the various weapons"
                " he acquired from bosses in past games.")
        text = unicode(text)
        video = 'http://www.youtube.com/watch?v=aX2KNyaoNV4'

        info = self.sbot.get_info_from_post(url, self.cookie)
        self.assertTrue(info.is_video_post())
        self.assertEqual(info.author, 'Sakurai')
        self.assertTrue(isinstance(info.text, str))  # Not unicode
        self.assertTrue(isinstance(info.author, str))
        self.assertEqual(info.text, text)
        self.assertIsNone(info.picture)
        self.assertEqual(info.video, video)
        self.assertIsNone(info.smashbros_pic)


class ImgurTests(unittest.TestCase):

    def setUp(self):
        self.sbot = sakuraibot.SakuraiBot(USERNAME, SUBREDDIT, IMGUR_ALBUM_ID,
                                          LAST_POST_FILENAME,
                                          EXTRA_COMMENT_FILENAME,
                                          PICTURE_MD5_FILENAME,
                                          debug=True)
        self.picture = 'http://i.imgur.com/uQIRrD2.gif'

    def test_upload_to_imgur(self):
        unique_text = unicode(uuid.uuid4()) \
            + u' No \u0CA0_\u0CA0 ; Yes \u0CA0\u203F\u0CA0 \u2026'
        unique_text = unique_text.encode('utf-8')
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              self.picture, None, None)
        picture_url = self.sbot.upload_to_imgur(post_details)
        picture_id = picture_url[19:-4]

        req = urllib2.Request('https://api.imgur.com/3/image/' + picture_id)
        req.add_header("Authorization", "Client-ID " + IMGUR_CLIENT_ID)
        json_resp = loads(urllib2.urlopen(req).read())
        id_json = json_resp['data']['id']
        title_json = json_resp['data']['title'].encode('utf-8')
        self.assertEqual(picture_id, id_json)
        self.assertEqual(unique_text, title_json)

        req = urllib2.Request('https://api.imgur.com/3/album/'
                              + IMGUR_ALBUM_ID)
        req.add_header("Authorization", "Client-ID " + IMGUR_CLIENT_ID)
        json_resp = loads(urllib2.urlopen(req).read())
        album_id_json = json_resp['data']['id']
        picture_id_json = json_resp['data']['images'][-1]['id']
        self.assertEqual(IMGUR_ALBUM_ID, album_id_json)
        self.assertEqual(picture_id, picture_id_json)


class RedditTests(unittest.TestCase):

    def setUp(self):
        self.sbot = sakuraibot.SakuraiBot(USERNAME, SUBREDDIT, IMGUR_ALBUM_ID,
                                          LAST_POST_FILENAME,
                                          EXTRA_COMMENT_FILENAME,
                                          PICTURE_MD5_FILENAME,
                                          debug=True)
        self.r = praw.Reddit(user_agent=USER_AGENT)
        self.r.login(USERNAME, REDDIT_PASSWORD)
        self.subreddit = self.r.get_subreddit(SUBREDDIT)
        self.r.config.cache_timeout = 0

        self.unicode_text = u' No \u0CA0_\u0CA0 ;' \
                            u' Yes \u0CA0\u203F\u0CA0 \u2026'
        self.long_text = \
            u'. By the way this text is very very very very very very very ' \
            u'very very very very very very very very very very very very ' \
            u'very very very very very very very very very very very very ' \
            u'very very very very very very very very very very very long.'

    def test_post_to_reddit_text(self):
        unique_text = u'Text test: ' + unicode(uuid.uuid4()) +\
                      self.unicode_text
        unique_text = unique_text.encode('utf-8')
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              None, None, None)
        submission = self.sbot.post_to_reddit(post_details)
        self.assertEquals(submission,
                          self.subreddit.get_new(limit=1).next())
        self.assertEquals(submission,
                          self.r.user.get_submitted(limit=1).next())
        date = datetime.now().strftime('%y-%m-%d')
        title = 'New Pug post! (' + date + ') "' \
                + unique_text + '" (No picture)'
        self.assertEquals(title, submission.title.encode('utf-8'))
        #TODO test comment

    def test_post_to_reddit_text_long(self):
        unique_text = u'Long text test: ' + unicode(uuid.uuid4()) + \
            self.unicode_text + self.long_text
        unique_text = unique_text.encode('utf-8')
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              None, None, None)
        submission = self.sbot.post_to_reddit(post_details)
        self.assertEquals(submission,
                          self.subreddit.get_new(limit=1).next())
        self.assertEquals(submission,
                          self.r.user.get_submitted(limit=1).next())
        date = datetime.now().strftime('%y-%m-%d')
        title = 'New Pug post! (' + date + \
                ') (Text too long! See post) (No picture)'
        self.assertEquals(title, submission.title.encode('utf-8'))
        #TODO test comment

    def test_post_to_reddit_picture(self):
        unique = uuid.uuid4()
        picture = 'http://i.imgur.com/uQIRrD2.gif?unique=' + str(unique)
        unique_text = u'Picture test: ' + unicode(unique) + \
                      self.unicode_text
        unique_text = unique_text.encode('utf-8')
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              picture, None, picture)
        submission = self.sbot.post_to_reddit(post_details)
        self.assertEquals(submission,
                          self.subreddit.get_new(limit=1).next())
        self.assertEquals(submission,
                          self.r.user.get_submitted(limit=1).next())
        date = datetime.now().strftime('%y-%m-%d')
        title = 'New Pug picture! (' + date + ') "' + unique_text + '"'
        self.assertEquals(title, submission.title.encode('utf-8'))
        self.assertEquals(picture, submission.url)
        #TODO test comment

    def test_post_to_reddit_picture_long(self):
        unique = uuid.uuid4()
        picture = 'http://i.imgur.com/uQIRrD2.gif?unique=' + str(unique)
        unique_text = u'Long Picture test: ' + unicode(unique) + \
                      self.unicode_text + self.long_text
        unique_text = unique_text.encode('utf-8')
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              picture, None, picture)
        submission = self.sbot.post_to_reddit(post_details)
        self.assertEquals(submission,
                          self.subreddit.get_new(limit=1).next())
        self.assertEquals(submission,
                          self.r.user.get_submitted(limit=1).next())
        date = datetime.now().strftime('%y-%m-%d')
        title = 'New Pug picture! (' + date + \
                ') (Text too long! See comment)'
        self.assertEquals(title, submission.title.encode('utf-8'))
        self.assertEquals(picture, submission.url)
        comment = submission.comments[0].body.encode('utf-8')
        self.assertTrue(unique_text in comment)

    def test_post_to_reddit_video(self):
        unique = uuid.uuid4()
        video = 'http://www.youtube.com/watch?v=7anpvGqQxwI?unique='\
                + str(unique)
        unique_text = u'Video test: ' + unicode(unique) + \
                      self.unicode_text
        unique_text = unique_text.encode('utf-8')
        post_details = sakuraibot.PostDetails('Pug', unique_text,
                                              None, video, None)
        submission = self.sbot.post_to_reddit(post_details)
        self.assertEquals(submission,
                          self.subreddit.get_new(limit=1).next())
        self.assertEquals(submission,
                          self.r.user.get_submitted(limit=1).next())
        date = datetime.now().strftime('%y-%m-%d')
        title = 'New Pug video! (' + date + ') "' + unique_text + '"'
        self.assertEquals(title, submission.title.encode('utf-8'))
        self.assertEquals(video, submission.url)
        #TODO test comment


class CompleteTests(unittest.TestCase):

    def setUp(self):
        self.sbot = sakuraibot.SakuraiBot(USERNAME, SUBREDDIT, IMGUR_ALBUM_ID,
                                          LAST_POST_FILENAME,
                                          EXTRA_COMMENT_FILENAME,
                                          PICTURE_MD5_FILENAME,
                                          debug=True)

    def test_bot_cycle(self):
        self.sbot.bot_cycle()
        #TODO: asserts


if __name__ == '__main__':
    unittest.main()
