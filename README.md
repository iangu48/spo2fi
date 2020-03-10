# Spo2fi - queue with friends

### Environment variables to set before running:
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SESSION_SECRET_KEY` (random string of characters for Flask.session)
- `REDIRECT_URI` (redirect callback for spotify web api)

### backlog:
- [ ] and player controls (prev, next, pause, resume)
- [ ] fill playlist when end is reached (this will be hard to do)
- [ ] allow users to browse / add songs from their other playlists
- [x] flash message errors
- [ ] find better solution than keeping everything in memory (possibly implement a mongodb integration)
- [ ] find elegant solution to deleting old sessions
