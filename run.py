import argparse
import enum
import tweepy
import yaml
from datetime import datetime

"""
API limitation stuff. Per the docs at
https://developer.twitter.com/en/docs/twitter-api/v1/tweets/timelines/api-reference/get-statuses-user_timeline
the maximum number of tweets returned per page is 200, so we use that max in
every request we can. Separately, the API imposes a *firm* limit of 3,200
tweets total, regardless of any pagination trickery. The only way to find
tweets past this 3,200-tweet limit is to request an archive export. Therefore,
we "squeeze" the limit down by 100 (chosen arbitrarily) so the account can
never amass enough tweets to require another archive export in the future.
"""
PER_PAGE = 200
HOLY_LIMIT = 3200
HOLY_LIMIT_SQUEEZE = HOLY_LIMIT - 100


class TweetWrap:
    class KIND(enum.Enum):
        TWEET = 'Tweet'
        RETWEET = 'Retweet'
        FAVORITE = 'Favorite'

    def __init__(self, status, *, favorite=False):
        self.api = status._api
        self.id = status.id_str or str(status.id)
        self.created_at = status.created_at
        self.keep_days = 365
        self.keep_ids = []

        if favorite:
            self.kind = self.KIND.FAVORITE
        elif hasattr(status, 'retweeted_status'):
            self.kind = self.KIND.RETWEET
        else:
            self.kind = self.KIND.TWEET

    def __str__(self):
        return f'<{self.kind.value} {self.id}>'

    @property
    def should_delete(self):
        if (datetime.now() - self.created_at).days < self.keep_days:
            return False

        if self.id in self.keep_ids:
            return False

        return True

    def delete(self):
        return  # TODO
        if self.kind == self.KIND.TWEET:
            self.api.destroy_status(self.id)
        elif self.kind == self.KIND.RETWEET:
            self.api.unretweet(self.id)
        elif self.kind == self.KIND.FAVORITE:
            self.api.destroy_favorite(self.id)


def main(*, config_file, archive_dir):
    with open(config_file, 'r') as fh:
        cfg = yaml.safe_load(fh)

    if archive_dir is not None:
        pass  # TODO

    auth = tweepy.OAuthHandler(cfg['consumer_key'], cfg['consumer_secret'])
    auth.set_access_token(cfg['access_token'], cfg['access_token_secret'])
    api = tweepy.API(auth_handler=auth)

    """
    Clean up favorites.
    """
    for status in tweepy.Cursor(
            api.favorites, screen_name=cfg['screen_name'],
            count=PER_PAGE).items():

        tweet = TweetWrap(status, favorite=True)
        tweet.keep_days = cfg['keep_days']
        tweet.keep_ids = cfg['keep_ids']

        if tweet.should_delete:
            print(tweet)
            tweet.delete()

    """
    Clean up tweets and retweets.
    """
    for i, status in enumerate(tweepy.Cursor(
            api.user_timeline, screen_name=cfg['screen_name'], count=PER_PAGE,
            exclude_replies=False, include_rts=True).items()):

        tweet = TweetWrap(status)
        tweet.keep_days = cfg['keep_days']
        tweet.keep_ids = cfg['keep_ids']

        if tweet.should_delete or i >= HOLY_LIMIT_SQUEEZE:
            print(tweet)
            tweet.delete()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Delete old tweets, either by API iteration or archives')
    parser.add_argument(
        '-c', '--config', metavar='FILE', required=True,
        help='read account configuration from FILE')
    parser.add_argument(
        '-a', '--archive', metavar='DIR',
        help='process Twitter archive data DIR')
    args = parser.parse_args()

    main(config_file=args.config, archive_dir=args.archive)
