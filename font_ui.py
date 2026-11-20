"""Persistent interface and reading text sizes, independent of AI settings."""
import json
import tkinter as tk
from tkinter import ttk,font
from pathlib import Path

class FontSizeUX:
    def __init__(self):
        self._font_widgets={};self._font_pending=None
        super().__init__()
        self.apply_font_sizes()
        self.bind_all('<Map>',self.queue_font_update,add='+')
    def config(self):
        super().config()
        self.appearance_path=Path(self.store.path).parent/'appearance.json'
        try:preferences=json.loads(self.appearance_path.read_text(encoding='utf-8'))
        except (OSError,ValueError):preferences={}
        def value(key,default,low,high):
            try:return max(low,min(high,int(preferences.get(key,default))))
            except (ValueError,TypeError,AttributeError):return default
        self.ui_font_size=tk.IntVar(value=value('interface',10,9,20))
        self.body_font_size=tk.IntVar(value=value('body',11,10,24))
        page=self.pages['Kimi 与设置'];row=ttk.Frame(page,padding=(0,0,0,15))
        row.pack(side='top',fill='x',before=page.winfo_children()[0])
        ttk.Label(row,text='字体大小',font=('Microsoft YaHei UI',13,'bold')).pack(side='left',padx=(0,16))
        for title,var,values in [('界面',self.ui_font_size,list(range(9,21))),('笔记与转写正文',self.body_font_size,list(range(10,25)))]:
            ttk.Label(row,text=title).pack(side='left',padx=(0,6))
            box=ttk.Combobox(row,textvariable=var,values=values,state='readonly',width=4);box.pack(side='left',padx=(0,14));box.bind('<<ComboboxSelected>>',lambda e:self.safe(self.save_font_sizes))
        self.button(row,'恢复默认字号',self.reset_font_sizes)
        ttk.Label(row,text='立即生效并自动保存；PDF 请用阅读器缩放。',style='Muted.TLabel').pack(side='left')
    def reset_font_sizes(self):
        self.ui_font_size.set(10);self.body_font_size.set(11);self.save_font_sizes()
    def save_font_sizes(self):
        self.apply_font_sizes()
        self.appearance_path.write_text(json.dumps({'interface':self.ui_font_size.get(),'body':self.body_font_size.get()},ensure_ascii=False,indent=2),encoding='utf-8')
        self.status.set('字号已保存，下次启动继续使用；PDF 可单独缩放')
    def queue_font_update(self,event=None):
        if self._font_pending is None:self._font_pending=self.after_idle(self.apply_font_sizes)
    def apply_font_sizes(self):
        if self._font_pending is not None:
            self.after_cancel(self._font_pending);self._font_pending=None
        if not hasattr(self,'ui_font_size'):return
        size=self.ui_font_size.get();body=self.body_font_size.get();delta=size-10
        self.sidebar.configure(width=180+max(0,delta)*8)
        style=ttk.Style(self)
        style.configure('.',font=('Microsoft YaHei UI',size))
        style.configure('Muted.TLabel',font=('Microsoft YaHei UI',max(8,size-1)))
        style.configure('Heading.TLabel',font=('Microsoft YaHei UI',22+delta,'bold'))
        style.configure('Treeview',font=('Microsoft YaHei UI',size),rowheight=43+delta*3)
        style.configure('Treeview.Heading',font=('Microsoft YaHei UI',size))
        self.option_add('*TCombobox*Listbox.font',('Microsoft YaHei UI',size))
        def visit(w):
            try:
                if 'font' in w.keys():
                    original=self._font_widgets.get(w)
                    if original is None:
                        spec=w.cget('font')
                        if spec:
                            original=font.Font(root=self,font=spec).actual();self._font_widgets[w]=original
                    if original:
                        desired=body if isinstance(w,tk.Text) else max(8,abs(original['size'])+delta)
                        w.configure(font=(original['family'],desired,original['weight'],original['slant']))
                if isinstance(w,ttk.Treeview):w.tag_configure('group',font=('Microsoft YaHei UI',size,'bold'))
                for child in w.winfo_children():visit(child)
            except tk.TclError:pass
        visit(self)
        self._font_widgets={w:v for w,v in self._font_widgets.items() if w.winfo_exists()}
    def render_tree(self):
        super().render_tree()
        if hasattr(self,'ui_font_size'):self.tree.tag_configure('group',font=('Microsoft YaHei UI',self.ui_font_size.get(),'bold'))
