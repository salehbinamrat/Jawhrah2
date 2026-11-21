"""Requirements locked before priority fixes; no live MikroTik required."""
from pathlib import Path
import re
import unittest
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent

class HighPriorityTests(unittest.TestCase):
    def test_captive_login_uses_the_complete_portal_and_keeps_routeros_json(self):
        index = BeautifulSoup((ROOT/'index.html').read_text(encoding='utf-8'),'html.parser')
        login_source = (ROOT/'login.html').read_text(encoding='utf-8')
        login = BeautifulSoup(login_source,'html.parser')
        for page in (index, login):
            for name in ('login','status','price','previous-cards','jawharaAnimatedLogo','sell-point','instructions'):
                self.assertIsNotNone(page.select_one('#'+name), name)
        self.assertIn('$(if var == "")',login_source)
        self.assertIn('onLoginError',login_source)
        self.assertIn('$(chap-id)',login_source)
        self.assertIn('$(chap-challenge)',login_source)
        self.assertIn('$(link-login-only)',login_source)
        self.assertIn('$(link-orig)',login_source)
        self.assertEqual((ROOT/'flogin.html').read_text(),login_source)

    def test_safe_opt_in_and_history_removal(self):
        login=BeautifulSoup((ROOT/'login.html').read_text(),'html.parser')
        keep=login.select_one('#rememberCards')
        self.assertIsNotNone(keep)
        self.assertNotIn('checked',keep.attrs)
        script=(ROOT/'js/portal.core.js').read_text()
        self.assertIn('if (user && rememberEnabled()) rememberCard(user, pass)',script)
        self.assertIn('savedAt:itemTime',script)
        self.assertIn('HISTORY_TTL',script)

    def test_stable_polling_and_versioned_assets(self):
        script=(ROOT/'js/portal.core.js').read_text()
        self.assertIn('statusFailures',script)
        self.assertIn('Math.min(',script)
        self.assertIn('30000',script)
        self.assertIn('60000',script)
        for f in ('index.html','login.html'):
            html=(ROOT/f).read_text()
            self.assertIn('jawhara-priority-r7',html)
            self.assertNotIn('jawhara-performance-r6',html)

    def test_accessible_fallback_and_low_cost_graphics(self):
        login=(ROOT/'login.html').read_text()
        self.assertIn('<noscript>',login)
        self.assertIn('login-submit',login)
        css=(ROOT/'css/style.css').read_text()
        self.assertIn('html.low-performance #jawharaAnimatedLogo .orbit-b',css)
        self.assertIn('prefers-reduced-motion',css)

    def test_error_and_balance_are_semantically_accurate(self):
        script=(ROOT/'js/portal.core.js').read_text()
        self.assertIn("code = 'NO_VALID_PROFILE'; message = 'لا توجد باقة فعالة لهذا الحساب'",script)
        for name in ('index.html','login.html'):
            html=(ROOT/name).read_text()
            self.assertIn('البيانات المتبقية',html)
            self.assertNotIn('التحميل المتبقي',html)

if __name__=='__main__': unittest.main()
