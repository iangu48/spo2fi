import os
import random
import string
from typing import Dict

import flask
import spotify.sync as spotify
from flask import Blueprint

from main.models import ListeningSession

bp = Blueprint('auth', __name__)

#  Client Keys
SPOTIFY_CLIENT_ID = os.environ['SPOTIFY_CLIENT_ID']
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = os.environ['REDIRECT_URI']

SPOTIFY_CLIENT = spotify.Client(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)

OAUTH2_SCOPES = ('user-modify-playback-state',
                 'user-read-currently-playing',
                 'user-read-playback-state',
                 'user-read-playback-state',
                 'user-modify-playback-state',
                 'user-read-currently-playing',
                 'streaming app-remote-control',
                 'playlist-read-collaborative',
                 'playlist-modify-private',
                 'playlist-read-private',
                 'playlist-modify-public',
                 'user-library-read',
                 'playlist-read-private',
                 'user-top-read',
                 'user-read-recently-played',
                 'user-follow-read',
                 'user-follow-modify')
OAUTH2: spotify.OAuth2 = spotify.OAuth2(SPOTIFY_CLIENT.id, REDIRECT_URI, scopes=OAUTH2_SCOPES)

SPOTIFY_USERS: Dict[str, spotify.User] = {}
listeningSessions: Dict[str, ListeningSession] = {}
partyIdMap: Dict[str, str] = {}


@bp.route('/spotify/callback')
def spotify_callback():
    try:
        code = flask.request.args['code']
    except KeyError:
        return flask.redirect('/spotify/failed')
    else:
        key = ''.join(random.choice(string.ascii_uppercase) for _ in range(16))
        while key in SPOTIFY_USERS:
            key = ''.join(random.choice(string.ascii_uppercase) for _ in range(16))

        # noinspection PyTypeChecker
        SPOTIFY_USERS[key] = spotify.User.from_code(SPOTIFY_CLIENT, code, redirect_uri=REDIRECT_URI)

        flask.session['spotify_user_id'] = key

    return flask.redirect('/')


@bp.route('/spotify/failed')
def spotify_failed():
    flask.session.pop('spotify_user_id', None)
    return 'Failed to authenticate with Spotify.'
