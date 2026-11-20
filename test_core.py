import tempfile, unittest, json
from pathlib import Path
from unittest.mock import patch
import core
tempfile.tempdir = str(core.ROOT)

class CoreTests(unittest.TestCase):
    def test_course_isolation_and_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            s=core.Store(Path(td)/'test.db'); s.course('电动力学')
            id=s.add('量子力学','教材','第一章','波函数是概率幅')
            self.assertEqual(s.docs('电动力学'),[])
            s.update(id,'第二章','薛定谔方程')
            self.assertEqual(core.Store(s.path).docs('量子力学')[0]['body'],'薛定谔方程')
            s.delete(id); self.assertEqual(s.docs('量子力学'),[])
    def test_evidence_retrieval(self):
        docs=[{'id':1,'title':'教材','body':'无关文字'*400+'薛定谔方程决定波函数的演化。'},{'id':2,'title':'其他','body':'经典电磁学'}]
        context=core.retrieve(docs,'薛定谔方程',1)
        self.assertIn('薛定谔方程',context); self.assertIn('资料 1',context); self.assertNotIn('经典电磁学',context)
    def test_import_utf8_and_gbk(self):
        with tempfile.TemporaryDirectory() as td:
            for encoding in ['utf-8-sig','gb18030']:
                p=Path(td)/'a.txt'; p.write_text('量子力学笔记',encoding=encoding)
                self.assertEqual(core.read_document(p),'量子力学笔记')
    def test_chat_request_contract(self):
        response={'choices':[{'message':{'content':'试卷'},'finish_reason':'stop'}]}
        with patch('core.request',return_value=response) as req:
            self.assertEqual(core.generate({'base':'https://example.test/v1','model':'test'},'secret','出题','证据'),'试卷')
            args=req.call_args.args; self.assertEqual(args[1],'/chat/completions')
            self.assertIn('证据',args[3]['messages'][1]['content'])
    def test_speech_multipart(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'课堂.wav'; p.write_bytes(b'RIFF-test')
            with patch('core.request',return_value={'text':'课堂文字'}) as req:
                text=core.transcribe(p,{'speech_base':'https://example.test/v1','speech_model':'whisper-1'},'secret')
                self.assertEqual(text,'课堂文字'); self.assertIn(b'RIFF-test',req.call_args.kwargs['raw'])
    def test_reject_empty_and_plaintext_endpoint(self):
        with self.assertRaises(ValueError):core.request('http://example.com','/models','secret')
        with self.assertRaises(ValueError):core.generate({'model':''},'','','')

if __name__=='__main__':unittest.main()
