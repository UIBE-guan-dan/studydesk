"""Flashcards backed by the upstream py-fsrs scheduler (MIT)."""
import json
from datetime import datetime, timezone
import tkinter as tk
from tkinter import ttk, messagebox
from fsrs import Card, Scheduler, Rating
from core import generate, retrieve

class ReviewStore:
    def __init__(self,store):self.store=store
    def add(self,course,question,answer,source=''):
        if not question.strip() or not answer.strip():raise ValueError('请填写问题与答案')
        card=Card()
        with self.store.connect() as db:
            return db.execute('INSERT INTO cards(course,question,answer,source,state,due) VALUES (?,?,?,?,?,?)',(course,question.strip(),answer.strip(),source,card.to_json(),card.due.isoformat())).lastrowid
    def cards(self,course):
        with self.store.connect() as db:return [dict(r) for r in db.execute('SELECT * FROM cards WHERE course=? ORDER BY due,id',(course,))]
    def due(self,course,now=None):
        now=now or datetime.now(timezone.utc)
        return [c for c in self.cards(course) if datetime.fromisoformat(c['due'])<=now]
    def grade(self,id,rating,now=None):
        if rating not in (1,2,3,4):raise ValueError('无效的复习评分')
        now=now or datetime.now(timezone.utc)
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM cards WHERE id=?',(id,)).fetchone()
            if not row:raise ValueError('卡片已不存在')
            card=Card.from_json(row['state'])
            if card.due>now:raise ValueError('这张卡还未到复习时间，请刷新列表')
            updated,log=Scheduler().review_card(card,Rating(rating),review_datetime=now)
            db.execute('UPDATE cards SET state=?,due=? WHERE id=?',(updated.to_json(),updated.due.isoformat(),id))
            db.execute('INSERT INTO reviews(card_id,reviewed,rating,log) VALUES (?,?,?,?)',(id,now.isoformat(),rating,log.to_json()))
            return updated.due
    def delete(self,id):
        with self.store.connect() as db:
            db.execute('DELETE FROM cards WHERE id=?',(id,)); db.execute('DELETE FROM reviews WHERE card_id=?',(id,))

def parse_drafts(text):
    text=text.strip()
    if text.startswith('```'):text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    try:data=json.loads(text)
    except ValueError:raise ValueError('AI 返回的卡片格式不完整，请重试或手动制作卡片') from None
    if not isinstance(data,list) or not 1<=len(data)<=10:raise ValueError('AI 返回的卡片数量或格式有误')
    for card in data:
        if not isinstance(card,dict) or any(not isinstance(card.get(k),str) or not card[k].strip() for k in ('question','answer')):raise ValueError('AI 卡片缺少问题或答案，请重试')
    return data

