"""Kılavuz Markdown'ını gerçek görseller ve otomatik içindekilerle PDF'ye dönüştürür."""
from pathlib import Path
from xml.sax.saxutils import escape
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import re
import matplotlib
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                               Spacer, Image, PageBreak, KeepTogether)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT=Path(__file__).resolve().parent
FONT=Path(matplotlib.get_data_path())/'fonts/ttf'
for name,file in [('Body','DejaVuSans.ttf'),('Bold','DejaVuSans-Bold.ttf'),('Code','DejaVuSansMono.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Body',boldItalic='Bold')
W,H=A4
M=43
CW=W-2*M
INK=colors.HexColor('#142F40'); ACCENT=colors.HexColor('#007D79'); MUTED=colors.HexColor('#5D707B')
styles={
 'body':ParagraphStyle('body',fontName='Body',fontSize=9.3,leading=14.4,textColor=INK,spaceAfter=9),
 'title':ParagraphStyle('title',fontName='Bold',fontSize=31,leading=39,textColor=INK,spaceAfter=18),
 'h':ParagraphStyle('h',fontName='Bold',fontSize=20,leading=27,textColor=INK,spaceAfter=17,keepWithNext=True),
 'sub':ParagraphStyle('sub',fontName='Bold',fontSize=11,leading=16,textColor=ACCENT,spaceAfter=11),
 'caption':ParagraphStyle('caption',fontName='Body',fontSize=7.7,leading=11,textColor=MUTED,spaceAfter=13),
 'toc':ParagraphStyle('toc',fontName='Body',fontSize=10,leading=16,textColor=INK,spaceBefore=5,leftIndent=0,firstLineIndent=0,rightIndent=25),
}

def rich(text):
    text=escape(text)
    text=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',text)
    return re.sub(r'`([^`]+)`',r'<font name="Code">\1</font>',text)

def p(text,style='body',raw=False):
    return Paragraph(text if raw else rich(text),styles[style])

manifest=json.loads((ROOT/'gorseller/manifest.json').read_text())
date=datetime.fromisoformat(manifest['captured_at'].replace('Z','+00:00')).astimezone(ZoneInfo('Europe/Istanbul')).strftime('%d.%m.%Y')

def photo(file,caption,max_height=None):
    path=ROOT/file
    if not path.is_file(): raise FileNotFoundError(path)
    img=Image(str(path))
    # Uzun panellerden ayrıntı görüntüleri dar; geniş ekranlar sayfa genişliğinde tutulur.
    if max_height is None:
        max_height=250 if img.imageHeight>img.imageWidth else 280
    scale=min(CW/img.imageWidth,max_height/img.imageHeight,0.75)
    img.drawWidth=img.imageWidth*scale;img.drawHeight=img.imageHeight*scale;img.hAlign='LEFT'
    return KeepTogether([img,Spacer(1,7),p(caption,'caption')])

def decorate(c,doc):
    c.setFillColor(ACCENT);c.rect(0,H-8,W,8,fill=1,stroke=0)
    c.setFont('Bold',8);c.setFillColor(INK);c.drawString(M,H-33,'HİSAR / ARAYÜZ KULLANIM KILAVUZU')
    c.setFont('Body',7.5);c.setFillColor(MUTED);c.drawRightString(W-M,H-33,'SÜRÜM 2.0')
    c.setStrokeColor(colors.HexColor('#D7E4E7'));c.line(M,41,W-M,41)
    c.drawString(M,26,f'Güncel arayüz görselleri · {date}');c.drawRightString(W-M,26,f'{doc.page:02d}')

class GuideDoc(BaseDocTemplate):
    def afterFlowable(self,flowable):
        if hasattr(flowable,'chapter_key'):
            title=flowable.getPlainText();key=flowable.chapter_key
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title,key,level=0,closed=False)
            self.notify('TOCEntry',(0,title,self.page,key))

text=(ROOT/'kilavuz.md').read_text(encoding='utf-8')
sections=re.split(r'^## ',text,flags=re.M)[1:]
story=[Spacer(1,25),p('EKRANLAR • KONTROLLER • GÖRÜNTÜLEME','sub'),p('Arayüz<br/>Kullanım Kılavuzu','title',True),
       p('HİSAR · Sivil alan güvenliği uygulaması','sub'),
       photo('gorseller/acik-tema.png','Çalışan uygulamadan alınan genel görünüm.',max_height=305),
       Spacer(1,12),p('Harita ve panellerden zaman çizelgesine, kayıt detaylarından bildirim ve belge kontrollerine kadar mevcut arayüzün açıklamalı rehberi.'),
       p('Ekran adları uygulamayla eşleştirmek için aynen korunmuştur. Kılavuz arayüz işlevlerini açıklar; değerlendirme veya müdahale önerisi içermez.','caption'),
       p(f'{len(sections)} bölüm · {date} · Sürüm 2.0','sub'),PageBreak(),p('İçindekiler','h'),
       p('Bölüm başlıkları tıklanabilir. PDF okuyucunuzun yer imleri panelinden de gezinebilirsiniz.','caption')]
toc=TableOfContents();toc.levelStyles=[styles['toc']];story.append(toc)
for i,section in enumerate(sections,1):
    title,_,body=section.partition('\n')
    heading=p(title,'h');heading.chapter_key=f'bolum-{i}'
    story += [PageBreak(),heading]
    for block in re.split(r'\n\s*\n',body.strip()):
        block=block.strip()
        if not block:continue
        match=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',block,re.S)
        if match:
            caption,file=match.groups();story.append(photo(file,caption))
        else:story.append(p(block))
output=ROOT/'kullanim-kilavuzu.pdf'
doc=GuideDoc(str(output),pagesize=A4,leftMargin=M,rightMargin=M,topMargin=59,bottomMargin=58,title='HİSAR — Arayüz Kullanım Kılavuzu',author='HİSAR',subject='Ekranlar ve mevcut arayüz kontrolleri',pageCompression=1)
frame=Frame(M,58,CW,H-117,id='body',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
doc.addPageTemplates(PageTemplate(id='guide',frames=[frame],onPage=decorate))
doc.multiBuild(story)
print(output)
