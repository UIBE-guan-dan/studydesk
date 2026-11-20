import json, tempfile, unittest, zipfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
import app
from core import Store,ROOT
from learning import LearningStore,task_data,due_label,reading_ai

def task(**kw):
    data=dict(title='小组展示',kind='小组作业',status='未开始',due='2026-11-20 23:59',hours=3,owner='同学 A',notes='提交报告',steps=[dict(title='阅读教材',owner='同学 B',due='',status='进行中',notes='第 2 章')],docs=[])
    data.update(kw);return data

class LearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT); self.store=Store(Path(self.tmp.name)/'study.db'); self.learning=LearningStore(self.store)
        self.source=Path(self.tmp.name)/'教材.txt';self.source.write_text('ordinary least squares 最小二乘法',encoding='utf-8')
        self.doc=self.store.import_file('量子力学','教材',self.source)
    def tearDown(self):self.tmp.cleanup()
    def test_tasks_deadlines_and_scope(self):
        id=self.learning.save_task('量子力学',task(docs=[self.doc],pages={str(self.doc):[48,65]}))
        loaded=self.learning.tasks('量子力学')[0]
        self.assertEqual(loaded['steps'][0]['owner'],'同学 B'); self.assertEqual(loaded['pages'][str(self.doc)],[48,65])
        self.assertEqual(due_label(loaded,datetime(2026,11,20,12)),'今天截止')
        self.assertEqual(due_label(loaded,datetime(2026,11,21)),'已逾期')
        with self.assertRaises(ValueError):self.learning.save_task('另一课程',task(),id)
        with self.assertRaises(ValueError):self.learning.save_task('另一课程',task(docs=[self.doc]))
        with self.assertRaises(ValueError):task_data(task(due='下周五'))
        with self.assertRaises(ValueError):task_data(task(pages={'1':[5,3]}))
    def test_quote_translation_metadata_and_task_filter(self):
        id=self.learning.save_task('量子力学',task(docs=[self.doc]))
        data=dict(doc_id=self.doc,source_title='教材',page=48,printed_page='25',quote='Original words',translation='译文',notes='个人理解',task_id=id)
        self.learning.save_record('量子力学','excerpt',data)
        self.learning.save_record('量子力学','term',dict(data,quote='OLS'))
        self.learning.save_metadata(self.doc,dict(title='教材名称',author='作者',year='2020'))
        text=self.learning.bibliography('量子力学',id)
        for part in ('Original words','译文','个人理解','PDF 页序 48','书内页码 25','作者','待补充'):self.assertIn(part,text)
        self.assertEqual(len(self.learning.records('量子力学','excerpt',id)),1)
        self.assertEqual(self.learning.records('另一课程'),[])
    def test_package_roundtrip_remaps_sources_and_does_not_overwrite(self):
        id=self.learning.save_task('量子力学',task(docs=[self.doc],pages={str(self.doc):[3,5]}))
        self.learning.save_record('量子力学','excerpt',dict(doc_id=self.doc,source_title='教材',page=3,quote='原文',translation='译文',task_id=id))
        self.learning.save_metadata(self.doc,dict(author='原作者'))
        path=Path(self.tmp.name)/'group.zip';self.learning.export_package('量子力学',id,path)
        imported=self.learning.import_package('另一课程',path)
        self.assertNotEqual(imported,id);self.assertEqual(len(self.learning.tasks('量子力学')),1)
        record=self.learning.records('另一课程','excerpt')[0];self.assertNotEqual(record['doc_id'],self.doc);self.assertEqual(record['task_id'],imported)
        doc=self.store.docs('另一课程')[0];self.assertEqual(self.store.original(doc).read_bytes(),self.source.read_bytes())
        self.assertEqual(self.learning.metadata(doc['id'])['author'],'原作者')
        self.assertEqual(self.learning.tasks('另一课程')[0]['pages'],{str(doc['id']):[3,5]})
    def test_bad_package_has_no_partial_import(self):
        path=Path(self.tmp.name)/'bad.zip';data={'format':'studydesk-group','version':1,'task':task(docs=[1]),'records':[],'docs':[dict(id=1,kind='教材',title='标题',body='正文',file='originals/../../evil.pdf')]}
        with zipfile.ZipFile(path,'w') as z:z.writestr('manifest.json',json.dumps(data))
        with self.assertRaises(ValueError):self.learning.import_package('另一课程',path)
        self.assertEqual(self.store.docs('另一课程'),[]);self.assertEqual(self.learning.tasks('另一课程'),[])
    def test_ai_uses_source_and_glossary_without_real_network(self):
        response={'choices':[{'message':{'content':'译文'},'finish_reason':'stop'}]}
        with patch('learning.request',return_value=response) as mocked:
            self.assertEqual(reading_ai({'base':'https://example.test','model':'kimi'},'test','translate','original','OLS = 最小二乘'),'译文')
            payload=mocked.call_args.args[3];self.assertIn('OLS',payload['messages'][1]['content']);self.assertIn('original',payload['messages'][1]['content'])
        with patch('learning.request') as mocked:
            with self.assertRaises(ValueError):reading_ai({'model':'kimi'},'test','translate',' ')
            mocked.assert_not_called()
    def test_pdf_snapshot_and_return_to_archived_source(self):
        from reportlab.pdfgen import canvas
        path=Path(self.tmp.name)/'source.pdf';c=canvas.Canvas(str(path))
        for number in range(1,4):c.drawString(40,700,f'Course source page {number}: ordinary least squares regression');c.showPage()
        c.save();doc=self.store.import_file('量子力学','教材',path)
        with patch.object(app,'Store',return_value=self.store):ui=app.App()
        ui.withdraw();ui.update()
        try:
            ui.open_doc(doc);ui.reader.index=1;ui.reader.render();snapshot=ui.reading_snapshot()
            self.assertEqual(snapshot['page'],2);self.assertIn('page 2',snapshot['quote'])
            self.store.move_docs('量子力学',[doc],'archive');ui.refresh()
            ui.open_learning_source('量子力学',doc,3)
            self.assertEqual(ui.library_state.get(),'归档');self.assertEqual(ui.reader.index,2)
        finally:ui.destroy()
    def test_overview_includes_other_course_deadline(self):
        self.store.course('数学');today=datetime.now().strftime('%Y-%m-%d')+' 23:59'
        self.learning.save_task('数学',task(title='跨课程期末报告',due=today))
        with patch.object(app,'Store',return_value=self.store):ui=app.App()
        ui.withdraw();ui.course.set('量子力学');ui.refresh();ui.update()
        try:
            self.assertIn('跨课程期末报告',ui.due_summary.cget('text'))
            self.assertIn('数学',ui.due_summary.cget('text'))
        finally:ui.destroy()
    def test_ui_task_forms_and_record_course_snapshot(self):
        from tkinter import ttk
        with patch.object(app,'Store',return_value=self.store):ui=app.App()
        ui.withdraw();ui.update()
        try:
            ui.task_dialog(task(docs=[self.doc]));win=ui.winfo_children()[-1]
            def buttons(w):
                for child in w.winfo_children():
                    if isinstance(child,ttk.Button):yield child
                    yield from buttons(child)
            next(b for b in buttons(win) if b.cget('text')=='保存任务').invoke()
            self.assertEqual(len(ui.learning.tasks('量子力学')),1)
            ui.open_doc(self.doc); snap=ui.reading_snapshot();self.assertIn('ordinary',snap['quote'])
            ui.record_dialog(snap);win=ui.winfo_children()[-1]
            ui.course.set('另一课程')
            next(b for b in buttons(win) if b.cget('text')=='保存记录').invoke()
            self.assertEqual(len(ui.learning.records('量子力学','excerpt')),1);self.assertEqual(ui.learning.records('另一课程'),[])
        finally:ui.destroy()

if __name__=='__main__':unittest.main()
