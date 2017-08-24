#!/usr/bin/env python
# -*- coding: utf-8 -*-

import twitter
import requests
from SPARQLWrapper import SPARQLWrapper, JSON

import logging
import re
import urllib
import argparse
import os
import time

FINTO_ENDPOINT="http://api.dev.finto.fi/sparql"
YSO_GRAPH="http://www.yso.fi/onto/yso/"
FINNA_API_SEARCH='https://api.finna.fi/v1/search'
FINNA_WEB_SEARCH='https://finna.fi/Search/Results'

BOT_NAME='YSO Bot'
SCREEN_NAME='YSOuudet'

# limits on tweeting
TWEET_INTERVAL=15*60	# interval between successive tweets
MAX_LIMIT=30		# maximum number of tweets per run


CREDENTIALS_FILE='~/.ysobot_credentials'
# App registered by @OsmaSuominen
# I don't care that these are public, as the real authentication is done using OAuth tokens
CONSUMER_KEY='ykls7PFsyCV6iVgY2aFAbYVSM'
CONSUMER_SECRET='jkRgoEDLxNtBeSYm5LgQx8mjYT0fPheBrU3QIDA0vo714fpHfd'


def query_new_yso():
    """query for the most recent concepts added to YSO"""
    sparql = SPARQLWrapper(FINTO_ENDPOINT)
    sparql.setQuery("""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
        PREFIX dct:  <http://purl.org/dc/terms/>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        SELECT ?conc ?label
        FROM <%s>
        WHERE {
            ?conc a skos:Concept .
            ?conc skos:prefLabel ?label .
            ?conc dct:created ?created .
            FILTER(LANG(?label)='fi')
            FILTER NOT EXISTS { ?conc owl:deprecated true }
            FILTER(?created >= "2017-02-01"^^xsd:date)
        }
        ORDER BY DESC(?created)
        LIMIT 100
    """ % YSO_GRAPH)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    return [(r['conc']['value'], r['label']['value']) for r in results['results']['bindings']]

def label_to_hashtag(label):
    """convert a label to a Twitter hashtag, taking care of spaces and special characters"""
    label = label.replace(' ','_')
    label = label.replace('-','_')
    label = re.sub(r'\W', '', label, flags=re.UNICODE)
    return '#' + label

def compose_tweet(conc, label, hits):
    """return the text of a tweet about this concept"""
    text1 = u"Uusi #YSO-käsite: %s %s" % (label_to_hashtag(label), conc)
    if hits == 0:
        text2 = u"Ei löydy aiheena Finnasta."
    elif hits == 1:
        text2 = u"Finnassa aiheena kerran: %s" % get_finna_url(label)
    else:
        text2 = u"Finnassa aiheena %d kertaa: %s" % (hits, get_finna_url(label))
    return text1 + u' ' + text2

def search_finna(label):
    """return the number of hits when searching for this subject on Finna"""
    params = {'lookfor': '"%s"' % label.encode('UTF-8'), 'type': 'Subject', 'field[]': "['id']", 'headers':{'User-Agent: YSObot'}}
    r = requests.get(FINNA_API_SEARCH, params=params)
    result = r.json()
    return result['resultCount']

def get_finna_url(label):
    """return an URL for a Finna search result list with the specified label as subject"""
    params = {'lookfor': '"%s"' % label.encode('UTF-8'), 'type': 'Subject'}
    return FINNA_WEB_SEARCH + '?' + urllib.urlencode(params)

if __name__ == '__main__':
    # initialize command line parsing
    parser = argparse.ArgumentParser(description='Tweet new YSO concepts')
    parser.add_argument('-n', '--simulate', action='store_true', help="Simulation mode: Don't actually tweet anything")
    args = parser.parse_args()
    
    # initialize logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')
    
    # initialize twitter authentication
    MY_TWITTER_CREDS = os.path.expanduser(CREDENTIALS_FILE)
    if not os.path.exists(MY_TWITTER_CREDS):
        twitter.oauth_dance(BOT_NAME, CONSUMER_KEY, CONSUMER_SECRET, MY_TWITTER_CREDS)
    oauth_token, oauth_secret = twitter.read_token_file(MY_TWITTER_CREDS)
    t = twitter.Twitter(auth=twitter.OAuth(oauth_token, oauth_secret, CONSUMER_KEY, CONSUMER_SECRET))
    
    # find out concepts we have already tweeted (based on hashtags)
    already_posted = set()
    for tweet in t.statuses.user_timeline(screen_name=SCREEN_NAME, count=200):
        for hashtag in ['#' + h['text'] for h in tweet['entities']['hashtags']]:
            if hashtag != '#YSO':
                already_posted.add(hashtag)
                break
    
    to_send = []
    for conc,label in query_new_yso():
        if label_to_hashtag(label) in already_posted:
            logging.debug('We have already posted %s (%s)', conc, label)
            continue
        to_send.append((conc,label))
    
    for idx, conclabel in enumerate(to_send[:MAX_LIMIT]):
        conc,label = conclabel
        text = compose_tweet(conc, label, search_finna(label))
        logging.info("Posting: %s", text)
        if args.simulate:
            logging.info("Actual posting disabled due to simulation mode.")
        else:
            t.statuses.update(status=text)
            if idx != len(to_send)-1: # not last item
                logging.info("Sleeping for %d seconds" % INTERVAL)
                time.sleep(INTERVAL)
