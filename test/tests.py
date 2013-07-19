#!/usr/bin/python
'''
Created on 2013-07-17
Author: Wiwiweb

SakuraiBot test suite
'''
from lxml.html.builder import IMG

import unittest
import sakuraibot
import urllib2
import uuid
import praw
from time import sleep
from datetime import datetime
from json import loads
from shutil import copy
from filecmp import cmp
from os import remove

USERNAME = 'SakuraiBot_test'
SUBREDDIT = 'SakuraiBot_test'
USER_AGENT = "SakuraiBot test suite"

REDDIT_PASSWORD_FILENAME = "../res/private/reddit-password.txt"
LAST_POST_FILENAME = "last-post.txt"
EXTRA_COMMENT_FILENAME = "extra-comment.txt"
IMGUR_CLIENT_ID = '45b2e3810d7d550'

f = open(REDDIT_PASSWORD_FILENAME, 'r')
reddit_password = f.read().strip()
f.close()


class BasicTests(unittest.TestCase):

    def test_get_new_miiverse_cookie(self):
        self.sbot = sakuraibot.SakuraiBot(LAST_POST_FILENAME, EXTRA_COMMENT_FILENAME)
        cookie = self.sbot.get_new_miiverse_cookie()
        self.assertRegexpMatches(cookie, r'^[0-9]{10}[.].{43}$', "Malformed cookie: " + cookie)

    def test_is_new_post_yes(self):
        self.sbot = sakuraibot.SakuraiBot(LAST_POST_FILENAME, EXTRA_COMMENT_FILENAME)
        self.assertTrue(self.sbot.is_new_post('/posts/AYMHAAABAAAYUKk9MS0TYA'))
   
    def test_is_new_post_no(self):
        self.sbot = sakuraibot.SakuraiBot(LAST_POST_FILENAME, EXTRA_COMMENT_FILENAME)
        self.assertFalse(self.sbot.is_new_post('/posts/AYMHAAABAAD4UV51j0kRvw'))

    def test_set_last_post(self):
        file_before = 'last-post-before.txt'
        file_copy = 'last-post-before-copy.txt'
        copy(file_before, file_copy)
        self.sbot = sakuraibot.SakuraiBot(file_copy, EXTRA_COMMENT_FILENAME)
        self.sbot.set_last_post('/posts/AYMHAAABAABtUV58VKXjyQ')
        self.assertTrue(cmp(file_copy, LAST_POST_FILENAME))
        remove(file_copy)


class MiiverseTests(unittest.TestCase):
    
    def setUp(self):
        self.sbot = sakuraibot.SakuraiBot(LAST_POST_FILENAME, EXTRA_COMMENT_FILENAME)
        self.cookie = self.sbot.get_new_miiverse_cookie()
 
    def test_get_miiverse_last_post(self):
        url = self.sbot.get_miiverse_last_post(self.cookie)
        self.assertRegexpMatches(url, r'^/posts/.{22}$', "Malformed URL: " + url)
         
    def test_get_info_from_post_text(self):
        url = '/posts/AYMHAAABAADOUV51jNwWyg'
        text = unicode("Hi I'm the director of Super Smash Bros., Masahiro Sakurai of Sora.\r\n" 
                "From now on, I'll be posting on Miiverse, so I hope you'll look forward to my posts.\r\n" 
                "Please note that I won't be able to answer any questions.")
         
        info = self.sbot.get_info_from_post(url, self.cookie)
        self.assertTrue(info.is_text_post())
        self.assertEqual(info.author, 'Sakurai')
        self.assertEqual(info.text, text)
        self.assertIsNone(info.picture)
        self.assertIsNone(info.video)
        self.assertIsNone(info.smashbros_pic)
     
    def test_get_info_from_post_picture(self):
        url = '/posts/AYMHAAABAABtUV58IEIGrA'
        text = unicode("Mega Man 2 seems to be the most popular, so many of his moves are from that game.")
        picture = 'https://d3esbfg30x759i.cloudfront.net/ss/zlCfzRAybhUAGnxAWi'
         
        info = self.sbot.get_info_from_post(url, self.cookie)
        self.assertTrue(info.is_picture_post())
        self.assertEqual(info.author, 'Sakurai')
        self.assertEqual(info.text, text)
        self.assertEqual(info.picture, picture)
        self.assertIsNone(info.video)
        self.assertIsNone(info.smashbros_pic)
          
    def test_get_info_from_post_video(self):
        url = '/posts/AYMHAAABAADMUKlXokfF0g'
        text = unicode("The long-awaited super robot Mega Man joins the battle!\r\n"
                       "He fights using the various weapons he acquired from bosses in past games.")
        video = 'http://www.youtube.com/watch?v=aX2KNyaoNV4'
         
        info = self.sbot.get_info_from_post(url, self.cookie)
        self.assertTrue(info.is_video_post())
        self.assertEqual(info.author, 'Sakurai')
        self.assertEqual(info.text, text)
        self.assertIsNone(info.picture)
        self.assertEqual(info.video, video)
        self.assertIsNone(info.smashbros_pic)


