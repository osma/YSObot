# YSObot

This is a Twitter bot that announces new YSO concepts

# Installing

You need Python 2.x with the following libraries:

* twitter
* requests

You can install the dependencies using `pip install` or your distribution's package manager.

# Operation

This bot is expected to be launched periodically from e.g. a cron job. It
performs a [Finto](http://finto.fi) search for newly added YSO concepts. For
each concept, it also checks whether [Finna](http://finna.fi) has any items
with the concept label as subject. Then it will announce the new concepts in
status updates and exit.

# Licence

CC0
