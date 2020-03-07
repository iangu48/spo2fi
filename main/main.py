import warnings
import requests
import spotipy
import os
import flask
from flask import Flask, redirect, request

app = Flask(__name__)

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
username = 'i9iwajo8z5oz85pmrrqsthwrj'
token = {}
sp = {}


@app.route('/')
def main():
    cb = redirect_user_to_oauth(username, scope)
    sp[0] = spotipy.Spotify(auth=cb)
    # print(sp[0])
    return redirect(cb)


@app.route('/callback')
def redir():
    print(request.args.get('code'))
    t = (request.args.get('access_token'))
    print(t)

    return spotipy.Spotify(auth=t).current_playback()


@app.route('/test')
def test():
    return spotipy.Spotify(auth=token[0]).currently_playing()


sp_oauth = None


def redirect_user_to_oauth(username, scope2=None, client_id=None,
                           client_secret=None, redirect_uri=None,
                           cache_path=None):
    sp_oauth = spotipy.oauth2.SpotifyOAuth(client_id, client_secret, redirect_uri,
                                           scope=scope2, cache_path=cache_path)
    # print(sp_oauth.get_access_token())
    token_info = sp_oauth.get_cached_token()
    if not token_info:
        auth_url = sp_oauth.get_authorize_url()
        return auth_url


def handle_callback(code):
    token_info = sp_oauth.get_access_token(code)
    return token_info['access_token']
