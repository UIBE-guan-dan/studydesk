import json, os, queue, threading, webbrowser, wave, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / '.vendor'))
sys.path.insert(0, str(Path(__file__).resolve().parent / '.vendor' / 'audio_compat'))
sys.path.insert(0, str(Path(__file__).resolve().parent / '.vendor' / 'sense_runtime'))
from urllib.parse import quote
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from core import Store, DATA, ROOT, DEFAULTS, read_document, retrieve, generate, transcribe, request
from pdf_reader import PDFReader
if os.name == 'nt':
    import ctypes
    try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception: pass

class LegacyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.tk.call('tk','scaling',1.25)
        self.title('知课 StudyDesk · 大学生学习工作台')
        self.geometry('1440x900'); self.minsize(1100,740)
        if (ROOT/'study.ico').exists():self.iconbitmap(str(ROOT/'study.ico'))
        self.configure(bg='#f3f5fa')
        self.store=Store(); self.jobs=queue.Queue(); self.busy=False; self.selected=None; self.stream=None
        self.settings=DEFAULTS.copy()
        try: self.settings.update(json.loads((DATA/'settings.json').read_text(encoding='utf-8')))
        except (FileNotFoundError,ValueError): pass
        style=ttk.Style(self); style.theme_use('clam')
        style.configure('.',font=('Microsoft YaHei UI',10),background='#f3f5fa')
        style.configure('TButton',padding=(12,8)); style.configure('TNotebook.Tab',padding=(20,12))
        style.configure('TNotebook.Tab',background='#e5eaf7',foreground='#354163')
        style.map('TNotebook.Tab',background=[('selected','#ffffff')],foreground=[('selected','#3e5be0')])
        style.configure('Treeview',rowheight=34,background='white',fieldbackground='white')
        style.configure('Accent.TButton',foreground='white',background='#3e5be0')
        self.course=tk.StringVar(value=self.store.courses()[0])
        self.build_shell()
        self.pages={}
        for name in ['学习概览','资料与笔记','课程任务','AI 自定义组卷','课堂录音','记忆与复习','资料检索','Kimi 与设置']:
            page=ttk.Frame(self.tabs,padding=18); self.tabs.add(page,text=name); self.pages[name]=page
        self.library(); self.exam(); self.audio(); self.search(); self.config()
        from review import ReviewPanel
        self.review=ReviewPanel(self.pages['记忆与复习'],self)
        self.review.pack(fill='both',expand=True)
        self.status=tk.StringVar(value='就绪 · 资料保存在本机；点击 AI 操作时，相关文本才会发往配置的接口。')
        ttk.Label(self.status_bar,textvariable=self.status,style='Muted.TLabel').pack(side='left',fill='x',expand=True)
        self.progress=ttk.Progressbar(self.status_bar,mode='indeterminate',length=110); self.progress.pack(side='right')
        self.build_home()
        self.refresh(); self.after(150,self.poll)
        self.protocol('WM_DELETE_WINDOW',self.close)

    def button(self,parent,text,command):
        b=ttk.Button(parent,text=text,command=lambda:self.safe(command)); b.pack(side='left',padx=(0,8)); return b
    def safe(self,fn):
        try: fn()
        except Exception as e: messagebox.showerror('操作未完成',str(e),parent=self)
    def entry(self,parent,label,value='',secret=False):
        ttk.Label(parent,text=label).pack(anchor='w',pady=(9,3))
        v=tk.StringVar(value=value); ttk.Entry(parent,textvariable=v,show='•' if secret else '').pack(fill='x'); return v
    def text(self,parent,height=12):
        w=ScrolledText(parent,wrap='word',height=height,font=('Microsoft YaHei UI',11),relief='flat',padx=14,pady=12,undo=True)
        w.pack(fill='both',expand=True,pady=10); return w
    def get(self,w): return w.get('1.0','end-1c').strip()
    def put(self,w,text): w.delete('1.0','end'); w.insert('1.0',text)
    def run(self,label,fn,done):
        if self.busy: raise ValueError('上一项任务仍在进行，请稍候。')
        self.busy=True; self.status.set(label+'… 可以继续浏览资料。')
        self.progress.start(15)
        def work():
            try: self.jobs.put((done,fn(),None))
            except Exception as e: self.jobs.put((done,None,str(e)))
        threading.Thread(target=work,daemon=True).start()
    def poll(self):
        try:
            done,value,error=self.jobs.get_nowait(); self.busy=False
            self.progress.stop()
            if error: self.status.set('任务失败，可调整后重试'); messagebox.showerror('任务失败',error)
            else:
                self.status.set('任务完成'); self.safe(lambda:done(value))
        except queue.Empty: pass
        self.after(150,self.poll)
    def close(self):
        if self.busy and not messagebox.askyesno('任务仍在运行','关闭会中断正在执行的任务，仍要退出吗？'): return
        self.flush_edits(); self.save_side_note()
        if self.stream: self.stop_record()
        self.destroy()
    def new_course(self):
        name=simpledialog.askstring('新课程','课程名称，例如：量子力学',parent=self)
        if name and name.strip():
            self.store.course(name); self.course_box['values']=self.store.courses(); self.course.set(name.strip()); self.refresh()
    def refresh(self):
        previous=(self.selected,self.title_var.get(),self.get(self.editor))
        same_course=getattr(self,'current_course',None)==self.course.get()
        self.current_course=self.course.get()
        self.docs=self.store.docs(self.course.get()); self.selected=None
        self.tree.delete(*self.tree.get_children())
        for d in self.docs: self.tree.insert('', 'end',iid=str(d['id']),values=(d['kind'],d['title']))
        self.title_var.set(''); self.put(self.editor,'')
        if same_course and (previous[0] is None or any(d['id']==previous[0] for d in self.docs)):
            self.selected=previous[0]; self.title_var.set(previous[1]); self.put(self.editor,previous[2])
        self.books={f'{d["id"]} · {d["title"]}':d for d in self.docs if d['kind']=='教材'}
        self.book_box['values']=list(self.books)
        if self.book.get() not in self.books: self.book.set(next(iter(self.books),''))
        if not same_course or self.selected is None:
            self.reader.clear(); self.document_tabs.select(self.text_page)
        if hasattr(self,'review'):self.review.refresh()
    def library(self):
        p=self.pages['资料与笔记']; row=ttk.Frame(p); row.pack(fill='x')
        self.kind=tk.StringVar(value='教材'); ttk.Combobox(row,textvariable=self.kind,values=['教材','参考卷','笔记','资料'],state='readonly',width=10).pack(side='left',padx=(0,8))
        self.button(row,'导入文件',self.import_files); self.button(row,'新建笔记',self.new_note)
        self.button(row,'保存编辑',self.save_note); self.button(row,'导出 Markdown',lambda:self.export(self.get(self.editor)))
        self.button(row,'删除',self.delete_doc)
        self.button(row,'补关联原文件',self.attach_original)
        split=ttk.Panedwindow(p,orient='horizontal'); split.pack(fill='both',expand=True,pady=12)
        left=ttk.Frame(split); right=ttk.Frame(split); split.add(left,weight=1); split.add(right,weight=3)
        self.tree=ttk.Treeview(left,columns=('kind','title'),show='headings',selectmode='browse')
        self.tree.heading('kind',text='类型'); self.tree.heading('title',text='标题'); self.tree.column('kind',width=65,stretch=False); self.tree.column('title',width=200)
        self.tree.pack(fill='both',expand=True); self.tree.bind('<<TreeviewSelect>>',self.select_doc)
        self.title_var=self.entry(right,'资料标题')
        actions=ttk.Frame(right); actions.pack(fill='x',pady=7)
        self.button(actions,'系统阅读器打开',self.open_original)
        self.button(actions,'AI 整理 → 新笔记',self.summarize)
        self.document_tabs=ttk.Notebook(right); self.document_tabs.pack(fill='both',expand=True)
        self.reader=PDFReader(self.document_tabs,on_page=self.remember_page)
        self.text_page=ttk.Frame(self.document_tabs)
        self.document_tabs.add(self.reader,text='PDF 原版阅读')
        self.document_tabs.add(self.text_page,text='文字索引 / 笔记编辑')
        self.editor=self.text(self.text_page)
        self.document_tabs.select(self.text_page)
        ttk.Label(p,text='支持 PDF / TXT / MD / SRT / VTT。教材与参考卷请分别分类；PDF 使用文件页序，可能与书面页码不同。').pack(anchor='w',pady=8)
    def select_doc(self,event=None):
        sel=self.tree.selection()
        if sel:
            self.selected=int(sel[0]); d=next(x for x in self.docs if x['id']==self.selected)
            self.title_var.set(d['title']); self.put(self.editor,d['body'])
            source=self.store.original(d)
            if source and source.suffix.lower()=='.pdf':
                self.document_tabs.select(self.reader); self.reader.load(source,d.get('read_page',0))
            elif d['title'].lower().endswith('.pdf'):
                self.document_tabs.select(self.reader); self.reader.clear('这条旧版资料仅保存了文字。\n点击上方「补关联原文件」选择原 PDF，即可恢复图文阅读。')
            else:self.reader.clear(); self.document_tabs.select(self.text_page)
    def remember_page(self,page):
        if self.selected:
            self.store.remember_page(self.selected,page)
            for d in self.docs:
                if d['id']==self.selected:d['read_page']=page
    def selected_doc(self):
        doc=next((d for d in self.docs if d['id']==self.selected),None)
        if not doc:raise ValueError('请先在左侧选择资料')
        return doc
    def open_original(self):
        source=self.store.original(self.selected_doc())
        if not source or not source.exists():raise ValueError('没有原文件，请先点击「补关联原文件」')
        os.startfile(source)
    def attach_original(self):
        doc=self.selected_doc()
        path=filedialog.askopenfilename(title='选择这条资料对应的原文件',filetypes=[('PDF / 文本','*.pdf *.txt *.md *.srt *.vtt')])
        if not path:return
        id=doc['id']; course=self.course.get()
        def done(_):
            self.refresh()
            if self.course.get()==course and self.tree.exists(str(id)):
                self.selected=None
                self.tree.selection_set(str(id)); self.select_doc()
            self.status.set('原文件副本已保存，原有文字与笔记保留')
        self.run('正在保存原文件',lambda:self.store.attach_file(id,path),done)
    def import_files(self):
        paths=filedialog.askopenfilenames(filetypes=[('学习资料','*.pdf *.txt *.md *.srt *.vtt')])
        if not paths:return
        course,kind=self.course.get(),self.kind.get()
        def work():
            errors=[]
            for path in paths:
                try:self.store.import_file(course,kind,path)
                except Exception as e:errors.append(Path(path).name+': '+str(e))
            return errors
        def done(errors):
            self.refresh()
            if errors:messagebox.showwarning('部分文件未导入','\n'.join(errors))
        self.run('正在保存原文件并建立 AI 文字索引',work,done)
    def new_note(self):
        self.reader.clear(); self.document_tabs.select(self.text_page)
        self.selected=None; self.title_var.set('新笔记'); self.put(self.editor,''); self.editor.focus_set()
    def save_note(self):
        if self.selected:self.store.update(self.selected,self.title_var.get(),self.get(self.editor))
        else:self.selected=self.store.add(self.course.get(),'笔记',self.title_var.get(),self.get(self.editor))
        self.refresh(); self.status.set('笔记已保存')
    def delete_doc(self):
        if self.selected and messagebox.askyesno('删除资料','确定删除当前资料？'):
            self.store.delete(self.selected); self.refresh()
    def export(self,body):
        if not body:raise ValueError('没有可导出的内容')
        path=filedialog.asksaveasfilename(defaultextension='.md',filetypes=[('Markdown','*.md'),('文本','*.txt')])
        if path:Path(path).write_text(body,encoding='utf-8'); self.status.set('已导出 '+path)
    def ai(self,task,evidence,title,kind='笔记',target=None):
        if not evidence.strip():raise ValueError('请先导入相关资料')
        settings=self.values(); key=self.key.get(); course=self.course.get()
        def done(result):
            id=self.store.add(course,kind,title,result); self.refresh()
            self.last_result=(course,id); self.result_button.pack(side='right',padx=10)
            if target:self.put(target,result)
            self.status.set('已生成并保存到 '+course+' 的资料库')
        self.run('Kimi 正在分析资料',lambda:generate(settings,key,task,evidence),done)
    def summarize(self):
        text=self.get(self.editor)
        if len(text)>24000:raise ValueError('所选资料超过 24000 字，请复制需要整理的章节到一条新笔记再处理。')
        self.ai('整理为：知识结构、重要定义与公式、易错点、5 个自测问题。',text,self.title_var.get()+' · 知识梳理')
    def exam(self):
        p=self.pages['AI 自定义组卷']
        ttk.Label(p,text='用自己的教材，生成适合自己的练习',font=('Microsoft YaHei UI',17,'bold')).pack(anchor='w')
        self.scope=self.entry(p,'章节 / 考点范围','波函数、薛定谔方程')
        row=ttk.Frame(p); row.pack(fill='x',pady=14); self.counts={}
        for kind,n in [('单选题',5),('多选题',2),('填空题',3),('简答题',2),('计算题',2)]:
            ttk.Label(row,text=kind).pack(side='left'); v=tk.StringVar(value=str(n)); self.counts[kind]=v
            ttk.Spinbox(row,from_=0,to=20,width=4,textvariable=v).pack(side='left',padx=(5,18))
        row=ttk.Frame(p); row.pack(fill='x')
        self.level=tk.StringVar(value='中等'); ttk.Combobox(row,textvariable=self.level,values=['基础','中等','进阶'],width=10,state='readonly').pack(side='left',padx=(0,12))
        self.use_ref=tk.BooleanVar(value=True); ttk.Checkbutton(row,text='参考本课程已导入的参考卷风格',variable=self.use_ref).pack(side='left',padx=8)
        self.button(row,'生成试卷',self.make_exam); self.button(row,'导出试卷',lambda:self.export(self.get(self.exam_text)))
        self.exam_text=self.text(p)
        ttk.Label(p,text='答案与解析放在卷末。生成结果保存在资料库；题量和答案需人工复核后用于正式考试。').pack(anchor='w')
    def make_exam(self):
        try:counts={k:int(v.get()) for k,v in self.counts.items()}
        except ValueError:raise ValueError('题数必须是整数')
        if any(n<0 or n>20 for n in counts.values()) or not 1<=sum(counts.values())<=40:raise ValueError('每种题型 0–20 道，总题数 1–40 道')
        docs=self.store.docs(self.course.get()); sources=[d for d in docs if d['kind'] in ['教材','资料','笔记']]
        if self.exam_source_id is not None:sources=[d for d in docs if d['id']==self.exam_source_id]
        if not sources:raise ValueError('请先导入教材或课程资料')
        evidence=retrieve(sources,self.scope.get())
        if self.use_ref.get():
            refs=[d for d in docs if d['kind']=='参考卷']
            if refs:evidence+='\n\n仅供题型风格参考，不照抄：\n'+retrieve(refs,self.scope.get(),4)
        task=f'为课程 {self.course.get()} 出一份 {self.level.get()} 难度的练习卷。范围：{self.scope.get()}。精确题数：{json.dumps(counts,ensure_ascii=False)}。零道题型不要出现。按题型分节，先完整题目，末尾统一答案、推导解析、来源。单选只能有一个正确项，多选标明规则。证据不足的考点明确说明，禁止编造教材原题号。最后核对各题型数量。'
        self.ai(task,evidence,'练习卷 '+datetime.now().strftime('%m-%d %H:%M'),'试卷',self.exam_text)
    def audio(self):
        p=self.pages['课堂录音']; ttk.Label(p,text='录音 → 转写 → 教材定位',font=('Microsoft YaHei UI',17,'bold')).pack(anchor='w')
        row=ttk.Frame(p); row.pack(fill='x',pady=12)
        self.button(row,'导入录音转写',self.import_audio); self.button(row,'开始录音',self.start_record); self.button(row,'停止并保存',self.stop_record)
        self.button(row,'打开录音文件夹',self.open_recordings); self.button(row,'读取转写文本',self.import_transcript)
        self.local=tk.BooleanVar(value=True); ttk.Checkbutton(p,text='使用本地语音识别（无需 API Key；优先 large-v3-turbo，SenseVoice 更快）',variable=self.local).pack(anchor='w')
        quality=ttk.Frame(p); quality.pack(fill='x',pady=8)
        ttk.Label(quality,text='识别模型').pack(side='left')
        self.local_model=tk.StringVar(value=self.settings['local_model'])
        ttk.Combobox(quality,textvariable=self.local_model,values=['sensevoice','base','small','medium','large-v3','large-v3-turbo'],state='readonly',width=14).pack(side='left',padx=8)
        ttk.Label(quality,text='录音语言').pack(side='left')
        self.speech_language=tk.StringVar(value=self.settings['speech_language'])
        ttk.Combobox(quality,textvariable=self.speech_language,values=['zh','en','auto'],state='readonly',width=7).pack(side='left',padx=8)
        ttk.Label(quality,text='zh 中文 / en 英文 / auto 自动',style='Muted.TLabel').pack(side='left')
        self.speech_hotwords=self.entry(p,'专业术语（仅 Whisper 支持，逗号分隔；SenseVoice 本版不使用此项）',self.settings['speech_hotwords'])
        hotword_entry=p.winfo_children()[-1]
        def update_hotword_state(*args):hotword_entry.configure(state='disabled' if self.local_model.get()=='sensevoice' else 'normal')
        self.local_model.trace_add('write',update_hotword_state); update_hotword_state()
        self.book=tk.StringVar(); self.book_box=ttk.Combobox(p,textvariable=self.book,state='readonly'); self.book_box.pack(fill='x',pady=8)
        ttk.Label(p,text='上方指定教材；下方粘贴或导入课堂转写文本，可先手动纠正专有名词。').pack(anchor='w')
        self.transcript=self.text(p,height=5)
        row=ttk.Frame(p); row.pack(fill='x'); self.button(row,'对照教材分析本节课',self.match_book); self.button(row,'保存课堂转写',self.save_transcript)
        self.match_text=self.text(p,height=5)
    def open_recordings(self):
        folder=DATA/'recordings'; folder.mkdir(exist_ok=True); os.startfile(folder)
    def import_transcript(self):
        path=filedialog.askopenfilename(filetypes=[('转写文本','*.txt *.md *.srt *.vtt')])
        if path:self.put(self.transcript,read_document(path))
    def import_audio(self):
        path=filedialog.askopenfilename(initialdir=DATA/'recordings',filetypes=[('音频','*.mp3 *.wav *.m4a *.webm *.ogg *.flac')])
        if not path:return
        settings=self.values(); key=self.speech_key.get(); local=self.local.get(); course=self.course.get()
        def done(text):
            if not text.strip():raise ValueError('未识别到语音')
            engine=settings['local_model'] if local else settings['speech_model']
            self.store.add(course,'课堂转写',Path(path).stem+' · '+engine,text); self.refresh(); self.put(self.transcript,text)
            self.status.set('已保存 '+engine+' 原始识别结果；请回听核对专业术语。旧转写记录保留。')
        self.run('正在转写录音',lambda:transcribe(path,settings,key,local),done)
    def save_transcript(self):
        self.store.add(self.course.get(),'课堂转写','课堂 '+datetime.now().strftime('%m-%d %H:%M'),self.get(self.transcript)); self.refresh()
    def match_book(self):
        text=self.get(self.transcript); book=self.books.get(self.book.get())
        if not text or not book:raise ValueError('请先填写课堂转写，并选择已导入的教材')
        if len(text)>24000:raise ValueError('转写超过 24000 字，请分节分析')
        self.ai('根据课堂转写逐项分析：讲授知识点、教材对应片段与 PDF 页序、证据摘录、覆盖程度、可对应习题及原题号（仅限片段明确出现）、复习建议。检索不到不代表教材没有，标注待核实。课堂转写：\n'+text,retrieve([book],text,18),'课堂教材匹配 '+datetime.now().strftime('%m-%d %H:%M'),'课堂分析',self.match_text)
    def start_record(self):
        if self.stream:raise ValueError('正在录音')
        if not messagebox.askokcancel('课程录音许可确认','请务必确定该课程老师允许你进行课程录音。\n\n已获得老师允许，请点击“确定”开始录音；未获得允许，请点击“取消”。',parent=self,default='cancel'):
            return
        try:import sounddevice as sd
        except ImportError:raise ValueError('请先安装录音组件：python -m pip install -r requirements-audio.txt') from None
        folder=DATA/'recordings'; folder.mkdir(exist_ok=True); self.audio_path=folder/(datetime.now().strftime('%Y%m%d-%H%M%S')+'.wav')
        self.wav=wave.open(str(self.audio_path),'wb'); self.wav.setnchannels(1); self.wav.setsampwidth(2); self.wav.setframerate(16000)
        try:
            self.stream=sd.RawInputStream(samplerate=16000,channels=1,dtype='int16',callback=lambda data,frames,time,status:self.wav.writeframesraw(bytes(data)))
            self.stream.start(); self.status.set('● 正在录音；停止后从录音文件夹导入转写。')
        except Exception:
            if self.stream:self.stream.close(); self.stream=None
            self.wav.close(); raise
    def stop_record(self):
        if self.stream:
            self.stream.stop(); self.stream.close(); self.stream=None; self.wav.close(); self.status.set('录音已保存：'+str(self.audio_path))
    def search(self):
        p=self.pages['资料检索']; ttk.Label(p,text='把课程资料带回你的知识库',font=('Microsoft YaHei UI',17,'bold')).pack(anchor='w')
        self.query=self.entry(p,'关键词 / 书名 / 作者','量子力学')
        row=ttk.Frame(p); row.pack(fill='x',pady=20)
        for title,url in [('MIT 公开课','https://ocw.mit.edu/search/?q={query}'),('arXiv 论文','https://arxiv.org/search/?query={query}&searchtype=all'),('Open Library','https://openlibrary.org/search?q={query}')]:
            self.button(row,title,lambda u=url:self.open_search(u))
        self.button(row,'自定义 / Z-Library 入口',lambda:self.open_search(self.search_url.get()))
        ttk.Label(p,text='检索在默认浏览器打开。下载或复制资料后，在「资料与笔记」中导入。\n\n自定义网站可在设置中填写含 {query} 的搜索地址模板。\n此版本不代登录、不抓取搜索结果，也不自动下载书籍。',font=('Microsoft YaHei UI',12),wraplength=820).pack(anchor='w')
    def open_search(self,url):
        if not url.startswith('https://') or '{query}' not in url:raise ValueError('请在设置中填写 https:// 开头、包含 {query} 的搜索地址模板')
        webbrowser.open(url.replace('{query}',quote(self.query.get())))
    def config(self):
        p=self.pages['Kimi 与设置']; left=ttk.Frame(p); left.pack(side='left',fill='both',expand=True,padx=(0,22)); right=ttk.Frame(p); right.pack(side='left',fill='both',expand=True)
        ttk.Label(left,text='Kimi · 文本分析与出卷',font=('Microsoft YaHei UI',15,'bold')).pack(anchor='w')
        self.base=self.entry(left,'API 地址',self.settings['base']); self.key=self.entry(left,'API Key（仅当前会话，不写入文件）',os.environ.get('MOONSHOT_API_KEY',''),True)
        ttk.Label(left,text='模型名称（可手动填写）').pack(anchor='w',pady=(12,3)); self.model=tk.StringVar(value=self.settings['model']); self.models=ttk.Combobox(left,textvariable=self.model); self.models.pack(fill='x')
        row=ttk.Frame(left); row.pack(fill='x',pady=12); self.button(row,'获取模型列表 / 测试连接',self.load_models)
        self.search_url=self.entry(left,'自定义检索模板，使用 {query} 占位',self.settings['search_url'])
        row=ttk.Frame(left); row.pack(fill='x',pady=20); self.button(row,'保存设置',self.save_config); self.button(row,'Kimi 开放平台',lambda:webbrowser.open('https://platform.kimi.com/'))
        ttk.Label(left,text='教材片段和课堂文字会随 AI 请求发往上述接口。\n模型列表测试不会上传课程资料。',wraplength=430).pack(anchor='w')
        ttk.Label(right,text='语音转写 · 独立配置',font=('Microsoft YaHei UI',15,'bold')).pack(anchor='w')
        self.speech_base=self.entry(right,'兼容语音转写 API 地址（可选）',self.settings['speech_base'])
        self.speech_key=self.entry(right,'语音 API Key（仅当前会话）','',True)
        self.speech_model=self.entry(right,'云端语音模型',self.settings['speech_model'])
        ttk.Label(right,text='本地语音模型（课堂页也可切换）').pack(anchor='w',pady=(9,3))
        ttk.Combobox(right,textvariable=self.local_model,values=['sensevoice','base','small','medium','large-v3','large-v3-turbo'],state='readonly').pack(fill='x')
        ttk.Label(right,text='本地转写无需语音 API Key；首次需联网下载模型。\nKimi 文本接口和语音转写接口独立配置。\n\n数据位置：项目 data 文件夹。\n备份时关闭软件，复制整个 data 文件夹。',wraplength=430).pack(anchor='w',pady=20)
    def values(self):return {k:getattr(self,k).get().strip() for k in DEFAULTS}
    def save_config(self):
        (DATA/'settings.json').write_text(json.dumps(self.values(),ensure_ascii=False,indent=2),encoding='utf-8'); self.status.set('设置已保存，API Key 未写入文件')
    def load_models(self):
        base,key=self.base.get(),self.key.get()
        def done(response):
            names=[m['id'] for m in response['data']]; self.models['values']=names
            if not self.model.get() and names:self.model.set(names[0])
            self.status.set(f'连接成功，获取到 {len(names)} 个模型，请选择用于分析的模型')
        self.run('连接 Kimi',lambda:request(base,'/models',key),done)

from workspace_ui import WorkspaceUX
from learning_ui import LearningUX
from lecture_links import LectureUX
from exam_ui import ExamUX
from font_ui import FontSizeUX
class App(FontSizeUX,ExamUX,LectureUX,LearningUX,WorkspaceUX,LegacyApp):
    pass

if __name__=='__main__': App().mainloop()
