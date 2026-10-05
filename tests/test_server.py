"""Exercise the real HTTP handlers in memory, without binding a network socket."""
import importlib.util
import io
import json
import os
from pathlib import Path
from http.cookies import SimpleCookie
from email.message import Message
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_server(directory):
    old = os.environ.get('QUICKPLAY_DATA')
    os.environ['QUICKPLAY_DATA'] = str(directory)
    try:
        spec = importlib.util.spec_from_file_location('quickplay_test_server', ROOT / 'server.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if old is None:
            os.environ.pop('QUICKPLAY_DATA', None)
        else:
            os.environ['QUICKPLAY_DATA'] = old


class Client:
    def __init__(self, server):
        self.server, self.cookies = server, {}

    def request(self, route, item=None, raw=None, content_type='application/json', extra_headers=None):
        handler = self.server.Handler.__new__(self.server.Handler)
        handler.path = route
        handler.command = 'GET' if item is None and raw is None else 'POST'
        handler.client_address = ('127.0.0.1', 1234)
        handler.headers = Message()
        handler.headers['Host'] = '127.0.0.1:4174'
        handler.headers['Cookie'] = '; '.join('%s=%s' % pair for pair in self.cookies.items())
        if item is not None:
            raw = json.dumps(item).encode()
        handler.headers['Content-Type'] = content_type
        handler.headers['Content-Length'] = str(len(raw or b''))
        for name, value in (extra_headers or {}).items():
            handler.headers[name] = value
        handler.rfile, handler.wfile = io.BytesIO(raw or b''), io.BytesIO()
        headers = []
        handler.send_response = lambda code: setattr(handler, 'status', code)
        handler.send_header = lambda key, value: headers.append((key, value))
        handler.end_headers = lambda: None
        (handler.do_GET if handler.command == 'GET' else handler.do_POST)()
        for key, value in headers:
            if key == 'Set-Cookie':
                cookie = SimpleCookie(value)
                for name, morsel in cookie.items():
                    if morsel.value:
                        self.cookies[name] = morsel.value
                    else:
                        self.cookies.pop(name, None)
        body = handler.wfile.getvalue()
        kind = dict(headers).get('Content-Type', '')
        return handler.status, json.loads(body) if kind.startswith('application/json') else body, headers

    def signup(self, email, role='developer'):
        status, result, _ = self.request('/api/auth/signup', {'name': email.split('@')[0], 'email': email, 'password': 'a-good-password', 'role': role})
        assert status == 201, result
        return result['user']

    def upload(self, title='Click Rush', extension='html'):
        boundary = 'quickplaytestboundary'
        chunks = []
        for name, value in {'title': title, 'studio': 'Test Studio', 'description': 'A complete playable game.', 'genre': 'Arcade'}.items():
            chunks.append('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (boundary, name, value))
        chunks.append('--%s\r\nContent-Disposition: form-data; name="file"; filename="demo.%s"\r\nContent-Type: text/html\r\n\r\n%s\r\n--%s--\r\n' % (boundary, extension, (ROOT / 'sample-demo.html').read_text(), boundary))
        return self.request('/api/uploads', raw=''.join(chunks).encode(), content_type='multipart/form-data; boundary='+boundary)


class QuickPlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.server = load_server(self.temp.name)
        self.developer, self.other, self.player, self.guest = [Client(self.server) for _ in range(4)]
        self.dev = self.developer.signup('developer@example.com')
        self.other.signup('other@example.com')
        self.player.signup('player@example.com', 'player')
        status, game, _ = self.developer.upload()
        self.assertEqual(status, 201, game)
        self.game = game['id']

    def review(self):
        return self.player.request('/api/comments', {'gameId': self.game, 'rating': 4, 'category': 'Gameplay', 'body': 'Great game! <script>alert(1)</script>', 'name': 'Fake name'})

    def test_sessions_and_passwords(self):
        _, me, _ = self.developer.request('/api/auth/me')
        self.assertEqual(me['user']['id'], self.dev['id'])
        self.assertNotIn('password_hash', me['user'])
        _, _, headers = self.developer.request('/api/auth/login', {'email': 'DEVELOPER@example.com', 'password': 'a-good-password'})
        cookie = next(v for k, v in headers if k == 'Set-Cookie' and v.startswith('qp_session='))
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Strict', cookie)
        with self.server.database() as conn:
            password = conn.execute('SELECT password_hash FROM users WHERE id=?', (self.dev['id'],)).fetchone()[0]
            self.assertNotEqual(password, 'a-good-password')
        self.assertEqual(self.developer.request('/api/auth/login', {'email': 'developer@example.com', 'password': 'wrong'})[0], 401)
        old_session = self.developer.cookies['qp_session']
        self.developer.request('/api/auth/logout', {})
        self.assertIsNone(self.developer.request('/api/auth/me')[1]['user'])
        self.developer.cookies['qp_session'] = old_session
        self.assertIsNone(self.developer.request('/api/auth/me')[1]['user'])

    def test_expired_sessions(self):
        with self.server.database() as conn:
            conn.execute("UPDATE sessions SET expires=datetime('now','-1 day')")
        self.assertIsNone(self.developer.request('/api/auth/me')[1]['user'])
        self.assertEqual(self.developer.request('/api/feedback')[0], 401)

    def test_signup_validation(self):
        for fields in [dict(role='admin'), dict(password='short'), dict(email='invalid'), dict(name='')]:
            data = dict(name='Person', email='new@example.com', password='a-good-password', role='player', **{})
            data.update(fields)
            self.assertEqual(self.guest.request('/api/auth/signup', data)[0], 400)
        self.assertEqual(self.guest.request('/api/auth/signup', dict(name='Duplicate', email='DEVELOPER@example.com', password='a-good-password', role='developer'))[0], 409)

    def test_role_access(self):
        for route in ('/api/feedback', '/api/marketing'):
            self.assertEqual(self.guest.request(route)[0], 401)
            self.assertEqual(self.player.request(route)[0], 403)
        self.assertEqual(self.guest.upload()[0], 401)
        self.assertEqual(self.player.upload()[0], 403)
        self.assertEqual(self.guest.request('/marketing')[0], 302)
        self.assertEqual(self.player.request('/marketing')[0], 302)
        self.assertEqual(self.developer.request('/marketing')[0], 200)

    def test_reviews_identity_validation_and_uniqueness(self):
        self.assertEqual(self.guest.request('/api/comments', {'gameId': self.game, 'body': 'Anonymous', 'rating': 5})[0], 401)
        self.assertEqual(self.developer.request('/api/comments', {'gameId': self.game, 'body': 'Mine', 'rating': 5})[0], 403)
        for rating in (0, 6, True, '5'):
            self.assertEqual(self.player.request('/api/comments', {'gameId': self.game, 'rating': rating, 'body': 'Review'})[0], 400)
        self.assertEqual(self.review()[0], 201)
        review = self.guest.request('/api/comments/'+self.game)[1]['comments'][0]
        self.assertEqual(review['name'], 'player')
        self.assertEqual(review['rating'], 4)
        self.assertEqual(self.review()[0], 409)

    def test_feedback_ownership_read_and_reply(self):
        self.review()
        inbox = self.developer.request('/api/feedback')[1]
        self.assertEqual(len(inbox['reviews']), 1)
        review = inbox['reviews'][0]
        self.assertIsNone(review['read_at'])
        self.assertEqual(self.other.request('/api/feedback')[1]['reviews'], [])
        data = {'reviewId': review['id'], 'read': True}
        self.assertEqual(self.other.request('/api/feedback/update', data)[0], 404)
        self.assertEqual(self.developer.request('/api/feedback/update', data)[0], 200)
        self.assertIsNotNone(self.developer.request('/api/feedback')[1]['reviews'][0]['read_at'])
        self.assertEqual(self.developer.request('/api/feedback/update', {'reviewId': review['id'], 'reply': 'Thanks for playing!'})[0], 200)
        public = self.guest.request('/api/comments/'+self.game)[1]['comments'][0]
        self.assertEqual(public['reply'], 'Thanks for playing!')
        self.assertEqual(public['studio'], 'Test Studio')
        self.developer.request('/api/feedback/update', {'reviewId': review['id'], 'read': False})
        self.assertIsNone(self.developer.request('/api/feedback')[1]['reviews'][0]['read_at'])

    def test_uploads_html_only_and_isolation(self):
        self.assertEqual(self.developer.upload(extension='mp4')[0], 400)
        game = self.guest.request('/api/games')[1]['uploads'][0]
        self.assertEqual(game['owner_id'], self.dev['id'])
        status, content, headers = self.guest.request(game['url'])
        self.assertEqual(status, 200)
        self.assertIn(b'Click Rush', content)
        csp = dict(headers)['Content-Security-Policy']
        self.assertIn('sandbox allow-scripts', csp)
        self.assertIn("connect-src 'none'", csp)
        self.assertNotIn('allow-same-origin', csp)
        self.assertEqual(self.guest.request('/uploads/../server.py')[0], 404)

    def test_demo_campaign_access_price_duplicate_and_expiry(self):
        data = dict(gameId=self.game, planId='spark', confirmDemo=True, amount=1)
        self.assertEqual(self.guest.request('/api/marketing/purchase', data)[0], 401)
        self.assertEqual(self.player.request('/api/marketing/purchase', data)[0], 403)
        self.assertEqual(self.other.request('/api/marketing/purchase', data)[0], 404)
        self.assertEqual(self.developer.request('/api/marketing/purchase', {**data, 'planId':'invalid'})[0], 400)
        self.assertEqual(self.developer.request('/api/marketing/purchase', {**data, 'confirmDemo':False})[0], 400)
        status, result, _ = self.developer.request('/api/marketing/purchase', data)
        self.assertEqual(status, 201, result)
        self.assertEqual(result['mode'], 'demo')
        self.assertEqual(self.developer.request('/api/marketing/purchase', data)[0], 409)
        marketing = self.developer.request('/api/marketing')[1]
        self.assertEqual(marketing['campaigns'][0]['amount'], 900)
        self.assertEqual(marketing['campaigns'][0]['status'], 'active')
        self.assertEqual(self.other.request('/api/marketing')[1]['campaigns'], [])
        self.assertEqual(self.developer.upload('A newer organic demo')[0], 201)
        game = self.guest.request('/api/games')[1]['uploads'][0]
        self.assertEqual(game['id'], self.game, 'Promoted games must precede newer organic games')
        self.assertTrue(game['promoted'])
        with self.server.database() as conn:
            conn.execute("UPDATE campaigns SET expires=datetime('now','-1 day')")
        self.assertFalse(self.guest.request('/api/games')[1]['uploads'][0]['promoted'])
        self.assertEqual(self.developer.request('/api/marketing')[1]['campaigns'][0]['status'], 'ended')

    def test_legacy_upload_ownership_uses_original_cookie(self):
        with self.server.database() as conn:
            conn.execute('UPDATE uploads SET owner_id=NULL WHERE id=?', (self.game,))
        self.other.request('/api/auth/login', {'email': 'other@example.com', 'password': 'a-good-password'})
        self.assertEqual(self.other.request('/api/feedback')[1]['games'], [])
        self.developer.request('/api/auth/login', {'email': 'developer@example.com', 'password': 'a-good-password'})
        self.assertEqual(self.developer.request('/api/feedback')[1]['games'][0]['id'], self.game)

    def test_persistence_after_module_reload(self):
        self.review()
        self.developer.request('/api/marketing/purchase', dict(gameId=self.game, planId='momentum', confirmDemo=True))
        reloaded = load_server(self.temp.name)
        client = Client(reloaded)
        client.cookies = dict(self.developer.cookies)
        self.assertEqual(client.request('/api/auth/me')[1]['user']['id'], self.dev['id'])
        self.assertEqual(len(client.request('/api/feedback')[1]['reviews']), 1)
        self.assertEqual(len(client.request('/api/marketing')[1]['campaigns']), 1)

    def test_request_validation_and_cross_origin(self):
        self.assertEqual(self.guest.request('/api/likes', {'gameId':'orbit', 'liked':True}, extra_headers={'Origin':'https://evil.example'})[0], 403)
        self.assertEqual(self.guest.request('/api/auth/login', {}, extra_headers={'Sec-Fetch-Site':'cross-site'})[0], 403)
        self.assertEqual(self.guest.request('/api/likes', raw=b'{broken')[0], 400)
        self.assertEqual(self.guest.request('/api/likes', {'gameId':'missing', 'liked':True})[0], 404)
        self.assertEqual(self.guest.request('/api/likes', {'gameId':'orbit', 'liked':True})[0], 200)
        self.guest.request('/api/likes', {'gameId':'orbit', 'liked':True})
        self.assertEqual(self.guest.request('/api/games')[1]['engagement']['orbit']['likes'], 1)

    def test_auth_rate_limit(self):
        with self.server.database() as conn:
            conn.executemany('INSERT INTO auth_attempts(address) VALUES(?)', [('127.0.0.1',)]*30)
        self.assertEqual(self.guest.request('/api/auth/login', {'email':'developer@example.com', 'password':'wrong'})[0], 429)

    def test_old_database_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            conn = sqlite3.connect(Path(directory) / 'quickplay.sqlite')
            conn.executescript('''CREATE TABLE uploads(id TEXT PRIMARY KEY,title TEXT NOT NULL,studio TEXT NOT NULL,genre TEXT NOT NULL,description TEXT NOT NULL,filename TEXT NOT NULL,kind TEXT NOT NULL,visitor TEXT NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE comments(id TEXT PRIMARY KEY,game_id TEXT NOT NULL,visitor TEXT NOT NULL,name TEXT NOT NULL,body TEXT NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO uploads(id,title,studio,genre,description,filename,kind,visitor) VALUES('old','Old game','Old studio','Arcade','Demo','old.html','html','visitor');
            INSERT INTO comments(id,game_id,visitor,name,body) VALUES('old-review','old','visitor','Old player','Nice demo');''')
            conn.commit()
            conn.close()
            migrated = Client(load_server(directory))
            self.assertEqual(migrated.request('/api/games')[1]['uploads'][0]['title'], 'Old game')
            review = migrated.request('/api/comments/old')[1]['comments'][0]
            self.assertEqual(review['body'], 'Nice demo')
            self.assertIsNone(review['rating'])


if __name__ == '__main__':
    unittest.main()
