import html
import json
import re
from datetime import datetime


def enrich_json(obj):
    """
    Turn JSON types into more useful object types when warranted.
    """
    if 'created_at' in obj:
        obj['created_at'] = datetime.strptime(
            obj['created_at'], '%a %b %d %H:%M:%S %z %Y')

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


archive = load_archive_file('/Users/ssmitelli/Downloads/twitter-2020-09-29-c4dfed4c9e517c72171510f18eed14c13c2bd1286774c1177557c6bcbb9f6a24/data/tweet.js')
archive = sorted(archive, key=lambda t: int(t['tweet']['id_str']), reverse=True)

for t in archive:
    # t['tweet']['source'] - str w/ post client
    # t['tweet']['display_text_range'][1] - str w/ number, ?
    # t['tweet']['favorite_count'] - str w/ number, fav count
    # t['tweet']['id_str'] - str w/ number, ID
    # t['tweet']['retweet_count'] - str w/ number, RT count
    # t['tweet']['lang'] - str w/ 2-char code or "und"
    # t['tweet']['full_text'] - str

    #print(t['tweet']['created_at'], t['tweet']['full_text'], t['tweet']['id'])
    pass

print(archive)
