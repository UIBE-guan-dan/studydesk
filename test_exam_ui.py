import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import app
from core import Store,ROOT
from exam_ui import validate_exam,exam_markdown,TYPES,prepare_exam_evidence,request_exam
class ExamTests(unittest.TestCase):
 def test_validation_and_answer_separation(self):
  counts={k:int(k=='单选题') for k in TYPES};q=dict(type='单选题',question='Which estimate?',options=['alpha','beta'],correct=[1],answer='beta',explanation='The coefficient is beta.',source='教材',pages=[2]);data={'questions':[q]}
  result=validate_exam(json.dumps(data),counts,{2});paper,answers=exam_markdown(result,'Test','pages 2')
  self.assertNotIn('The coefficient',paper);self.assertIn('答案：B',answers)
  with self.assertRaises(ValueError):validate_exam(json.dumps(data),counts,{3})
  q['correct']=[0,1]
  with self.assertRaises(ValueError):validate_exam(json.dumps(data),counts,{2})
 def test_long_evidence_uses_exact_source_ids(self):
  quote='A coefficient has a line-\nbreak and a ligature ﬁ. '
  evidence='\n\n'.join(f'[资料 6 · book · PDF 第 {i} 页]\n'+quote*230 for i in range(31,37))
  sent=[]
  def select(base,endpoint,key,payload):
   candidates=json.loads(payload['messages'][1]['content']);sent.extend(candidates)
   ids=[candidates[0]['id'],candidates[0]['id']]
   return {'choices':[{'message':{'content':json.dumps({'ids':ids})}}]}
  with patch('exam_ui.request',side_effect=select):
   prepared,pages=prepare_exam_evidence(evidence,{'model':'test','base':'https://example.test'},'fake','')
  self.assertEqual({c['page'] for c in sent},set(range(31,37)))
  self.assertIn(sent[0]['text'],prepared);self.assertLess(len(prepared),48000)
  self.assertIn('line-\nbreak',prepared);self.assertIn('ﬁ',prepared)
 def test_invalid_ids_retry_and_never_become_evidence(self):
  evidence='[资料 6 · book · PDF 第 20 页]\n'+('Original text. '*4000)
  bad={'choices':[{'message':{'content':'{"ids":["invented-id"]}'}}]}
  with patch('exam_ui.request',return_value=bad) as mocked:
   with self.assertRaisesRegex(ValueError,'两次未返回有效'):prepare_exam_evidence(evidence,{'model':'test','base':'https://example.test'},'fake','')
   self.assertEqual(mocked.call_count,2)
 def test_format_retry_recovers(self):
  evidence='[资料 6 · book · PDF 第 20 页]\n'+('Original text. '*4000);calls=[]
  def select(base,endpoint,key,payload):
   calls.append(payload)
   content='invalid' if len(calls)==1 else json.dumps({'ids':[json.loads(payload['messages'][1]['content'])[0]['id']]})
   return {'choices':[{'message':{'content':content}}]}
  with patch('exam_ui.request',side_effect=select):
   result,pages=prepare_exam_evidence(evidence,{'model':'test','base':'https://example.test'},'fake','')
  self.assertIn('Original text.',result);self.assertEqual(pages,{20});self.assertGreater(len(calls),1)
 def test_timeout_retry_and_auth_error_not_retried(self):
  with patch('exam_ui.request',side_effect=[TimeoutError('timed out'),{'ok':True}]) as req,patch('exam_ui.time.sleep'):
   self.assertEqual(request_exam({'base':'https://example.test'},'fake',{}),{'ok':True});self.assertEqual(req.call_count,2)
  with patch('exam_ui.request',side_effect=ValueError('HTTP 401')) as req:
   with self.assertRaises(ValueError):request_exam({'base':'https://example.test'},'fake',{})
   self.assertEqual(req.call_count,1)
 def test_partial_batches_resume_from_disk(self):
  evidence='\n\n'.join(f'[资料 6 · book · PDF 第 {page} 页]\n'+('Exact source passage. '*700) for page in range(20,25))
  settings={'model':'test','base':'https://example.test'};processed=[]
  def select(base,endpoint,key,payload):
   items=json.loads(payload['messages'][1]['content']);processed.append(items[0]['id'])
   if len(processed)>1:raise TimeoutError('timed out')
   return {'choices':[{'message':{'content':json.dumps({'ids':[items[0]['id']]})}}]}
  with tempfile.TemporaryDirectory() as folder:
   with patch('exam_ui.request',side_effect=select),patch('exam_ui.time.sleep'):
    with self.assertRaisesRegex(ValueError,'连续三次'):prepare_exam_evidence(evidence,settings,'fake','',cache_dir=folder)
   self.assertEqual(len(list(Path(folder).glob('*.json'))),1)
   def resume(base,endpoint,key,payload):
    items=json.loads(payload['messages'][1]['content']);self.assertNotEqual(items[0]['id'],processed[0])
    return {'choices':[{'message':{'content':json.dumps({'ids':[items[0]['id']]})}}]}
   with patch('exam_ui.request',side_effect=resume):out,pages=prepare_exam_evidence(evidence,settings,'fake','',cache_dir=folder)
   self.assertIn('Exact source passage.',out);self.assertIn(20,pages)
   with patch('exam_ui.request') as req:prepare_exam_evidence(evidence,settings,'fake','',cache_dir=folder);req.assert_not_called()
   for file in Path(folder).glob('*.json'):self.assertNotIn('fake',file.read_text(encoding='utf-8'))
 def test_short_evidence_does_not_make_extra_requests(self):
  with patch('exam_ui.request') as mocked:
   self.assertEqual(prepare_exam_evidence('short',{},'',''),('short',None));mocked.assert_not_called()
 def test_course_switch_and_pdf_result(self):
  with tempfile.TemporaryDirectory(dir=ROOT) as folder:
   store=Store(Path(folder)/'study.db');store.add('量子力学','笔记','原文','This is sufficient source evidence for a practice question about variables and measurement.');store.course('计量经济学')
   with patch.object(app,'Store',return_value=store):ui=app.App()
   ui.withdraw();ui.update()
   try:
    ui.course.set('量子力学');ui.refresh();ui.scope.set('旧考点');ui.course.set('计量经济学');ui.refresh();self.assertEqual(ui.scope.get(),'')
    ui.course.set('量子力学');ui.refresh();ui.model.set('test')
    for k,v in ui.counts.items():v.set('1' if k=='简答题' else '0')
    result={'choices':[{'message':{'content':json.dumps({'questions':[dict(type='简答题',question='解释变量',answer='答案',explanation='解释内容',source='原文',pages=[])]})}}]}
    with patch('exam_ui.request',return_value=result),patch.object(ui,'run',side_effect=lambda label,work,done:done(work())):ui.make_exam()
    self.assertTrue(ui.exam_reader.pdf);self.assertTrue(ui.answer_reader.pdf);self.assertEqual(ui.exam_tabs.select(),str(ui.exam_reader))
    self.assertEqual(len([d for d in store.docs('量子力学') if d['kind']=='试卷']),2)
   finally:ui.destroy()
if __name__=='__main__':unittest.main()