class ReviewPanel(ttk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent); self.app=app; self.store=ReviewStore(app.store); self.current=None; self.revealed=False; self.drafts=[]; self.draft_source=''; self.draft_course=None
        ttk.Label(self,text='主动回忆，让知识真正留下来',font=('Microsoft YaHei UI',16,'bold')).pack(anchor='w')
        ttk.Label(self,text='先回忆，再看答案。FSRS 根据每次反馈安排下次复习；无需 AI 也能使用。').pack(anchor='w',pady=6)
        tabs=ttk.Notebook(self); self.tabs=tabs; tabs.pack(fill='both',expand=True)
        due=ttk.Frame(tabs,padding=12); create=ttk.Frame(tabs,padding=12); library=ttk.Frame(tabs,padding=12)
        tabs.add(due,text='今日待复习'); tabs.add(create,text='制作卡片 / 错题'); tabs.add(library,text='全部卡片')
        row=ttk.Frame(due); row.pack(fill='x'); self.summary=ttk.Label(row); self.summary.pack(side='left',expand=True,anchor='w'); app.button(row,'刷新到期列表',self.refresh)
        self.question=app.text(due,height=5); self.question.configure(state='disabled')
        self.answer=app.text(due,height=6); self.answer.configure(state='disabled')
        row=ttk.Frame(due); row.pack(fill='x'); app.button(row,'显示答案',self.reveal)
        self.grade_buttons=[]
        for number,label in enumerate(['忘记','困难','记得','轻松'],1):self.grade_buttons.append(app.button(row,label,lambda n=number:self.grade(n)))
        self.feedback=ttk.Label(due); self.feedback.pack(anchor='w',pady=10)
        footer=ttk.Frame(create); footer.pack(side='bottom',fill='x')
        row=ttk.Frame(create); row.pack(fill='x'); app.button(row,'清空草稿',self.blank); app.button(row,'从所选资料生成 5 张草稿',self.ai_drafts)
        self.source_hint=ttk.Label(create,text='在「资料与笔记」选择资料后，点击「制卡」即可带入来源。',style='Muted.TLabel',wraplength=850); self.source_hint.pack(anchor='w',pady=5)
        self.draft_choice=tk.StringVar(); self.draft_box=ttk.Combobox(create,textvariable=self.draft_choice,state='readonly'); self.draft_box.pack(fill='x',pady=8); self.draft_box.bind('<<ComboboxSelected>>',self.load_draft)
        ttk.Label(create,text='问题 / 错题题干').pack(anchor='w'); self.front=app.text(create,height=2)
        ttk.Label(create,text='答案 / 思路 / 易错原因').pack(anchor='w'); self.back=app.text(create,height=3)
        self.source=app.entry(footer,'来源（教材页码或笔记名，可选）')
        row=ttk.Frame(footer); row.pack(fill='x',pady=7); app.button(row,'保存这张卡片',self.save)
        ttk.Label(row,text='AI 草稿需核对后逐张保存。').pack(side='left')
        self.list=ttk.Treeview(library,columns=('question','due'),show='headings',selectmode='browse'); self.list.heading('question',text='问题'); self.list.heading('due',text='下次复习时间（北京时间）'); self.list.column('due',width=190,stretch=False); self.list.pack(fill='both',expand=True)
        self.list.bind('<<TreeviewSelect>>',self.inspect)
        self.details=app.text(library,height=5); self.details.configure(state='disabled')
        row=ttk.Frame(library); row.pack(fill='x'); app.button(row,'删除所选卡片',self.delete)
    def show(self,widget,text):
        widget.configure(state='normal'); self.app.put(widget,text); widget.configure(state='disabled')
    def refresh(self):
        from datetime import timedelta
        course=self.app.course.get(); cards=self.store.cards(course); due=self.store.due(course)
        self.summary.config(text=f'{course} · 共 {len(cards)} 张卡片 · 到期 {len(due)} 张')
        self.current=due[0] if due else None; self.revealed=False
        self.show(self.question,self.current['question'] if self.current else '本轮复习完成，或还没有卡片。\n可以到「制作卡片 / 错题」添加知识点。')
        self.show(self.answer,'回忆后点击「显示答案」。' if self.current else '')
        for button in self.grade_buttons:button.configure(state='disabled')
        self.list.delete(*self.list.get_children())
        for card in cards:
            due_time=datetime.fromisoformat(card['due']).astimezone(timezone(timedelta(hours=8))).strftime('%m-%d %H:%M')
            self.list.insert('','end',iid=str(card['id']),values=(card['question'].replace('\n',' ')[:90],due_time))
        self.show(self.details,'选择卡片查看问题、答案和来源。')
    def reveal(self):
        if not self.current:return
        self.show(self.answer,self.current['answer']+'\n\n来源：'+(self.current['source'] or '手工卡片'))
        self.revealed=True
        for button in self.grade_buttons:button.configure(state='normal')
    def grade(self,rating):
        if not self.current or not self.revealed:return
        from datetime import timedelta
        due=self.store.grade(self.current['id'],rating)
        self.refresh(); self.feedback.config(text='已安排下次复习：'+due.astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')+'（北京时间）')
    def blank(self):
        self.app.put(self.front,''); self.app.put(self.back,''); self.source.set(''); self.draft_course=None; self.draft_choice.set('')
    def save(self):
        if self.draft_course and self.draft_course!=self.app.course.get():raise ValueError('这份 AI 草稿属于 '+self.draft_course+'，请先切回该课程')
        self.store.add(self.app.course.get(),self.app.get(self.front),self.app.get(self.back),self.source.get())
        index=self.draft_box.current()
        if index>=0 and self.drafts:
            self.drafts.pop(index); self.set_drafts()
        else:self.blank()
        self.refresh(); self.app.status.set('卡片已保存，可以开始复习')
    def ai_drafts(self):
        doc=self.app.selected_doc(); course=self.app.course.get(); settings=self.app.values(); key=self.app.key.get()
        evidence=self.app.context_evidence()
        task='根据资料制作 5 张用于主动回忆的问答卡，优先关键定义、理解和常见易错点。只返回 JSON 数组，每项包含 question 和 answer 两个字符串。每个答案标注资料编号；不得编造没有依据的内容。'
        def done(data):
            self.drafts=data; self.draft_source=f'资料 {doc["id"]} · {doc["title"]}'; self.draft_course=course; self.set_drafts()
            self.app.status.set('已生成卡片草稿，请检查答案和来源后逐张保存')
        self.app.run('Kimi 正在制作卡片草稿',lambda:parse_drafts(generate(settings,key,task,evidence)),done)
    def set_drafts(self):
        self.draft_box['values']=[f'{i+1}. {d["question"][:60]}' for i,d in enumerate(self.drafts)]
        if self.drafts:self.draft_box.current(0); self.load_draft()
        else:self.blank()
    def load_draft(self,event=None):
        index=self.draft_box.current()
        if index>=0:
            card=self.drafts[index]; self.app.put(self.front,card['question']); self.app.put(self.back,card['answer']); self.source.set(self.draft_source)
    def inspect(self,event=None):
        selection=self.list.selection()
        if selection:
            card=next(c for c in self.store.cards(self.app.course.get()) if c['id']==int(selection[0]))
            self.show(self.details,card['question']+'\n\n'+card['answer']+'\n\n来源：'+card['source'])
    def delete(self):
        selection=self.list.selection()
        if selection and messagebox.askyesno('删除卡片','同时删除这张卡片及其复习记录？'):
            self.store.delete(int(selection[0])); self.refresh()
