"""User-facing workspace shell and context-preserving learning flows."""
import html
import json
import re
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from core import retrieve
from pdf_reader import PDFReader

class WorkspaceUX:
    def button(self,parent,text,command):
        button=super().button(parent,text,command); button.configure(width=0); return button
    def destroy(self):
        for callback in self.tk.call('after','info'):
            try:self.after_cancel(callback)
            except tk.TclError:pass
        super().destroy()
    def build_shell(self):
        self.loading_editor=False; self.editor_course=None; self.editor_baseline=('', ''); self.autosave_job=None
        self.side_context=None; self.side_baseline=''; self.side_visible=False; self.side_job=None; self.exam_source_id=None
        style=ttk.Style(self)
        style.configure('.',font=('Microsoft YaHei UI',10),background='#f5f7fb',foreground='#24324b')
        style.configure('TFrame',background='#f5f7fb'); style.configure('TLabel',background='#f5f7fb')
        style.configure('Muted.TLabel',foreground='#748097',font=('Microsoft YaHei UI',9))
        style.configure('Heading.TLabel',font=('Microsoft YaHei UI',22,'bold'),foreground='#172b4d')
        style.configure('TButton',padding=(12,8),background='#ffffff',borderwidth=1,relief='flat')
        style.map('TButton',background=[('active','#e9eefc')],foreground=[('disabled','#a3acba')])
        style.configure('Accent.TButton',background='#4968df',foreground='white',borderwidth=0)
        style.map('Accent.TButton',background=[('active','#3755c4'),('disabled','#c1cae8')],foreground=[('disabled','#f6f7fb')])
        style.configure('TEntry',padding=7,fieldbackground='white',bordercolor='#dfe5ef')
        style.configure('TCombobox',padding=6,fieldbackground='white',background='white',arrowsize=14)
        style.configure('Treeview',rowheight=43,borderwidth=0,background='white',fieldbackground='white',foreground='#31415c')
        style.configure('Treeview.Heading',background='#eef2f8',relief='flat',padding=8)
        style.map('Treeview',background=[('selected','#e7edff')],foreground=[('selected','#3457cd')])
        style.configure('TNotebook',borderwidth=0,background='#f5f7fb')
        style.configure('TNotebook.Tab',padding=(15,8),background='#edf1f8',borderwidth=0)
        style.map('TNotebook.Tab',background=[('selected','white')],foreground=[('selected','#4968df')])
        style.layout('Shell.TNotebook.Tab',[])
        style.configure('Shell.TNotebook',tabmargins=0,borderwidth=0)
        self.sidebar=tk.Frame(self,bg='#172640',width=180); self.sidebar.pack(side='left',fill='y'); self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar,text='知课',bg='#172640',fg='white',font=('Microsoft YaHei UI',25,'bold')).pack(anchor='w',padx=24,pady=(28,0))
        tk.Label(self.sidebar,text='S T U D Y D E S K',bg='#172640',fg='#94a5c4',font=('Segoe UI',9)).pack(anchor='w',padx=24,pady=(3,30))
        self.nav={}
        labels=[('学习概览','概览'),('资料与笔记','资料与笔记'),('课程任务','课程任务'),('课堂录音','课堂整理'),('记忆与复习','记忆与复习'),('AI 自定义组卷','练习与出卷'),('资料检索','发现资料'),('Kimi 与设置','设置')]
        for key,label in labels:
            b=tk.Button(self.sidebar,text='  '+label,anchor='w',font=('Microsoft YaHei UI',11),bg='#172640',fg='#b6c3d9',activebackground='#2a3e61',activeforeground='white',relief='flat',bd=0,padx=16,pady=13,cursor='hand2',command=lambda k=key:self.navigate(k))
            b.pack(fill='x',padx=12,pady=3); self.nav[key]=b
        tk.Label(self.sidebar,text='本地保存 · 专注学习',bg='#172640',fg='#8597b6',font=('Microsoft YaHei UI',9)).pack(side='bottom',pady=22)
        main=ttk.Frame(self); main.pack(side='left',fill='both',expand=True)
        top=ttk.Frame(main,padding=(24,18)); top.pack(fill='x')
        self.page_title=ttk.Label(top,text='学习概览',font=('Microsoft YaHei UI',16,'bold')); self.page_title.pack(side='left')
        ttk.Button(top,text='＋ 新课程',command=lambda:self.safe(self.new_course)).pack(side='right')
        self.course_box=ttk.Combobox(top,textvariable=self.course,values=self.store.courses(),state='readonly',width=18)
        self.course_box.pack(side='right',padx=(12,10)); self.course_box.bind('<<ComboboxSelected>>',lambda e:self.safe(self.refresh))
        ttk.Label(top,text='当前课程',style='Muted.TLabel').pack(side='right')
        self.status_bar=ttk.Frame(main,padding=(24,10)); self.status_bar.pack(side='bottom',fill='x')
        self.result_button=ttk.Button(self.status_bar,text='查看生成结果 →',command=lambda:self.safe(self.open_result))
        self.tabs=ttk.Notebook(main,style='Shell.TNotebook'); self.tabs.pack(fill='both',expand=True,padx=6)
        self.bind('<Control-s>',lambda e:self.safe(self.save_current))
        self.bind('<Control-e>',lambda e:self.safe(self.export_visible))
        self.bind('<Control-n>',lambda e:self.safe(self.new_note))
        self.bind('<Control-f>',lambda e:self.focus_search())
    def navigate(self,key):
        self.flush_edits(); self.save_side_note()
        self.tabs.select(self.pages[key]); self.page_title.config(text=dict([('AI 自定义组卷','练习与出卷'),('课堂录音','课堂整理'),('Kimi 与设置','设置')]).get(key,key))
        for name,button in self.nav.items():button.config(bg='#30466c' if name==key else '#172640',fg='white' if name==key else '#b6c3d9')
        if key=='学习概览':self.refresh_home()
        if key=='记忆与复习':self.review.refresh()
    def build_home(self):
        p=self.pages['学习概览']
        ttk.Label(p,text='让每一次学习，都有所积累。',style='Heading.TLabel').pack(anchor='w',pady=(16,8))
        ttk.Label(p,text='从上次的阅读继续，或用几分钟回顾已经学过的知识。',style='Muted.TLabel').pack(anchor='w',pady=(0,26))
        stats=ttk.Frame(p); stats.pack(fill='x'); self.stat_labels={}
        for label in ['课程资料','学习笔记','待复习卡片']:
            card=tk.Frame(stats,bg='white',padx=24,pady=20); card.pack(side='left',fill='x',expand=True,padx=(0,14))
            tk.Label(card,text=label,bg='white',fg='#78849a',font=('Microsoft YaHei UI',10)).pack(anchor='w')
            value=tk.Label(card,text='0',bg='white',fg='#314fbe',font=('Segoe UI',30,'bold')); value.pack(anchor='w',pady=(5,0)); self.stat_labels[label]=value
        actions=ttk.Frame(p); actions.pack(fill='x',pady=24)
        self.button(actions,'继续阅读',self.continue_reading).configure(style='Accent.TButton')
        self.button(actions,'开始复习',lambda:self.navigate('记忆与复习'))
        self.button(actions,'写一条笔记',self.new_note)
        self.button(actions,'导入学习资料',lambda:(self.navigate('资料与笔记'),self.import_files()))
        ttk.Label(p,text='最近的学习资料',font=('Microsoft YaHei UI',13,'bold')).pack(anchor='w',pady=(8,10))
        self.recent=ttk.Treeview(p,columns=('kind','title'),show='headings',height=6); self.recent.heading('kind',text='类型'); self.recent.heading('title',text='标题 · 双击打开'); self.recent.column('kind',width=100,stretch=False); self.recent.pack(fill='both',expand=True)
        self.recent.bind('<Double-1>',lambda e:self.open_recent())
        ttk.Label(p,text='阅读资料 → 记录理解 → 制作卡片 → 练习检验',style='Muted.TLabel').pack(anchor='w',pady=20)
        self.navigate('学习概览')
    def refresh_home(self):
        if not hasattr(self,'recent'):return
        docs=self.store.docs(self.course.get())
        for name,count in [('课程资料',len(docs)),('学习笔记',sum(d['kind']=='笔记' for d in docs)),('待复习卡片',len(self.review.store.due(self.course.get())))]:self.stat_labels[name].config(text=str(count))
        self.recent.delete(*self.recent.get_children())
        for d in docs[:8]:self.recent.insert('','end',iid=str(d['id']),values=(d['kind'],d['title']))
    def continue_reading(self):
        docs=self.store.docs(self.course.get()); last=self.store.last_reading(self.course.get())
        doc=next((d for d in docs if d['id']==last),None) or next((d for d in docs if d.get('source_path','').endswith('.pdf')),None)
        if doc:self.open_doc(doc['id'])
        else:self.navigate('资料与笔记')
    def open_recent(self):
        if self.recent.selection():self.open_doc(int(self.recent.selection()[0]))
    def library(self):
        p=self.pages['资料与笔记']; self.library_split=ttk.Panedwindow(p,orient='horizontal'); self.library_split.pack(fill='both',expand=True)
        left=ttk.Frame(self.library_split,width=300,padding=(0,0,14,0)); self.library_list=left; self.library_split.add(left,weight=0)
        row=ttk.Frame(left); row.pack(fill='x',pady=(0,10)); self.button(row,'＋ 导入',self.import_files).configure(style='Accent.TButton'); self.button(row,'写笔记',self.new_note)
        self.kind=tk.StringVar(value='教材'); ttk.Combobox(left,textvariable=self.kind,values=['教材','参考卷','笔记','资料'],state='readonly',width=13).pack(fill='x')
        ttk.Label(left,text='上方类型用于新导入的文件',style='Muted.TLabel').pack(anchor='w',pady=(3,12))
        self.library_state=tk.StringVar(value='使用中')
        states=ttk.Frame(left); states.pack(fill='x',pady=(0,10))
        for label in ('使用中','归档','回收站'):
            ttk.Radiobutton(states,text=label,value=label,variable=self.library_state,command=self.change_library_state).pack(side='left',expand=True)
        self.filter_query=tk.StringVar(); self.search_entry=ttk.Entry(left,textvariable=self.filter_query); self.search_entry.pack(fill='x')
        ttk.Label(left,text='搜索标题或正文  Ctrl+F',style='Muted.TLabel').pack(anchor='w',pady=(3,8))
        self.filter_kind=tk.StringVar(value='全部'); ttk.Combobox(left,textvariable=self.filter_kind,values=['全部','教材','笔记','参考卷','试卷','课堂转写','课堂分析','资料'],state='readonly').pack(fill='x',pady=(0,10))
        self.filter_query.trace_add('write',lambda *args:self.render_tree()); self.filter_kind.trace_add('write',lambda *args:self.render_tree())
        tree_frame=ttk.Frame(left); tree_frame.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(tree_frame,columns=('kind',),show='tree',selectmode='extended',height=5)
        self.tree.column('#0',width=270); self.tree.column('kind',width=0,stretch=False)
        scroll=ttk.Scrollbar(tree_frame,orient='vertical',command=self.tree.yview)
        scroll.pack(side='right',fill='y'); self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left',fill='both',expand=True); self.tree.bind('<<TreeviewSelect>>',self.select_doc)
        self.tree.bind('<Delete>',lambda e:(self.safe(self.delete_doc),'break')[-1])
        row=ttk.Frame(left); row.pack(fill='x',pady=(8,0))
        self.archive_button=self.button(row,'归档',lambda:self.manage_docs('archive'))
        self.restore_button=self.button(row,'恢复',lambda:self.manage_docs('restore'))
        self.delete_button=self.button(row,'删除',self.delete_doc)
        self.list_count=ttk.Label(left,text='',style='Muted.TLabel'); self.list_count.pack(anchor='w',pady=(7,2))
        ttk.Label(left,text='Ctrl / Shift 多选 · 删除可在回收站恢复',style='Muted.TLabel').pack(anchor='w')
        right=ttk.Frame(self.library_split); self.library_split.add(right,weight=1)
        row=ttk.Frame(right); row.pack(fill='x')
        self.title_var=tk.StringVar(); self.title_entry=ttk.Entry(row,textvariable=self.title_var,font=('Microsoft YaHei UI',13,'bold')); self.title_entry.pack(side='left',fill='x',expand=True)
        self.title_entry.bind('<KeyRelease>',lambda e:self.schedule_save())
        more=ttk.Menubutton(row,text='更多 ···'); more.pack(side='right',padx=(8,0)); menu=tk.Menu(more,tearoff=False); more['menu']=menu
        for text,command in [('用系统阅读器打开',self.open_original),('补关联原文件',self.attach_original),('回到笔记来源',self.return_source),('删除当前资料',self.delete_doc)]:menu.add_command(label=text,command=lambda fn=command:self.safe(fn))
        actions=ttk.Frame(right); actions.pack(fill='x',pady=10)
        self.button(actions,'阅读笔记',self.toggle_side_notes).configure(style='Accent.TButton')
        self.button(actions,'制卡',self.to_cards); self.button(actions,'出题',self.to_exam); self.button(actions,'AI 梳理',self.summarize); self.button(actions,'导出',self.export_current)
        self.save_label=ttk.Label(right,text='选择左侧资料，或新建一条笔记',style='Muted.TLabel'); self.save_label.pack(anchor='w',pady=(0,6))
        self.document_tabs=ttk.Notebook(right); self.document_tabs.pack(fill='both',expand=True)
        self.reader=PDFReader(self.document_tabs,on_page=self.remember_page); self.text_page=ttk.Frame(self.document_tabs)
        self.document_tabs.add(self.reader,text='原版阅读'); self.document_tabs.add(self.text_page,text='笔记 / 文字')
        self.editor=self.text(self.text_page); self.editor.configure(spacing1=3,spacing3=6,selectbackground='#dbe5ff',selectforeground='#24324b')
        self.editor.bind('<<Modified>>',self.editor_changed)
        self.document_tabs.select(self.text_page)
        self.document_tabs.bind('<<NotebookTabChanged>>',self.refresh_pdf_tab)
        self.side_panel=ttk.Frame(self.library_split,width=285,padding=(14,0,0,0))
        head=ttk.Frame(self.side_panel); head.pack(fill='x'); ttk.Label(head,text='页边笔记',font=('Microsoft YaHei UI',13,'bold')).pack(side='left'); ttk.Button(head,text='收起',width=5,command=self.toggle_side_notes).pack(side='right')
        self.side_caption=ttk.Label(self.side_panel,text='与教材页面一起保存',style='Muted.TLabel',wraplength=230); self.side_caption.pack(anchor='w',pady=10)
        footer=ttk.Frame(self.side_panel); footer.pack(side='bottom',fill='x',pady=8)
        self.button(footer,'导出笔记',self.export_side); self.button(footer,'做成卡片',self.side_to_card)
        self.side_editor=self.text(self.side_panel); self.side_editor.configure(width=24,spacing3=6)
        self.side_editor.bind('<<Modified>>',self.side_changed)
    def view_docs(self):
        return self.store.docs(self.course.get(),{'使用中':'active','归档':'archived','回收站':'trash'}[self.library_state.get()])
    def clear_document(self):
        self.selected=None; self.editor_baseline=('', ''); self.title_var.set(''); self.put(self.editor,'')
        self.side_context=None; self.side_baseline=''; self.put(self.side_editor,'')
        self.reader.clear(); self.document_tabs.select(self.text_page); self.load_side_note()
    def change_library_state(self):
        self.flush_edits(); self.save_side_note(); self.clear_document(); self.refresh()
    def manage_docs(self,action):
        ids=[int(i) for i in self.tree.selection() if i.isdigit()]
        if not ids:raise ValueError('请先选中要操作的资料；按 Ctrl 或 Shift 可以多选。')
        self.flush_edits(); self.save_side_note()
        count=self.store.move_docs(self.course.get(),ids,action)
        if self.selected in ids:self.clear_document()
        self.refresh()
        self.status.set({'archive':f'已归档 {count} 份资料，可在归档区恢复',
                         'trash':f'已将 {count} 份资料移入回收站，原文件和关联笔记保留',
                         'restore':f'已恢复 {count} 份资料到删除或归档前的位置'}[action])
    def delete_doc(self):
        self.manage_docs('trash')
    def render_tree(self):
        if not hasattr(self,'tree'):return
        previous=self.tree.selection(); focus=self.tree.focus()
        q=self.filter_query.get().strip().lower(); kind=self.filter_kind.get()
        opened={i:self.tree.item(i,'open') for i in self.tree.get_children()}
        self.tree.delete(*self.tree.get_children())
        groups={'教材':[], '学习笔记':[], '课堂记录':[], '试卷':[], '其他资料':[]}
        for d in getattr(self,'docs',[]):
            if (kind!='全部' and kind!=d['kind']) or (q and q not in (d['title']+' '+d['body']).lower()):continue
            group={'教材':'教材','笔记':'学习笔记','课堂转写':'课堂记录','课堂分析':'课堂记录','试卷':'试卷','参考卷':'试卷'}.get(d['kind'],'其他资料')
            groups[group].append(d)
        count=0
        for group,docs in groups.items():
            if not docs:continue
            parent='group:'+group
            self.tree.insert('','end',iid=parent,text=f'{group}  ({len(docs)})',open=opened.get(parent,True),tags=('group',))
            for d in docs:self.tree.insert(parent,'end',iid=str(d['id']),text=d['title'],values=(d['kind'],))
            count+=len(docs)
        self.tree.tag_configure('group',foreground='#304f9c',font=('Microsoft YaHei UI',10,'bold'))
        keep=[i for i in previous if self.tree.exists(i)]
        if not keep and self.selected and self.tree.exists(str(self.selected)):keep=[str(self.selected)]
        self.tree.selection_set(keep)
        if focus and self.tree.exists(focus):self.tree.focus(focus)
        if hasattr(self,'list_count'):
            self.list_count.config(text=f'{self.library_state.get()} · {count} 份资料')
            self.archive_button.config(state='normal' if self.library_state.get()=='使用中' else 'disabled')
            self.restore_button.config(state='disabled' if self.library_state.get()=='使用中' else 'normal')
            self.delete_button.config(state='disabled' if self.library_state.get()=='回收站' else 'normal')
    def refresh(self):
        self.flush_edits(); self.save_side_note()
        changed=getattr(self,'current_course',None)!=self.course.get()
        self.current_course=self.course.get(); self.docs=self.view_docs()
        if changed or (self.selected and not any(d['id']==self.selected for d in self.docs)):self.clear_document()
        self.books={f'{d["id"]} · {d["title"]}':d for d in self.store.docs(self.course.get()) if d['kind']=='教材'}
        self.book_box['values']=list(self.books)
        if self.book.get() not in self.books:self.book.set(next(iter(self.books),''))
        self.editor_course=self.course.get(); self.editor_baseline=(self.title_var.get(),self.get(self.editor))
        if changed:
            self.exam_source_id=None
            if hasattr(self,'exam_context'):self.exam_context.config(text='出题依据：当前课程的教材与笔记')
        if hasattr(self,'review'):self.review.refresh()
        self.render_tree(); self.refresh_home()
    def select_doc(self,event=None):
        selection=tuple(i for i in self.tree.selection() if i.isdigit())
        if not selection:return
        target=self.tree.focus() if self.tree.focus() in selection else selection[0]
        if int(target)==self.selected:return
        self.flush_edits(); self.save_side_note()
        if self.tree.exists(target):self.tree.selection_set(target)
        super().select_doc(event)
        self.tree.selection_set([i for i in selection if self.tree.exists(i)])
        self.editor_course=self.course.get(); self.editor_baseline=(self.title_var.get(),self.get(self.editor))
        self.save_label.config(text='已保存到本机 · 编辑后自动保存 · Ctrl+S 保存 · Ctrl+E 导出')
        self.load_side_note()
        doc=self.selected_doc()
        if not self.store.original(doc) and doc['kind'] in ('笔记','试卷','课堂分析','课堂转写'):
            self.safe(self.show_note_pdf)
    def show_note_pdf(self):
        from note_pdf import build_note_pdf
        self.flush_edits(); doc=self.selected_doc()
        if self.store.original(doc):return
        path=build_note_pdf(self.title_var.get(),self.get(self.editor),Path(self.store.path).parent/'note_previews')
        self.generated_pdf_path=path
        self.document_tabs.tab(self.reader,text='PDF 阅读')
        self.document_tabs.select(self.reader)
        if self.reader.path!=path:self.reader.load(path,doc.get('read_page',0))
        self.save_label.config(text='已排版为 PDF · 修改请切换「笔记 / 文字」· 导出可选择 PDF')
    def refresh_pdf_tab(self,event=None):
        if self.document_tabs.select()!=str(self.reader) or not self.selected:return
        doc=next((d for d in self.docs if d['id']==self.selected),None)
        if doc and not self.store.original(doc):self.safe(self.show_note_pdf)
    def open_doc(self,id):
        self.flush_edits(); self.save_side_note(); self.navigate('资料与笔记')
        doc=next((d for d in self.store.docs(self.course.get(),'all') if d['id']==id),None)
        if not doc:return
        state={'active':'使用中','archived':'归档','trash':'回收站'}[doc['status']]
        if self.library_state.get()!=state:self.library_state.set(state); self.change_library_state()
        self.filter_query.set(''); self.filter_kind.set('全部'); self.docs=self.view_docs(); self.render_tree()
        if self.tree.exists(str(id)):
            self.tree.selection_set(str(id)); self.tree.see(str(id)); self.select_doc()
    def put(self,widget,text):
        super().put(widget,text)
        widget.edit_modified(False)
    def editor_changed(self,event=None):
        if self.editor.edit_modified():self.editor.edit_modified(False); self.schedule_save()
    def schedule_save(self):
        if self.autosave_job:self.after_cancel(self.autosave_job)
        self.save_label.config(text='正在编辑… 停顿后自动保存')
        self.autosave_job=self.after(900,lambda:self.safe(self.flush_edits))
    def flush_edits(self):
        if not hasattr(self,'editor') or self.editor_course is None:return
        if self.autosave_job:self.after_cancel(self.autosave_job); self.autosave_job=None
        title=self.title_var.get().strip(); body=self.get(self.editor)
        if (title,body)==self.editor_baseline:return
        # Empty drafts remain in the editor; never silently clear a stored document.
        if not body:self.save_label.config(text='空白内容未覆盖原记录'); return
        title=title or '未命名笔记'; self.title_var.set(title)
        if self.selected:self.store.update(self.selected,title,body)
        else:self.selected=self.store.add(self.editor_course,'笔记',title,body)
        self.editor_baseline=(title,body); self.docs=self.view_docs(); self.render_tree(); self.save_label.config(text='已自动保存到本机'); self.refresh_home()
    def save_note(self):self.flush_edits(); self.status.set('笔记已保存到本机')
    def save_current(self):self.flush_edits(); self.save_side_note(); self.status.set('当前编辑已保存')
    def new_note(self):
        self.flush_edits(); self.save_side_note(); self.navigate('资料与笔记')
        self.library_state.set('使用中'); self.change_library_state(); self.filter_query.set(''); self.filter_kind.set('全部'); super().new_note()
        self.editor_course=self.course.get(); self.editor_baseline=(self.title_var.get(),''); self.side_context=None
        self.put(self.side_editor,''); self.side_baseline=''; self.side_caption.config(text='选择 PDF 后，笔记自动关联当前页。')
        self.load_side_note()
        self.save_label.config(text='写下你的理解，内容会自动保存。')
    def focus_search(self):self.navigate('资料与笔记'); self.search_entry.focus_set(); return 'break'
    def remember_page(self,page):
        self.save_side_note(); super().remember_page(page)
        if self.selected:self.store.record_reading(self.course.get(),self.selected)
        if hasattr(self,'side_editor'):self.load_side_note()
    def toggle_side_notes(self):
        if self.side_visible:
            self.save_side_note(); self.library_split.forget(self.side_panel); self.side_visible=False
            if str(self.library_list) not in self.library_split.panes():self.library_split.insert(0,self.library_list,weight=0)
        else:
            doc=self.selected_doc()
            if not self.store.original(doc) or not str(self.store.original(doc)).lower().endswith('.pdf'):raise ValueError('页边笔记用于 PDF 阅读。普通笔记可直接在中间编辑。')
            self.library_split.add(self.side_panel,weight=0); self.side_visible=True; self.load_side_note()
            if self.winfo_width()<1300:self.library_split.forget(self.library_list)
            self.after(50,lambda:self.library_split.sashpos(len(self.library_split.panes())-2,max(350,self.library_split.winfo_width()-300)))
        self.after(100,self.reader.fit)
    def load_side_note(self):
        if not hasattr(self,'side_editor'):return
        doc=next((d for d in getattr(self,'docs',[]) if d['id']==self.selected),None)
        if not doc or not self.reader.pdf or not self.store.original(doc):
            if self.side_visible:
                self.library_split.forget(self.side_panel); self.side_visible=False
                if str(self.library_list) not in self.library_split.panes():self.library_split.insert(0,self.library_list,weight=0)
            self.side_context=None; self.side_baseline=''; self.put(self.side_editor,''); self.side_caption.config(text='选择 PDF 后，笔记自动关联当前页。'); return
        page=self.reader.index; self.side_context=(self.course.get(),doc['id'],page,doc['title'])
        note=self.store.page_note(doc['id'],page); self.side_baseline=note['body'] if note else ''; self.put(self.side_editor,self.side_baseline)
        self.side_caption.config(text=f'PDF 第 {page+1} 页 · 自动保存\n{doc["title"][:44]}')
    def side_changed(self,event=None):
        if self.side_editor.edit_modified():
            self.side_editor.edit_modified(False)
            if self.side_job:self.after_cancel(self.side_job)
            self.side_job=self.after(900,lambda:self.safe(self.save_side_note))
    def save_side_note(self):
        if not getattr(self,'side_context',None):return
        if self.side_job:self.after_cancel(self.side_job); self.side_job=None
        body=self.get(self.side_editor)
        if not body or body==self.side_baseline:return
        course,id,page,title=self.side_context
        self.store.save_page_note(course,id,page,f'{title} · 第 {page+1} 页笔记',body); self.side_baseline=body
        self.docs=self.view_docs(); self.render_tree(); self.status.set('页边笔记已保存，并关联教材页码'); self.refresh_home()
    def return_source(self):
        doc=self.selected_doc(); link=self.store.note_source(doc['id'])
        if not link:raise ValueError('这条笔记没有教材来源。阅读时使用「阅读笔记」可自动建立关联。')
        self.open_doc(link['source_id'])
        if self.reader.pdf:self.reader.index=link['page']; self.reader.render()
    def context_evidence(self):
        self.flush_edits(); doc=self.selected_doc()
        if self.reader.pdf and self.store.original(doc) and self.document_tabs.select()==str(self.reader):
            page=self.reader.pdf[self.reader.index]
            try:
                textpage=page.get_textpage()
                try:body=textpage.get_text_range()
                finally:textpage.close()
            finally:page.close()
            if not body.strip():raise ValueError('当前 PDF 页没有可识别文字，请先 OCR，或手动写一条阅读笔记。')
            self.require_source_text(body)
            return f'[资料 {doc["id"]} · {doc["title"]} · PDF 第 {self.reader.index+1} 页]\n'+body
        try:body=self.editor.get('sel.first','sel.last')
        except tk.TclError:body=self.get(self.editor)
        if len(body)>24000:raise ValueError('请选中要处理的文字，或切到 PDF 原版阅读后处理当前页。')
        self.require_source_text(body)
        return f'[资料 {doc["id"]} · {doc["title"]}]\n'+body
    def require_source_text(self,body):
        if len(re.sub(r'\s|[#>*_`\-]','',body))<80:
            raise ValueError('当前内容太少，可能只有标题或关键词，无法据此整理教材。\n\n请在左侧选择教材，翻到含正文的一页再点「AI 梳理」；也可以在笔记中粘贴相关原文（至少约 80 个非空白字符）。\n\n本次尚未发送 AI 请求。')
    def summarize(self):
        self.flush_edits(); doc=self.selected_doc(); source=self.store.original(doc)
        if source and source.suffix.lower()=='.pdf':
            self.summary_range_dialog(doc,source); return
        evidence=self.context_evidence(); title=self.title_var.get()+' · 知识梳理'
        self.ai('仅依据所给原文整理知识结构、重要公式、易错点和自测问题。用 Markdown 标题、列表和表格排版，数学公式使用 LaTeX $...$ 或 $$...$$。保留来源。资料不支持的部分省略，不要自行补写一整份通用笔记。确需提示时，在开头一次说明具体缺少什么依据，不要每个标题都重复“未核实”。',evidence,title)
    def summary_range_dialog(self,doc,source):
        from source_range import extract_pdf_range
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(str(source)) as pdf:total=len(pdf)
        current=(self.reader.index+1) if self.reader.pdf else max(1,doc.get('read_page',0)+1)
        window=tk.Toplevel(self); self.range_window=window
        window.title('AI 梳理 · 选择教材页码'); window.geometry('620x490'); window.transient(self); window.grab_set()
        frame=ttk.Frame(window,padding=24); frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='这次想整理哪一段？',font=('Microsoft YaHei UI',18,'bold')).pack(anchor='w')
        ttk.Label(frame,text=doc['title'],style='Muted.TLabel',wraplength=565).pack(anchor='w',pady=(8,12))
        ttk.Label(frame,text=f'教材共 {total} 页 · 当前 PDF 第 {current} 页',font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w')
        ttk.Label(frame,text='按 PDF 文件页序填写，包含封面和目录，不是书内印刷页码。',wraplength=565).pack(anchor='w',pady=(7,12))
        row=ttk.Frame(frame); row.pack(fill='x')
        start=tk.StringVar(value=str(current)); end=tk.StringVar(value=str(current))
        self.range_start=start; self.range_end=end
        ttk.Label(row,text='从第').pack(side='left'); ttk.Spinbox(row,from_=1,to=total,textvariable=start,width=7).pack(side='left',padx=8)
        ttk.Label(row,text='页，到第').pack(side='left'); ttk.Spinbox(row,from_=1,to=total,textvariable=end,width=7).pack(side='left',padx=8)
        ttk.Label(row,text='页（含首尾）').pack(side='left')
        ttk.Button(row,text='仅当前页',command=lambda:(start.set(str(current)),end.set(str(current)))).pack(side='right')
        detail=tk.StringVar(value='一次最多 50 页、48,000 字；超过上限会提示缩小范围，不会悄悄截断。')
        ttk.Label(frame,textvariable=detail,wraplength=565,foreground='#4262b5').pack(anchor='w',pady=16)
        ttk.Label(frame,text='当前会读取所选页的文字。图片、扫描内容和复杂公式仍需结合原教材核对。',style='Muted.TLabel',wraplength=565).pack(anchor='w')
        preview=tk.Text(frame,height=5,wrap='word',font=('Microsoft YaHei UI',9),relief='flat',padx=8,pady=8,state='disabled'); preview.pack(fill='both',expand=True,pady=10)
        cached={}
        def inspect():
            key=(start.get(),end.get())
            if key!=cached.get('key'):
                result=extract_pdf_range(source,doc['title'],doc['id'],*key)
                cached.update(key=key,result=result)
            result=cached['result']; missing=result['empty_pages']
            text=f"将整理 PDF 第 {result['start']}–{result['end']} 页，共 {result['end']-result['start']+1} 页，提取 {result['characters']:,} 字。"
            if missing:text+='\n以下页文字很少或为空：'+', '.join(map(str,missing))+'。结果会说明覆盖缺口。'
            detail.set(text); preview.config(state='normal'); preview.delete('1.0','end'); preview.insert('1.0',result['evidence'][:650]); preview.config(state='disabled')
            return result
        def submit():
            result=inspect()
            title=f"{doc['title']} · 第 {result['start']}–{result['end']} 页梳理"
            task=f"请仅依据以下教材 PDF 第 {result['start']}–{result['end']} 页原文，按主题整理知识结构、重要公式、易错点和自测问题，每项引用对应 PDF 页码。用 Markdown 标题、列表和表格排版，数学公式使用 LaTeX。不要补写原文不支持的知识。文字不足页为 {result['empty_pages']}，必须在开头说明无法充分覆盖这些页的图像内容，不得假装已分析图片；不需要每个标题重复未核实。"
            self.ai(task,result['evidence'],title)
            window.destroy()
        row=ttk.Frame(frame); row.pack(fill='x',pady=(4,0))
        ttk.Button(row,text='检查范围与正文',command=lambda:self.safe(inspect)).pack(side='left')
        ttk.Button(row,text='开始梳理',style='Accent.TButton',command=lambda:self.safe(submit)).pack(side='right')
        ttk.Button(row,text='取消',command=window.destroy).pack(side='right',padx=8)
    def to_cards(self):
        self.flush_edits(); self.selected_doc(); self.navigate('记忆与复习'); self.review.tabs.select(1)
        self.review.source_hint.config(text='当前来源：'+self.title_var.get()[:70]+' · PDF 阅读时仅处理当前页')
    def side_to_card(self):
        self.save_side_note()
        if not self.side_context or not self.get(self.side_editor):raise ValueError('先写下这页的理解，再制作卡片')
        course,id,page,title=self.side_context; body=self.get(self.side_editor)
        self.navigate('记忆与复习'); self.review.tabs.select(1); self.review.blank(); self.put(self.review.back,body)
        self.review.source.set(f'资料 {id} · {title} · PDF 第 {page+1} 页'); self.review.draft_course=course; self.review.front.focus_set()
        self.status.set('笔记已带入答案区，补充一个自测问题即可保存卡片')
    def exam(self):
        super().exam(); p=self.pages['AI 自定义组卷']; self.exam_context=ttk.Label(p,text='出题依据：当前课程的教材与笔记',style='Muted.TLabel')
        self.exam_context.pack(anchor='w',before=p.winfo_children()[1],pady=8)
        row=ttk.Frame(p); row.pack(fill='x',before=p.winfo_children()[1]); self.button(row,'使用整个课程',self.reset_exam_source)
    def reset_exam_source(self):self.exam_source_id=None; self.exam_context.config(text='出题依据：当前课程的教材与笔记')
    def search(self):
        super().search()
        row=ttk.Frame(self.pages['资料检索']); row.pack(fill='x',pady=24)
        self.button(row,'导入找到的资料 →',lambda:(self.navigate('资料与笔记'),self.import_files())).configure(style='Accent.TButton')
    def to_exam(self):
        self.flush_edits(); doc=self.selected_doc(); self.exam_source_id=doc['id']; self.scope.set(doc['title']); self.exam_context.config(text='出题依据：'+doc['title'][:90]); self.navigate('AI 自定义组卷')
    def open_result(self):
        if not getattr(self,'last_result',None):return
        course,id=self.last_result
        self.flush_edits(); self.save_side_note()
        if self.course.get()!=course:self.course.set(course); self.refresh()
        self.open_doc(id)
    def export_visible(self):
        active=self.tabs.select()
        if active==str(self.pages['AI 自定义组卷']):self.export_dialog('练习卷',self.get(self.exam_text))
        elif active==str(self.pages['课堂录音']):self.export_dialog('课堂整理',self.get(self.match_text) or self.get(self.transcript))
        else:self.export_current()
    def export_current(self):
        self.flush_edits(); doc=self.selected_doc(); self.export_dialog(doc['title'],self.get(self.editor),self.store.original(doc))
    def export_side(self):
        self.save_side_note()
        if not self.side_context:raise ValueError('请先选择教材页面')
        course,id,page,title=self.side_context; self.export_dialog(f'{title} · 第 {page+1} 页笔记',self.get(self.side_editor))
    def export(self,body):self.export_dialog('学习记录',body)
    def export_dialog(self,title,body,original=None):
        if not body.strip():raise ValueError('还没有可导出的内容')
        window=tk.Toplevel(self); window.title('导出学习成果'); window.geometry('490x410'); window.transient(self); window.grab_set()
        frame=ttk.Frame(window,padding=26); frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='把学习成果带走',font=('Microsoft YaHei UI',18,'bold')).pack(anchor='w')
        ttk.Label(frame,text=title[:48],style='Muted.TLabel',wraplength=420).pack(anchor='w',pady=10)
        mode=tk.StringVar(value='pdf')
        options=[('PDF · 排版后阅读、打印或分享','pdf'),('Markdown · 继续编辑笔记','md'),('纯文本 · 通用阅读','txt'),('网页文档 · 浏览器阅读或打印','html')]
        if original and original.exists():options.append(('原始文件 · 保留完整图片和排版','original'))
        for label,value in options:ttk.Radiobutton(frame,text=label,variable=mode,value=value).pack(anchor='w',pady=5)
        def save():
            ext=original.suffix if mode.get()=='original' else '.'+mode.get()
            name=re.sub(r'[<>:"/\\|?*]','_',title)[:90]
            path=filedialog.asksaveasfilename(parent=window,initialfile=name+ext,defaultextension=ext,filetypes=[('所选格式','*'+ext)])
            if not path:return
            if mode.get()=='original':
                if Path(path).resolve()!=original.resolve():shutil.copyfile(original,path)
            elif mode.get()=='pdf':
                from note_pdf import build_note_pdf
                rendered=build_note_pdf(title,body,Path(self.store.path).parent/'note_previews')
                if Path(path).resolve()!=rendered.resolve():shutil.copyfile(rendered,path)
            elif mode.get()=='html':
                content='<!doctype html><html lang="zh"><meta charset="utf-8"><title>'+html.escape(title)+'</title><style>body{max-width:800px;margin:60px auto;padding:0 32px;color:#24324b;font:17px/1.85 system-ui}pre{white-space:pre-wrap;font:inherit}h1{font-size:28px}</style><h1>'+html.escape(title)+'</h1><pre>'+html.escape(body)+'</pre></html>'
                Path(path).write_text(content,encoding='utf-8')
            else:Path(path).write_text(('# '+title+'\n\n' if mode.get()=='md' else title+'\n\n')+body,encoding='utf-8')
            self.status.set('已导出到 '+path); window.destroy()
        ttk.Button(frame,text='选择保存位置',style='Accent.TButton',command=lambda:self.safe(save)).pack(anchor='e',pady=15)
