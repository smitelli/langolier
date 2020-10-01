import argparse
import enum
import html
import json
import os
import re
import tweepy
import yaml
from datetime import datetime

"""
API limitation stuff. Per the docs at
https://developer.twitter.com/en/docs/twitter-api/v1/tweets/timelines/api-reference/get-statuses-user_timeline
the maximum number of tweets returned per page is 200, so we use that max in
every request we can. Separately, the API imposes a *firm* return limit of
3,200 tweets total, regardless of any pagination trickery. The only way to find
tweets past this 3,200-tweet limit is to request an archive export. Therefore,
we "squeeze" the limit down by 100 (chosen arbitrarily) so the account will
(probably) never amass enough tweets to require another archive export.
"""
PER_PAGE = 200
HOLY_LIMIT = 3200
HOLY_LIMIT_SQUEEZE = HOLY_LIMIT - 100


class TweetBuilder:
    def __init__(self, *, api, keep_days, keep_ids):
        self.api = api
        self.keep_days = keep_days
        self.keep_ids = keep_ids

    def from_api_favorite(self, status):
        return Tweet(
            id_=status.id_str or str(status.id), created_at=status.created_at,
            kind=Tweet.KIND.FAVORITE, keep_days=self.keep_days,
            keep_ids=self.keep_ids, api=self.api)

    def from_api_status(self, status):
        if hasattr(status, 'retweeted_status'):
            kind = Tweet.KIND.RETWEET
        else:
            kind = Tweet.KIND.TWEET

        return Tweet(
            id_=status.id_str or str(status.id), created_at=status.created_at,
            kind=kind, keep_days=self.keep_days, keep_ids=self.keep_ids,
            api=self.api)

    def from_archive_status(self, status):
        if status['tweet']['full_text'].startswith('RT @'):  # ugh...
            kind = Tweet.KIND.RETWEET
        else:
            kind = Tweet.KIND.TWEET

        return Tweet(
            id_=status['tweet']['id_str'] or str(status['tweet']['id']),
            created_at=status['tweet']['created_at'], kind=kind,
            keep_days=self.keep_days, keep_ids=self.keep_ids, api=self.api)


class Tweet:
    class KIND(enum.Enum):
        TWEET = 'Tweet'
        RETWEET = 'Retweet'
        FAVORITE = 'Favorite'

    def __init__(self, *, id_, created_at, kind, keep_days, keep_ids, api):
        self.id = id_
        self.created_at = created_at
        self.kind = kind
        self.keep_days = keep_days
        self.keep_ids = keep_ids
        self.api = api

    def __str__(self):
        return f'<{self.kind.value} {self.id}>'

    @property
    def should_delete(self):
        if (datetime.now() - self.created_at).days <= self.keep_days:
            return False

        if self.id in self.keep_ids:
            return False

        return True

    def delete(self, *, force=False):
        CODE_DOES_NOT_EXIST = 34
        CODE_NOT_FOUND = 144

        if force:
            fn_sequence = (
                self.api.destroy_status,
                self.api.unretweet,
                self.api.destroy_favorite)
        elif self.kind == self.KIND.TWEET:
            fn_sequence = (self.api.destroy_status, )
        elif self.kind == self.KIND.RETWEET:
            fn_sequence = (self.api.unretweet, )
        elif self.kind == self.KIND.FAVORITE:
            fn_sequence = (self.api.destroy_favorite, )

        for fn in fn_sequence:
            try:
                fn(self.id)
            except tweepy.error.TweepError as exc:
                if exc.api_code not in (CODE_DOES_NOT_EXIST, CODE_NOT_FOUND):
                    raise


def enrich_json(obj):
    """
    Turn JSON types into more useful object types when warranted.
    """
    if 'created_at' in obj:
        obj['created_at'] = datetime.strptime(
            obj['created_at'], '%a %b %d %H:%M:%S %z %Y').replace(tzinfo=None)

    for key in ('full_text', 'name'):
        if key in obj:
            obj[key] = html.unescape(obj[key])

    return obj


