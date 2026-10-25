"""Regression checks using the retained actual hardware capture as the positive control."""
from pathlib import Path
import json,re,tempfile,unittest
import analyze
HERE=Path(__file__).resolve().parent
class CaptureChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.text=Path(json.loads((HERE/'latest_capture.json').read_text())['capture']).read_text()
 def parse(self,text):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'modified_capture.txt';p.write_text(text);return analyze.validate(p)
 def mutate(self,prefix,index):
  lines=self.text.splitlines()
  i=next(i for i,s in enumerate(lines) if s.startswith(prefix))
  head,data=lines[i].split(' data=');w=analyze.words(data);w[index]^=1
  lines[i]=head+' data='+''.join(f'{v:08x}' for v in reversed(w))
  return '\n'.join(lines)
 def test_actual_capture(self):self.assertEqual(len(self.parse(self.text)['rows']),66)
 def test_missing_restore(self):
  with self.assertRaises(ValueError):self.parse(re.sub(r'^RESTORED.*$','',self.text,flags=re.M))
 def test_missing_timing(self):
  with self.assertRaises(ValueError):self.parse(re.sub(r'^FAST kind=1 bytes=16 repeats=1000 sample=0 .*\n','',self.text,flags=re.M))
 def test_bad_digest(self):
  with self.assertRaises(ValueError):self.parse(self.mutate('FAST kind=1 bytes=16 ',6))
 def test_bad_gcm_tag(self):
  with self.assertRaises(ValueError):self.parse(self.mutate('FAST kind=3 bytes=16 ',6))
 def test_bad_stream_tag(self):
  with self.assertRaises(ValueError):self.parse(self.mutate('FAST kind=5 bytes=65536 ',6))
 def test_failed_negative_check(self):
  with self.assertRaises(ValueError):self.parse(self.mutate('FAST kind=4 bytes=16 ',14))
 def test_missing_cipher_fragment(self):
  with self.assertRaises(ValueError):self.parse(re.sub(r'^CIPHER kind=3 bytes=8192 sample=0 offset=512 .*\n','',self.text,flags=re.M))
 def test_bad_cipher_fragment(self):
  lines=self.text.splitlines();i=next(i for i,s in enumerate(lines) if s.startswith('CIPHER kind=3 bytes=16 sample=0 '))
  head,data=lines[i].split(' data=');lines[i]=head+' data='+('1' if data[0]=='0' else '0')+data[1:]
  with self.assertRaises(ValueError):self.parse('\n'.join(lines))
 def test_duplicate_timing(self):
  row=next(s for s in self.text.splitlines() if s.startswith('FAST '))
  with self.assertRaises(ValueError):self.parse(self.text+'\n'+row)
 def test_missing_pq_batch(self):
  with self.assertRaises(ValueError):self.parse(re.sub(r'^PQ kind=6 case=0 sample=0 .*\n','',self.text,flags=re.M))
 def test_pq_wrong_decision(self):
  with self.assertRaises(ValueError):self.parse(self.mutate('PQ kind=7 case=1 sample=0 ',5))
 def test_pq_wrong_hash_count(self):
  with self.assertRaises(ValueError):self.parse(self.mutate('PQ kind=6 case=0 sample=0 ',6))
 def test_pq_malformed_guard(self):
  with self.assertRaises(ValueError):self.parse(self.mutate('PQ_GUARD kind=6 case=4 ',5))
 def test_padded_shake_kat(self):
  with self.assertRaises(ValueError):self.parse(self.mutate('SHAKE_KAT bytes=55 ',6))
 def test_missing_pq_upload(self):
  with self.assertRaises(ValueError):self.parse(self.text.replace('PQ_VECTOR kind=7 UPLOAD_VERIFIED=YES',''))
if __name__=='__main__':unittest.main()
