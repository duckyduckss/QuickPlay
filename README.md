# QuickPlay

A vertical, snapping game-discovery feed with playable demos, likes, comments, and file uploads.

## Run locally

Requires Python 3.10 or newer. No additional packages are needed.

```
python server.py
```

Open http://127.0.0.1:4174. Use this server rather than opening index.html directly or serving only the dist folder: uploads, likes, and comments require its API.

## Upload a game

Choose **Upload**, fill out the title, studio, description, and genre, and select a file. Accepted formats:

- Self-contained HTML game, up to 5 MB. Include scripts, styles, and assets inside the file. HTML runs with sandboxed scripts and no network or parent-page access.
- MP4/WebM gameplay video, up to 30 MB. Videos play inside the feed.

The included sample-demo.html is a playable game you can upload to try the flow.

## Data

Uploads and social interactions are saved in data/quickplay.sqlite and data/uploads on the server, surviving browser reloads and server restarts. Keep these together when backing up. Anonymous visitor cookies identify likes; clearing cookies creates a new visitor. Display names on comments are user-entered, not verified identities. Saves remain a device-local preference. Play metrics are session-only.

QUICKPLAY_DATA changes the data directory; QUICKPLAY_PORT changes the local port. The server binds to localhost. It is a local implementation and is not currently deployed online. Public hosting would require a compatible application server, secure visitor identity, upload moderation, and persistent storage; the existing static Sites manifest cannot host the Python API.

## Validation

Checked JavaScript syntax, upload publication, shared and idempotent like counts, comments, upload isolation headers, invalid input handling, cross-origin rejection, and persistence across server restarts.
