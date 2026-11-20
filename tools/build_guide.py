#!/usr/bin/env python3
"""Build the curated Hungarian installation guide from this repository.

Run from any directory: python tools/build_guide.py
Dependency: reportlab. Set DRONELOG_FONT_DIR if DejaVu fonts are elsewhere.
Sources: docs/KEZDES_WINDOWS.md, docs/ELLENORZES.md, README.md and stack.yml.
The guide is instructional; it never turns development checks into Swarm evidence.
"""
from __future__ import annotations
import os
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'DroneLog_Telepitesi_utmutato.pdf'
FONT_DIR = Path(os.environ.get('DRONELOG_FONT_DIR', '/usr/share/fonts/truetype/dejavu'))
for name, file in [('Sans','DejaVuSans.ttf'),('Sans-Bold','DejaVuSans-Bold.ttf'),('Sans-Oblique','DejaVuSans-Oblique.ttf'),('Mono','DejaVuSansMono.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
pdfmetrics.registerFontFamily('Sans', normal='Sans', bold='Sans-Bold', italic='Sans-Oblique', boldItalic='Sans-Bold')
NAVY=colors.HexColor('#123244'); TEAL=colors.HexColor('#087f78'); INK=colors.HexColor('#243e4e'); MUTED=colors.HexColor('#5e7480'); LINE=colors.HexColor('#dbe5e9'); PALE=colors.HexColor('#eef6f5'); BG=colors.HexColor('#f4f7f9')
WIDTH=A4[0]-96
STYLES={
 'body':ParagraphStyle('body',fontName='Sans',fontSize=9.7,leading=14.5,textColor=INK,spaceAfter=8),
 'small':ParagraphStyle('small',fontName='Sans',fontSize=8.3,leading=12,textColor=MUTED,spaceAfter=7),
 'h1':ParagraphStyle('h1',fontName='Sans-Bold',fontSize=23,leading=29,textColor=NAVY,spaceAfter=14),
 'h2':ParagraphStyle('h2',fontName='Sans-Bold',fontSize=12,leading=16,textColor=NAVY,spaceBefore=8,spaceAfter=7),
 'eyebrow':ParagraphStyle('eyebrow',fontName='Sans-Bold',fontSize=8,leading=11,textColor=TEAL,spaceAfter=7),
 'cell':ParagraphStyle('cell',fontName='Sans',fontSize=8.4,leading=12.2,textColor=INK),
 'headcell':ParagraphStyle('headcell',fontName='Sans-Bold',fontSize=8.3,leading=12,textColor=colors.white),
}

def p(text,style='body'): return Paragraph(text.replace('–','-').replace('—','-').replace('‑','-'), STYLES[style])
def plain(text): return escape(text).replace('`','')
def h2(text): return p(text,'h2')
def gap(n=6):return Spacer(1,n)
def bullet(text):return p('<font color="#087f78">•</font> '+text)
def code(text):return Code(text.strip('\n'))

def table(headers, rows, widths=None, small=False):
    widths=widths or [WIDTH/len(headers)]*len(headers)
    data=[[p(h,'headcell') for h in headers]] + [[p(str(v),'cell') for v in row] for row in rows]
    t=Table(data,colWidths=widths,hAlign='LEFT',repeatRows=1)
    t.setStyle(TableStyle([
      ('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),
      ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
      ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
      ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,BG]),
      ('LINEBELOW',(0,0),(-1,0),.6,NAVY),('LINEBELOW',(0,1),(-1,-1),.35,LINE)
    ]))
    return t

def callout(title,text):
    t=Table([[p(title,'h2')],[p(text,'body')]],colWidths=[WIDTH])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('LINEBEFORE',(0,0),(0,-1),3,TEAL),('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14),('TOPPADDING',(0,0),(-1,0),6),('BOTTOMPADDING',(0,-1),(-1,-1),8)]))
    return t

class Code(Flowable):
    def __init__(self,text):
        Flowable.__init__(self);self.lines=text.splitlines();self.fontsize=8.1;self.leading=12.3;self.width=WIDTH;self.height=24+len(self.lines)*self.leading
        longest=max((pdfmetrics.stringWidth(line,'Mono',self.fontsize) for line in self.lines),default=0)
        if longest>WIDTH-24:raise ValueError('Code line too long: '+max(self.lines,key=len))
    def draw(self):
        c=self.canv;c.setFillColor(NAVY);c.roundRect(0,0,self.width,self.height,8,fill=1,stroke=0)
        c.setFillColor(colors.HexColor('#edf7f7'));c.setFont('Mono',self.fontsize)
        y=self.height-18
        for line in self.lines:c.drawString(12,y,line);y-=self.leading

class Cover(Flowable):
    def __init__(self):super().__init__();self.width=WIDTH;self.height=166
    def draw(self):
        c=self.canv;c.setFillColor(NAVY);c.roundRect(0,0,WIDTH,self.height,12,fill=1,stroke=0)
        c.setFillColor(colors.HexColor('#78d9cb'));c.setFont('Sans-Bold',9);c.drawString(22,138,'DRONELOG  /  DOCKER SWARM')
        c.setFillColor(colors.white);c.setFont('Sans-Bold',27)
        c.drawString(22,98,'A forráscsomagtól');c.drawString(22,63,'a beadásig')
        c.setFont('Sans',10);c.setFillColor(colors.HexColor('#bfd4df'));c.drawString(22,27,'Windows 11 • lépésről lépésre • 2026. november 20.')

class Architecture(Flowable):
    def __init__(self):super().__init__();self.width=WIDTH;self.height=282
    def draw(self):
        c=self.canv
        def box(x,y,w,h,title,sub,fill=BG):
            c.setFillColor(fill);c.setStrokeColor(LINE);c.roundRect(x,y,w,h,7,fill=1,stroke=1)
            c.setFillColor(NAVY);c.setFont('Sans-Bold',9);c.drawCentredString(x+w/2,y+h-17,title)
            c.setFillColor(MUTED);c.setFont('Sans',7.7);c.drawCentredString(x+w/2,y+11,sub)
        def arrow(x1,y1,x2,y2):
            c.setStrokeColor(TEAL);c.setFillColor(TEAL);c.setLineWidth(1.3);c.line(x1,y1,x2,y2)
            path=c.beginPath()
            if x2>x1:path.moveTo(x2,y2);path.lineTo(x2-5,y2+3);path.lineTo(x2-5,y2-3)
            elif y2<y1:path.moveTo(x2,y2);path.lineTo(x2-3,y2+5);path.lineTo(x2+3,y2+5)
            path.close();c.drawPath(path,fill=1,stroke=0)
        box(4,230,180,44,'Böngésző / tanár','nyilvános HTTPS URL')
        box(253,230,240,44,'Cloudflare Quick Tunnel','a futó 8080-as port továbbítása',PALE)
        arrow(184,252,253,252)
        c.setStrokeColor(LINE);c.setFillColor(colors.white);c.roundRect(4,10,489,195,9,fill=1,stroke=1)
        c.setFillColor(MUTED);c.setFont('Sans-Bold',8);c.drawString(190,188,'SAJÁT GÉP  •  1 SWARM MANAGER NODE')
        c.setStrokeColor(TEAL);c.setLineWidth(1.3);c.lines([(373,230,373,215),(373,215,79,215)]);arrow(79,215,79,173)
        box(20,126,128,47,'frontend · Nginx','1 replika • web:8080')
        box(218,126,257,47,'backend · FastAPI','2 replika • API:8000',PALE)
        arrow(148,149,218,149);c.setFillColor(MUTED);c.setFont('Sans',7.7);c.drawCentredString(183,160,'app_net')
        box(229,49,140,47,'db · PostgreSQL','1 replika • belső:5432')
        arrow(299,126,299,96);c.setFillColor(MUTED);c.setFont('Sans',7.7);c.drawString(310,108,'data_net (belső)')
        box(399,49,78,47,'pgdata','külső volume',PALE);arrow(369,72,399,72)
        c.setFillColor(MUTED);c.setFont('Sans',7.7);c.drawString(20,25,'Volume: dronelog_pgdata; a DB a címkézett node-hoz kötve.')


def page_head(number,title):return [p(f'{number:02d}  /  TELEPÍTÉSI ÚTMUTATÓ','eyebrow'),p(title,'h1')]
def footer(c,doc):
    c.saveState();c.setStrokeColor(LINE);c.setLineWidth(.5);c.line(48,42,A4[0]-48,42)
    c.setFillColor(MUTED);c.setFont('Sans',7.7);c.drawString(48,28,'DroneLog | Telepítés, nyilvános elérés és beadás')
    c.setFont('Sans-Bold',8);c.drawRightString(A4[0]-48,28,f'{doc.page:02d}')
    if doc.page>1:
        c.setFillColor(TEAL);c.setFont('Sans-Bold',8);c.drawString(48,A4[1]-29,'DRONELOG')
        c.setFillColor(MUTED);c.setFont('Sans',7.4);c.drawRightString(A4[0]-48,A4[1]-29,'Forráscsomag v1.0.0 • 2026.11.20.')
    c.restoreState()

# Read the source documents so missing or relocated source files fail explicitly.
for required in ['docs/KEZDES_WINDOWS.md','docs/ELLENORZES.md','README.md','stack.yml']:
    (ROOT/required).read_text(encoding='utf-8')

pages=[]
pages.append([
    Cover(),gap(21),p('<b>Egy működő, nyilvánosan elérhető drónos feladatnapló.</b> A csomag saját frontendből, Python API-ból és PostgreSQL-adatbázisból áll. Ez az útmutató végigvisz a saját gépes indításon, a bizonyító teszteken és a beadáson.'),
    callout('Az elkészített csomag és a saját futtatás','A forráskód és az automatizáló scriptek elkészültek. A tényleges image-buildet, Swarm-telepítést és nyilvános URL-t a saját gépeden kell létrehozni és igazolni. <b>Ez a PDF telepítési útmutató; a beadandó mért jelentést később a saját teszteredményeidből készíted.</b>'),gap(15),
    h2('A végén ezt adod be'),
    bullet('<b>GitHub-repository:</b> teljes forráskód, Dockerfile-ok, stack, README és bizonyítékok.'),
    bullet('<b>Nyilvános HTTPS URL:</b> a működő alkalmazás aktuális címe.'),
    bullet('<b>Rövid PDF-jelentés:</b> architektúra, telepítés és a saját mérések.'),gap(6),
    table(['Útvonal','Oldal'],[['Előkészítés és a rendszer megértése','2–3'],['Image-build, feltöltés és Swarm-telepítés','4'],['Webes próba és nyilvános cím','5'],['Automatikus tesztek és bizonyítékok','6'],['GitHub, jelentéskészítés és beadás','7–9'],['Hibakeresés és ellenőrzési státusz','10–11']],[WIDTH-70,70]),gap(10),
    p('<b>Határidő:</b> a mellékelt képernyőképen 2026. november 21. 00:00 szerepel, vagyis november 20. végén éjfél. A leírás szövege ugyanakkor nyitott határidőt említ; az aktuális Moodle-beállítást ellenőrizd.','small')
])
pages.append(page_head(2,'Mit építünk fel?')+[
    p('A három különböző alkalmazásszolgáltatás egy Swarm stack része. Alapállapotban <b>négy alkalmazáskonténer</b> fut: egy frontend, két API-példány és egy adatbázis.'),Architecture(),gap(8),
    table(['Szolgáltatás','Feladat'],[['frontend','Nginx: statikus felület és API-proxy. Csak a webes 8080-as port publikált.'],['backend','Python/FastAPI: ellenőrzött CRUD-műveletek, szerkesztőkulcs és adatbázis-elérés. Állapotmentes, ezért skálázható.'],['db','PostgreSQL: közös, tartós adattárolás. A név szerinti elérés a belső data_net hálózaton történik.']],[93,WIDTH-93]),gap(9),
    h2('Miért teljesíti a technikai felépítést?'),
    p('A két saját image saját Dockerfile-ból épül. A stack image-hivatkozásokat használ; az építés és a registrybe feltöltés a telepítés előtt történik. A szolgáltatásokhoz healthcheck és újraindítási szabály tartozik. A jelszavakat Docker secrets szolgáltatja.'),
    callout('A két legfontosabb korlát','Az egy node-os Swarm konténerpótlást mutat be; a teljes gép kiesése ellen nem véd. A helyi volume a konténercserét túléli, de önmagában nem biztonsági mentés. A Quick Tunnel továbbítja a kéréseket; a kód a saját gépeden fut.')
])
pages.append(page_head(3,'Egyszeri előkészítés')+[
    h2('1. Docker Desktop, WSL 2, Linux-konténerek'),
    p('A hivatalos Windows-telepítőt használd. Válaszd a WSL 2 hátteret és a Linux-konténereket. Ha a telepítő újraindítást kér, végezd el. Indítsd el a Docker Desktopot, majd PowerShellben ellenőrizd:'),
    code("wsl --version\ndocker version\ndocker info --format '{{.OSType}}'"),gap(9),
    p('A <font name="Mono">docker version</font> kimenetben Client <b>és</b> Server kell. Az utolsó parancs kívánt eredménye <font name="Mono">linux</font>. Hiányzó vagy elavult WSL esetén a Docker hivatalos WSL-lépéseit kövesd; a hardveres virtualizáció is legyen engedélyezve.'),
    h2('2. Fiókok és két segédprogram'),
    bullet('Saját <b>Docker Hub</b> fiók az image-ekhez; saját <b>GitHub</b> fiók a forráshoz.'),
    bullet('<b>Git for Windows:</b> telepítsd, ha a git --version még nem működik.'),
    code('winget install --id Cloudflare.cloudflared -e\ncloudflared --version\ngit --version'),gap(9),
    p('Telepítés után nyiss új PowerShell-ablakot a PATH frissítéséhez. Ha a winget nem elérhető, a hivatalos Cloudflare Windows-letöltést használd. Python, Node.js és PostgreSQL külön hosttelepítése az alkalmazás indításához nem kell.'),
    h2('3. Bontsd ki a projektet'),
    p('A ZIP teljes drone-swarm mappáját például a következő helyre csomagold ki; a ZIP belsejéből ne futtass scriptet:'),
    code('cd C:\\projektek\\drone-swarm\nGet-ChildItem'),gap(7),
    p('Itt látnod kell a stack.yml, README.md, backend, frontend, database és scripts elemeket. A további parancsok munkamappája ez a projektgyökér.','small'),
    p('Letöltési források: Docker Desktop [1], cloudflared [2], Git for Windows [3]. A kattintható hivatkozások a 11. oldalon szerepelnek.','small')
])
pages.append(page_head(4,'Build, push és Swarm-telepítés')+[
    p('A Docker Hubon hozz létre <b>dronelog-backend</b> és <b>dronelog-frontend</b> nevű repositoryt a saját felhasználóneved alatt. A Public láthatóság egyszerű a bemutatóhoz. A Docker Hub image-eket tárol; a GitHubra a forrás kerül.'),
    p('A SAJAT_DOCKERHUB_NEV helyére a tényleges Docker Hub-nevedet írd, kisbetűkkel, szóköz nélkül:'),
    code(r'''docker login -u SAJAT_DOCKERHUB_NEV
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\deploy.ps1 `
  -DockerHubUser SAJAT_DOCKERHUB_NEV'''),gap(9),
    p('A belépési titkot a Docker által kért helyre add meg. Kétlépcsős azonosításnál a támogatott belépési módot vagy személyes tokent használd. A fenti ExecutionPolicy beállítás erre a PowerShell-folyamatra vonatkozik.'),
    h2('Mit végez el a telepítő?'),
    p('Ellenőrzi a Linux Docker motort és a manager szerepet. Szükség esetén inicializálja a Swarmot. Létrehozza a node címkéjét, a volume-ot és a véletlen secreteket. Felépíti és a registrybe feltölti a két saját image-et, majd <b>docker stack deploy</b> segítségével telepít és kivárja a szolgáltatásokat.'),
    h2('A végén ezt ellenőrizd'),
    code('docker node ls\ndocker stack services dronelog\ndocker stack ps dronelog\nInvoke-RestMethod http://localhost:8080/api/health'),gap(9),
    table(['Elem','Elvárt eredmény'],[['dronelog_frontend','1/1'],['dronelog_backend','2/2'],['dronelog_db','1/1'],['API health','status: ok; database: ok']],[WIDTH*.52,WIDTH*.48]),gap(8),
    p('Induláskor rövid ideig lehet 0/1 vagy 1/2 állapot. Tartós eltérésnél a 10. oldal szerint keress hibát. A végső sikeres állapotról készíts képernyőképet úgy, hogy titok ne látszódjon.','small')
])
pages.append(page_head(5,'Valódi felület és nyilvános cím')+[
    h2('Először a saját gépen'),
    p('A böngészőben nyisd meg: <b>http://localhost:8080</b>. A fájlra kattintás nem indítja el az alkalmazást; a felületet a Dockerben futó webszerver szolgálja ki. A szerkesztőkulcsot PowerShellben így olvasod ki:'),
    code(r'Get-Content .\.secrets\admin_token.txt'),gap(9),
    p('Másold a kulcsot a felület szerkesztésengedélyező ablakába. Hozz létre egy egyedi, fiktív feladatot, például <b>Bemutató - tetőfelmérés</b>. Frissítsd az oldalt, majd próbálj állapotot váltani. A mentett rekordnak vissza kell jönnie. Készíts képet a felületről; a kulcs maradjon kívül a képen.'),
    h2('Második PowerShell-ablak: Quick Tunnel'),
    code('cloudflared tunnel --url http://localhost:8080'),gap(9),
    p('A kimenetben valódi <b>https://…trycloudflare.com</b> cím jelenik meg. Ezt a teljes címet másold ki. A cím véletlenszerű, előre nem tudható.'),
    table(['Cím','Mire szolgál?'],[['http://localhost:8080','Helyi alkalmazásmegnyitás a saját gépeden.'],['A tunnel által kiírt HTTPS URL','Ezt kapja a tanár az alkalmazás eléréséhez.'],['A saját GitHub-repository URL-je','Ezt kapja a tanár a forráskódhoz.']],[WIDTH*.47,WIDTH*.53]),gap(13),
    h2('Külső hálózati próba'),
    p('Telefonon kapcsold ki a Wi-Fi-t, és <b>mobilinterneten</b> nyisd meg a kiírt HTTPS címet. Ellenőrizd, hogy ugyanaz a felület és a létrehozott rekord látszik. Jegyezd fel az időpontot, és készíts képernyőképet az URL-lel.'),
    callout('A link addig működik, amíg a rendszer fut','A tunnel terminálját hagyd nyitva; a gép ne aludjon el, a Docker Desktop maradjon működőképes. Leállításkor megszűnik az elérés, és új tunnelindításkor új URL keletkezik. A beadásban és a bemutatón is az aktuális linket használd.')
])
pages.append(page_head(6,'Mért tesztek és bizonyítékok')+[
    p('Az első PowerShell-ablakban, a projekt mappájából indítsd a tesztet. Az alábbi helyőrző helyére a tunnel <b>tényleges</b> címét írd:'),
    code(r'''powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\test.ps1 `
  -PublicUrl 'https://TENYLEGES-CIM.trycloudflare.com' '''.rstrip()),gap(12),
    table(['Próba','Mit ellenőriz a script?'],[['Funkció és jogosultság','Egyedi adat rögzítése és visszaolvasása; jogosulatlan írás elutasítása.'],['Skálázás','Az állapotmentes API replikaszámának növelése és a tényleges futó taskok kivárása.'],['Konténerpótlás','API-konténer leállítása, új task és konténer létrejöttének követése.'],['Perzisztencia','Az adatbázis taskjának újralétrehozása után ugyanaz a rekord olvasható.'],['Nyilvános HTTP-elérés','A megadott publikus URL-re küldött kérés ellenőrzése.']],[120,WIDTH-120]),gap(11),
    p('A hibapróbák rövid megszakítást okozhatnak. A teszt végül visszaállítja az eredeti API-replikaszámot. Az eredmények az <font name="Mono">evidence/run_...</font> mappába kerülnek: <b>test-results.json</b> és <b>commands.txt</b>.'),
    table(['Jelzés','Jelentés'],[['PASSED','Az adott automatikus feltételt a futás ellenőrizte.'],['FAILED','A pont nem igazolt; a hibát ki kell javítani.'],['SKIPPED','A próba kimaradt. PublicUrl nélkül a külső teszt ilyen.']],[100,WIDTH-100]),gap(10),
    callout('Két kézi bizonyítékot te teszel hozzá','A script nem végzi el a böngészős űrlappróbát és a telefonos, másik hálózati megnyitást. Az 5. oldalon leírt saját próbák, megjegyzések és képernyőképek ezeket külön igazolják. A JSON-ban ne írj át kézzel sikertelen vagy kihagyott pontot sikeresre.')
])
pages.append(page_head(7,'Saját GitHub-repository')+[
    p('A GitHubon hozz létre egy <b>üres, drone-swarm nevű Public repositoryt</b>. Ne kérj hozzá automatikus README-t, .gitignore-t vagy licencet. A forráscsomag már tartalmazza a szükséges projektfájlokat. Privát repo esetén az oktatónak hozzáférést kell adnod.'),
    p('A saját repo címe például https://github.com/SAJAT_GITHUB_NEV/drone-swarm. A Docker Hub- és a GitHub-felhasználónév különbözhet.'),
    code(r'''git init
git branch -M main
git check-ignore .secrets/admin_token.txt .secrets/db_password.txt
git status --short'''),gap(10),
    callout('A titkok kizárását még a feltöltés előtt ellenőrizd','A git check-ignore kimenetében szerepeljen mindkét titokfájl neve. Ez a fájlnevet mutatja, nem a titkot. Ha egyik sem jelenik meg, ellenőrizd a .gitignore-t a git add és a feltöltés előtt. A .secrets és .env tartalmát ne tedd a repositoryba.'),gap(12),
    h2('Mi kerül a repositoryba?'),
    table(['Hely','Tartalom'],[['frontend/ és backend/','Saját alkalmazáskód és a két Dockerfile.'],['database/init.sql','Adatbázisséma, fiktív demóadatok.'],['stack.yml','Szolgáltatások, overlay hálózatok, volume, secretek, replikák.'],['scripts/ és tests/','Telepítés, bizonyító tesztek, jelentéskészítés és fejlesztői tesztek.'],['README.md és docs/','Leírás, aktuális linkek, saját beadási PDF és segédletek.'],['evidence/','A saját tényleges futtatás JSON-ja, parancskimenete és képernyőképei.']],[WIDTH*.39,WIDTH*.61]),gap(10),
    p('Hozz létre <font name="Mono">evidence/screenshots</font> mappát, és tedd bele a saját, titkokat nem tartalmazó képeket. Az automatikus parancskimeneteket a teszt már megőrzi. A teljes projektet a 9. oldalon töltöd fel, a mért jelentés elkészítése után.','small')
])
pages.append(page_head(8,'A saját mérésekből beadási PDF')+[
    p('A jelentéskészítő a legfrissebb <b>valódi tesztfutás JSON-ját</b> olvassa. Add meg a neved, a saját repositoryd és az aktuális tunnel címed. Az alábbi parancs a kézi próbák igazolását is rögzíti, ezért ezeket a kapcsolókat csak az elvégzett próbák után használd:'),
    code(r'''powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\make-report.ps1 `
  -StudentName 'SAJAT NEV' `
  -RepositoryUrl 'https://github.com/SAJAT_NEV/drone-swarm' `
  -PublicUrl 'https://TENYLEGES-CIM.trycloudflare.com' `
  -UiVerified -UiNote 'Rekordcim es az UI-proba idopontja.' `
  -ExternalVerified `
  -ExternalNote 'Telefon, mobilinternet, megnyitas idopontja.' `
  -Open'''),gap(10),
    p('<b>Másolható PowerShell:</b> a sorvégi backtick (<font name="Mono">`</font>) után ne kerüljön szóköz. A parancs egy sorban is megadható. A helyőrzőket és a megjegyzéseket cseréld saját, tényleges adatokra.'),
    p('Ha a kézi próbák még nincsenek készen, hagyd el a UiVerified, UiNote, ExternalVerified és ExternalNote argumentumokat. A jelentés ekkor ezeket függőben jelzi. Opcionálisan Neptun-kód is megadható; a nyilvános repóba kerülő személyes adatokról tudatosan dönts.'),
    h2('HTML-jelentésből rövid PDF'),
    p('Megnyílik a <b>docs/Beadasi_dokumentacio.html</b>. A böngészőben válaszd a <b>Ctrl+P → Mentés PDF-ként → A4</b> beállítást. Mentsd <b>docs/Beadasi_dokumentacio.pdf</b> néven. A böngésző saját fejlécét/láblécét szükség esetén kapcsold ki.'),
    table(['Automatikus kimenet','Feladat'],[['docs/Beadasi_dokumentacio.html','Architektúra, szolgáltatások, telepítés és a saját mérések. Ebből nyomtatod a beadási PDF-et.'],['README.md','Frissülnek az aktuális repository- és alkalmazáslinkek.'],['docs/BEADAS.txt','Előkészített beadási szöveg a saját linkekkel.']],[WIDTH*.47,WIDTH*.53]),gap(9),
    p('Másik méréshez az <font name="Mono">-EvidenceFile</font> a projekt saját evidence/run_... könyvtárában levő test-results.json fájlra mutasson. Új tunnelcím esetén az új URL-lel futtasd újra a tesztet is. A most olvasott telepítési útmutató nem helyettesíti ezt a mért beadási dokumentációt.','small')
])
pages.append(page_head(9,'Feltöltés, beadás és bemutató')+[
    p('A projektgyökérből add hozzá a kész forrást és a valódi bizonyítékokat. A staged fájllistát nézd át: ne szerepeljen benne .secrets vagy .env.'),
    code(r'''git add .
git diff --cached --name-only
git commit -m 'DroneLog Swarm projekt es meresi bizonyitekok'
git remote add origin https://github.com/SAJAT_NEV/drone-swarm.git
git push -u origin main'''),gap(9),
    p('Ha a Git nevet/e-mailt kér, a projektben állítsd be a <font name="Mono">git config user.name</font> és <font name="Mono">git config user.email</font> értékeket. Használható a GitHub által megadott noreply cím. Létező origin esetén előbb <font name="Mono">git remote -v</font>; ne add hozzá újra.'),
    h2('A tényleges beadás ellenőrzése'),
    bullet('Nyisd meg a GitHub-repót: a forrás, README, Dockerfile-ok, stack, mérések és a beadási PDF látszanak.'),
    bullet('A Moodle-be add be a repo linkjét, az aktuális nyilvános alkalmazáslinket és a beadási PDF-et. A docs/BEADAS.txt segít; a tényleges Beadás gombot is használd.'),
    bullet('Ha a PDF később készült el: git add docs/Beadasi_dokumentacio.pdf, majd új commit és git push.'),
    h2('3–5 perces élő bemutató'),
    table(['Idő','Mit mutass?'],[['0:00–0:40','Nyilvános alkalmazás: egyedi feladat felvétele és visszaolvasása.'],['0:40–1:20','docker stack services: 3 különböző service, az API-ból 2 replika.'],['1:20–2:00','API skálázása 3-ra; a harmadik futó task kivárása.'],['2:00–2:50','Egy API-konténer leállítása, új task és konténer bemutatása.'],['2:50–4:20','DB-konténercsere bizonyítéka és megmaradt rekord; tunnel és egy node korlátja.']],[90,WIDTH-90]),gap(9),
    p('A pontos kézi parancsok és a gyakori kérdések a docs/VEDES.md fájlban vannak. Olvasd át a stack.yml-t, a Dockerfile-okat és az API végpontjait; tudj elmondani egy teljes adatmentési kérést a böngészőtől az adatbázisig.','small')
])
pages.append(page_head(10,'Gyors hibakeresés')+[
    table(['Jelenség','Első ellenőrzés / teendő'],[
      ['docker nem ismert; nincs Server','Docker Desktop telepítése/indítása, a motor kivárása, új PowerShell.'],
      ['OSType: windows','Válts Linux containers módra a Docker Desktopban.'],
      ['Push: denied / unauthorized','docker login; egyezzen a név a saját Docker Hub-repository tulajdonosával.'],
      ['invalid reference format','Valódi, kisbetűs Docker Hub-név; a script állítja be az image-változókat.'],
      ['Nem választható advertise cím','A hiba által felsorolt node-cím alapján add meg az AdvertiseAddr argumentumot.'],
      ['Tartós db 0/1 vagy API 503','Nézd meg a service ps és logs kimenetét; node-címke, secret és volume is számít.'],
      ['8080-as port foglalt','A portot használó saját program leállítása, vagy célzott portcsere a stackben és URL-ekben.'],
      ['Helyben jó, nyilvánosan 502','A tunnel a localhost:8080 felé mutat-e; a Docker és a frontend fut-e?'],
      ['Tunnelkapcsolat nem jön létre','Blokkolt QUIC/UDP esetén használd a lent látható HTTP/2 változatot.'],
      ['cloudflared nem ismert','Új terminál, telepítő/PATH ellenőrzés, cloudflared --version.'],
      ['Szerkesztés: 401','A saját .secrets/admin_token.txt pontos tartalmával jelentkezz be.'],
      ['Secret fingerprint eltérés','Az eredeti helyi .secrets fájlokat állítsd vissza; a secretet vagy DB-t ne töröld találomra.']
    ],[153,WIDTH-153]),gap(10),
    code('docker stack services dronelog\ndocker stack ps --no-trunc dronelog\ndocker service logs --tail 80 dronelog_backend\ndocker service logs --tail 80 dronelog_db\nInvoke-RestMethod http://localhost:8080/api/health'),gap(8),
    code('cloudflared tunnel --protocol http2 --url http://localhost:8080'),gap(8),
    p('Elakadáskor a hiba képét vagy a fenti parancsok kimenetét küldd vissza. A jelszót, tokent és a .secrets tartalmát hagyd ki. Új tunnelindítás után az új címet használd.','small')
])
# Exact QA scope is extracted from the maintained development checklist.
qa=[]
for line in (ROOT/'docs/ELLENORZES.md').read_text(encoding='utf-8').splitlines():
    if line.startswith('| ') and not line.startswith('| Ellenőrzés') and not line.startswith('| ---'):
        cells=[plain(x.strip()) for x in line.strip().strip('|').split('|')]
        if len(cells)==3:qa.append(cells)
pages.append(page_head(11,'Mit ellenőriztünk, mi jön nálad?')+[
    p('A fejlesztési ellenőrzések pontos hatóköre az ELLENORZES.md szerint. Ezek nem a saját Swarm-futtatásod bizonyítékai.','small'),
    table(['Ellenőrzés','Eredmény és hatókör'],[[r[0],'<b>'+r[1]+'</b><br/>'+r[2]] for r in qa],[145,WIDTH-145]),gap(8),
    h2('Bemutató után'),
    p('A tunnel ablakában <b>Ctrl+C</b> zárja a nyilvános elérést. Ha a tanár később ellenőrzi, maradjon működőképes az egyeztetett ideig. A <font name="Mono">docker stack rm dronelog</font> külön leállítja a stacket; a külső volume és secretek megmaradnak.','small'),
    h2('Hivatalos források és kiinduló dokumentumok'),
    p('[1] <link href="https://docs.docker.com/desktop/setup/install/windows-install/" color="#087f78">Docker Desktop Windows</link> · [2] <link href="https://developers.cloudflare.com/tunnel/downloads/" color="#087f78">cloudflared letöltése</link> · [3] <link href="https://git-scm.com/downloads/win" color="#087f78">Git for Windows</link><br/>[4] <link href="https://docs.docker.com/engine/swarm/stack-deploy/" color="#087f78">Docker: stack telepítése Swarmba</link> · [5] <link href="https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/" color="#087f78">Cloudflare: Quick Tunnels</link>','small'),
    p('Követelmények: a mellékelt Docker_Swarm_projektfeladat.pdf, 1–3. oldal. Projektforrások: KEZDES_WINDOWS.md, ELLENORZES.md, README.md, stack.yml és VEDES.md.','small')
])

story=[]
for idx,page in enumerate(pages):
    if idx:story.append(PageBreak())
    story.extend(page)
OUT.parent.mkdir(parents=True,exist_ok=True)
doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=51,bottomMargin=55,title='DroneLog - Telepítési útmutató',author='DroneLog projekt',subject='Windows, Docker Swarm, Cloudflare Quick Tunnel, GitHub és beadás',allowSplitting=1)
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
