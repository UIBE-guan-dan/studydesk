"""Local Markdown-to-PDF typesetting. Never rewrites source note text."""
import hashlib, html, io, re, unicodedata, xml.etree.ElementTree as ET
from pathlib import Path
import markdown
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.pagesizes import A4

VERSION='study-notes-v3'

def fonts():
    if 'StudyText' not in pdfmetrics.getRegisteredFontNames():
        folder=Path('C:/Windows/Fonts')
        pdfmetrics.registerFont(TTFont('StudyText',str(folder/'msyh.ttc'),subfontIndex=0))
        pdfmetrics.registerFont(TTFont('StudyBold',str(folder/'msyhbd.ttc'),subfontIndex=0))
        pdfmetrics.registerFontFamily('StudyText',normal='StudyText',bold='StudyBold',italic='StudyText',boldItalic='StudyBold')
        import matplotlib
        pdfmetrics.registerFont(TTFont('StudySymbols',str(Path(matplotlib.get_data_path())/'fonts/ttf/DejaVuSans.ttf')))

def build_note_pdf(title,body,folder):
    fonts(); folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256((VERSION+'exam-header-v1\n'+title+'\n'+body).encode()).hexdigest()
    output=folder/(digest+'.pdf')
    if output.exists():return output
    width=A4[0]-104; math_images={}
    def render_formula(expr):
        expr=expr.strip()
        token='STUDYMATH'+str(len(math_images))+'TOKEN'
        try:
            from matplotlib.mathtext import math_to_image
            from matplotlib.font_manager import FontProperties
            from PIL import Image
            dest=folder/(hashlib.sha256(expr.encode()).hexdigest()+'.png')
            math_to_image('$'+expr+'$',str(dest),prop=FontProperties(size=13),dpi=180,format='png',color='#253856')
            with Image.open(dest) as image:w,h=image.size
            factor=min(72/180,width/w,30/h)
            math_images[token]=f'<img src="{html.escape(str(dest),quote=True)}" width="{w*factor:.2f}" height="{h*factor:.2f}" valign="middle"/>'
        except Exception:
            math_images[token]=html.escape('［公式原文：'+expr+'］')
        return token
    def formula(match):return render_formula(next(g for g in match.groups() if g is not None))
    body=re.sub(r'\$\$(.*?)\$\$|\\\[(.*?)\\\]|(?<!\\)\$([^$\n]+)\$|\\\((.*?)\\\)',formula,body,flags=re.S)
    # Preserve Unicode hats/bars/subscripts as mathematical glyphs, not missing-font boxes.
    greek={'β':r'\beta','σ':r'\sigma','ε':r'\epsilon','α':r'\alpha','μ':r'\mu','Σ':r'\Sigma'}
    subs=str.maketrans('₀₁₂₃₄₅₆₇₈₉ᵢⱼ','0123456789ij')
    def decorated(match):
        letter,marks,index=match.groups()
        if not marks and not index:return match.group(0)
        expr=greek.get(letter,letter)
        for mark in marks:
            if mark=='\u0302':expr=r'\hat{'+expr+'}'
            elif mark=='\u0304':expr=r'\bar{'+expr+'}'
            else:return match.group(0)
        if index:expr+='_{'+index.translate(subs)+'}'
        return render_formula(expr)
    body=re.sub(r'([A-Za-zβσεαμΣ])([\u0300-\u036f]*)([₀-₉ᵢⱼ]*)',decorated,unicodedata.normalize('NFD',body))
    # Markdown emits HTML; unsupported markup is escaped rather than executed.
    rendered=markdown.markdown(body,extensions=['tables','fenced_code','sane_lists'])
    try:root=ET.fromstring('<root>'+rendered.replace('<br>','<br/>').replace('<hr>','<hr/>')+'</root>')
    except ET.ParseError:
        root=ET.Element('root'); ET.SubElement(root,'p').text=body
    styles={
        'body':ParagraphStyle('body',fontName='StudyText',fontSize=10.5,leading=18.5,textColor=colors.HexColor('#293953'),spaceAfter=9,wordWrap='CJK'),
        'h1':ParagraphStyle('h1',fontName='StudyBold',fontSize=22,leading=31,textColor=colors.HexColor('#173968'),spaceAfter=17,keepWithNext=True,wordWrap='CJK'),
        'h2':ParagraphStyle('h2',fontName='StudyBold',fontSize=14,leading=22,textColor=colors.HexColor('#315bb4'),spaceBefore=17,spaceAfter=9,keepWithNext=True,wordWrap='CJK'),
        'h3':ParagraphStyle('h3',fontName='StudyBold',fontSize=11.5,leading=19,textColor=colors.HexColor('#263d62'),spaceBefore=10,spaceAfter=7,keepWithNext=True,wordWrap='CJK'),
        'quote':ParagraphStyle('quote',fontName='StudyText',fontSize=9.5,leading=17,textColor=colors.HexColor('#596b83'),backColor=colors.HexColor('#edf3fc'),borderPadding=10,leftIndent=12,rightIndent=12,spaceBefore=9,spaceAfter=15,wordWrap='CJK'),
        'cell':ParagraphStyle('cell',fontName='StudyText',fontSize=9,leading=15,textColor=colors.HexColor('#293953'),wordWrap='CJK'),
    }
    # ReportLab's CJK line breaker cannot handle inline image fragments.
    # Its regular breaker splits long CJK runs while preserving formula images.
    for style in styles.values():style.wordWrap=None
    def clean(text):
        text=(text or '').replace('\ufe0f','').replace('⚠','提示：')
        supported=pdfmetrics.getFont('StudyText').face.charToGlyph
        value=''.join(html.escape(ch) if ord(ch) in supported or ch.isspace() else '<font name="StudySymbols">'+html.escape(ch)+'</font>' for ch in text)
        for token,replacement in math_images.items():value=value.replace(token,replacement)
        return value
    def inline(node):
        value=clean(node.text)
        for child in node:
            tag=child.tag
            content=inline(child)
            if tag in ('strong','b'):value+='<b>'+content+'</b>'
            elif tag in ('em','i'):value+='<i>'+content+'</i>'
            elif tag=='br':value+='<br/>'
            elif tag=='code':value+='<font color="#315bb4">'+content+'</font>'
            else:value+=content
            value+=clean(child.tail)
        return value
    story=[]
    if not list(root) or list(root)[0].tag!='h1':story.append(Paragraph(clean(title),styles['h1']))
    def emit(node,depth=0,prefix=''):
        tag=node.tag
        if tag in ('h1','h2','h3','h4','h5','h6'):
            story.append(Paragraph(inline(node),styles[tag if tag in styles else 'h3']))
        elif tag=='blockquote':
            story.append(Paragraph('<br/><br/>'.join(inline(c) for c in node if ''.join(c.itertext()).strip()),styles['quote']))
        elif tag in ('ul','ol'):
            for i,child in enumerate(node):emit(child,depth+1,(str(i+1)+'. ' if tag=='ol' else '• '))
        elif tag=='li':
            text=clean(node.text)
            for child in node:
                if child.tag not in ('ul','ol'):
                    part=inline(child)
                    if child.tag=='strong':part='<b>'+part+'</b>'
                    text+=part+clean(child.tail)
            style=ParagraphStyle('list',parent=styles['body'],leftIndent=12*depth,spaceAfter=6)
            story.append(Paragraph(clean(prefix)+text,style))
            for child in node:
                if child.tag in ('ul','ol'):emit(child,depth)
        elif tag=='table':
            rows=[]
            for tr in node.iter('tr'):
                rows.append([Paragraph(('<b>'+inline(cell)+'</b>') if cell.tag=='th' else inline(cell),styles['cell']) for cell in tr])
            if rows:
                count=max(len(row) for row in rows); rows=[r+[Paragraph('',styles['cell'])]*(count-len(r)) for r in rows]
                widths=([width*.27,width*.73] if count==2 else [width/count]*count)
                table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
                table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6edf9')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f7fb')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#c7d6ef'))]))
                story.extend([table,Spacer(1,14)])
        elif tag=='hr':story.extend([Spacer(1,3),HRFlowable(width='100%',thickness=.5,color=colors.HexColor('#dce5f1')),Spacer(1,8)])
        elif tag=='pre':story.append(Paragraph(inline(node).replace('\n','<br/>'),styles['quote']))
        elif tag=='p':story.append(Paragraph(inline(node),styles['body']))
        else:
            text=inline(node)
            if text:story.append(Paragraph(text,styles['body']))
    for node in root:emit(node)
    def page_decoration(canvas,doc):
        canvas.saveState(); canvas.setFont('StudyText',8); canvas.setFillColor(colors.HexColor('#7d8ca2'))
        canvas.drawString(52,A4[1]-32,'知课 StudyDesk  /  '+('练习试卷' if '卷' in title or '答案解析' in title else '学习笔记'))
        canvas.drawRightString(A4[0]-52,28,f'{doc.page}'); canvas.setStrokeColor(colors.HexColor('#e0e7f0')); canvas.line(52,43,A4[0]-52,43); canvas.restoreState()
    temporary=output.with_suffix('.tmp.pdf')
    try:
        SimpleDocTemplate(str(temporary),pagesize=A4,rightMargin=52,leftMargin=52,topMargin=58,bottomMargin=60,title=title,author='StudyDesk').build(story,onFirstPage=page_decoration,onLaterPages=page_decoration)
        temporary.replace(output)
    finally:
        if temporary.exists():temporary.unlink()
    return output