def load_archive_file(filename):
    """
    Parse a Twitter archive file into an object (usually a list of dicts).

    This is needed because the Twitter archive data files are actually
    JavaScript, and not conformant JSON. As of September 2020, the format is:

        window.YTD.tweet.part0 = [ {
          ...
        } ]

    This function reads the provided filename, strips off the assignment, and
    tries to strip any trailing code that may be present, returning an object.
    """
    with open(filename, 'r') as fh:
        payload = fh.read()

    payload = re.search(r'^(?:.+?)=(.+)$', payload, re.DOTALL).group(1)

    try:
        return json.loads(payload, object_hook=enrich_json)
    except json.decoder.JSONDecodeError as exc:
        # HACK: If the decode fails, make a blind assumption that the reason is
        # due to a trailing semicolon or continuation of JS code in the file.
        # Slice the string at the position of the decode error then retry.
        payload = payload[:exc.pos]

        return json.loads(payload, object_hook=enrich_json)


def main(*, config_file, archive_dir=None, force=False, skip=None):
    if force:
        print('Using force.')

    if skip is not None:
        print(f'Skipping past ID {skip}.')

    with open(config_file, 'r') as fh:
        cfg = yaml.safe_load(fh)

    auth = tweepy.OAuthHandler(cfg['consumer_key'], cfg['consumer_secret'])
    auth.set_access_token(cfg['access_token'], cfg['access_token_secret'])
    api = tweepy.API(auth_handler=auth)

    tb = TweetBuilder(
        api=api, keep_days=cfg['keep_days'], keep_ids=cfg['keep_ids'])
    kept = 0

    if archive_dir is not None:
        print(f'Using {archive_dir} for archive mode.')

        archive_data = load_archive_file(os.path.join(archive_dir, 'tweet.js'))

        archive_data = sorted(
            archive_data, key=lambda s: int(s['tweet']['id_str']), reverse=True)

        """
        Clean up tweets and retweets referenced in the archive data.
        """
        for status in archive_data:
            tweet = tb.from_archive_status(status)

            if skip is not None and int(tweet.id) >= skip:
                continue

            if tweet.should_delete or kept >= HOLY_LIMIT_SQUEEZE:
                print(tweet)
                tweet.delete(force=force)
            else:
                kept += 1
    else:
        print('Using the API.')

        """
        Clean up favorites.
        """
        for status in tweepy.Cursor(
            api.favorites, screen_name=cfg['screen_name'], count=PER_PAGE
        ).items():
            tweet = tb.from_api_favorite(status)

            if skip is not None and int(tweet.id) >= skip:
                continue

            if tweet.should_delete:
                print(tweet)
                tweet.delete(force=force)

        """
        Clean up tweets and retweets.
        """
        for status in tweepy.Cursor(
            api.user_timeline, screen_name=cfg['screen_name'], count=PER_PAGE,
            exclude_replies=False, include_rts=True
        ).items():
            tweet = tb.from_api_status(status)

            if skip is not None and int(tweet.id) >= skip:
                continue

            if tweet.should_delete or kept >= HOLY_LIMIT_SQUEEZE:
                print(tweet)
                tweet.delete(force=force)
            else:
                kept += 1

    print(f'{kept} tweets kept.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Delete old tweets, either by API iteration or archives')
    parser.add_argument(
        '-c', '--config', metavar='FILE', required=True,
        help='read account configuration from FILE')
    parser.add_argument(
        '-a', '--archive', metavar='DIR',
        help='process Twitter archive data DIR')
    parser.add_argument(
        '-f', '--force', action='store_true',
        help='whale on the API to delete unusually persistent items')
    parser.add_argument(
        '-s', '--skip', metavar='ID', type=int,
        help='skip processing up to ID (inclusive)')
    args = parser.parse_args()

    main(
        config_file=args.config, archive_dir=args.archive, force=args.force,
        skip=args.skip)
