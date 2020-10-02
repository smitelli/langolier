Langolier
=========

Nothing good ever came from a ten-year-old tweet.

by [Scott Smitelli](mailto:scott@smitelli.com)

Langolier eats old tweets from [Twitter](https://twitter.com/). It can operate in **API mode**, where it reads tweets directly from Twitter's API, or in **archive mode**, where it extracts tweets from the `data/` directory of an archive export. For any account that has (or has ever had) more than 3,200 tweets, archive mode _must_ be used at least once to delete otherwise unreachable tweets. Once the account is below 3,200 tweets, API mode can be used on a recurring basis to clean up tweets.

3,200 Tweets
------------

Twitter's API is an odd duck. Once an item passes the 3,200-tweet boundary, there's no way to reach it through any available pagination method. Furthermore, once an item falls out of pagination, it never comes back into view. Even if everything posted above these items is removed, they don't slide back into the viewable range. This doesn't appear to be documented anywhere, but the behavior was observed empirically.

To avoid having to request additional archive exports for high-volume accounts, Langolier will start deleting tweets starting at the 3,100-tweet mark _even if they are not old enough to expire naturally._ This is done solely to protect against tweets spilling over the 3,200 boundary and becoming inaccessible to subsequent runs. This means that Langolier will _either_ preserve `keep_days` days worth of tweets, or 3,100 tweets, _whichever is smaller._

**Important:** Once an account's timeline grows this large, tweets protected by the `keep_ids` list might get deleted. If you want to ensure that your `keep_id` tweets aren't swept away by this process, **never** allow more than ~3,100 tweets to pile up above them on the timeline.

Installation
------------

You'll almost certainly want to use a virtualenv to install this. The exact steps to create one will vary depending on your environment and tastes, but the end result is that you will end up with a `pip` binary that is somewhere other than the system-wide location. Run `/path/to/virtualenv/pip install /path/to/this/repo`, and upon successful completion there should be a new `langolier` binary next to `pip`.

Configuration
-------------

Langolier requires a configuration file to perform any useful work. The format is YAML, and a template follows:

    consumer_key: xyzzy
    consumer_secret: zxcvb
    access_token: foobar
    access_token_secret: bazquux
    screen_name: smitelli
    keep_days: 365
    keep_ids:
      - '12345'
      - '23456'
      - '34567'

* `consumer_key`, `consumer_secret`, `access_token`, and `access_token_secret`: These are OAuth keys for the Twitter API. You'll likely have to register a new app if you don't have consumer keys already. Make sure the key you generate has both read and write access to your account.
* `screen_name`: Should be set to your Twitter handle. I.E. if your profile is https://twitter.com/smitelli and people mention you as `@smitelli`, this should be set to `smitelli`. It goes without saying that this needs to match the API tokens, otherwise Langolier will read tweets from an account that it doesn't have the authority to delete from.
* `keep_days`: The maximum number of days a tweet will be retained for. Once a tweet is older than this, it becomes eligible for automatic deletion. Tweets may be removed earlier than this if the account has more than 3,100 tweets at any given time.
* `keep_ids`: A list of tweet IDs, **as strings and not numbers.** Each ID in this list will be spared from deletion. So, if you wanted to preserve the tweet seen at https://twitter.com/smitelli/status/335455012, the line should look like `- '335455012'`. To preserve no tweets, use the format `keep_ids: []`. Tweets in this list _may_ be deleted if the account currently has more than 3,100 tweets that have been posted since.

Save this file anywhere on your filesystem with any extension, although `.yml` or `.yaml` is customary.

Command-Line Options
--------------------

Usage: `langolier [-h] [-V] -c FILE [-a DIR] [-f] [-s ID]`

* `-h`, `--help`: Show the help message and exit.
* `-V`, `--version`: Show program's version number and exit
* `-c FILE`, `--config FILE`: Read account configuration from FILE. This is required for any operation that contacts the Twitter API.
* `-a DIR`, `--archive DIR`: Process Twitter archive data DIR. Twitter archives are delivered as a zip file containing many subdirectories and files. Of particular interest is a `data/` directory containing several `.js` files. This data directory name should be provided here. With this option present, the program operates in archive mode. If this option is omitted, API mode is used.
* `-f`, `--force`: Whale on the API to delete unusually persistent items. Some troublesome items (especially retweets from the mid-2010s) don't respond to the "delete retweet" method. This option tries every delete method on every item to give the best chance of actually deleting things.
* `-s ID`, `--skip ID`: Skip processing up to ID (inclusive). If something happens and the program crashes without finishing, pass the ID of the last item that was known to have been successfully deleted and all work prior to that point will be skipped. This is especially useful when processing a large archive that fails halfway.
