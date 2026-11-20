"""Read inclusive PDF file-page ranges without silently truncating evidence."""
import pypdfium2 as pdfium

def validate_range(start,end,total,max_pages=50):
    try:start,end=int(start),int(end)
    except (ValueError,TypeError):raise ValueError('起始页和结束页必须为整数') from None
    if not 1<=start<=end<=total:raise ValueError(f'请输入 1–{total} 内的有效范围，起始页不能大于结束页')
    if end-start+1>max_pages:raise ValueError(f'一次最多选择 {max_pages} 页。请按章节分段整理，以免遗漏内容。')
    return start,end

def extract_pdf_range(path,title,doc_id,start,end,max_chars=48000,max_pages=50):
    with pdfium.PdfDocument(str(path)) as pdf:
        start,end=validate_range(start,end,len(pdf),max_pages)
        parts=[]; empty=[]; characters=0
        for index in range(start-1,end):
            page=pdf[index]
            try:
                textpage=page.get_textpage()
                try:text=textpage.get_text_range().strip()
                finally:textpage.close()
            finally:page.close()
            if len(''.join(text.split()))<20:empty.append(index+1)
            characters+=len(text)
            if max_chars is not None and characters>max_chars:raise ValueError(f'所选范围超过 {max_chars} 字的单次上限，请缩小页数范围。未发送 AI 请求，也没有截断正文。')
            parts.append(f'[资料 {doc_id} · {title} · PDF 第 {index+1} 页]\n{text or "（本页没有可提取文字）"}')
    if characters<80:raise ValueError('所选页面缺少足够的可提取正文。扫描页请先 OCR；图表页可以连同前后正文一起选择。')
    return {'evidence':'\n\n'.join(parts),'empty_pages':empty,'characters':characters,'start':start,'end':end}
