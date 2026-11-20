# 知课 StudyDesk

面向大学生的 Windows 桌面学习助手。支持 PDF 原版阅读、课程笔记、课堂录音转写与教材对照、AI 练习卷、记忆卡片和课程任务。

## 下载与运行

这是源码版项目，暂不提供独立 exe。GitHub 页面点击 Code → Download ZIP，解压后按以下步骤运行。

建议使用 Windows 10/11 与 Python 3.11–3.13（包含 Tkinter），在项目文件夹打开终端：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

音频转写和录音是可选功能：

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-audio.txt
```

安装依赖后可双击 `start.vbs` 启动。初次使用 Whisper 模型需要联网下载，耗时与内存占用取决于所选模型。默认 large-v3-turbo，配置较低时可手动选择 small。SenseVoice 需要另行下载模型到 `data/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17`，参见 [sherpa-onnx 模型文档](https://k2-fsa.github.io/sherpa/onnx/sense-voice/pretrained.html)。

## 基本使用

1. 新建课程，在“资料与笔记”导入教材 PDF 或笔记。
2. 在“设置”填写自己的 Kimi API 地址、密钥和模型；可以调节界面和正文字号。
3. 阅读教材时记录页边笔记、使用阅读助手，或在“练习与出卷”选页码生成题目卷与答案 PDF。
4. “课堂整理”支持本地转写、教材匹配和高亮回听；开始录音前须确认已获老师允许。
5. “课程任务”管理截止时间、小组分工、引用摘录；小组资料包以文件方式交换，不实时同步。

## 数据与使用边界

- 本仓库不包含用户教材、录音、笔记、数据库、密钥或已下载的模型。
- 数据存储于本地 `data/`。备份时关闭软件，再复制该文件夹。
- API Key 仅在当前会话使用，不写入配置文件。AI 请求会把相应教材片段或转写文本发往你配置的服务；调用费用由你的账户承担。
- 录音前请获得课程老师允许。分享资料包前请确认文件可以共享。
- PDF 匹配和出题当前主要使用文字层；扫描件需先 OCR。AI 生成内容与高亮匹配需人工核对，不保证逐字对齐或题目完全正确。
- 长章节分批处理，出卷支持完成批次缓存与超时重试。截止提醒只在软件打开时更新。

## 开发与验证

```powershell
.venv\Scripts\python.exe -m unittest discover -p "test_*.py"
```

部分测试需要 Windows 图形桌面与可选音频依赖。接口测试使用模拟响应，不代表真实服务持续可用。

## 依赖与许可证

项目源码采用 MIT 许可证，见 LICENSE。第三方库与模型保留各自许可证，不因本项目许可证而改变。主要依赖包括 pypdf、pypdfium2、Pillow、ReportLab、Markdown、matplotlib、py-fsrs，以及可选的 faster-whisper、PyAV、sounddevice、sherpa-onnx。

欢迎通过 Issues 提交复现步骤和脱敏错误信息，通过 Pull Requests 改进功能。请勿上传密钥、个人课程文件或同学的录音。
