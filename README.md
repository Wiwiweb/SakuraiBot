SakuraiBot
==========

SakuraiBot is a reddit bot for fetching new Smash Bros 4 posts and pictures posted by the developper Sakurai on Miiverse.  
It is made in Python using the libraries [PRAW](https://github.com/praw-dev/praw), [Requests](http://docs.python-requests.org/en/latest/) and [Beautiful Soup](http://www.crummy.com/software/BeautifulSoup/).

The bot will periodically look at the top post of the [Miiverse Smash Bros Director](https://miiverse.nintendo.net/titles/14866558073037299863/14866558073037300685) page. If the post is new, it will follow its link and read the text, picture and/or video.  
If the post contains a picture, the bot will find the [smashbros.com daily picture](http://www.smashbros.com/update/images/daily.jpg), which is the same picture but higher quality and without a watermark. Since the Miiverse post can sometimes be posted before the smashbros.com picture is updated, the bot checks the picture's md5 to see if it is really new.  
If everything is new, the bot then uploads this picture to imgur, [adding it to an album](http://imgur.com/a/8KnTr), and posts the imgur link to [/r/smashbros](www.reddit.com/r/smashbros/), using the text of the Miiverse post as the title of the reddit post.  
Finally, if everything went correctly, the Miiverse post ID and smashbros.com md5 will be added to files so we remember they have already been processed.

In case of error (such as Miiverse being down), the bot will try 5 more cycles. After that, it will send an email containing the logfile to the address indicated.

Usage
-----

Make sure you are using Python 3. If not done already, install PRAW, requests and Beautiful Soup:

`pip install praw requests bs4`

After that, you will need to fill out the cfg/config-private.ini file with your passwords and tokens, as well as modify the defaults in cfg/config.ini if needed.

Once done, run the bot using the `start.sh` script.

Contribute
----------

Pull requests are welcome! Feel free to submit after reading the following:

This code respects [PEP8](http://www.python.org/dev/peps/pep-0008/) and [PEP257](http://www.python.org/dev/peps/pep-0257/). Tests will verify if these are respected, and will give out messages pointing out errors, however it might be more convenient to use the existing command line scripts: Download them with `pip install pep8 pep257`.

If you add something, please also add tests to `tests.py`. The tests use a subreddit, [/r/SakuraiBot_test](http://www.reddit.com/r/SakuraiBot_test/) and a user [/u/SakuraiBot_test](http://www.reddit.com/user/SakuraiBot_test/).

Thank you for your interest!
