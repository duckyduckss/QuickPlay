"""QuickPlay local application server. Run: python server.py (then open port 4174)."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from http.cookies import SimpleCookie
from email.parser import BytesParser
from email.policy import default
import json, sqlite3, secrets, uuid, mimetypes, os

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('QUICKPLAY_DATA', str(ROOT / 'data'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
UPLOADS = DATA / 'uploads'
UPLOADS.mkdir(exist_ok=True)
DB = DATA / 'quickplay.sqlite'
BUILTINS = {'orbit', 'neon', 'prism'}
MAX_BODY = 32 * 1024 * 1024

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
    ''')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Do not log uploaded content or visitor cookies.
        print('%s %s' % (self.command, self.path.split('?')[0]))

    def visitor(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie', ''))
        except Exception:
            pass
        value = cookies['qp_visitor'].value if 'qp_visitor' in cookies else ''
        if len(value) != 48 or any(c not in '0123456789abcdef' for c in value):
            value = secrets.token_hex(24)
        self.identity = value
        return value

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
                if route == '/api/games':
                    uploads = [dict(r) for r in conn.execute('SELECT id,title,studio,genre,description,filename,kind,created FROM uploads ORDER BY created DESC')]
                    for item in uploads:
                        item['url'] = '/uploads/' + item.pop('filename')
                    ids = list(BUILTINS) + [r['id'] for r in uploads]
                    return self.send(200, {'uploads': uploads, 'engagement': {i: self.engagement(conn, i) for i in ids}})
                if route.startswith('/api/comments/'):
                    game_id = route.removeprefix('/api/comments/')
                    if not self.game_exists(conn, game_id):
                        return self.fail(404, 'Game not found.')
                    rows = [dict(r) for r in conn.execute('SELECT id,name,body,created FROM comments WHERE game_id=? ORDER BY created DESC,rowid DESC LIMIT 100', (game_id,))]
                    return self.send(200, {'comments': rows})
            if route.startswith('/uploads/'):
                name = route.removeprefix('/uploads/')
                if '/' in name or '\\' in name or not name or Path(name).name != name:
                    return self.fail(404, 'File not found.')
                file = UPLOADS / name
                if not file.is_file():
                    return self.fail(404, 'File not found.')
                return self.send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or 'application/octet-stream', sandbox=file.suffix == '.html')
            paths = {'/': 'index.html', '/index.html': 'index.html', '/app.js': 'app.js', '/social.js': 'social.js', '/style.css': 'style.css'}
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
                return self.fail(413, 'Choose a file smaller than 30 MB.')
            raw = self.rfile.read(length)
            route = self.path.split('?')[0]
            if route == '/api/uploads':
                return self.upload(raw)
            if length > 8192 or not self.headers.get('Content-Type', '').startswith('application/json'):
                return self.fail(400, 'Invalid request.')
            item = json.loads(raw)
            if not isinstance(item, dict):
                return self.fail(400, 'Invalid request.')
            game_id = item.get('gameId')
            if not isinstance(game_id, str):
                return self.fail(400, 'Choose a game.')
            with database() as conn:
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
                    name, body = item.get('name', ''), item.get('body', '')
                    if not isinstance(name, str) or not isinstance(body, str) or not 1 <= len(name.strip()) <= 40 or not 1 <= len(body.strip()) <= 500:
                        return self.fail(400, 'Enter a name (up to 40 characters) and a comment (up to 500 characters).')
                    count = conn.execute("SELECT COUNT(*) FROM comments WHERE visitor=? AND created > datetime('now','-1 minute')", (self.identity,)).fetchone()[0]
                    if count >= 10:
                        return self.fail(429, 'Please wait a minute before posting again.')
                    conn.execute('INSERT INTO comments(id,game_id,visitor,name,body) VALUES(?,?,?,?,?)', (str(uuid.uuid4()), game_id, self.identity, name.strip(), body.strip()))
                    conn.commit()
                    return self.send(201, self.engagement(conn, game_id))
            self.fail(404, 'Action not found.')
        except (ValueError, UnicodeError):
            self.fail(400, 'Invalid request.')
        except Exception:
            self.fail(500, 'Could not save. Your input has been preserved; please try again.')

    def upload(self, raw):
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
        if not file_data or extension not in ('.html', '.mp4', '.webm'):
            return self.fail(400, 'Use a self-contained .html demo or an .mp4/.webm video.')
        if len(file_data) > (5 if extension == '.html' else 30) * 1024 * 1024:
            return self.fail(413, 'HTML demos must be under 5 MB and videos under 30 MB.')
        if extension == '.html':
            text = file_data.decode('utf-8')
            if '<html' not in text.lower() and '<!doctype html' not in text.lower():
                return self.fail(400, 'The HTML file must be a complete, self-contained page.')
        elif extension == '.mp4' and b'ftyp' not in file_data[:64]:
            return self.fail(400, 'This file is not a valid MP4 video.')
        elif extension == '.webm' and not file_data.startswith(b'\x1a\x45\xdf\xa3'):
            return self.fail(400, 'This file is not a valid WebM video.')
        if not 1 <= len(fields.get('title', '')) <= 80 or not 1 <= len(fields.get('studio', '')) <= 80 or not 1 <= len(fields.get('description', '')) <= 300 or fields.get('genre') not in ('Arcade', 'Puzzle', 'Adventure', 'Strategy'):
            return self.fail(400, 'Complete the title, studio, description, and genre.')
        game_id = str(uuid.uuid4())
        filename = game_id + extension
        file = UPLOADS / filename
        with database() as conn:
            count = conn.execute("SELECT COUNT(*) FROM uploads WHERE visitor=? AND created > datetime('now','-1 hour')", (self.identity,)).fetchone()[0]
            if count >= 10:
                return self.fail(429, 'Upload limit reached. Please try again in an hour.')
            file.write_bytes(file_data)
            try:
                conn.execute('INSERT INTO uploads(id,title,studio,genre,description,filename,kind,visitor) VALUES(?,?,?,?,?,?,?,?)', (game_id, fields['title'], fields['studio'], fields['genre'], fields['description'], filename, 'html' if extension == '.html' else 'video', self.identity))
                conn.commit()
            except Exception:
                file.unlink(missing_ok=True)
                raise
        self.send(201, {'id': game_id, 'message': 'Upload published to the local feed.'})

if __name__ == '__main__':
    port = int(os.environ.get('QUICKPLAY_PORT', '4174'))
    print('QuickPlay: http://127.0.0.1:%s' % port, flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