class ImgurTests(unittest.TestCase):
    
    def setUp(self):
        self.sbot = sakuraibot.SakuraiBot(LAST_POST_FILENAME, EXTRA_COMMENT_FILENAME)
        self.picture = 'http://i.imgur.com/uQIRrD2.gif'
        
    def test_upload_to_imgur(self):
        album_id = 'ugL4N'
        unique = unicode(uuid.uuid4()) + u' No \u0CA0_\u0CA0 ; Yes \u0CA0\u203F\u0CA0'
        unique = unique.encode('utf-8')
        post_details = sakuraibot.PostDetails('Pug', unique, self.picture, None, None)
        picture_url = self.sbot.upload_to_imgur(post_details, album_id)
        picture_id = picture_url[19:-4]

        req = urllib2.Request('https://api.imgur.com/3/image/' + picture_id)
        req.add_header("Authorization", "Client-ID " + IMGUR_CLIENT_ID)
        json_resp = loads(urllib2.urlopen(req).read())
        id_json = json_resp['data']['id']
        title_json = json_resp['data']['title'].encode('utf-8')
        self.assertEqual(picture_id, id_json)
        self.assertEqual(unique, title_json)

        req = urllib2.Request('https://api.imgur.com/3/album/' + album_id)
        req.add_header("Authorization", "Client-ID " + IMGUR_CLIENT_ID)
        json_resp = loads(urllib2.urlopen(req).read())
        album_id_json = json_resp['data']['id']
        picture_id_json = json_resp['data']['images'][-1]['id']
        self.assertEqual(album_id, album_id_json)
        self.assertEqual(picture_id, picture_id_json)


class RedditTests(unittest.TestCase):

    def setUp(self):
        self.sbot = sakuraibot.SakuraiBot(LAST_POST_FILENAME, EXTRA_COMMENT_FILENAME)
        self.r = praw.Reddit(user_agent=USER_AGENT)
        self.r.login(USERNAME, reddit_password)
        self.subreddit = self.r.get_subreddit(SUBREDDIT)
        self.r.config.cache_timeout = 0

    def test_post_to_reddit_text(self):
        unique = unicode(uuid.uuid4()) + u' No \u0CA0_\u0CA0 ; Yes \u0CA0\u203F\u0CA0'
        unique = unique.encode('utf-8')
        post_details = sakuraibot.PostDetails('Pug', unique, None, None, None)
        submission = self.sbot.post_to_reddit(post_details, SUBREDDIT, USERNAME, reddit_password)
        self.assertEquals(submission, self.subreddit.get_new(limit=1).next())
        self.assertEquals(submission, self.r.user.get_submitted(limit=1).next())
        date = datetime.now().strftime('%y-%m-%d')
        title = 'New Pug post! (' + date + ') "' + unique + '" (No picture)'
        self.assertEquals(title, submission.title.encode('utf-8'))
        #TODO: test comment

    def test_post_to_reddit_text_long(self):
        unique = unicode(uuid.uuid4()) \
            + u' No \u0CA0_\u0CA0 ; Yes \u0CA0\u203F\u0CA0'\
            u'. By the way this text is very very very very very very very '\
            u'very very very very very very very very very very very very ' \
            u'very very very very very very very very very very very very ' \
            u'very very very very very very very very very very very long.'
        unique = unique.encode('utf-8')
        post_details = sakuraibot.PostDetails('Pug', unique, None, None, None)
        submission = self.sbot.post_to_reddit(post_details, SUBREDDIT, USERNAME, reddit_password)
        self.assertEquals(submission, self.subreddit.get_new(limit=1).next())
        self.assertEquals(submission, self.r.user.get_submitted(limit=1).next())
        date = datetime.now().strftime('%y-%m-%d')
        title = 'New Pug post! (' + date + ') (Text too long! See post) (No picture)'
        self.assertEquals(title, submission.title.encode('utf-8'))
        #TODO: test comment