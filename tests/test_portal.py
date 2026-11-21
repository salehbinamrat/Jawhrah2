"""Interactive tests against a local RouterOS template/JSON simulator, not a live router.
Run in CI with RUN_BROWSER_TESTS=1 after `python -m playwright install chromium`.
"""
import hashlib
import json
import os
import pathlib
import re
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

ROOT = pathlib.Path(__file__).resolve().parent.parent
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

CHAP_ID = b'\x01'
CHAP_CHALLENGE = b'\x02\x80\xff'

def render_routeros_login(chap=True):
    source = (ROOT / 'login.html').read_text(encoding='utf-8')
    # Mimic GET /login: RouterOS renders the HTML servlet branch and its
    # challenge placeholders. The other branch serves JSON for ?var=callBack.
    html = source.split('\n$(else)\n$(if error == "")\n', 1)[0]
    html = html.replace('$(if var == "")\n', '', 1)
    html = re.sub(r'\$\(if error\)\s*<span id="routerInitialError".*?</span>\s*\$\(endif\)', '', html, flags=re.S)
    html = re.sub(r'\$\(if chap-id\)(.*?)\$\(endif\)', lambda m: m.group(1) if chap else '', html, flags=re.S)
    for macro, value in {
        '$(chap-id)': r'\x01', '$(chap-challenge)': r'\x02\x80\xff',
        '$(link-login-only)': '/login', '$(link-status)': '/status',
        '$(link-logout)': '/logout', '$(link-orig)': '/status',
    }.items():
        html = html.replace(macro, value)
    return html

class RouterMock(BaseHTTPRequestHandler):
    logged_in = False
    pending = 0
    chap = True
    received_password = None
    poll_count = 0
    def log_message(self, *_): pass
    def respond(self, status, content, ct='text/html; charset=utf-8'):
        body = content.encode('utf-8') if isinstance(content, str) else content
        self.send_response(status)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/status':
            type(self).poll_count += 1
            if type(self).pending:
                type(self).pending -= 1
                if not type(self).pending: type(self).logged_in = True
            payload = {
                'logged_in': 'yes' if type(self).logged_in else 'no',
                'action': 'onStatusQuery', 'username':'ok',
                'remain_bytes_total':'10240','session_time_left':'1h2m',
                'uptime':'4m','bytes_out':'900','bytes_in':'200'
            }
            return self.respond(200, json.dumps(payload), 'application/json')
        if path == '/logout':
            type(self).logged_in = False
            return self.respond(200, json.dumps({'logged_in':'no','action':'onLoggedOut'}), 'application/json')
        if path == '/login':
            return self.respond(200, render_routeros_login(type(self).chap))
        # Do not serve templated login.html statically: use /login servlet.
        target = ROOT / (path.lstrip('/') or 'index.html')
        if target.is_file() and ROOT in target.resolve().parents:
            ct = 'text/css' if path.endswith('.css') else 'text/javascript' if path.endswith('.js') else 'font/woff2' if path.endswith('.woff2') else 'font/woff' if path.endswith('.woff') else 'text/html'
            return self.respond(200, target.read_bytes(), ct)
        return self.respond(404, '404')
    def do_POST(self):
        if self.path.split('?')[0] != '/login': return self.respond(404,'404')
        n = int(self.headers.get('Content-Length', 0))
        form = parse_qs(self.rfile.read(n).decode('utf-8'))
        user = form.get('username',[''])[0]
        pwd = form.get('password',[''])[0]
        type(self).received_password = pwd
        right = hashlib.md5(CHAP_ID + b'123' + CHAP_CHALLENGE).hexdigest() if type(self).chap else '123'
        if user == 'ok' and pwd == right:
            type(self).pending = 2
            obj = {'logged_in':'no', 'action':'onLoginStart'}
        else:
            reason = {
                'busy':'no more sessions are allowed',
                'expired':'account has expired',
                'quota':'transfer limit reached',
                'profile':'no valid profile',
                'bad':'invalid username',
                'unknown':'unknown authentication refusal',
            }.get(user, 'invalid password')
            obj={'logged_in':'no','action':'onLoginError','error_orig':reason,'error':reason}
        return self.respond(200, json.dumps(obj), 'application/json')

