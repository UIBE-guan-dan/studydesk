"""Task workspace and source-aware reading tools, integrated with the existing shell."""
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from datetime import datetime
from learning import LearningStore, STATUSES, KINDS, due_label, reading_ai

class LearningUX:
    def build_home(self):
        self.learning=LearningStore(self.store)
        self.build_tasks()
        super().build_home()
        p=self.pages['学习概览']
        row=ttk.Frame(p,padding=(0,8)); row.pack(fill='x',before=self.recent)
        self.due_summary=ttk.Label(row,text='',foreground='#b05822',wraplength=800); self.due_summary.pack(side='left',fill='x',expand=True)
        self.button(row,'跨课程日程',self.schedule_dialog)
        self.refresh_home()
        self.after(60000,self.tick_deadlines)
    def tick_deadlines(self):
        self.refresh_home(); self.after(60000,self.tick_deadlines)
    def refresh_home(self):
        super().refresh_home()
        if not hasattr(self,'due_summary'):return
        pending=[t for course in self.store.courses() for t in self.learning.tasks(course) if t['status']!='已完成']
        pending.sort(key=lambda t:t['due'] or '9999')
        urgent=[t for t in pending if due_label(t) in ('已逾期','今天截止','7 天内截止')]
        self.due_summary.config(text='近期任务：'+('；'.join(f"{due_label(t)} · {t['course']} / {t['title']} ({t['due']})" for t in urgent[:3]) or '暂无 7 天内截止任务')+f'\n全部课程还有 {len(pending)} 项未完成任务 · 提醒在软件打开时更新')
    def refresh(self):
        super().refresh()
        if hasattr(self,'learning'):self.refresh_tasks(); self.refresh_records()
    def navigate(self,key):
        super().navigate(key)
        if key=='课程任务' and hasattr(self,'task_tree'):self.refresh_tasks(); self.refresh_records()
    def library(self):
        super().library()
        # Keep the existing PDF reader intact; the assistant captures a stable source/page snapshot.
        tools=ttk.Frame(self.pages['资料与笔记'])
        tools.pack(fill='x',before=self.library_split,pady=(0,8))
        self.button(tools,'阅读助手 / 保存摘录',self.open_reading_assistant)
        self.button(tools,'加入课程任务',self.task_from_document)
        self.button(tools,'摘录与术语库',lambda:(self.navigate('课程任务'),self.learning_tabs.select(1)))
    def build_tasks(self):
        p=self.pages['课程任务']
        ttk.Label(p,text='把资料、分工和截止日期放在一起',font=('Microsoft YaHei UI',17,'bold')).pack(anchor='w',pady=(0,12))
        self.learning_tabs=ttk.Notebook(p); self.learning_tabs.pack(fill='both',expand=True)
        tasks=ttk.Frame(self.learning_tabs,padding=12); records=ttk.Frame(self.learning_tabs,padding=12); terms=ttk.Frame(self.learning_tabs,padding=12)
        for page,title in [(tasks,'课程任务'),(records,'摘录与引用'),(terms,'课程术语')]:self.learning_tabs.add(page,text=title)
        row=ttk.Frame(tasks); row.pack(fill='x')
        for label,fn in [('＋ 新任务',self.task_dialog),('编辑 / 分工',self.edit_task),('从通知提取',self.notice_dialog),('跨课程日程',self.schedule_dialog),('导入小组资料包',self.import_group)]:self.button(row,label,fn)
        self.task_filter=tk.StringVar(value='未完成')
        box=ttk.Combobox(row,textvariable=self.task_filter,values=['未完成','全部','已完成'],state='readonly',width=9); box.pack(side='right'); box.bind('<<ComboboxSelected>>',lambda e:self.refresh_tasks())
        self.task_tree=ttk.Treeview(tasks,columns=('title','kind','due','state','owner'),show='headings',height=6,selectmode='browse')
        for key,label,width in [('title','任务',300),('kind','类型',100),('due','截止时间',165),('state','状态 / 提醒',140),('owner','负责人',120)]:
            self.task_tree.heading(key,text=label); self.task_tree.column(key,width=width,stretch=key=='title')
        self.task_tree.pack(fill='both',expand=True,pady=12); self.task_tree.bind('<<TreeviewSelect>>',lambda e:self.show_task()); self.task_tree.bind('<Double-1>',lambda e:self.safe(self.edit_task))
        self.task_tree.tag_configure('urgent',foreground='#b04b28')
        row=ttk.Frame(tasks); row.pack(fill='x')
        for label,fn in [('标记完成',self.complete_task),('打开关联资料',self.task_sources),('相关摘录 / 引用',self.task_records),('导出小组资料包',self.export_group),('AI 合稿检查',self.review_group)]:self.button(row,label,fn)
        self.task_detail=ScrolledText(tasks,height=7,wrap='word',font=('Microsoft YaHei UI',10),relief='flat',padx=12,pady=10,state='disabled'); self.task_detail.pack(fill='both',expand=True,pady=(12,4))
        ttk.Label(tasks,text='本机分工与进度需手动更新；资料包是一次快照，可通过群聊交换，不会实时同步。',style='Muted.TLabel').pack(anchor='w')
        self.record_task_filter=None
        row=ttk.Frame(records); row.pack(fill='x')
        self.record_scope=ttk.Label(row,text='当前课程全部摘录'); self.record_scope.pack(side='left')
        self.button(row,'显示全部',self.all_records); self.button(row,'编辑摘录',self.edit_record); self.button(row,'回到来源',self.record_source); self.button(row,'导出引用与摘录',self.export_references)
        self.record_tree=ttk.Treeview(records,columns=('quote','source','page'),show='headings',selectmode='browse')
        for key,label,width in [('quote','摘录原文',430),('source','来源',270),('page','PDF 页序',90)]:self.record_tree.heading(key,text=label); self.record_tree.column(key,width=width)
        self.record_tree.pack(fill='both',expand=True,pady=12); self.record_tree.bind('<Double-1>',lambda e:self.safe(self.edit_record))
        ttk.Label(records,text='原文、译文和个人批注分开保存；来源缺失字段显示“待补充”，PDF 页序不等于书内页码。',style='Muted.TLabel').pack(anchor='w')
        row=ttk.Frame(terms); row.pack(fill='x'); self.button(row,'编辑术语',lambda:self.edit_record('term')); self.button(row,'回到来源',lambda:self.record_source('term'))
        self.term_tree=ttk.Treeview(terms,columns=('quote','meaning','source'),show='headings',selectmode='browse')
        for key,label,width in [('quote','英文 / 专业术语',240),('meaning','中文含义 / 解释',450),('source','来源',240)]:self.term_tree.heading(key,text=label); self.term_tree.column(key,width=width)
        self.term_tree.pack(fill='both',expand=True,pady=12); self.term_tree.bind('<Double-1>',lambda e:self.safe(lambda:self.edit_record('term')))
        ttk.Label(terms,text='术语可在阅读助手中保存；翻译和解释时会参考本课程术语表。',style='Muted.TLabel').pack(anchor='w')
    def schedule_dialog(self):
        win=tk.Toplevel(self);win.title('跨课程日程 · 按截止时间排序');win.geometry('940x560');win.transient(self)
        f=ttk.Frame(win,padding=18);f.pack(fill='both',expand=True)
        ttk.Label(f,text='所有课程未完成任务 · 双击回到任务与资料',font=('Microsoft YaHei UI',14,'bold')).pack(anchor='w',pady=(0,12))
        tree=ttk.Treeview(f,columns=('course','title','due','state'),show='headings',selectmode='browse')
        for key,label,width in [('course','课程',140),('title','任务',340),('due','截止时间',165),('state','提醒',130)]:tree.heading(key,text=label);tree.column(key,width=width)
        tree.pack(fill='both',expand=True)
        tasks=[t for course in self.store.courses() for t in self.learning.tasks(course) if t['status']!='已完成'];tasks.sort(key=lambda t:t['due'] or '9999')
        mapping={t['id']:t for t in tasks}
        for t in tasks:tree.insert('','end',iid=t['id'],values=(t['course'],t['title'],t['due'] or '未设截止',due_label(t)))
        def open_task(event=None):
            if not tree.selection():return
            t=mapping[tree.selection()[0]];self.flush_edits();self.save_side_note();self.course.set(t['course']);self.refresh();self.task_filter.set('全部');self.navigate('课程任务');self.learning_tabs.select(0);self.task_tree.selection_set(t['id']);self.task_tree.see(t['id']);self.show_task();win.destroy()
        tree.bind('<Double-1>',open_task)
        row=ttk.Frame(f);row.pack(fill='x',pady=10);self.button(row,'打开任务',open_task)
        ttk.Label(row,text='软件关闭时不会推送提醒；重新打开后自动显示逾期与近期任务。',style='Muted.TLabel').pack(side='left')
    def refresh_tasks(self):
        old=self.task_tree.selection(); self.task_tree.delete(*self.task_tree.get_children())
        for t in self.learning.tasks(self.course.get()):
            if self.task_filter.get()=='未完成' and t['status']=='已完成':continue
            if self.task_filter.get()=='已完成' and t['status']!='已完成':continue
            label=due_label(t)
            self.task_tree.insert('','end',iid=t['id'],values=(t['title'],t['kind'],t['due'] or '未设置',t['status']+' · '+label,t['owner']),tags=('urgent',) if label in ('已逾期','今天截止') else ())
        if old and self.task_tree.exists(old[0]):self.task_tree.selection_set(old[0])
        self.show_task()
    def chosen_task(self):
        ids=self.task_tree.selection()
        if not ids:raise ValueError('请先选中一项课程任务')
        return next(t for t in self.learning.tasks(self.course.get()) if t['id']==ids[0])
    def show_task(self):
        try:
            t=self.chosen_task(); docs={d['id']:d for d in self.store.docs(self.course.get(),'all')}
            lines=[t['title'],f"预计 {t['hours']:g} 小时 · 负责人：{t['owner'] or '待分配'}",t['notes'],'','步骤 / 分工：']
            lines += [f"{i+1}. [{s['status']}] {s['title']} · {s['owner'] or '待分配'} · {s['due'] or '未设截止'}\n   {s['notes']}" for i,s in enumerate(t['steps'])]
            lines+=['','关联资料：']+[docs[i]['title'] for i in t['docs'] if i in docs]
            text='\n'.join(lines)
        except (ValueError,StopIteration):text='选择一个任务查看步骤、负责人和关联资料。'
        self.task_detail.config(state='normal'); self.put(self.task_detail,text); self.task_detail.config(state='disabled')
    def task_from_document(self):
        self.flush_edits(); d=self.selected_doc(); self.task_dialog(initial={'docs':[d['id']]})
    def edit_task(self):self.task_dialog(self.chosen_task())
    def task_dialog(self,initial=None):
        initial=initial or {}; course=self.course.get(); win=tk.Toplevel(self); win.title('课程任务 · 分工与资料'); win.geometry('850x740'); win.transient(self); win.grab_set()
        f=ttk.Frame(win,padding=18); f.pack(fill='both',expand=True)
        form=ttk.Frame(f); form.pack(fill='x'); form.columnconfigure(1,weight=1); form.columnconfigure(3,weight=1)
        fields={}
        specs=[('title','任务名称',''),('kind','任务类型','作业'),('due','截止 YYYY-MM-DD HH:MM',''),('status','状态','未开始'),('owner','负责人 / 组员',''),('hours','预计耗时（小时）','0')]
        for n,(key,label,default) in enumerate(specs):
            r=n//2;c=(n%2)*2;ttk.Label(form,text=label).grid(row=r,column=c,sticky='w',padx=6,pady=5)
            fields[key]=tk.StringVar(value=str(initial.get(key,default)))
            widget=ttk.Combobox(form,textvariable=fields[key],values=KINDS if key=='kind' else STATUSES,state='readonly') if key in ('kind','status') else ttk.Entry(form,textvariable=fields[key])
            widget.grid(row=r,column=c+1,sticky='ew',padx=6,pady=5)
        ttk.Label(f,text='任务说明 / 提交要求').pack(anchor='w',pady=(8,0))
        notes=ScrolledText(f,height=3,wrap='word'); notes.pack(fill='x'); notes.insert('1.0',initial.get('notes',''))
        tabs=ttk.Notebook(f); tabs.pack(fill='both',expand=True,pady=12)
        sp=ttk.Frame(tabs,padding=10); dp=ttk.Frame(tabs,padding=10); tabs.add(sp,text='步骤与小组分工'); tabs.add(dp,text='关联教材、笔记与提交材料')
        steps=[dict(s) for s in initial.get('steps',[])]
        tree=ttk.Treeview(sp,columns=('title','owner','due','status'),show='headings',height=5)
        for k,label,w in [('title','步骤 / 成果',230),('owner','负责人',110),('due','截止',150),('status','状态',90)]:tree.heading(k,text=label); tree.column(k,width=w)
        tree.pack(fill='both',expand=True)
        def redraw():
            tree.delete(*tree.get_children())
            for i,s in enumerate(steps):tree.insert('','end',iid=str(i),values=(s['title'],s['owner'],s['due'],s['status']))
        def step_dialog(edit=False):
            idx=int(tree.selection()[0]) if edit and tree.selection() else None
            if edit and idx is None:return
            d=steps[idx] if idx is not None else {}; sub=tk.Toplevel(win); sub.title('步骤 / 成员分工'); sub.geometry('500x490'); sub.transient(win); sub.grab_set(); sf=ttk.Frame(sub,padding=18); sf.pack(fill='both',expand=True); values={}
            for k,label in [('title','步骤名称'),('owner','负责人'),('due','截止 YYYY-MM-DD HH:MM'),('status','状态'),('notes','成果说明 / 文件名称')]:
                ttk.Label(sf,text=label).pack(anchor='w'); values[k]=tk.StringVar(value=d.get(k,'未开始' if k=='status' else ''))
                w=ttk.Combobox(sf,textvariable=values[k],values=STATUSES,state='readonly') if k=='status' else ttk.Entry(sf,textvariable=values[k]); w.pack(fill='x',pady=(2,9))
            def save_step():
                from learning import deadline
                data={k:v.get().strip() for k,v in values.items()}
                if not data['title']:raise ValueError('请填写步骤名称')
                data['due']=deadline(data['due'])
                if idx is None:steps.append(data)
                else:steps[idx]=data
                redraw(); sub.destroy(); win.grab_set()
            self.button(sf,'保存步骤',save_step)
            sub.protocol('WM_DELETE_WINDOW',lambda:(sub.destroy(),win.grab_set()))
        row=ttk.Frame(sp); row.pack(fill='x',pady=8)
        self.button(row,'＋ 添加步骤',step_dialog); self.button(row,'编辑分工',lambda:step_dialog(True))
        def remove_step():
            if tree.selection():steps.pop(int(tree.selection()[0])); redraw()
        self.button(row,'移除步骤',remove_step); redraw()
        ttk.Label(dp,text='按 Ctrl / Shift 多选。选中一份 PDF 后，可设置关联的 PDF 页序范围。',wraplength=730).pack(anchor='w')
        docs=self.store.docs(course,'all'); lb=tk.Listbox(dp,selectmode='extended',exportselection=False,height=6); lb.pack(fill='both',expand=True,pady=8)
        for i,d in enumerate(docs):
            lb.insert('end',f"[{d['kind']}] {d['title']}"+({'archived':'（归档）','trash':'（回收站）'}.get(d['status'],'')))
            if d['id'] in initial.get('docs',[]):lb.selection_set(i)
        pages={k:list(v) for k,v in initial.get('pages',{}).items()}
        page_row=ttk.Frame(dp);page_row.pack(fill='x');start=tk.StringVar();end=tk.StringVar()
        ttk.Label(page_row,text='PDF 起始页').pack(side='left');ttk.Entry(page_row,textvariable=start,width=5).pack(side='left',padx=5)
        ttk.Label(page_row,text='结束页').pack(side='left');ttk.Entry(page_row,textvariable=end,width=5).pack(side='left',padx=5)
        def load_range(event=None):
            chosen=lb.curselection()
            value=pages.get(str(docs[chosen[0]]['id']),['','']) if len(chosen)==1 else ['','']
            start.set(value[0]);end.set(value[1])
        def set_range():
            chosen=lb.curselection()
            if len(chosen)!=1:raise ValueError('设置页码时请只选中一份 PDF；设置后可继续多选其他关联资料')
            d=docs[chosen[0]];source=self.store.original(d)
            if not source or source.suffix.lower()!='.pdf':raise ValueError('仅 PDF 原文件支持页码范围')
            if not start.get().strip() and not end.get().strip():pages.pop(str(d['id']),None);return
            from source_range import extract_pdf_range
            import pypdfium2 as pdfium
            a,b=int(start.get()),int(end.get())
            with pdfium.PdfDocument(str(source)) as pdf:total=len(pdf)
            if not 1<=a<=b<=total:raise ValueError(f'页码应在 1–{total} 之间，结束页不能小于起始页')
            pages[str(d['id'])]=[a,b];range_hint.config(text=f'已关联 PDF 第 {a}–{b} 页')
        self.button(page_row,'应用页码',set_range)
        range_hint=ttk.Label(dp,text='不填页码表示关联整份资料；清空后应用可取消页码。',style='Muted.TLabel');range_hint.pack(anchor='w')
        lb.bind('<<ListboxSelect>>',load_range);load_range()
        row=ttk.Frame(f); row.pack(fill='x')
        ttk.Label(row,text='保存到课程：'+course,style='Muted.TLabel').pack(side='left')
        def save():
            data={k:v.get() for k,v in fields.items()}; data.update(notes=notes.get('1.0','end-1c'),steps=steps,docs=[docs[i]['id'] for i in lb.curselection()],pages={k:v for k,v in pages.items() if int(k) in [docs[i]['id'] for i in lb.curselection()]})
            id=self.learning.save_task(course,data,initial.get('id')); win.destroy(); self.refresh_tasks(); self.refresh_home()
            if self.task_tree.exists(id):self.task_tree.selection_set(id)
            self.status.set('课程任务已保存')
        ttk.Button(row,text='保存任务',style='Accent.TButton',command=lambda:self.safe(save)).pack(side='right')
    def complete_task(self):
        t=self.chosen_task(); t['status']='已完成'; self.learning.save_task(self.course.get(),t,t['id']); self.refresh_tasks(); self.refresh_home()
    def task_sources(self):
        t=self.chosen_task()
        if not t['docs']:raise ValueError('尚未关联资料，请点击“编辑 / 分工”添加')
        win=tk.Toplevel(self); win.title('关联资料'); win.geometry('650x350'); course=self.course.get()
        docs={d['id']:d for d in self.store.docs(course,'all')}; ids=[i for i in t['docs'] if i in docs]
        lb=tk.Listbox(win);lb.pack(fill='both',expand=True,padx=15,pady=15)
        for i in ids:lb.insert('end',docs[i]['title']+(f" · PDF 第 {t['pages'][str(i)][0]}–{t['pages'][str(i)][1]} 页" if str(i) in t.get('pages',{}) else '')+('（回收站）' if docs[i]['status']=='trash' else ''))
        def open_source():
            if lb.curselection():self.open_learning_source(course,ids[lb.curselection()[0]],t.get('pages',{}).get(str(ids[lb.curselection()[0]]),[None])[0]); win.destroy()
        self.button(win,'打开所选资料',open_source)
    def task_records(self):
        t=self.chosen_task(); self.record_task_filter=t['id']; self.record_scope.config(text='任务：'+t['title'][:28]); self.refresh_records(); self.learning_tabs.select(1)
    def all_records(self):
        self.record_task_filter=None; self.record_scope.config(text='当前课程全部摘录'); self.refresh_records()
    def refresh_records(self):
        if not hasattr(self,'record_tree'):return
        if self.record_task_filter and not any(t['id']==self.record_task_filter for t in self.learning.tasks(self.course.get())):self.record_task_filter=None; self.record_scope.config(text='当前课程全部摘录')
        for kind,tree in [('excerpt',self.record_tree),('term',self.term_tree)]:
            old=tree.selection(); tree.delete(*tree.get_children())
            for r in self.learning.records(self.course.get(),kind,self.record_task_filter if kind=='excerpt' else None):
                values=(r['quote'].replace('\n',' ')[:160],r.get('source_title',''),r.get('page') or '—') if kind=='excerpt' else (r['quote'],r.get('translation',''),r.get('source_title',''))
                tree.insert('','end',iid=r['id'],values=values)
            if old and tree.exists(old[0]):tree.selection_set(old[0])
    def chosen_record(self,kind='excerpt'):
        tree=self.term_tree if kind=='term' else self.record_tree
        if not tree.selection():raise ValueError('请先选中一条记录')
        return next(r for r in self.learning.records(self.course.get(),kind) if r['id']==tree.selection()[0])
    def edit_record(self,kind='excerpt'):
        r=self.chosen_record(kind); self.record_dialog(r,kind,r['id'])
    def record_source(self,kind='excerpt'):
        r=self.chosen_record(kind)
        if not r.get('doc_id'):raise ValueError('此记录没有关联本机来源文件')
        self.open_learning_source(r['course'],r['doc_id'],r.get('page'))
    def open_learning_source(self,course,id,page):
        self.flush_edits(); self.save_side_note()
        if course!=self.course.get():self.course.set(course); self.refresh()
        self.open_doc(id)
        if page and self.reader.pdf:self.reader.index=max(0,min(page-1,len(self.reader.pdf)-1)); self.reader.render()
    def export_references(self):
        if not self.learning.records(self.course.get(),'excerpt',self.record_task_filter):raise ValueError('当前范围没有摘录')
        self.export_dialog('摘录与参考来源',self.learning.bibliography(self.course.get(),self.record_task_filter))
    def export_group(self):
        t=self.chosen_task(); course=self.course.get()
        path=filedialog.asksaveasfilename(parent=self,title='导出任务、分工、关联资料原文件及摘录',defaultextension='.zip',initialfile='小组资料包.zip',filetypes=[('StudyDesk 资料包','*.zip')])
        if path:self.run('导出小组资料包',lambda:self.learning.export_package(course,t['id'],path),lambda _:self.status.set('资料包已导出，可通过群聊发送；这是快照，不会实时同步'))
    def import_group(self):
        path=filedialog.askopenfilename(parent=self,title='导入资料包为当前课程副本',filetypes=[('StudyDesk 资料包','*.zip')]); course=self.course.get()
        if path:
            def done(id):self.refresh(); self.status.set('资料包已导入为独立副本，原有任务未覆盖')
            self.run('导入小组资料包',lambda:self.learning.import_package(course,path),done)
    def review_group(self):
        t=self.chosen_task(); docs=[d for d in self.store.docs(self.course.get()) if d['id'] in t['docs']]
        if not docs:raise ValueError('请先关联需要检查的笔记或成果材料')
        text='任务：'+t['title']+'\n'+t['notes']+'\n\n'+'\n\n'.join(f"[资料 {d['id']} · {d['title']}]\n{d['body']}" for d in docs)
        if len(text)>16000:raise ValueError('合稿检查最多 16000 字，请关联整理后的成果笔记，减少完整教材')
        settings=self.values(); key=self.key.get(); course=self.course.get()
        def done(result):
            id=self.store.add(course,'笔记',t['title']+' · 合稿检查',result); self.last_result=(course,id); self.result_button.pack(side='right'); self.refresh(); self.status.set('检查建议已保存为新笔记，原稿未修改')
        self.run('检查小组材料',lambda:reading_ai(settings,key,'review',text),done)
    def notice_dialog(self):
        win=tk.Toplevel(self); win.title('粘贴课程通知'); win.geometry('620x430'); win.transient(self)
        ttk.Label(win,text='粘贴老师通知。AI 提取后进入任务编辑页，请核对日期再保存。',wraplength=560).pack(padx=20,pady=15)
        text=ScrolledText(win,wrap='word');text.pack(fill='both',expand=True,padx=20)
        def extract():
            body=text.get('1.0','end-1c'); settings=self.values(); key=self.key.get(); course=self.course.get()
            def done(result):
                raw=result.strip()
                if raw.startswith('```'):raw='\n'.join(raw.splitlines()[1:-1])
                try:data=json.loads(raw)
                except ValueError:raise ValueError('AI 未返回有效任务信息，请手动新建任务') from None
                if not isinstance(data,dict):raise ValueError('AI 返回的任务信息无效')
                if data.get('kind') not in KINDS:data['kind']='其他'
                data['notes']=body
                self.flush_edits();self.save_side_note(); self.course.set(course); self.refresh()
                if win.winfo_exists():win.destroy()
                self.task_dialog(data)
            self.run('提取通知',lambda:reading_ai(settings,key,'notice',body),done)
        row=ttk.Frame(win,padding=15);row.pack(fill='x');self.button(row,'提取后核对',extract)
    def reading_snapshot(self):
        self.flush_edits(); d=self.selected_doc(); page=None
        if self.reader.pdf and self.store.original(d) and self.document_tabs.select()==str(self.reader):
            page=self.reader.index+1; p=self.reader.pdf[self.reader.index]
            try:
                tp=p.get_textpage()
                try:text=tp.get_text_range()
                finally:tp.close()
            finally:p.close()
        else:
            try:text=self.editor.get('sel.first','sel.last')
            except tk.TclError:text=self.get(self.editor)
        return dict(course=self.course.get(),doc_id=d['id'],source_title=d['title'],page=page,quote=text,translation='',notes='')
    def open_reading_assistant(self):
        snapshot=self.reading_snapshot(); win=tk.Toplevel(self);win.title('阅读助手 · '+snapshot['source_title'][:50]);win.geometry('960x720'); win.transient(self)
        frame=ttk.Frame(win,padding=18);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text=f"{snapshot['source_title'][:85]}\nPDF 页序：{snapshot['page'] or '不适用'} · 来源固定在打开时的资料和页面",wraplength=900).pack(anchor='w')
        ttk.Label(frame,text='PDF 使用当前页文字；可在左侧删减成需要的段落。扫描页需先 OCR 或粘贴原文。',style='Muted.TLabel').pack(anchor='w',pady=8)
        split=ttk.Panedwindow(frame,orient='horizontal');split.pack(fill='both',expand=True)
        left=ttk.Frame(split);right=ttk.Frame(split);split.add(left,weight=1);split.add(right,weight=1)
        ttk.Label(left,text='原文（可选中其中一段处理）').pack(anchor='w'); original=ScrolledText(left,wrap='word',width=40,exportselection=False);original.pack(fill='both',expand=True,padx=(0,10));original.insert('1.0',snapshot['quote'])
        ttk.Label(right,text='译文 / AI 解释（可修订）').pack(anchor='w'); result=ScrolledText(right,wrap='word',width=40);result.pack(fill='both',expand=True)
        state={'busy':False,'processed':None}; hint=ttk.Label(frame,text='选择翻译或解释，结果可以连同原文保存为摘录。',style='Muted.TLabel');hint.pack(anchor='w',pady=10)
        def selection():
            try:return original.get('sel.first','sel.last').strip()
            except tk.TclError:return original.get('1.0','end-1c').strip()
        def process(mode):
            text=selection(); settings=self.values();key=self.key.get()
            terms='\n'.join(r['quote']+' = '+r.get('translation','') for r in self.learning.records(snapshot['course'],'term'))
            if len(terms)>6000:raise ValueError('课程术语表过长，请精简术语内容后重试')
            def done(output):
                state['busy']=False; state['processed']=text
                if win.winfo_exists():self.put(result,output);hint.config(text='已完成。保存时将使用本次实际处理的原文，译文和原文分别存储。')
            self.run('翻译教材' if mode=='translate' else '解释教材',lambda:reading_ai(settings,key,mode,text,terms),done)
            state['busy']=True
        def save(kind):
            data=dict(snapshot);data['quote']=state['processed'] if state['processed'] is not None else selection();data['translation']=result.get('1.0','end-1c')
            self.record_dialog(data,kind)
        row=ttk.Frame(frame);row.pack(fill='x')
        for label,fn in [('翻译成中文',lambda:process('translate')),('解释概念与公式',lambda:process('explain')),('保存摘录与来源',lambda:save('excerpt')),('保存为术语',lambda:save('term'))]:self.button(row,label,fn)
        def close():
            if state['busy'] and self.busy:messagebox.showinfo('正在处理','请等待本次 AI 处理结束后关闭阅读助手。',parent=win);return
            win.destroy()
        win.protocol('WM_DELETE_WINDOW',close)
    def record_dialog(self,data,kind='excerpt',id=None):
        course=data.get('course',self.course.get()); win=tk.Toplevel(self);win.title('保存术语' if kind=='term' else '摘录与引用');win.geometry('820x740');win.transient(self);win.grab_set()
        f=ttk.Frame(win,padding=18);f.pack(fill='both',expand=True)
        ttk.Label(f,text=data.get('source_title','来源待补充')+f" · PDF 页序 {data.get('page') or '不适用'}",wraplength=760).pack(anchor='w')
        fields={}
        for key,label,height in [('quote','术语 / 原文' if kind=='term' else '摘录原文',4),('translation','中文含义 / 译文 / AI 解释（与原文分开）',3),('notes','个人批注',2)]:
            ttk.Label(f,text=label).pack(anchor='w',pady=(8,3)); w=ScrolledText(f,height=height,wrap='word');w.pack(fill='both',expand=True);w.insert('1.0',data.get(key,''));fields[key]=w
        meta=self.learning.metadata(data.get('doc_id')) if data.get('doc_id') else data.get('metadata',{})
        row=ttk.Frame(f);row.pack(fill='x',pady=8);row.columnconfigure(1,weight=1);row.columnconfigure(3,weight=1);mf={}
        for n,(key,label) in enumerate([('title','文献标题'),('author','作者'),('year','年份'),('publisher','出版社 / 来源'),('url','链接 / DOI'),('printed_page','书内印刷页码')]):
            r=n//2;c=n%2*2;ttk.Label(row,text=label).grid(row=r,column=c,sticky='w',padx=4,pady=3)
            value=data.get(key,'') if key=='printed_page' else meta.get(key,data.get('source_title','') if key=='title' else '')
            mf[key]=tk.StringVar(value=value);ttk.Entry(row,textvariable=mf[key]).grid(row=r,column=c+1,sticky='ew',padx=4,pady=3)
        tasks={'不关联任务':None};tasks.update({t['title']+' · '+t['id'][:6]:t['id'] for t in self.learning.tasks(course)})
        selected=tk.StringVar(value=next((label for label,tid in tasks.items() if tid==data.get('task_id')),'不关联任务'))
        row=ttk.Frame(f);row.pack(fill='x',pady=8);ttk.Label(row,text='关联作业').pack(side='left');ttk.Combobox(row,textvariable=selected,values=list(tasks),state='readonly',width=45).pack(side='left',padx=8)
        ttk.Label(f,text='缺失文献信息可留空，导出时标为待补充。保存后可在课程任务 → 摘录与引用 / 课程术语中查看。',style='Muted.TLabel',wraplength=760).pack(anchor='w')
        def save():
            record={k:v for k,v in data.items() if k not in ('id','kind','course')};record.update({k:w.get('1.0','end-1c').strip() for k,w in fields.items()});record['task_id']=tasks[selected.get()];record['printed_page']=mf['printed_page'].get().strip()
            metadata={k:v.get().strip() for k,v in mf.items() if k!='printed_page'};record['metadata']=metadata
            self.learning.save_record(course,kind,record,id)
            if record.get('doc_id'):self.learning.save_metadata(record['doc_id'],metadata)
            win.destroy();self.refresh_records();self.status.set('术语已保存' if kind=='term' else '摘录、来源和批注已保存')
        row=ttk.Frame(f);row.pack(fill='x',pady=(12,0));self.button(row,'保存记录',save)
