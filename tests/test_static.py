"""Source and compatibility smoke tests without network or browser."""
from pathlib import Path
import re
import subprocess
import unittest
from bs4 import BeautifulSoup
import tinycss2
R=Path(__file__).resolve().parent.parent
class StaticTests(unittest.TestCase):
 def test_form_and_controls(self):
  p=BeautifulSoup((R/'index.html').read_text(),'html.parser')
  form=p.select_one('form[name=login]');self.assertIsNotNone(form)
  self.assertEqual(form['method'],'post')
  self.assertEqual(form['action'],'$(link-login-only)')
  self.assertTrue(p.select_one('form input[name=username][required]'))
  self.assertTrue(p.select_one('form input[name=password][required]'))
  self.assertTrue(p.select_one('button.login-submit[type=submit]'))
  self.assertTrue(p.select_one('#jawharaAnimatedLogo .logo-core'))
  for required in ['price','sell-point','instructions','previous-cards','status','block']:
   self.assertTrue(p.select_one('#'+required))
 def test_routeros_json_endpoints_retained(self):
  for f,action in [('login.html','onLoginError'),('flogin.html','onLoginError'),('status.html','onStatusQuery'),('alogin.html','onLoggedIn'),('logout.html','onLoggedOut'),('fstatus.html','onStatusQuery')]:
   self.assertIn(action,(R/f).read_text())
  self.assertIn('$(error-orig-esc)',(R/'login.html').read_text())
 def test_css_parsing_and_legacy_fallback(self):
  s=(R/'css/style.css').read_text()
  self.assertIn('html.low-performance #jawharaAnimatedLogo .orbit-b',s)
  self.assertIn('prefers-reduced-motion:reduce',s)
  self.assertNotIn(':has(',s)
  self.assertIn('background:#ffffff',s)
  rules=tinycss2.parse_stylesheet(s,skip_comments=True,skip_whitespace=True)
  self.assertFalse([x for x in rules if x.type=='error'])
 def test_javascript_syntax_and_error_classification(self):
  subprocess.run(['node','--check',str(R/'js/portal.core.js')],check=True)
  subprocess.run(['node',str(R/'tests/test_diagnostics.js')],check=True)
 def test_sources_within_budget(self):
  self.assertLess((R/'js/portal.core.js').stat().st_size,60000)
  self.assertLess((R/'css/style.css').stat().st_size,60000)
if __name__=='__main__': unittest.main(verbosity=2)