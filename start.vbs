Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder
python = "pythonw.exe"
If fso.FileExists(folder & "\.venv\Scripts\pythonw.exe") Then python = folder & "\.venv\Scripts\pythonw.exe"
shell.Run """" & python & """ """ & folder & "\app.py""", 0, False
