import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import app
from lecture_links import align,segments,evidence_batches
from reportlab.pdfgen import canvas
class AlignmentTests(unittest.TestCase):
 def test_exact_anchors_and_rejected_invented_quotes(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'book.pdf';c=canvas.Canvas(str(p));c.drawString(50,700,'Ordinary least squares minimizes residuals.');c.save()
   result={'choices':[{'message':{'content':json.dumps({'matches':[{'segment':0,'page':1,'quote':'Ordinary least squares','confidence':'high','reason':'matching concept'},{'segment':0,'page':1,'quote':'invented textbook words'}]})},'finish_reason':'stop'}]}
   with patch('lecture_links.request',return_value=result):data=align(p,1,1,'[1.0s–3.0s] Ordinary least squares',{'model':'test','base':'https://example.test'},'fake')
   self.assertEqual(len(data['matches']),1);self.assertEqual(data['rejected'],1);self.assertTrue(data['matches'][0]['rects']);self.assertEqual(data['matches'][0]['segment']['start'],1)
 def test_large_material_batches_preserve_all_pages_and_timestamps(self):
  pages={i:('page '+str(i)+' ordinary regression\n')*600 for i in range(1,32)}
  segs=[dict(id=i,start=i*5,end=i*5+4,text='teacher text '*1000) for i in range(4)]
  batches=evidence_batches(pages,segs)
  self.assertGreater(len(batches),1)
  pairs={(p['page'],t['id']) for b in batches for p in b['pages'] for t in b['segments']}
  self.assertEqual(pairs,{(i,j) for i in pages for j in range(4)})
  for b in batches:self.assertLess(len(json.dumps(b,ensure_ascii=False)),65000)
  for page,text in pages.items():
   chunks=[p['text'] for b in batches for p in b['pages'] if p['page']==page]
   self.assertTrue(any(text[-500:] in chunk for chunk in chunks))
 def test_duplicate_batches_merge_and_failure_is_not_success(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'book.pdf';c=canvas.Canvas(str(p));c.drawString(50,700,'Ordinary least squares minimizes residuals.');c.save()
   batch={'pages':[{'page':1,'text':'Ordinary least squares'}],'segments':[{'id':0}]}
   result={'choices':[{'message':{'content':json.dumps({'matches':[{'segment':0,'page':1,'quote':'Ordinary least squares'}]})}}]}
   with patch('lecture_links.evidence_batches',return_value=[batch,batch]),patch('lecture_links.request',return_value=result):
    data=align(p,1,1,'[1s–3s] lecture',{'model':'test','base':'https://example.test'},'fake')
    self.assertEqual(len(data['matches']),1);self.assertEqual(data['batch_count'],2)
   with patch('lecture_links.evidence_batches',return_value=[batch,batch]),patch('lecture_links.request',side_effect=[result,ValueError('offline')]):
    with self.assertRaisesRegex(ValueError,'2/2'):align(p,1,1,'[1s–3s] lecture',{'model':'test','base':'https://example.test'},'fake')
 def test_requires_timestamp_and_valid_order(self):
  with self.assertRaises(ValueError):segments('普通转写')
  with self.assertRaises(ValueError):segments('[5s–2s] invalid')
if __name__=='__main__':unittest.main()
