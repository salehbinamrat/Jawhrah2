'use strict';
const vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto');
const assert=require('node:assert/strict');
const window={};
vm.runInNewContext(fs.readFileSync(__dirname+'/../js/chap-md5.js','utf8'), {window,unescape,encodeURIComponent,Math,String});
const chap=window.PortalChap;
for (const value of ['', 'a', 'abc', 'message digest', 'abcdefghijklmnopqrstuvwxyz','\x00\x7f\x80\xff', '1234567890'.repeat(10)]) {
  assert.equal(chap.md5Binary(value),crypto.createHash('md5').update(Buffer.from(value,'latin1')).digest('hex'));
}
for (const password of ['123', 'كلمةمرور', 'A1!','']) {
 const id='\x01', challenge='\x02\x80\xff';
 const expected=crypto.createHash('md5').update(Buffer.concat([Buffer.from(id,'latin1'),Buffer.from(password,'utf8'),Buffer.from(challenge,'latin1')])).digest('hex');
 assert.equal(chap.response(id,password,challenge),expected);
}
console.log('PASS: RFC1321 and MikroTik CHAP vectors');
