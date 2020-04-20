import os
import random
import string
from typing import List

from flask import flash, redirect, url_for, Flask, render_template, session, request, jsonify
import spotify.sync as spotify
import main.auth as auth
from main.auth import SPOTIFY_CLIENT, SPOTIFY_USERS, listeningSessions, OAUTH2, partyIdMap
from main.models import ListeningSession

APP = Flask(__name__)
APP.register_blueprint(auth.bp)
APP.secret_key = os.environ['SESSION_SECRET_KEY']
APP.config.from_mapping({'spotify_client': SPOTIFY_CLIENT})


@APP.errorhandler(500)
def error500(e):
    flash(str(e), category="error")
    return redirect(url_for('.index'))


@APP.route('/')
def index():
    try:
        currentUser = SPOTIFY_USERS[session['spotify_user_id']]
        currentSession = listeningSessions.get(currentUser.id)
        
        if currentUser.id in listeningSessions:
            ownerId = partyIdMap[session['party']]
            party = listeningSessions[ownerId]
            playlist = party.playlist
            playlists = currentUser.get_all_playlists()
            return render_template("queue.html",
                                         user=currentUser,
                                         owner=party.owner,
                                         tracks=playlist.get_tracks(),
                                         joinId=party.joinId,
                                         isOwner=currentUser == party.owner,
                                         playlists=playlists,
                                         members=party.members)
        else:
            try:
                ownerId = partyIdMap[session['party']]
                party = listeningSessions[ownerId]
                playlist = party.playlist
                playlists = currentUser.get_all_playlists()
                return render_template("queue.html",
                                       user=currentUser,
                                       owner=party.owner,
                                       tracks=playlist.get_tracks(),
                                       joinId=party.joinId,
                                       isOwner=currentUser == party.owner,
                                       playlists=playlists,
                                       members=party.members)
            except KeyError as e:
                print(e)

        print('current users: ', SPOTIFY_USERS)
        print('parties: ', listeningSessions.keys())
        return render_template("index.html",
                                     user=currentUser,
                                     openSession=currentSession,
                                     owner=currentUser,
                                     isOwner=False)
    except KeyError:
        return redirect(OAUTH2.url)


@APP.route('/newSession')
def start():
    currentUser: spotify.User = SPOTIFY_USERS[session['spotify_user_id']]
    if currentUser.id in listeningSessions:
        # todo check if idiot user deletes playlist
        flash("You are already owner of a session", category="error")
        return redirect(url_for('.index'))
    try:
        currentUser.currently_playing()['item']
    except KeyError:
        flash("Playback device not found.. Please open your Spotify app and begin playing (any random song)",
                    category='error')
        return redirect(url_for('.index'))
    playlists: List[spotify.Playlist] = currentUser.get_playlists()  # todo empty playlists are not included
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

    session['party'] = listeningSessions[currentUser.id].joinId
    print('user ', currentUser.display_name, ' joined ' , session['party'])

    try:
        currentUser.get_player().play(playlist)
        currentUser.get_player().shuffle(False)
    except spotify.errors.NotFound:
        flash("Playback device not found.. Please open your Spotify app and begin playing (any random song)",
                    category='error')
        return redirect(url_for('.index'))
    return redirect(url_for('.index'))


@APP.route('/join')
def join():
    currentUser = SPOTIFY_USERS[session['spotify_user_id']]
    try:
        joinId = str.upper(request.args['joinId'])
        ownerId = partyIdMap[joinId]
        party = listeningSessions[ownerId]
    except KeyError:
        flash('Code not found', category='error')
        return redirect('/')
    else:
        if currentUser not in party.members:
            party.members.append(currentUser)
        session['party'] = party.joinId
        return redirect(url_for('.index'))


