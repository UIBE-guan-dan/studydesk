import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import app
from core import Store, ROOT

class WorkspaceFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT); self.store=Store(Path(self.tmp.name)/'study.db')
        self.first=self.store.add('量子力学','笔记','第一份','原文 A')
        self.second=self.store.add('量子力学','笔记','第二份','原文 B')
        self.factory=patch.object(app,'Store',return_value=self.store); self.factory.start()
        self.ui=app.App(); self.ui.withdraw(); self.ui.update()
    def tearDown(self):
        self.ui.destroy(); self.factory.stop(); self.tmp.cleanup()
    def test_switch_document_saves_edits_and_opens_target(self):
        self.ui.open_doc(self.first); self.ui.editor.insert('end',' 新增理解')
        self.ui.tree.selection_set(str(self.second)); self.ui.select_doc()
        self.assertEqual(self.ui.selected,self.second)
        self.assertEqual(self.ui.get(self.ui.editor),'原文 B')
        doc=next(d for d in self.store.docs('量子力学') if d['id']==self.first)
        self.assertIn('新增理解',doc['body'])
    def test_course_switch_saves_to_original_course(self):
        self.ui.new_note(); self.ui.title_var.set('课程笔记'); self.ui.editor.insert('end','这是量子力学笔记')
        self.store.course('计量经济学'); self.ui.course.set('计量经济学'); self.ui.refresh()
        self.assertEqual(self.store.docs('计量经济学'),[])
        self.assertTrue(any(d['title']=='课程笔记' for d in self.store.docs('量子力学')))
    def test_page_note_persistence_is_linked_and_not_duplicated(self):
        self.ui.side_context=('量子力学',self.first,12,'教材'); self.ui.put(self.ui.side_editor,'对这一页的理解'); self.ui.save_side_note()
        note=self.store.page_note(self.first,12); self.assertEqual(note['body'],'对这一页的理解')
        self.ui.put(self.ui.side_editor,'修订后的理解'); self.ui.save_side_note()
        self.assertEqual(self.store.page_note(self.first,12)['id'],note['id'])
        self.assertEqual(self.store.note_source(note['id']),{'source_id':self.first,'page':12})
    def test_document_to_exam_carries_source(self):
        self.ui.open_doc(self.first); self.ui.to_exam()
        self.assertEqual(self.ui.exam_source_id,self.first)
        self.assertEqual(self.ui.tabs.select(),str(self.ui.pages['AI 自定义组卷']))
    def test_note_to_card_preserves_source_and_answer(self):
        self.ui.side_context=('量子力学',self.first,4,'教材'); self.ui.put(self.ui.side_editor,'知识点答案')
        self.ui.side_to_card()
        self.assertEqual(self.ui.get(self.ui.review.back),'知识点答案')
        self.assertIn('第 5 页',self.ui.review.source.get())
        self.assertEqual(self.ui.tabs.select(),str(self.ui.pages['记忆与复习']))
    def test_export_formats_and_original_copy(self):
        from tkinter import ttk
        original=Path(self.tmp.name)/'source.txt'; original.write_text('原始文件内容',encoding='utf-8')
        for mode in ['md','txt','html','original']:
            destination=Path(self.tmp.name)/('export-'+mode+'.txt')
            self.ui.export_dialog('学习笔记','<script>不能执行</script>',original)
            dialog=self.ui.winfo_children()[-1]; frame=dialog.winfo_children()[0]
            for widget in frame.winfo_children():
                if isinstance(widget,ttk.Radiobutton) and widget.cget('value')==mode:widget.invoke()
            save=next(w for w in frame.winfo_children() if isinstance(w,ttk.Button))
            with patch('workspace_ui.filedialog.asksaveasfilename',return_value=str(destination)):save.invoke()
            content=destination.read_text(encoding='utf-8')
            if mode=='original':self.assertEqual(content,'原始文件内容')
            elif mode=='html':self.assertIn('&lt;script&gt;',content); self.assertNotIn('<script>',content)
            else:self.assertIn('学习笔记',content)
    def test_short_prompt_blocked_before_ai(self):
        self.ui.open_doc(self.first)
        with self.assertRaises(ValueError):self.ui.context_evidence()
    def test_notes_default_to_pdf_and_pdf_export(self):
        from tkinter import ttk
        self.ui.open_doc(self.first)
        self.assertEqual(self.ui.document_tabs.select(),str(self.ui.reader))
        self.assertTrue(self.ui.reader.pdf)
        destination=Path(self.tmp.name)/'export.pdf'
        self.ui.export_dialog('笔记','可阅读的笔记正文')
        dialog=self.ui.winfo_children()[-1]
        button=next(w for w in dialog.winfo_children()[0].winfo_children() if isinstance(w,ttk.Button))
        with patch('workspace_ui.filedialog.asksaveasfilename',return_value=str(destination)):button.invoke()
        self.assertTrue(destination.read_bytes().startswith(b'%PDF'))

if __name__=='__main__':unittest.main()
