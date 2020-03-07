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
        currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
        currentSession = listeningSessions.get(currentUser.id)
        print(SPOTIFY_USERS)
        print(listeningSessions)
        return flask.render_template("index.html", user=currentUser, openSession=currentSession)
    except KeyError:
        return flask.redirect(OAUTH2.url)


@APP.route('/newSession')
def start():
    currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
    playlists = currentUser.get_all_playlists()

    playlist = currentUser.create_playlist('Spo2fi Queue', collaborative=True, public=False)
    # print(playlists)
    return flask.render_template("newSession.html", playlists=playlists)


@APP.route('/newPlaylist')
def newPlaylist():
    currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
    playlist = currentUser.create_playlist('Spo2fi Queue', collaborative=True, public=False)
    listeningSessions[currentUser.id] = ListeningSession(currentUser, [], playlist)
    return flask.render_template("queue.html", user=currentUser, playlist=playlist)


@APP.route('/search')
def search():
    try:
        query = flask.request.args["query"]
    except KeyError:
        return "no query entered"
    else:
        currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
        results = SPOTIFY_CLIENT.search(query, limit=5)
        return flask.render_template("queue.html",
                                     artists=results[0],
                                     playlists=results[1],
                                     albums=results[2],
                                     tracks=results[3])


if __name__ == '__main__':
    APP.run('localhost', port=5000, debug=False)
