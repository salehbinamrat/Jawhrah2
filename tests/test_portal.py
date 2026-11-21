"""Offline, simulated RouterOS v6 HTML/JSON endpoint smoke tests. Never tests a live router."""
import json
import os
import pathlib
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

ROOT = pathlib.Path(__file__).resolve().parent.parent
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

class RouterMock(BaseHTTPRequestHandler):
    logged_in = False
    pending = 0
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
            if type(self).pending:
                type(self).pending -= 1
                if not type(self).pending: type(self).logged_in = True
            payload={'logged_in':'yes' if type(self).logged_in else 'no','action':'onStatusQuery','username':'ok','remain_bytes_total':'10240','session_time_left':'1h2m','uptime':'4m','bytes_out':'900','bytes_in':'200'}
            return self.respond(200,json.dumps(payload), 'application/json')
        if path == '/logout':
            type(self).logged_in = False
            return self.respond(200, json.dumps({'logged_in':'no','action':'onLoggedOut'}),'application/json')
        target = ROOT/(path.lstrip('/') or 'index.html')
        if target.is_file() and ROOT in target.resolve().parents:
            return self.respond(200,target.read_bytes(), 'text/css' if path.endswith('.css') else 'text/javascript' if path.endswith('.js') else 'font/woff2' if path.endswith('.woff2') else 'font/woff' if path.endswith('.woff') else 'text/html')
        return self.respond(404,'404')
    def do_POST(self):
        if self.path.split('?')[0] != '/login': return self.respond(404,'404')
        n=int(self.headers.get('Content-Length',0))
        form=parse_qs(self.rfile.read(n).decode())
        user=form.get('username',[''])[0]
        pwd=form.get('password',[''])[0]
        if user=='ok' and pwd=='123':
            type(self).pending=2
            obj={'logged_in':'no','action':'onLoginStart'}
        else:
            reason={'busy':'no more sessions are allowed','expired':'account has expired','quota':'transfer limit reached','bad':'invalid username', 'unknown':'unknown authentication refusal'}.get(user,'invalid password')
            obj={'logged_in':'no','action':'onLoginError','error_orig':reason,'error':reason}
        return self.respond(200,json.dumps(obj), 'application/json')

@unittest.skipUnless(os.environ.get('RUN_BROWSER_TESTS') == '1' and sync_playwright is not None, 'pip install playwright, and provide Chromium')
class PortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd=ThreadingHTTPServer(('127.0.0.1',0),RouterMock)
        cls.thread=threading.Thread(target=cls.httpd.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.httpd.server_port}/index.html'
        cls.play=sync_playwright().start()
        cls.browser=cls.play.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.play.stop();cls.httpd.shutdown();cls.httpd.server_close()
    def setUp(self):
        RouterMock.logged_in=False;RouterMock.pending=0
        self.ctx=self.browser.new_context(viewport={'width':320,'height':568},device_scale_factor=2,is_mobile=True,has_touch=True)
        self.page=self.ctx.new_page()
        self.errors=[]
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.goto(self.url)
    def tearDown(self): self.ctx.close()
    def test_login_visible_and_no_horizontal_overflow(self):
        self.assertTrue(self.page.locator('button.login-submit').is_visible())
        self.assertGreaterEqual(self.page.locator('.login-submit').bounding_box()['height'],44)
        self.assertEqual(self.page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),True)
        self.assertFalse(self.errors)
    def test_theme_modal_and_history(self):
        self.page.locator('[data-set-theme="blue"]').click()
        self.assertEqual(self.page.locator('html').get_attribute('data-theme'),'blue')
        self.page.locator('button[parent-id="price"]').click()
        self.assertTrue(self.page.locator('#price').is_visible())
        self.page.locator('#price .app-logout').click()
        self.assertTrue(self.page.locator('.login-submit').is_visible())
        self.page.locator('button[parent-id="previous-cards"]').click()
        self.assertTrue(self.page.locator('#previous-cards').is_visible())
        self.page.locator('#previous-cards .app-logout').click()
        self.assertFalse(self.errors)
    def submit(self,user,pwd='123'):
        self.page.locator('[name="username"]').fill(user)
        self.page.locator('[name="password"]').fill(pwd)
        self.page.locator('.login-submit').click()
    def test_success_after_on_login_start_eventually_verifies(self):
        self.submit('ok')
        self.page.locator('#status.active').wait_for(timeout=8000)
        self.assertIn('10.0', self.page.locator('#remain_bytes_total').inner_text())
        self.assertFalse(self.errors)
    def test_known_router_errors_are_distinct_and_accurate(self):
        for user,expected in [('busy','جهاز آخر'),('expired','صلاحية'),('quota','رصيد'),('bad','الكرت خطأ'),('unknown','تعذر تسجيل الدخول')]:
            self.submit(user)
            self.page.locator('#error.show').wait_for(timeout=3500)
            self.assertIn(expected,self.page.locator('#error').inner_text())
            self.assertTrue(self.page.locator('button.login-submit').is_enabled())
        self.assertFalse(self.errors)
    def test_legacy_browser_ui_does_not_require_javascript(self):
        self.ctx.close()
        self.ctx=self.browser.new_context(viewport={'width':320,'height':568},java_script_enabled=False)
        self.page=self.ctx.new_page()
        self.page.goto(self.url)
        self.assertTrue(self.page.locator('button.login-submit').is_visible())
        self.assertTrue(self.page.locator('input[name="password"]').is_visible())

if __name__=='__main__':unittest.main(verbosity=2)