# QuickPlay

Playable discovery for indie games: try a demo in your browser, leave a review, and help its developer make the next version better.

## Run locally

Requires Python 3.10 or newer. The application has no third-party runtime dependencies.

```sh
python3 server.py
```

Open http://127.0.0.1:4174. Use this Python server rather than opening the HTML file directly or serving only `dist`: accounts, uploads, reviews, and promotions require its API.

## Players and developers

- **Sign up / log in** at `/signup` or `/login`. Choose a player or developer account when registering. Passwords use salted scrypt hashes; sessions are stored server-side and identified by an HttpOnly, SameSite cookie. Signing out revokes the session.
- **Players** can play, like, save games, and post one rated review per game. Reviews use the account's display name, a 1–5 star rating, and a category (General, Gameplay, Visuals, Bug report, or Suggestion). Saves remain local to the browser.
- **Developers** can also upload games, view only their own uploads in `/studio`, and read their own games' reviews at `/feedback`. Search, game filters, sorting, unread status, rating summaries, and developer replies are supported. Replies appear in the game's public reviews. Developers cannot review their own games.
- Guests can browse a clearly labeled sample feedback inbox. Sample reviews are illustrative and are never inserted into the database.

All game players now use a responsive **16:9 desktop viewport**. The built-in games and their controls have been adapted for landscape play.

## Upload a game

Create a developer account, open **Developer studio**, and choose a complete, self-contained `.html` file up to 5 MB. Include JavaScript, CSS, and assets inside that file. Demos run with sandboxed scripts and no network or parent-page access. New uploads accept HTML/JavaScript games only; standalone JS files, ZIPs, and gameplay videos are not accepted. Previously uploaded videos are preserved for compatibility.

The included `sample-demo.html` is a responsive, playable game for trying the upload flow. Demo performance metrics reflect this browser session; they are not analytics for all visitors.

## Developer promotions

**Promote your game** at `/marketing` is available only to signed-in developers. Both page access and API actions enforce that role. Campaigns can only promote a game owned by the purchaser.

The promotion plans are **demo prices**, in USD:

| Plan | Sample price | Priority period |
| --- | --- | --- |
| Spark | $9 | 3 days |
| Momentum | $19 | 7 days |
| Spotlight | $39 | 14 days |

Checkout explicitly shows **$0 charged**, requires confirmation of demo mode, and never requests a payment card. It creates a persistent local visibility campaign. Active promoted demos appear ahead of organic games and carry a “Promoted · demo campaign” label. Within each group, newer uploads appear first. A game can have one active campaign at a time; expired campaigns lose priority automatically.

No payment provider is configured. Demo checkout does not collect money. Real payments would require a provider, verified payment callbacks, and activation only after confirmed payment. Visibility does not guarantee plays, likes, or reviews.

## Data and existing uploads

Accounts, sessions, uploads, likes, reviews, replies, and campaigns are stored in `data/quickplay.sqlite`; game files are stored in `data/uploads`. They survive restarts. Back up both together. Do not distribute the data folder with source archives.

The database migration preserves existing uploads and comments. Older comments appear as unrated reviews. Older anonymous uploads are associated with a developer account on sign-up/log-in only when the original visitor cookie matches; otherwise they remain public without a developer owner.

`QUICKPLAY_DATA` sets the data directory. `QUICKPLAY_PORT` sets the port (default 4174). The server binds to localhost and is intended for local use. The Python API must run alongside the frontend; static-only hosting cannot provide these features.

## Validation

```sh
python3 -m unittest discover -s tests -v
node --check dist/app.js
node --check dist/social.js
node --check dist/workspace.js
```

The tests run the real HTTP handlers in memory without a network socket. They cover account validation, password/session behavior, expiration and logout, developer/player access, upload ownership and sandbox headers, verified review identity, duplicate review prevention, feedback privacy, read states and replies, campaign authorization and server-owned prices, duplicate campaigns, expiry, cross-origin rejection, database migration, and persistence.

Browser visual testing could not run in the editing environment because network socket creation and Chromium's required process sockets are restricted. Test the rendered desktop and mobile layouts by running the server locally.
