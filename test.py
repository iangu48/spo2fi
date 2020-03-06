from models import ListeningSession
import os
import string
import random
from typing import Tuple, Dict

import flask
import spotify.sync as spotify

#  Client Keys
SPOTIFY_CLIENT_ID = os.environ['SPOTIFY_CLIENT_ID']
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

SPOTIFY_CLIENT = spotify.Client(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)

APP = flask.Flask(__name__)
APP.secret_key = os.environ['SESSION_SECRET_KEY']
APP.config.from_mapping({'spotify_client': SPOTIFY_CLIENT})

REDIRECT_URI: str = 'http://localhost:5000/spotify/callback'

OAUTH2_SCOPES = ('user-modify-playback-state', 'user-read-currently-playing', 'user-read-playback-state')
OAUTH2: spotify.OAuth2 = spotify.OAuth2(SPOTIFY_CLIENT.id, REDIRECT_URI, scopes=OAUTH2_SCOPES)

SPOTIFY_USERS: Dict[str, spotify.User] = {}
listeningSessions: Dict[str, ListeningSession]


@APP.route('/spotify/callback')
def spotify_callback():
    try:
        code = flask.request.args['code']
    except KeyError:
        return flask.redirect('/spotify/failed')
    else:
        key = ''.join(random.choice(string.ascii_uppercase) for _ in range(16))
        # noinspection PyTypeChecker
        SPOTIFY_USERS[key] = spotify.User.from_code(SPOTIFY_CLIENT, code, redirect_uri=REDIRECT_URI)

        flask.session['spotify_user_id'] = key

    return flask.redirect('/')


@APP.route('/spotify/failed')
def spotify_failed():
    flask.session.pop('spotify_user_id', None)
    return 'Failed to authenticate with Spotify.'


@APP.route('/')
@APP.route('/index')
def index():
    try:
        return repr(SPOTIFY_USERS[flask.session['spotify_user_id']])
    except KeyError:
        return flask.redirect(OAUTH2.url)


@APP.route('/user')
def user():
    currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
    # print(SPOTIFY_USERS)
    track = currentUser.currently_playing()['item'].images
    print(track)
    return flask.render_template("test.html", user=currentUser)


if __name__ == '__main__':
    APP.run('127.0.0.1', port=5000, debug=False)
