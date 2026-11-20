import tempfile, unittest, sqlite3
from pathlib import Path
from unittest.mock import patch
import app
from core import Store,ROOT

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT); self.store=Store(Path(self.tmp.name)/'study.db')
        self.a=self.store.add('量子力学','教材','教材','教材正文')
        self.b=self.store.add('量子力学','笔记','笔记','笔记正文')
    def tearDown(self):self.tmp.cleanup()
    def test_scoped_batch_restore_and_links(self):
        note=self.store.save_page_note('量子力学',self.a,3,'页边笔记','理解')
        other=self.store.add('另一门课','笔记','其他','正文')
        self.assertEqual(self.store.move_docs('量子力学',[self.a,other],'archive'),1)
        self.store.move_docs('量子力学',[self.a,self.b],'trash')
        self.assertEqual(len(self.store.docs('量子力学','trash')),2)
        self.store.move_docs('量子力学',[self.a,self.b],'restore')
        self.assertEqual(self.store.docs('量子力学','archived')[0]['id'],self.a)
        self.assertIn(self.b,[d['id'] for d in self.store.docs('量子力学')])
        self.assertEqual(self.store.note_source(note),{'source_id':self.a,'page':3})
    def test_legacy_migration(self):
        path=Path(self.tmp.name)/'old.db'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE docs(id INTEGER PRIMARY KEY,course TEXT,kind TEXT,title TEXT,body TEXT,created TEXT)')
            db.execute("INSERT INTO docs VALUES(1,'课程','笔记','旧笔记','原文','昨天')")
        db.close()
        store=Store(path)
        self.assertEqual(store.docs('课程')[0]['status'],'active')
        self.assertEqual(store.docs('课程')[0]['body'],'原文')
    def test_ui_group_batch_save_delete_restore(self):
        with patch.object(app,'Store',return_value=self.store):ui=app.App()
        ui.withdraw()
        try:
            ui.update(); ui.open_doc(self.b)
            ui.editor.insert('end',' 新理解')
            ui.tree.selection_set(str(self.a),str(self.b)); ui.manage_docs('archive')
            self.assertEqual(self.store.docs('量子力学'),[])
            ui.library_state.set('归档'); ui.change_library_state()
            self.assertTrue(ui.tree.exists('group:教材')); self.assertTrue(ui.tree.exists('group:学习笔记'))
            ui.tree.selection_set('group:教材'); ui.select_doc()
            ui.tree.selection_set(str(self.a),str(self.b)); ui.delete_doc()
            ui.update(); self.assertEqual(len(self.store.docs('量子力学','trash')),2)
            ui.library_state.set('回收站'); ui.change_library_state()
            ui.tree.selection_set(str(self.a),str(self.b)); ui.manage_docs('restore')
            self.assertEqual(len(self.store.docs('量子力学','archived')),2)
            ui.open_doc(self.b)
            self.assertIn('新理解',ui.get(ui.editor))
            self.assertEqual(ui.library_state.get(),'归档')
            ui.new_note(); self.assertEqual(ui.library_state.get(),'使用中')
        finally:ui.destroy()

if __name__=='__main__':unittest.main()
