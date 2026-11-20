import sys, tempfile, unittest, sqlite3
from pathlib import Path
import app  # Use the exact dependency search order of the desktop launcher.
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from core import Store,ROOT
from review import ReviewStore,parse_drafts

class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT); self.path=Path(self.tmp.name)/'study.db'
    def tearDown(self):self.tmp.cleanup()
    def test_migration_preserves_old_notes_and_backup(self):
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE docs(id INTEGER PRIMARY KEY,course TEXT,kind TEXT,title TEXT,body TEXT,created TEXT)')
            db.execute("INSERT INTO docs VALUES (1,'量子力学','笔记','旧笔记','不能丢失的正文','2026')")
        db.close()
        store=Store(self.path); note=store.docs('量子力学')[0]
        self.assertEqual(note['body'],'不能丢失的正文'); self.assertEqual(note['source_path'],'')
        self.assertTrue(self.path.with_suffix('.before-reader.db').exists())
        Store(self.path) # repeat initialization must be idempotent
    def test_original_copy_and_scan_fallback(self):
        store=Store(self.path); original=Path(self.tmp.name)/'scan.pdf'; original.write_bytes(b'original-pdf-bytes')
        with patch('core.read_document',side_effect=ValueError('no text')):
            store.import_file('量子力学','教材',original)
        doc=store.docs('量子力学')[0]; copy=store.original(doc)
        self.assertEqual(copy.read_bytes(),original.read_bytes()); original.unlink()
        self.assertTrue(copy.exists()); self.assertIn('文字索引不可用',doc['body'])
        store.remember_page(doc['id'],7); self.assertEqual(store.docs('量子力学')[0]['read_page'],7)
    def test_reattach_keeps_notes(self):
        store=Store(self.path); id=store.add('量子力学','教材','book.pdf','已有批注')
        path=Path(self.tmp.name)/'book.pdf'; path.write_bytes(b'PDF')
        store.attach_file(id,path); self.assertEqual(store.docs('量子力学')[0]['body'],'已有批注')
    def test_fsrs_persist_and_course_isolation(self):
        store=Store(self.path); review=ReviewStore(store); id=review.add('量子力学','问题','答案','第 2 页')
        self.assertEqual(len(review.due('量子力学')),1); self.assertEqual(review.due('电动力学'),[])
        now=datetime.now(timezone.utc); due=review.grade(id,3,now)
        self.assertGreater(due,now); self.assertEqual(review.due('量子力学',now),[])
        restored=ReviewStore(Store(self.path)); self.assertEqual(len(restored.due('量子力学',due+timedelta(seconds=1))),1)
        with store.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM reviews').fetchone()[0],1)
        with self.assertRaises(ValueError):review.grade(id,3,now)
    def test_ai_draft_validation(self):
        self.assertEqual(parse_drafts('```json\n[{"question":"Q","answer":"A"}]\n```')[0]['question'],'Q')
        for invalid in ['not JSON','[]','[{"question":"Q"}]','{"question":"Q","answer":"A"}']:
            with self.assertRaises(ValueError):parse_drafts(invalid)

if __name__=='__main__':unittest.main()
