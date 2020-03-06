import spotipy
import os
import flask
from flask import Flask, request, render_template, session, redirect, url_for
from markupsafe import escape


app = Flask(__name__, template_folder='./templates')


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
    token[0] = spotipy.prompt_for_user_token(username, scope)
    sp[0] = spotipy.Spotify(auth=token[0])
    print(token)
    print(sp)
    return "asdf"


@app.route('/callback')
def redir():
    print()
    return render_template('return.html')


@app.route('/continue', methods=['POST'])
def cont():
    read, write = os.pipe()
    cu = request.form['callbackUrl']
    os.write(write, bytes(cu, 'utf-8'))
    os.close(write)

    print(request.form['callbackUrl'])
    return redirect(url_for('test'))


@app.route('/test')
def test():
    return spotipy.Spotify(auth=token[0]).currently_playing()
