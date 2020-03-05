# spo2fi

import warnings

import requests
import spotipy
import os
import flask
from flask import Flask, request

app = Flask(__name__)

clientId = os.environ['SPOTIPY_CLIENT_ID']
print(clientId)
clientSecret = os.getenv('SPOTIPY_CLIENT_SECRET')
print(clientSecret)
redirectUri = os.environ['SPOTIPY_REDIRECT_URI']
print(redirectUri)

scope = 'user-read-playback-state ' \
        'user-modify-playback-state ' \
        'user-read-currently-playing ' \
        'streaming app-remote-control ' \
        'playlist-read-collaborative ' \
        'playlist-modify-public ' \
        'user-library-read ' \
        'playlist-read-private ' \
        'user-top-read ' \
        'user-read-recently-played ' \
        'user-follow-read ' \
        'user-follow-modify ' \
        ' '

token = {}
sp = {}

os.environ['SPOTIPY_CLIENT_USERNAME'] = 'i9iwajo8z5oz85pmrrqsthwrj'


@app.route('/')
def main():
    username = 'i9iwajo8z5oz85pmrrqsthwrj'
    token[0] = prompt_for_user_token(username, scope)
    sp[0] = spotipy.Spotify(auth=token[0])
    print(token)
    print(sp)
    return "asdf"


@app.route('/return')
def redir():
    print()
    return 'token[0]'


@app.route('/test')
def test():
    return spotipy.Spotify(auth=token[0]).currently_playing()


def prompt_for_user_token(
        username,
        scopeLocal=None,
        client_id=None,
        client_secret=None,
        redirect_uri=None,
        cache_path=None,
        oauth_manager=None,
        show_dialog=False
):
    """ prompts the user to login if necessary and returns
        the user token suitable for use with the spotipy.Spotify
        constructor

        Parameters:

         - username - the Spotify username
         - scope - the desired scope of the request
         - client_id - the client id of your app
         - client_secret - the client secret of your app
         - redirect_uri - the redirect URI of your app
         - cache_path - path to location to save tokens
         - oauth_manager - Oauth manager object.

    """

    sp_oauth = spotipy.SpotifyOAuth(
        client_id,
        client_secret,
        redirect_uri,
        scope=scopeLocal,
        cache_path=cache_path,
        show_dialog=show_dialog
    )

    # try to get a valid token for this user, from the cache,
    # if not in the cache, the create a new (this will send
    # the user to a web page where they can authorize this app)

    token_info = sp_oauth.get_cached_token()

    if not token_info:
        url = sp_oauth.get_authorize_url()
        code = sp_oauth.parse_response_code(url)
        tokenLocal = sp_oauth.get_access_token(code, as_dict=False)
    else:
        return token_info["access_token"]

    # Auth'ed API request
    if tokenLocal:
        return tokenLocal
    else:
        return None
