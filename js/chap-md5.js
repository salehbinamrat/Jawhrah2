/* Local RFC 1321 MD5 for MikroTik HTTP-CHAP (not for password storage).
 * chap-id and chap-challenge must stay as raw byte strings, as provided by
 * RouterOS's JavaScript template escapes. Only the user password is UTF-8.
 * No external scripts or WebCrypto required; works with legacy Android WebView.
 */
(function (w) {
'use strict';
function utf8(value) {
  return unescape(encodeURIComponent(String(value)));
}
function md5Binary(input) {
  var data = String(input), length = data.length;
  var n = (((length + 8) >> 6) + 1) * 16;
  var words = [], i, j;
  for (i = 0; i < n; i++) words[i] = 0;
  for (i = 0; i < length; i++) words[i >> 2] |= (data.charCodeAt(i) & 255) << ((i % 4) * 8);
  words[length >> 2] |= 128 << ((length % 4) * 8);
  words[n - 2] = (length * 8) >>> 0;
  words[n - 1] = Math.floor(length / 0x20000000);
  var a = 0x67452301, b = 0xefcdab89, c = 0x98badcfe, d = 0x10325476;
  var shifts = [7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21];
  var table = [];
  for (i = 0; i < 64; i++) table[i] = Math.floor(Math.abs(Math.sin(i + 1)) * 4294967296) | 0;
  for (j = 0; j < n; j += 16) {
    var aa = a, bb = b, cc = c, dd = d;
    for (i = 0; i < 64; i++) {
      var f, g, shift;
      if (i < 16) { f = (b & c) | (~b & d); g = i; shift = shifts[i % 4]; }
      else if (i < 32) { f = (d & b) | (~d & c); g = (5 * i + 1) % 16; shift = shifts[4 + i % 4]; }
      else if (i < 48) { f = b ^ c ^ d; g = (3 * i + 5) % 16; shift = shifts[8 + i % 4]; }
      else { f = c ^ (b | ~d); g = (7 * i) % 16; shift = shifts[12 + i % 4]; }
      var v = (a + f + table[i] + words[j + g]) | 0;
      var next = (b + ((v << shift) | (v >>> (32 - shift)))) | 0;
      a = d; d = c; c = b; b = next;
    }
    a = (a + aa) | 0; b = (b + bb) | 0; c = (c + cc) | 0; d = (d + dd) | 0;
  }
  function hex(num) {
    var out = '', k, digit;
    for (k = 0; k < 4; k++) {
      digit = (num >>> (k * 8)) & 255;
      out += ('0' + digit.toString(16)).slice(-2);
    }
    return out;
  }
  return hex(a) + hex(b) + hex(c) + hex(d);
}
w.PortalChap = { md5Binary: md5Binary, utf8: utf8,
  response: function (chapId, password, challenge) {
    return md5Binary(String(chapId) + utf8(password) + String(challenge));
  }
};
})(window);
