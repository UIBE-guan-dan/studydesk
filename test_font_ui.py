import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from tkinter import font
import app
from core import Store,ROOT
class FontTests(unittest.TestCase):
 def test_sizes_restore_and_new_dialog(self):
  with tempfile.TemporaryDirectory(dir=ROOT) as folder:
   store=Store(Path(folder)/'study.db')
   with patch.object(app,'Store',return_value=store):ui=app.App()
   ui.withdraw();ui.update()
   def size(w):return font.Font(root=ui,font=w.cget('font')).actual()['size']
   try:
    baseline=size(ui.page_title);ui.body_font_size.set(20);ui.ui_font_size.set(20);ui.save_font_sizes();self.assertEqual(size(ui.editor),20);self.assertEqual(size(ui.transcript),20);self.assertEqual(size(ui.page_title),baseline+10)
    ui.apply_font_sizes();self.assertEqual(size(ui.page_title),baseline+10)
    win=tk.Toplevel(ui);text=tk.Text(win);text.pack();ui.update();self.assertEqual(size(text),20);win.destroy()
    saved=json.loads(ui.appearance_path.read_text());self.assertEqual(saved,{'interface':20,'body':20})
   finally:ui.destroy()
   with patch.object(app,'Store',return_value=store):ui=app.App()
   try:
    self.assertEqual(ui.ui_font_size.get(),20);self.assertEqual(ui.body_font_size.get(),20);self.assertEqual(size(ui.editor),20);ui.reset_font_sizes();self.assertEqual(size(ui.editor),11)
   finally:ui.destroy()
if __name__=='__main__':unittest.main()
