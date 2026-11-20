"""Render original PDF pages locally; extracted text is never used for display."""
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageTk
import pypdfium2 as pdfium

class PDFReader(ttk.Frame):
    def __init__(self, parent, on_page=None):
        super().__init__(parent)
        self.pdf=None; self.path=None; self.index=0; self.zoom=1.0; self.on_page=on_page; self.photo=None
        row=ttk.Frame(self); row.pack(fill='x',pady=5)
        for text,command in [('上一页',lambda:self.turn(-1)),('下一页',lambda:self.turn(1))]:
            ttk.Button(row,text=text,command=command,width=4).pack(side='left',padx=2)
        self.page_var=tk.StringVar(value='1'); entry=ttk.Entry(row,textvariable=self.page_var,width=5); entry.pack(side='left',padx=4); entry.bind('<Return>',lambda e:self.jump())
        ttk.Button(row,text='跳页',command=self.jump,width=3).pack(side='left')
        self.label=ttk.Label(row,text='未选择 PDF'); self.label.pack(side='left',padx=8)
        for text,command in [('−',lambda:self.scale(.8)),('+',lambda:self.scale(1.25)),('适宽',self.fit)]:
            ttk.Button(row,text=text,command=command,width=3).pack(side='right',padx=2)
        area=ttk.Frame(self); area.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(area,bg='#dce1ea',highlightthickness=0)
        vertical=ttk.Scrollbar(area,orient='vertical',command=self.canvas.yview)
        horizontal=ttk.Scrollbar(area,orient='horizontal',command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        area.rowconfigure(0,weight=1); area.columnconfigure(0,weight=1)
        self.canvas.grid(row=0,column=0,sticky='nsew'); vertical.grid(row=0,column=1,sticky='ns'); horizontal.grid(row=1,column=0,sticky='ew')
        self.canvas.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-int(e.delta/120)*3,'units'))
        self.canvas.bind('<Control-MouseWheel>',self.wheel_zoom)
    def wheel_zoom(self,event):
        self.scale(1.15 if event.delta>0 else 1/1.15); return 'break'
    def clear(self,message='选择 PDF 后在这里阅读原版页面。'):
        if self.pdf:self.pdf.close()
        self.pdf=None; self.path=None; self.photo=None; self.canvas.delete('all')
        self.canvas.create_text(25,35,text=message,anchor='nw',width=520,font=('Microsoft YaHei UI',11),fill='#48536c')
        self.label.config(text='未选择 PDF'); self.canvas.configure(scrollregion=(0,0,550,100))
    def load(self,path,page=0):
        self.clear(); self.path=path
        try:
            self.pdf=pdfium.PdfDocument(str(path))
            if not len(self.pdf):raise ValueError('PDF 没有页面')
            self.index=max(0,min(page,len(self.pdf)-1)); self.fit()
        except Exception as error:self.clear('无法打开 PDF：'+str(error)+'\n可尝试使用系统阅读器打开。')
    def fit(self):
        if not self.pdf:return
        self.update_idletasks()
        page=self.pdf[self.index]
        try:self.zoom=max(.2,min(3.0,(max(300,self.canvas.winfo_width())-24)/page.get_width()))
        finally:page.close()
        self.render()
    def scale(self,factor):
        self.zoom=max(.2,min(3.0,self.zoom*factor)); self.render()
    def turn(self,delta):
        if self.pdf:self.index=max(0,min(len(self.pdf)-1,self.index+delta)); self.render()
    def jump(self):
        if not self.pdf:return
        try:
            value=int(self.page_var.get())
            if not 1<=value<=len(self.pdf):raise ValueError()
        except ValueError:messagebox.showinfo('页码','请输入 1 至 '+str(len(self.pdf))+' 的页码'); return
        self.index=value-1; self.render()
    def render(self):
        if not self.pdf:return
        page=self.pdf[self.index]
        try:
            # Bound memory even for unusually large page dimensions.
            scale=min(self.zoom,3200/max(page.get_size()))
            bitmap=page.render(scale=scale)
            try:
                image=bitmap.to_pil().copy()
                self.photo=ImageTk.PhotoImage(image,master=self)
            finally:bitmap.close()
        finally:page.close()
        self.canvas.delete('all'); self.canvas.create_image(12,12,image=self.photo,anchor='nw')
        self.canvas.configure(scrollregion=(0,0,self.photo.width()+24,self.photo.height()+24)); self.canvas.yview_moveto(0); self.canvas.xview_moveto(0)
        self.page_var.set(str(self.index+1)); self.label.config(text=f'/ {len(self.pdf)} 页 · {round(scale*100)}%')
        if self.on_page:self.on_page(self.index)
    def destroy(self):
        if self.pdf:self.pdf.close(); self.pdf=None
        super().destroy()
