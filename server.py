"""QuickPlay application server. Run python3 server.py and open port 4174."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from http.cookies import SimpleCookie
from email.parser import BytesParser
from email.policy import default
import hashlib, hmac, json, sqlite3, secrets, uuid, mimetypes, os, re

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('QUICKPLAY_DATA', str(ROOT / 'data'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
UPLOADS = DATA / 'uploads'
UPLOADS.mkdir(exist_ok=True)
DB = DATA / 'quickplay.sqlite'
BUILTINS = {'orbit', 'neon', 'prism'}
MAX_BODY = 6 * 1024 * 1024
PROMOTION_PLANS = [
    {'id': 'spark', 'name': 'Spark', 'amount': 900, 'days': 3, 'description': 'A little spotlight for your next big idea.'},
    {'id': 'momentum', 'name': 'Momentum', 'amount': 1900, 'days': 7, 'description': 'Give more players a chance to discover you.'},
    {'id': 'spotlight', 'name': 'Spotlight', 'amount': 3900, 'days': 14, 'description': 'Keep your demo in the discovery loop.'},
]


def database():
    conn = sqlite3.connect(DB, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


with database() as conn:
    conn.executescript('''
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS uploads(id TEXT PRIMARY KEY,title TEXT NOT NULL,studio TEXT NOT NULL,genre TEXT NOT NULL,description TEXT NOT NULL,filename TEXT NOT NULL,kind TEXT NOT NULL,visitor TEXT NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS likes(game_id TEXT NOT NULL,visitor TEXT NOT NULL,PRIMARY KEY(game_id,visitor));
    CREATE TABLE IF NOT EXISTS comments(id TEXT PRIMARY KEY,game_id TEXT NOT NULL,visitor TEXT NOT NULL,name TEXT NOT NULL,body TEXT NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE INDEX IF NOT EXISTS idx_comments_game_created ON comments(game_id,created);
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,name TEXT NOT NULL,role TEXT NOT NULL,salt TEXT NOT NULL,password_hash TEXT NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS auth_attempts(address TEXT NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS campaigns(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,game_id TEXT NOT NULL,plan TEXT NOT NULL,amount INTEGER NOT NULL,mode TEXT NOT NULL,status TEXT NOT NULL,starts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,expires TEXT NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    ''')
    # Additive migration keeps existing uploads and comments intact.
    for table, columns in {'uploads': {'owner_id': 'TEXT'}, 'comments': {
        'user_id': 'TEXT', 'rating': 'INTEGER', 'category': "TEXT DEFAULT 'General'",
        'read_at': 'TEXT', 'reply': 'TEXT', 'replied_at': 'TEXT'
    }}.items():
        existing = {r['name'] for r in conn.execute('PRAGMA table_info(%s)' % table)}
        for name, kind in columns.items():
            if name not in existing:
                conn.execute('ALTER TABLE %s ADD COLUMN %s %s' % (table, name, kind))
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_user_review ON comments(game_id,user_id) WHERE user_id IS NOT NULL')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_upload_owner ON uploads(owner_id)')


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print('%s %s' % (self.command, self.path.split('?')[0]))

    def visitor(self):
        self.cookies = SimpleCookie()
        try:
            self.cookies.load(self.headers.get('Cookie', ''))
        except Exception:
            pass
        value = self.cookies['qp_visitor'].value if 'qp_visitor' in self.cookies else ''
        if not re.fullmatch(r'[0-9a-f]{48}', value):
            value = secrets.token_hex(24)
        self.identity = value

    def current_user(self, conn):
        token = self.cookies['qp_session'].value if 'qp_session' in self.cookies else ''
        if not re.fullmatch(r'[0-9a-f]{64}', token):
            return None
        return conn.execute('''SELECT u.id,u.email,u.name,u.role FROM users u JOIN sessions s ON u.id=s.user_id
            WHERE s.token_hash=? AND s.expires > datetime('now')''', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()

    def session(self, conn, user_id):
        token = secrets.token_hex(32)
        conn.execute("DELETE FROM sessions WHERE expires <= datetime('now')")
        conn.execute("INSERT INTO sessions VALUES(?,?,datetime('now','+30 days'))", (hashlib.sha256(token.encode()).hexdigest(), user_id))
        self.session_cookie = 'qp_session=%s; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000' % token

    def send(self, status, content, content_type='application/json; charset=utf-8', sandbox=False):
        if isinstance(content, (dict, list)):
            content = json.dumps(content).encode()
        elif isinstance(content, str):
            content = content.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        if hasattr(self, 'identity'):
            self.send_header('Set-Cookie', 'qp_visitor=%s; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000' % self.identity)
        if hasattr(self, 'session_cookie'):
            self.send_header('Set-Cookie', self.session_cookie)
        if sandbox:
            self.send_header('Content-Security-Policy', "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval' blob:; style-src 'unsafe-inline'; img-src data: blob:; media-src data: blob:; connect-src 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(content)

    def fail(self, code, message):
        self.send(code, {'error': message})

    def game_exists(self, conn, game_id):
        return game_id in BUILTINS or conn.execute('SELECT id FROM uploads WHERE id=?', (game_id,)).fetchone() is not None

    def engagement(self, conn, game_id):
        return {'likes': conn.execute('SELECT COUNT(*) FROM likes WHERE game_id=?', (game_id,)).fetchone()[0],
                'liked': conn.execute('SELECT 1 FROM likes WHERE game_id=? AND visitor=?', (game_id, self.identity)).fetchone() is not None,
                'comments': conn.execute('SELECT COUNT(*) FROM comments WHERE game_id=?', (game_id,)).fetchone()[0]}

    def do_GET(self):
        self.visitor()
        route = self.path.split('?')[0]
        try:
            with database() as conn:
                if route == '/api/auth/me':
                    user = self.current_user(conn)
                    return self.send(200, {'user': dict(user) if user else None})
                if route == '/api/games':
                    uploads = [dict(r) for r in conn.execute('SELECT id,title,studio,genre,description,filename,kind,created,owner_id FROM uploads ORDER BY created DESC,rowid DESC')]
                    for item in uploads:
                        item['url'] = '/uploads/' + item.pop('filename')
                        campaign = conn.execute("SELECT mode,expires FROM campaigns WHERE game_id=? AND status='active' AND expires > datetime('now') ORDER BY expires DESC LIMIT 1", (item['id'],)).fetchone()
                        item['promoted'] = bool(campaign)
                        item['promotion_mode'] = campaign['mode'] if campaign else None
                    uploads.sort(key=lambda item: not item['promoted'])
                    ids = list(BUILTINS) + [r['id'] for r in uploads]
                    return self.send(200, {'uploads': uploads, 'engagement': {i: self.engagement(conn, i) for i in ids}})
                if route == '/api/marketing':
                    user = self.current_user(conn)
                    if not user:
                        return self.fail(401, 'Sign in as a developer to promote your game.')
                    if user['role'] != 'developer':
                        return self.fail(403, 'Promotion is available to developer accounts.')
                    owned = [dict(r) for r in conn.execute('SELECT id,title,genre FROM uploads WHERE owner_id=? ORDER BY created DESC', (user['id'],))]
                    campaigns = [dict(r) for r in conn.execute('''SELECT c.id,c.game_id,c.plan,c.amount,c.mode,c.starts,c.expires,c.created,u.title,
                        CASE WHEN c.expires <= datetime('now') THEN 'ended' ELSE c.status END AS status
                        FROM campaigns c JOIN uploads u ON c.game_id=u.id WHERE c.owner_id=? ORDER BY c.created DESC,c.rowid DESC''', (user['id'],))]
                    return self.send(200, {'plans': PROMOTION_PLANS, 'games': owned, 'campaigns': campaigns, 'mode': 'demo', 'currency': 'USD'})
                if route == '/api/feedback':
                    user = self.current_user(conn)
                    if not user:
                        return self.fail(401, 'Sign in to see your feedback.')
                    if user['role'] != 'developer':
                        return self.fail(403, 'Feedback is available to developer accounts.')
                    games = [dict(r) for r in conn.execute('SELECT id,title,genre,created FROM uploads WHERE owner_id=? ORDER BY created DESC', (user['id'],))]
                    reviews = [dict(r) for r in conn.execute('''SELECT c.id,c.game_id,c.name,c.body,c.rating,c.category,c.created,c.read_at,c.reply,c.replied_at,u.title AS game_title,u.studio
                        FROM comments c JOIN uploads u ON c.game_id=u.id WHERE u.owner_id=? ORDER BY c.created DESC,c.rowid DESC''', (user['id'],))]
                    return self.send(200, {'games': games, 'reviews': reviews})
                if route.startswith('/api/comments/'):
                    game_id = route.removeprefix('/api/comments/')
                    if not self.game_exists(conn, game_id):
                        return self.fail(404, 'Game not found.')
                    rows = [dict(r) for r in conn.execute('''SELECT c.id,c.name,c.body,c.created,c.rating,c.category,c.reply,c.replied_at,u.studio
                        FROM comments c LEFT JOIN uploads u ON c.game_id=u.id WHERE game_id=? ORDER BY c.created DESC,c.rowid DESC LIMIT 100''', (game_id,))]
                    return self.send(200, {'comments': rows})
            if route.startswith('/uploads/'):
                name = route.removeprefix('/uploads/')
                if '/' in name or '\\' in name or not name or Path(name).name != name:
                    return self.fail(404, 'File not found.')
                file = UPLOADS / name
                if not file.is_file():
                    return self.fail(404, 'File not found.')
                return self.send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or 'application/octet-stream', sandbox=file.suffix == '.html')
            paths = {p: 'index.html' for p in ('/', '/index.html', '/login', '/signup', '/feedback', '/studio', '/saved')}
            if route == '/marketing':
                with database() as conn:
                    user = self.current_user(conn)
                if not user or user['role'] != 'developer':
                    self.send_response(302)
                    self.send_header('Location', '/login?next=marketing' if not user else '/')
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    return
                paths['/marketing'] = 'index.html'
            paths.update({('/' + f): f for f in ('app.js', 'social.js', 'workspace.js', 'style.css', 'workspace.css')})
            if route not in paths:
                return self.fail(404, 'Page not found.')
            file = ROOT / 'dist' / paths[route]
            self.send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        except Exception:
            self.fail(500, 'Could not load data. Please try again.')

    def do_POST(self):
        self.visitor()
        origin = self.headers.get('Origin')
        if origin and origin not in ('http://' + self.headers.get('Host', ''), 'https://' + self.headers.get('Host', '')):
            return self.fail(403, 'Request origin is not allowed.')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return self.fail(403, 'Cross-site requests are not allowed.')
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                return self.fail(413, 'Choose an HTML demo smaller than 5 MB.')
            raw = self.rfile.read(length)
            route = self.path.split('?')[0]
            if route == '/api/uploads':
                return self.upload(raw)
            if length > 8192 or not self.headers.get('Content-Type', '').startswith('application/json'):
                return self.fail(400, 'Invalid request.')
            item = json.loads(raw)
            if not isinstance(item, dict):
                return self.fail(400, 'Invalid request.')
            with database() as conn:
                if route.startswith('/api/auth/'):
                    return self.auth(conn, route, item)
                user = self.current_user(conn)
                if route == '/api/marketing/purchase':
                    if not user:
                        return self.fail(401, 'Sign in as a developer to promote your game.')
                    if user['role'] != 'developer':
                        return self.fail(403, 'A developer account is required.')
                    game_id, plan_id = item.get('gameId'), item.get('planId')
                    if not isinstance(game_id, str) or not isinstance(plan_id, str):
                        return self.fail(400, 'Choose a game and a promotion plan.')
                    plan = next((p for p in PROMOTION_PLANS if p['id'] == plan_id), None)
                    if not plan:
                        return self.fail(400, 'Choose a valid promotion plan.')
                    if not conn.execute('SELECT id FROM uploads WHERE id=? AND owner_id=?', (game_id, user['id'])).fetchone():
                        return self.fail(404, 'Your game could not be found.')
                    if item.get('confirmDemo') is not True:
                        return self.fail(400, 'Confirm the demo checkout. No money will be charged.')
                    conn.execute('BEGIN IMMEDIATE')
                    if conn.execute("SELECT id FROM campaigns WHERE game_id=? AND status='active' AND expires > datetime('now')", (game_id,)).fetchone():
                        return self.fail(409, 'This game already has an active promotion. Choose another game or wait for it to end.')
                    campaign_id = str(uuid.uuid4())
                    conn.execute("INSERT INTO campaigns(id,owner_id,game_id,plan,amount,mode,status,expires) VALUES(?,?,?,?,?,'demo','active',datetime('now',?))", (campaign_id, user['id'], game_id, plan['id'], plan['amount'], '+%s days' % plan['days']))
                    conn.commit()
                    return self.send(201, {'id': campaign_id, 'mode': 'demo', 'message': 'Demo promotion activated. No money was charged.'})
                if route == '/api/feedback/update':
                    if not user:
                        return self.fail(401, 'Sign in to manage feedback.')
                    if user['role'] != 'developer':
                        return self.fail(403, 'A developer account is required.')
                    review_id = item.get('reviewId')
                    if not isinstance(review_id, str):
                        return self.fail(400, 'Choose a review.')
                    review = conn.execute('''SELECT c.id FROM comments c JOIN uploads u ON c.game_id=u.id
                        WHERE c.id=? AND u.owner_id=?''', (review_id, user['id'])).fetchone()
                    if not review:
                        return self.fail(404, 'Review not found.')
                    if 'reply' in item:
                        reply = item['reply']
                        if not isinstance(reply, str) or not 1 <= len(reply.strip()) <= 1000:
                            return self.fail(400, 'Write a reply of up to 1,000 characters.')
                        conn.execute("UPDATE comments SET reply=?,replied_at=CURRENT_TIMESTAMP,read_at=CURRENT_TIMESTAMP WHERE id=?", (reply.strip(), review_id))
                    elif type(item.get('read')) is bool:
                        conn.execute('UPDATE comments SET read_at=%s WHERE id=?' % ('CURRENT_TIMESTAMP' if item['read'] else 'NULL'), (review_id,))
                    else:
                        return self.fail(400, 'Choose a read state or write a reply.')
                    conn.commit()
                    return self.send(200, {'ok': True})
                game_id = item.get('gameId')
                if not isinstance(game_id, str):
                    return self.fail(400, 'Choose a game.')
                if not self.game_exists(conn, game_id):
                    return self.fail(404, 'Game not found.')
                if route == '/api/likes':
                    if type(item.get('liked')) is not bool:
                        return self.fail(400, 'Choose a like state.')
                    if item['liked']:
                        conn.execute('INSERT OR IGNORE INTO likes(game_id,visitor) VALUES(?,?)', (game_id, self.identity))
                    else:
                        conn.execute('DELETE FROM likes WHERE game_id=? AND visitor=?', (game_id, self.identity))
                    conn.commit()
                    return self.send(200, self.engagement(conn, game_id))
                if route == '/api/comments':
                    if not user:
                        return self.fail(401, 'Sign in to leave a review.')
                    body, rating, category = item.get('body'), item.get('rating'), item.get('category', 'General')
                    if not isinstance(body, str) or not 1 <= len(body.strip()) <= 500 or type(rating) is not int or not 1 <= rating <= 5 or category not in ('General', 'Gameplay', 'Visuals', 'Bug report', 'Suggestion'):
                        return self.fail(400, 'Choose 1–5 stars and write a review of up to 500 characters.')
                    owner = conn.execute('SELECT owner_id FROM uploads WHERE id=?', (game_id,)).fetchone()
                    if owner and owner['owner_id'] == user['id']:
                        return self.fail(403, 'You cannot review your own game.')
                    if conn.execute('SELECT id FROM comments WHERE game_id=? AND user_id=?', (game_id, user['id'])).fetchone():
                        return self.fail(409, 'You have already reviewed this game. Thank you for your feedback!')
                    count = conn.execute("SELECT COUNT(*) FROM comments WHERE user_id=? AND created > datetime('now','-1 minute')", (user['id'],)).fetchone()[0]
                    if count >= 10:
                        return self.fail(429, 'Please wait a minute before posting again.')
                    conn.execute('INSERT INTO comments(id,game_id,visitor,name,body,user_id,rating,category) VALUES(?,?,?,?,?,?,?,?)', (str(uuid.uuid4()), game_id, self.identity, user['name'], body.strip(), user['id'], rating, category))
                    conn.commit()
                    return self.send(201, self.engagement(conn, game_id))
            self.fail(404, 'Action not found.')
        except (ValueError, UnicodeError):
            self.fail(400, 'Invalid request.')
        except Exception:
            self.fail(500, 'Could not save. Your input has been preserved; please try again.')

    def auth(self, conn, route, item):
        if route == '/api/auth/logout':
            token = self.cookies['qp_session'].value if 'qp_session' in self.cookies else ''
            conn.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))
            conn.commit()
            self.session_cookie = 'qp_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'
            return self.send(200, {'user': None})
        if route not in ('/api/auth/login', '/api/auth/signup'):
            return self.fail(404, 'Action not found.')
        address = self.client_address[0]
        conn.execute("DELETE FROM auth_attempts WHERE created <= datetime('now','-15 minutes')")
        if conn.execute('SELECT COUNT(*) FROM auth_attempts WHERE address=?', (address,)).fetchone()[0] >= 30:
            return self.fail(429, 'Too many attempts. Please try again in 15 minutes.')
        conn.execute('INSERT INTO auth_attempts(address) VALUES(?)', (address,))
        conn.commit()
        email, password = item.get('email'), item.get('password')
        if not isinstance(email, str) or not isinstance(password, str) or len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email.strip()) or len(password) > 128:
            return self.fail(400, 'Enter a valid email and a password of up to 128 characters.')
        email = email.strip().lower()
        if route.endswith('/signup'):
            name, role = item.get('name'), item.get('role')
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40 or role not in ('player', 'developer') or len(password) < 8:
                return self.fail(400, 'Enter a name, choose your account type, and use at least 8 characters for your password.')
            if conn.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone():
                return self.fail(409, 'An account already uses this email. Sign in instead.')
            user_id, salt = str(uuid.uuid4()), secrets.token_hex(16)
            conn.execute('INSERT INTO users(id,email,name,role,salt,password_hash) VALUES(?,?,?,?,?,?)', (user_id, email, name.strip(), role, salt, password_hash(password, salt)))
        else:
            row = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            # Perform the same password derivation even for unknown emails.
            derived = password_hash(password, row['salt'] if row else '0' * 32)
            if not row or not hmac.compare_digest(derived, row['password_hash']):
                return self.fail(401, 'Email or password is incorrect.')
            user_id = row['id']
        self.session(conn, user_id)
        account = conn.execute('SELECT role FROM users WHERE id=?', (user_id,)).fetchone()
        if account['role'] == 'developer':
            conn.execute('UPDATE uploads SET owner_id=? WHERE owner_id IS NULL AND visitor=?', (user_id, self.identity))
        conn.commit()
        user = dict(conn.execute('SELECT id,email,name,role FROM users WHERE id=?', (user_id,)).fetchone())
        self.send(201 if route.endswith('/signup') else 200, {'user': user})

    def upload(self, raw):
        with database() as conn:
            user = self.current_user(conn)
        if not user:
            return self.fail(401, 'Sign in as a developer to upload your game.')
        if user['role'] != 'developer':
            return self.fail(403, 'A developer account is required to upload games.')
        content_type = self.headers.get('Content-Type', '')
        if not content_type.startswith('multipart/form-data;'):
            return self.fail(400, 'Select a demo file.')
        message = BytesParser(policy=default).parsebytes(('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + raw)
        if not message.is_multipart():
            return self.fail(400, 'Invalid upload.')
        fields, file_data, extension = {}, None, ''
        for part in message.iter_parts():
            name = part.get_param('name', header='content-disposition')
            payload = part.get_payload(decode=True) or b''
            if name == 'file':
                extension = Path(part.get_filename() or '').suffix.lower()
                file_data = payload
            elif name in ('title', 'studio', 'description', 'genre'):
                if len(payload) > 2048:
                    return self.fail(400, 'Upload description is too long.')
                fields[name] = payload.decode('utf-8').strip()
        if not file_data or extension != '.html':
            return self.fail(400, 'Choose a self-contained .html game with embedded JavaScript.')
        if len(file_data) > 5 * 1024 * 1024:
            return self.fail(413, 'HTML demos must be under 5 MB.')
        text = file_data.decode('utf-8')
        if '<html' not in text.lower() and '<!doctype html' not in text.lower():
            return self.fail(400, 'The HTML file must be a complete, self-contained page.')
        if not 1 <= len(fields.get('title', '')) <= 80 or not 1 <= len(fields.get('studio', '')) <= 80 or not 1 <= len(fields.get('description', '')) <= 300 or fields.get('genre') not in ('Arcade', 'Puzzle', 'Adventure', 'Strategy'):
            return self.fail(400, 'Complete the title, studio, description, and genre.')
        game_id = str(uuid.uuid4())
        filename = game_id + '.html'
        file = UPLOADS / filename
        with database() as conn:
            count = conn.execute("SELECT COUNT(*) FROM uploads WHERE owner_id=? AND created > datetime('now','-1 hour')", (user['id'],)).fetchone()[0]
            if count >= 10:
                return self.fail(429, 'Upload limit reached. Please try again in an hour.')
            file.write_bytes(file_data)
            try:
                conn.execute('INSERT INTO uploads(id,title,studio,genre,description,filename,kind,visitor,owner_id) VALUES(?,?,?,?,?,?,?,?,?)', (game_id, fields['title'], fields['studio'], fields['genre'], fields['description'], filename, 'html', self.identity, user['id']))
                conn.commit()
            except Exception:
                file.unlink(missing_ok=True)
                raise
        self.send(201, {'id': game_id, 'message': 'Your demo is live in the feed.'})


if __name__ == '__main__':
    port = int(os.environ.get('QUICKPLAY_PORT', '4174'))
    print('QuickPlay: http://127.0.0.1:%s' % port, flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
