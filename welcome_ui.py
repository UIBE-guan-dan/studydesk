"""First-run guidance and explicit model preparation for desktop users."""
import json
import os
import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk


class WelcomeUX:
    def __init__(self):
        super().__init__()
        self.welcome_marker = Path(self.store.path).parent / 'welcome.json'
        if not self.welcome_marker.exists():
            self.after(600, self.show_welcome)

    def config(self):
        super().config()
        row = ttk.Frame(self.pages['Kimi 与设置'])
        row.pack(side='bottom', fill='x', pady=10)
        self.button(row, '首次使用指南', self.show_welcome)
        self.button(row, '下载 / 检查语音模型', self.prepare_model)
        self.button(row, '打开数据文件夹', lambda: os.startfile(str(Path(self.store.path).parent)))

    def show_welcome(self):
        w = tk.Toplevel(self); w.title('欢迎使用知课 StudyDesk')
        w.transient(self); w.geometry('680x430')
        frame = ttk.Frame(w, padding=24); frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='从一本教材开始', font=('Microsoft YaHei UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='① 新建课程，在“资料与笔记”导入 PDF。\n\n'
                  '② AI 整理与出卷：在设置中填写自己的 Kimi API Key，\n'
                  '    获取模型列表后选择模型。密钥只在本次运行中使用。\n\n'
                  '③ 课堂录音：先取得老师允许，再录音或导入音频。\n'
                  '    本地转写需先下载语音模型；下载失败可以重试。\n\n'
                  '阅读和记笔记可离线使用。AI 接口费用由自己的账户承担。',
                  wraplength=610).pack(anchor='w', pady=20)
        row=ttk.Frame(frame); row.pack(fill='x')
        def finish(settings=False):
            self.welcome_marker.write_text(json.dumps({'seen': True}), encoding='utf-8')
            w.destroy()
            if settings: self.navigate('Kimi 与设置')
        ttk.Button(row, text='配置 AI 与语音模型', command=lambda: finish(True)).pack(side='left', padx=(0,10))
        ttk.Button(row, text='先阅读教材', command=finish).pack(side='left')

    def prepare_model(self):
        if getattr(self, '_model_downloading', False):
            raise ValueError('语音模型仍在下载，请等待当前下载完成。')
        name=self.local_model.get()
        if name == 'sensevoice':
            raise ValueError('SenseVoice 请按 README 安装模型；一键下载请选择 base、small 或 large-v3-turbo。')
        from faster_whisper.utils import _MODELS
        if name not in _MODELS: raise ValueError('请选择列表中的 Whisper 模型。')
        folder=Path(self.store.path).parent/'models'/('faster-whisper-'+name)
        w=tk.Toplevel(self); w.title('准备本地语音模型'); w.geometry('650x270'); w.transient(self)
        f=ttk.Frame(w,padding=20); f.pack(fill='both',expand=True)
        ttk.Label(f,text=f'下载模型：{name}',font=('Microsoft YaHei UI',14,'bold')).pack(anchor='w')
        ttk.Label(f,text='从 Hugging Face 下载；较大模型可能需要数 GB 空间。\n文件会保存在本机，后续转写无需再次下载。',wraplength=600).pack(anchor='w',pady=12)
        state=tk.StringVar(value='正在连接模型服务器…')
        ttk.Label(f,textvariable=state,wraplength=600).pack(anchor='w')
        progress=ttk.Progressbar(f,mode='indeterminate');progress.pack(fill='x',pady=12);progress.start()
        events=queue.Queue(); self._model_downloading=True
        w.protocol('WM_DELETE_WINDOW',lambda: state.set('下载仍在进行；完成或失败后可关闭此窗口。'))
        def worker():
            try:
                from huggingface_hub import snapshot_download
                from tqdm.auto import tqdm
                class FileProgress(tqdm):
                    def update(bar,n=1):
                        result=super().update(n)
                        if bar.total: events.put(('progress',f'已处理 {int(bar.n)} / {int(bar.total)} 个模型文件（大文件下载可能较久）'))
                        return result
                snapshot_download(_MODELS[name],local_dir=str(folder),
                    allow_patterns=['config.json','preprocessor_config.json','model.bin','tokenizer.json','vocabulary.*','README.md','LICENSE*'],
                    tqdm_class=FileProgress)
                if not all((folder/x).is_file() for x in ('config.json','model.bin','tokenizer.json')):
                    raise ValueError('模型文件不完整，请重试。')
                events.put(('done','模型已准备好，现在可以导入录音进行本地转写。'))
            except Exception as e: events.put(('error',f'下载未完成：{e}\n请检查网络后重试，已缓存文件会复用。'))
        def poll():
            try:
                while True:
                    kind,value=events.get_nowait();state.set(value)
                    if kind != 'progress':
                        self._model_downloading=False;progress.stop()
                        w.protocol('WM_DELETE_WINDOW',w.destroy)
                        ttk.Button(f,text='关闭' if kind=='done' else '关闭后重试',command=w.destroy).pack(anchor='e')
                        return
            except queue.Empty: pass
            self.after(200,poll)
        threading.Thread(target=worker,daemon=True).start();poll()
