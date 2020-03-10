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

REDIRECT_URI = os.environ['REDIRECT_URI']

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
parties: Dict[str, str] = {}


@APP.route('/spotify/callback')
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
        return flask.render_template("index.html",
                                     user=currentUser,
                                     openSession=currentSession,
                                     owner=currentUser,
                                     isOwner=False)
    except KeyError:
        return flask.redirect(OAUTH2.url)


@APP.route('/newSession')
def start():
    currentUser: spotify.User = SPOTIFY_USERS[flask.session['spotify_user_id']]
    if currentUser.id in listeningSessions:
        # todo check if idiot user deletes playlist
        return flask.redirect(flask.url_for('.queue'))
    try:
        currentUser.currently_playing()['item']
    except KeyError:
        flask.flash("Playback device not found.. Please open your Spotify app and begin playing (any random song)",
                    category='error')
        return flask.redirect(flask.url_for('.index'))  # todo handle error
    playlists = currentUser.get_playlists()
    playlist: spotify.Playlist = None
    for p in playlists:
        print(p.name, p.name == 'Spo2fi Queue')
        if p.name == 'Spo2fi Queue':
            playlist = p
            break

    if not playlist:
        playlist = currentUser.create_playlist('Spo2fi Queue', collaborative=True, public=False)
        # currentUser.client.http.upload_playlist_cover_image(playlist.id, ) todo upload Spo2fi logo

    try:
        if currentUser.currently_playing()['is_playing']:
            playlist.replace_tracks(currentUser.currently_playing()['item'])
    except KeyError:  # currently_playing() is a beta endpoint, subject to possible future changes
        usersTopTracks = currentUser.top_tracks(limit=1, time_range='medium_term')
        print(usersTopTracks)
        playlist.replace_tracks(usersTopTracks[0])

    joinId = ''.join(random.choice(string.ascii_uppercase + string.digits) for i in range(4))
    while joinId in parties:
        joinId = ''.join(random.choice(string.ascii_uppercase + string.digits) for i in range(4))
    listeningSessions[currentUser.id] = ListeningSession(currentUser, [], playlist, joinId)
    parties[joinId] = currentUser.id

    print(currentUser.currently_playing())
    flask.session['party'] = listeningSessions[currentUser.id].joinId
    print(flask.session['party'])

    try:
        currentUser.get_player().play(playlist)
        currentUser.get_player().shuffle(False)
    except spotify.errors.NotFound:
        flask.flash("Playback device not found.. Please open your Spotify app and begin playing (any random song)",
                    category='error')
        return flask.redirect(flask.url_for('.index'))  # todo handle error
    return flask.redirect(flask.url_for('.queue'))


@APP.route('/join')
def join():
    currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
    try:
        joinId = str.upper(flask.request.args['joinId'])
        ownerId = parties[joinId]
        party = listeningSessions[ownerId]
    except KeyError:
        flask.flash('Code not found', category='error')
        return flask.redirect('/')
    else:
        if currentUser not in party.members:
            party.members.append(currentUser)
        flask.session['party'] = party.joinId
        return flask.redirect(flask.url_for('.queue'))


@APP.route('/search')
def search():
    try:
        query = flask.request.args["query"]
    except KeyError:
        return "no query entered"
    else:
        currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
        results = SPOTIFY_CLIENT.search(query, limit=10)
        ownerId = parties[flask.session['party']]
        party = listeningSessions[ownerId]
        return flask.render_template("search.html",
                                     user=currentUser,
                                     owner=party.owner,
                                     artists=results[0],
                                     playlists=results[1],
                                     albums=results[2],
                                     tracks=results[3],
                                     isOwner=currentUser == party.owner,
                                     joinId=party.joinId)


@APP.route('/add')
def addToQueue():
    try:
        print(flask.session['party'])
        ownerId = parties[flask.session['party']]
        party = listeningSessions[ownerId]
        print(party)
    except KeyError:
        return "no session currently found"
    else:
        currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
        track = SPOTIFY_CLIENT.get_track(flask.request.args['trackId'])

        # party.owner.add_tracks(party.playlist, track)  # only owner can add tracks to playlist
        party.playlist.extend([track])

        return flask.redirect(flask.url_for('.queue'))


@APP.route('/remove')
def removeTrack():
    try:
        print(flask.session['party'])
        ownerId = parties[flask.session['party']]
        party = listeningSessions[ownerId]
        print(party)
    except KeyError:
        return "no session currently found"
    else:
        currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
        track = SPOTIFY_CLIENT.get_track(flask.request.args['trackId'])

        party.playlist.remove(track)  # only owner can add tracks to playlist # todo fix this shit
        # todo removing a track removes all instances of the track in the playlist

        return flask.redirect(flask.url_for('.queue'))


@APP.route('/queue')
def queue():
    ownerId = parties[flask.session['party']]
    party = listeningSessions[ownerId]
    currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
    playlist = party.playlist
    playlists = currentUser.get_all_playlists()
    return flask.render_template("queue.html",
                                 user=currentUser,
                                 owner=party.owner,
                                 tracks=playlist.get_tracks(),
                                 joinId=party.joinId,
                                 isOwner=currentUser == party.owner,
                                 playlists=playlists)


@APP.route('/playTrack')
def playTrack():
    try:
        print(flask.session['party'])
        ownerId = parties[flask.session['party']]
        party = listeningSessions[ownerId]
        print(party)
    except KeyError:
        return "no session currently found"
    else:
        currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
        track = flask.request.args['track']
        party.owner.get_player().play(party.playlist.uri, offset=track)
        return flask.redirect(flask.url_for('.queue'))


if __name__ == '__main__':
    APP.run(host="0.0.0.0", port=5000, debug=False)
