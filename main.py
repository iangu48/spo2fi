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
        print('current users: ', SPOTIFY_USERS)
        print('parties: ', listeningSessions.keys())
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
        return flask.redirect(flask.url_for('.index'))
    playlists = currentUser.get_playlists()  # todo empty playlists are not included
    playlist: spotify.Playlist = None
    for p in playlists:
        if p.name == 'Spo2fi Queue':
            playlist = p
            break

    if not playlist:
        # noinspection PyTypeChecker
        playlist = currentUser.create_playlist('Spo2fi Queue', collaborative=True, public=False)
        # currentUser.client.http.upload_playlist_cover_image(playlist.id, ) todo upload Spo2fi logo

    try:
        if currentUser.currently_playing()['is_playing']:
            playlist.replace_tracks(currentUser.currently_playing()['item'])
    except KeyError:  # new users don't have any top tracks
        usersTopTracks = currentUser.top_tracks(limit=1, time_range='medium_term')
        playlist.replace_tracks(usersTopTracks[0])

    joinId = ''.join(random.choice(string.ascii_uppercase + string.digits) for i in range(4))
    while joinId in parties:
        joinId = ''.join(random.choice(string.ascii_uppercase + string.digits) for i in range(4))
    listeningSessions[currentUser.id] = ListeningSession(currentUser, [], playlist, joinId)
    parties[joinId] = currentUser.id

    flask.session['party'] = listeningSessions[currentUser.id].joinId
    print('user ', currentUser.display_name, ' joined ' , flask.session['party'])

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
        if not query:
            flask.flash('Empty search query', category='error')
            return flask.redirect(flask.url_for('.queue'))
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
        ownerId = parties[flask.session['party']]
        party = listeningSessions[ownerId]
        print('track added to ', flask.session['party'])
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
        ownerId = parties[flask.session['party']]
        party = listeningSessions[ownerId]
        print('track removed from ', flask.session['party'])
    except KeyError:
        return "no session currently found"
    else:
        currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
        track = SPOTIFY_CLIENT.get_track(flask.request.args['track'])
        party.playlist.remove_tracks((track, [int(flask.request.args['trackIndex'])]))

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
        ownerId = parties[flask.session['party']]
        party = listeningSessions[ownerId]
    except KeyError:
        return "no session currently found"
    else:
        currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
        try:
            currentUser.currently_playing()['item']
        except KeyError:
            flask.flash("Playback device not found.. Please open your Spotify app and begin playing",
                        category='error')
            return flask.redirect(flask.url_for('.queue'))

        track = flask.request.args['track']
        party.owner.get_player().play(party.playlist.uri, offset=track)
        return flask.redirect(flask.url_for('.queue'))


@APP.route('/next')
def nextTrack():
    print("ntext")
    try:
        ownerId = parties[flask.session['party']]
        party = listeningSessions[ownerId]
    except KeyError:
        return "no session currently found"
    else:
        currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
        try:
            currentUser.currently_playing()['item']
        except KeyError:
            flask.flash("Playback device not found.. Please open your Spotify app and begin playing",
                        category='error')
            return flask.redirect(flask.url_for('.queue'))
        party.owner.get_player().next()
        return flask.redirect(flask.url_for('.queue'))


@APP.route('/prev')
def previousTrack():
    try:
        ownerId = parties[flask.session['party']]
        party = listeningSessions[ownerId]
    except KeyError:
        return "no session currently found"
    else:
        currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
        try:
            currentUser.currently_playing()['item']
        except KeyError:
            flask.flash("Playback device not found.. Please open your Spotify app and begin playing",
                        category='error')
            return flask.redirect(flask.url_for('.queue'))
        party.owner.get_player().previous()
        return flask.redirect(flask.url_for('.queue'))


def checkEnd(party: ListeningSession):
    return
    #  todo call this method everytime endpoint /queue, /playTrack, /remove


if __name__ == '__main__':
    APP.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), debug=False)