@unittest.skipUnless(os.environ.get('RUN_BROWSER_TESTS') == '1' and sync_playwright is not None, 'Set RUN_BROWSER_TESTS=1 and install playwright')
class PortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), RouterMock)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.httpd.server_port}/login'
        cls.play = sync_playwright().start()
        cls.browser = cls.play.chromium.launch(headless=True, args=['--no-sandbox'])
    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.play.stop(); cls.httpd.shutdown(); cls.httpd.server_close()
    def setUp(self):
        RouterMock.logged_in = False; RouterMock.pending = 0
        RouterMock.chap = True; RouterMock.received_password = None; RouterMock.poll_count = 0
        self.ctx = self.browser.new_context(viewport={'width':320,'height':568}, device_scale_factor=2, is_mobile=True, has_touch=True)
        self.page = self.ctx.new_page()
        self.errors=[]
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(self.url, wait_until='domcontentloaded')
    def tearDown(self): self.ctx.close()
    def submit(self, user, pwd='123'):
        self.page.locator('input[name="username"]').fill(user)
        self.page.locator('input[name="password"]').fill(pwd)
        self.page.locator('.login-submit').click()
    def test_main_login_visible_on_captive_route(self):
        self.assertTrue(self.page.locator('button.login-submit').is_visible())
        self.assertTrue(self.page.locator('#jawharaAnimatedLogo').is_visible())
        self.assertTrue(self.page.locator('input[name=password]').is_visible())
        self.assertGreaterEqual(self.page.locator('.login-submit').bounding_box()['height'],44)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        self.assertFalse(self.errors)
    def test_viewports_and_low_performance_mode(self):
        for width in (320, 360, 393, 430):
            self.page.set_viewport_size({'width':width,'height':640})
            self.assertTrue(self.page.locator('.login-submit').is_visible(), str(width))
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'),str(width))
        self.assertFalse(self.errors)
    def test_theme_modal_and_history(self):
        self.page.locator('[data-set-theme="blue"]').click()
        self.assertEqual(self.page.locator('html').get_attribute('data-theme'),'blue')
        self.page.locator('button[parent-id="price"]').click()
        self.assertTrue(self.page.locator('#price').is_visible())
        self.page.locator('#price .app-logout').click()
        self.page.locator('button[parent-id="previous-cards"]').click()
        self.assertTrue(self.page.locator('#previous-cards').is_visible())
        self.page.locator('#previous-cards .app-logout').click()
        self.assertFalse(self.errors)
    def test_chap_login_does_not_transmit_clear_password(self):
        self.assertTrue(self.page.evaluate('window.PORTAL_CONFIG.chapEnabled'))
        self.submit('ok')
        self.page.locator('#status.active').wait_for(timeout=10000)
        self.assertEqual(RouterMock.received_password, hashlib.md5(CHAP_ID+b'123'+CHAP_CHALLENGE).hexdigest())
        self.assertEqual(self.page.locator('#remain_bytes_total').inner_text(),'10.0 كيلوبايت')
        self.assertFalse(self.errors)
    def test_no_implicit_credential_storage(self):
        self.submit('ok'); self.page.locator('#status.active').wait_for(timeout=10000)
        self.assertIsNone(self.page.evaluate('localStorage.getItem("jawhara_success_cards_v3")'))
    def test_opt_in_stores_last_card(self):
        self.page.locator('#rememberCards').check()
        self.submit('ok');self.page.locator('#status.active').wait_for(timeout=10000)
        saved=self.page.evaluate('JSON.parse(localStorage.getItem("jawhara_success_cards_v3"))')
        self.assertEqual(saved['cards'][0]['username'],'ok')
        self.assertEqual(saved['cards'][0]['password'],'123')
        self.assertIsInstance(saved['cards'][0]['savedAt'], int)
    def test_router_error_categories(self):
        for user, expected in [('busy','جهاز آخر'),('expired','صلاحية'),('quota','رصيد'),('profile','باقة فعالة'),('bad','الكرت خطأ'),('unknown','تعذر تسجيل الدخول')]:
            self.page.locator('input[name="username"]').fill(user)
            self.page.locator('input[name="password"]').fill('123')
            # Wait for the fresh challenge page, not a transient old error.
            with self.page.expect_navigation(timeout=7500):
                self.page.locator('.login-submit').click()
            self.page.locator('#error.show').wait_for(timeout=7500)
            self.assertIn(expected, self.page.locator('#error').inner_text())
            self.assertTrue(self.page.locator('button.login-submit').is_enabled())
        self.assertFalse(self.errors)
    def test_index_alias_redirects_to_router_servlet(self):
        self.page.goto(f'http://127.0.0.1:{self.httpd.server_port}/index.html', wait_until='domcontentloaded')
        self.page.wait_for_url('**/login',timeout=5000)
        self.assertTrue(self.page.locator('button.login-submit').is_visible())
    def test_no_javascript_fallback_form(self):
        self.ctx.close()
        self.ctx=self.browser.new_context(viewport={'width':320,'height':568}, java_script_enabled=False)
        self.page=self.ctx.new_page()
        self.page.goto(self.url)
        self.assertTrue(self.page.locator('button.login-submit').is_visible())
        self.assertTrue(self.page.locator('input[name="password"]').is_visible())
        self.assertTrue(self.page.locator('noscript').count() or self.page.get_by_text('يتطلب الدخول').count())

if __name__=='__main__': unittest.main(verbosity=2)