@APP.route('/search')
def search():
    try:
        query = request.args["query"]
    except KeyError:
        return "no query entered"
    else:
        if not query:
            flash('Empty search query', category='error')
            return redirect(url_for('.index'))
        currentUser = SPOTIFY_USERS[session['spotify_user_id']]
        results = SPOTIFY_CLIENT.search(query, limit=10)
        ownerId = partyIdMap[session['party']]
        party = listeningSessions[ownerId]
        return render_template("search.html",
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
        ownerId = partyIdMap[session['party']]
        party = listeningSessions[ownerId]
        print('track added to ', session['party'])
    except KeyError:
        return "no session currently found"
    else:
        currentUser = SPOTIFY_USERS[session['spotify_user_id']]
        track = SPOTIFY_CLIENT.get_track(request.args['trackId'])

        # party.owner.add_tracks(party.playlist, track)  # only owner can add tracks to playlist
        party.playlist.extend([track])

        return redirect(url_for('.index'))


@APP.route('/remove')
def removeTrack():
    try:
        ownerId = partyIdMap[session['party']]
        party = listeningSessions[ownerId]
        print('track removed from ', session['party'])
    except KeyError:
        return "no session currently found"
    else:
        currentUser = SPOTIFY_USERS[session['spotify_user_id']]
        track = SPOTIFY_CLIENT.get_track(request.args['track'])
        party.playlist.remove_tracks((track, [int(request.args['trackIndex'])]))

        return redirect(url_for('.index'))


@APP.route('/playTrack')
def playTrack():
    try:
        ownerId = partyIdMap[session['party']]
        party = listeningSessions[ownerId]
    except KeyError:
        return "no session currently found"
    else:
        currentUser = SPOTIFY_USERS[session['spotify_user_id']]
        try:
            currentUser.currently_playing()['item']
        except KeyError:
            flash("Playback device not found.. Please open your Spotify app and begin playing",
                        category='error')
            return redirect(url_for('.index'))

        track = request.args['track']
        party.owner.get_player().play(party.playlist.uri, offset=track)
        return redirect(url_for('.index'))


@APP.route('/resume')
def resumeTrack():
    try:
        ownerId = partyIdMap[session['party']]
        party = listeningSessions[ownerId]
    except KeyError:
        return jsonify({'error': 'no session'})
    else:
        currentUser = SPOTIFY_USERS[session['spotify_user_id']]
        try:
            currentUser.currently_playing()['item']
        except KeyError:
            return jsonify({'error': 'Playback device not found.. Please open your Spotify app and begin playing'})
        finally:
            try:
                party.owner.get_player().resume()
            except Exception as e:
                return jsonify({'error': str(e)}), 403
        return jsonify({'success': 's'})


@APP.route('/pause')
def pauseTrack():
    try:
        ownerId = partyIdMap[session['party']]
        party = listeningSessions[ownerId]
    except KeyError:
        return jsonify({'error': 'no session'})
    else:
        currentUser = SPOTIFY_USERS[session['spotify_user_id']]
        try:
            currentUser.currently_playing()['item']
        except KeyError:
            return jsonify({'error': 'Playback device not found.. Please open your Spotify app and begin playing'})
        finally:
            try:
                party.owner.get_player().pause()
            except Exception as e:
                return jsonify({'error': str(e)}), 403
        return jsonify({'success': 's'})


@APP.route('/prev')
def previousTrack():
    try:
        ownerId = partyIdMap[session['party']]
        party = listeningSessions[ownerId]
    except KeyError:
        return jsonify({'error': 'no session'})
    else:
        currentUser = SPOTIFY_USERS[session['spotify_user_id']]
        try:
            currentUser.currently_playing()['item']
        except KeyError:
            return jsonify({'error': 'Playback device not found.. Please open your Spotify app and begin playing'})
        finally:
            try:
                party.owner.get_player().previous()
            except Exception as e:
                return jsonify({'error': str(e)}), 403
        return jsonify({'success': 's'})


@APP.route('/restart')
def restartTrack():
    try:
        ownerId = partyIdMap[session['party']]
        party = listeningSessions[ownerId]
    except KeyError:
        return jsonify({'error': 'no session'})
    else:
        currentUser = SPOTIFY_USERS[session['spotify_user_id']]
        try:
            currentUser.currently_playing()['item']
        except KeyError:
            return jsonify({'error': 'Playback device not found.. Please open your Spotify app and begin playing'})
        finally:
            try:
                party.owner.get_player().seek(0)
            except Exception as e:
                return jsonify({'error': str(e)}), 403
        return jsonify({'success': 's'})


@APP.route('/next')
def nextTrack():
    try:
        ownerId = partyIdMap[session['party']]
        party = listeningSessions[ownerId]
    except KeyError:
        return jsonify({'error': 'no session'})
    else:
        currentUser = SPOTIFY_USERS[session['spotify_user_id']]
        try:
            currentUser.currently_playing()['item']
        except KeyError:
            return jsonify({'error': 'Playback device not found.. Please open your Spotify app and begin playing'})
        else:
            try:
                party.owner.get_player().next()
            except Exception as e:
                return jsonify({'error': str(e)}), 403
        return jsonify({'success': 's'})


# def checkEnd(party: ListeningSession):
#     return
#     #  todo call this method everytime endpoint /queue, /playTrack, /remove


@APP.route('/<user>/playlists/<page>')
def browsePlaylists(user, page):
    currentUser = SPOTIFY_USERS[session['spotify_user_id']]
    ownerId = partyIdMap[session['party']]
    party = listeningSessions[ownerId]

    if currentUser.id == user:
        playlists = currentUser.get_playlists(offset=page*20)

        return render_template('browse/browse.html',
                                     results=playlists,
                                     user=currentUser,
                                     owner=party.owner,
                                     offset=page*20,
                                     endpoint='/%s/playlists/' % user,
                                     page=page)
    else:
        playlistOwner = party.members[user]
        playlists = playlistOwner.get_playlists(offset=page*20)
        return render_template('browse/browse.html',
                                     results=playlists,
                                     user=playlistOwner,
                                     owner=party.owner,
                                     offset=page*20,
                                     endpoint='/%s/playlists/' % user,
                                     page=page)


@APP.route('/<user>/<offset>/<playlist_id>/<page>')
def browsePlaylistTracks(user, offset, playlist_id, page):
    currentUser = SPOTIFY_USERS[session['spotify_user_id']]
    ownerId = partyIdMap[session['party']]
    party = listeningSessions[ownerId]

    if currentUser.id == user:
        playlists = currentUser.get_playlists(offset=offset)
        print(repr(playlists))
        playlist = None
        for p in playlists:
            if p.id == playlist_id:
                playlist = p
                break
        tracks = playlist.get_tracks(offset=page*100, limit=100)

        return render_template('browse/tracks.html',
                                     playlist=playlist,
                                     owner=party.owner,
                                     tracks=tracks,
                                     endpoint='/%s/%s/%s/' % (user, offset, playlist_id),
                                     page=page)
    else:
        playlistOwner = party.members[user]
        playlists = playlistOwner.get_playlists(offset=offset)
        playlist = None
        for p in playlists:
            if p.id == playlist_id:
                playlist = p
                break
        tracks = playlist.get_tracks(offset=page*100, limit=100)

        return render_template('browse/browse.html',
                                     playlist=playlist,
                                     owner=party.owner,
                                     tracks=tracks,
                                     endpoint='/%s/%s/%s/' % (user, offset, playlist_id),
                                     page=page)


if __name__ == '__main__':
    APP.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), debug=False)
