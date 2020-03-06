from typing import List

import spotify.sync as spotify


class ListeningSession:
    def __init__(self, owner: spotify.User, members: List[spotify.User], playlist: spotify.Playlist):
        self.playlist = playlist
        self.owner = owner
        self.members = members
