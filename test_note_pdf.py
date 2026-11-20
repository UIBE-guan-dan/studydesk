import tempfile, unittest
from pathlib import Path
from pypdf import PdfReader
from note_pdf import build_note_pdf
from core import ROOT

class NotePDFTests(unittest.TestCase):
    def test_pdf_structure_cache_and_content(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as td:
            body='# 复习笔记\n\n## 重点\n\n这是**重要定义**。\n\n| 项目 | 含义 |\n|---|---|\n| 变量 | 待研究的量 |\n\n公式 $y = \\beta_0 + \\beta_1 x$。'
            path=build_note_pdf('笔记',body,td); self.assertTrue(path.read_bytes().startswith(b'%PDF'))
            reader=PdfReader(path); text=''.join(p.extract_text() for p in reader.pages)
            self.assertIn('重要定义',text); self.assertIn('待研究的量',text); self.assertNotIn('**',text)
            self.assertEqual(build_note_pdf('笔记',body,td),path)
            self.assertNotEqual(build_note_pdf('笔记',body+'\n\n补充内容',td),path)

if __name__=='__main__':unittest.main()
