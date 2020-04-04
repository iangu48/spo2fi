import os
import random
import string
import flask
import spotify.sync as spotify
import auth
from auth import SPOTIFY_CLIENT, SPOTIFY_USERS, listeningSessions, OAUTH2, partyIdMap
from models import ListeningSession

APP = flask.Flask(__name__)
APP.register_blueprint(auth.bp)
APP.secret_key = os.environ['SESSION_SECRET_KEY']
APP.config.from_mapping({'spotify_client': SPOTIFY_CLIENT})


@APP.errorhandler(500)
def error500(e):
    flask.flash(str(e), category="error")
    return flask.redirect(flask.url_for('.index'))


@APP.route('/')
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
        flask.flash("You are already owner of a session", category="error")
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
        currentUser.edit_playlist(playlist, description="Queue songs with friends! Warning: do not delete or your "
                                                        "party will not work as intended")
        # currentUser.client.http.upload_playlist_cover_image(playlist.id, ) todo upload Spo2fi logo

    try:
        if currentUser.currently_playing()['is_playing']:
            playlist.replace_tracks(currentUser.currently_playing()['item'])
    except KeyError:  # new users don't have any top tracks
        usersTopTracks = currentUser.top_tracks(limit=1, time_range='medium_term')
        playlist.replace_tracks(usersTopTracks[0])

    joinId = ''.join(random.choice(string.ascii_uppercase + string.digits) for i in range(4))
    while joinId in partyIdMap:
        joinId = ''.join(random.choice(string.ascii_uppercase + string.digits) for i in range(4))
    listeningSessions[currentUser.id] = ListeningSession(currentUser, [], playlist, joinId)
    partyIdMap[joinId] = currentUser.id

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
        ownerId = partyIdMap[joinId]
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
        ownerId = partyIdMap[flask.session['party']]
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
        ownerId = partyIdMap[flask.session['party']]
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
        ownerId = partyIdMap[flask.session['party']]
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
    ownerId = partyIdMap[flask.session['party']]
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
                                 playlists=playlists,
                                 members=party.members)


@APP.route('/playTrack')
def playTrack():
    try:
        ownerId = partyIdMap[flask.session['party']]
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
    try:
        ownerId = partyIdMap[flask.session['party']]
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
        ownerId = partyIdMap[flask.session['party']]
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


# def checkEnd(party: ListeningSession):
#     return
#     #  todo call this method everytime endpoint /queue, /playTrack, /remove


@APP.route('/<user>/playlists/<page>')
def browsePlaylists(user, page):
    currentUser = SPOTIFY_USERS[flask.session['spotify_user_id']]
    if currentUser.id == user:
        playlists = currentUser.get_playlists(offset=page*20)

        return flask.render_template('browse/browse.html',
                                     results=playlists)
    else:
        try:
            ownerId = partyIdMap[flask.session['party']]
            party = listeningSessions[ownerId]
            playlistOwner = party.members[user]
        except KeyError:
            flask.flash('User not found', category='error')
            return 'todo'
        finally:
            playlists = playlistOwner.get_playlists(offset=page*20)
            return flask.render_template('browse/browse.html',
                                         results=playlists)


if __name__ == '__main__':
    APP.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), debug=False)
