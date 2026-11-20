"""Build the short Hungarian project PDF from the evidence available in this checkout."""
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


root = Path(__file__).resolve().parents[1]
repository = "https://github.com/szoporitamas99/dronelog-swarm"
font_pairs = (
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
)
fonts = next((pair for pair in font_pairs if all(Path(f).exists() for f in pair)), None)
if fonts is None:
    raise SystemExit("Install fonts-dejavu-core to render the Hungarian report.")
for name, font in zip(("Body", "Strong"), fonts):
    pdfmetrics.registerFont(TTFont(name, str(font)))
ink = colors.HexColor("#163749")
teal = colors.HexColor("#007B75")
flow = []


def para(text, size=10, bold=False, color=ink):
    return Paragraph(text, ParagraphStyle("project", fontName="Strong" if bold else "Body",
                                          fontSize=size, leading=size * 1.48, textColor=color))


def section(title):
    flow.extend([Spacer(1, 12), para(title, 15, True), Spacer(1, 5)])


def grid(header, rows, widths):
    cells = [[para(escape(value), 9, True, colors.white) for value in header]]
    cells += [[para(escape(str(value)), 9) for value in row] for row in rows]
    table = Table(cells, colWidths=widths, hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), ink),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#edf4f4"), colors.white]),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                               ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    flow.append(table)


development = json.loads((root / "docs/development-integration-results.json").read_text(encoding="utf-8"))
results = sorted((root / "evidence").glob("run_*/test-results.json"))
run = json.loads(results[-1].read_text(encoding="utf-8-sig")) if results else {}
directory = results[-1].parent if results else None
checks = {c["id"]: c for c in run.get("checks", [])}
browser_file = directory / "browser.json" if directory else None
browser = json.loads(browser_file.read_text(encoding="utf-8")) if browser_file and browser_file.exists() else {}
external_file = directory / "external.json" if directory else None
external = json.loads(external_file.read_text(encoding="utf-8")) if external_file and external_file.exists() else {}
flow += [para("FELHŐSZÁMÍTÁS   /   GYAKORLATI PROJEKT", 10, True, teal),
         para("DroneLog", 32, True), para("Drónos feladatnapló Docker Swarm környezetben", 15),
         Spacer(1, 12), para("A felhasználó egy drónos feladat helyét, dátumát, állapotát és repülési idejét rögzíti. "
                              "Az összesítő a befejezett feladatok repülési perceit adja össze. A mintaadatok fiktívek.")]
section("Architektúra")
grid(["Szolgáltatás", "Szerep és kapcsolat", "Replika¹"], [
    ["frontend · Nginx", "A 8080-as belépési ponton kiszolgálja a felületet. Az /api/ kéréseket a backend:8000 címre továbbítja.", "1"],
    ["backend · FastAPI", "Ellenőrzi a bemenetet és a szerkesztőkulcsot. A db:5432 címen olvas és ír.", "2"],
    ["db · PostgreSQL", "A megjelölt node dronelog_pgdata kötetén tárolja a feladatokat. Csak a belső adathálózatról érhető el.", "1"]
], [116, 309, 74])
flow.extend([Spacer(1, 5), para("¹ A stackben beállított alapértékek. Az app_net az Nginxet és az API-t, a data_net az API-t és az adatbázist köti össze.", 9)])
section("Telepítés és elérés")
flow.append(para("A telepítő a két saját Dockerfile-ból verziózott image-et épít és registrybe tölti. "
                 "A manager node-on létrehozza a Docker secreteket és a tartós kötetet, majd a docker stack deploy paranccsal indítja a három szolgáltatást. "
                 "A webes íráshoz szerkesztőkulcs kell. Olvasáshoz elegendő a webcím."))
flow.extend([Spacer(1, 6), para("A GitHub Codespaces bemutatógépen a registry csak helyben érhető el. A GitHub a frontend 8080-as portját teszi elérhetővé nyilvános HTTPS-címen. "
                                "A gépnek a bemutató alatt futnia kell. Saját számítógépen ugyanehhez a belépési ponthoz Cloudflare Quick Tunnel is használható.")])
section("Projekt és bemutató")
flow.append(para(f'<link href="{repository}" color="#007B75">{repository}</link><br/>'
                 f'<link href="{repository}/blob/main/docs/VEDES.md" color="#007B75">Élő bemutató forgatókönyve</link>'))
public_url = run.get("urls", {}).get("public")
if public_url:
    safe_url = escape(public_url, {'"': '&quot;'})
    flow.extend([Spacer(1, 5), para(f'Nyilvános alkalmazás: <link href="{safe_url}" color="#007B75">{safe_url}</link>', 9)])
flow.append(PageBreak())
flow.extend([para("MÉRÉSI JEGYZŐKÖNYV", 10, True, teal), para("A próbák eredményei", 24, True)])
labels = {"preflight": "Swarm készenlét", "functional_api": "API-írás és visszaolvasás", "scale": "Skálázás",
          "self_healing": "Konténerpótlás", "persistence": "Tartós adat", "public_http": "Nyilvános elérés"}
states = {"passed": "Sikeres", "failed": "Sikertelen", "skipped": "Kihagyva"}
if run:
    flow.append(para("Swarm-futtatás (UTC): " + escape(run["started_at"])))
    environment = run.get("environment", {})
    if environment.get("docker_server_version"):
        flow.append(para("Docker Engine " + escape(environment["docker_server_version"]) + " · " +
                         ("egy manager node" if environment.get("single_node") else "több node"), 9))
else:
    flow.append(para("A dokumentum a forráscsomaghoz mellékelt fejlesztői méréseket tartalmazza. Swarm-mérési napló még nem áll rendelkezésre."))
rows = []
for key, label in labels.items():
    check = checks.get(key, {})
    data = check.get("details", {})
    detail = ""
    if check.get("status") == "passed":
        if key == "preflight": detail = f"Backend alapállapot: {data['original_backend_replicas']} replika."
        if key == "functional_api": detail = f"Rekord: #{data['record_id']}. Jogosulatlan írás: HTTP {data['unauthorized_status']}."
        if key == "scale": detail = f"{data['from']} → {data['to']} futó API-task."
        if key == "self_healing": detail = f"Korábbi task: {data['stopped_task'][:12]}. Új: {data['replacement_task_ids'][0][:12]}."
        if key == "persistence": detail = f"DB-task: {data['old_task'][:12]} → {data['new_task'][:12]}. Megmaradt rekord: #{data['preserved_record_id']}."
        if key == "public_http": detail = "A publikus címen visszaolvasott rekord egyezett a helyi rekorddal."
    elif key == "public_http": detail = "Az élő bemutatóhoz külön ellenőrzött nyilvános URL szükséges."
    else: detail = data.get("error") or data.get("reason") or "Nincs csatolt futtatási eredmény."
    rows.append([label, states.get(check.get("status"), "Függőben"), detail])
rows.append(["Webes űrlap", states.get(browser.get("status"), "Függőben"),
             f"{browser.get('browser', 'Chrome')}, HTTP {browser['http']}, #{browser['id']}. Frissítés után ugyanaz a cím látható." if browser else "A rögzítés és visszaolvasás böngészős igazolása hiányzik."])
if external:
    rows.append(["Külső böngésző", states.get(external.get("status"), "Függőben"), external["observation"]])
grid(["Próba", "Állapot", "Megfigyelés"], rows, [119, 79, 301])
section("Korábbi fejlesztői ellenőrzések")
passed = sum(c["status"] == "passed" for c in development["checks"])
flow.append(para(f'A csomagban rögzített {len(development["checks"])} PostgreSQL-integrációs ellenőrzésből {passed} sikeres. '
                 "A tesztkörnyezet PostgreSQL 16.2-t használt. A létrehozott rekord az adatbázisfolyamat újraindítása után is megmaradt. "
                 "A fejlesztési napló 17 sikeres backend-egységtesztet és 11 sikeres frontend-tesztcsoportot is rögzít."))
if directory:
    section("Nyers bizonyítékok")
    flow.append(para(f"Mérési mappa: {escape(directory.name)}. A test-results.json tartalmazza a taskazonosítókat és a mért állapotokat. "
                     "A commands.txt a Docker-parancsokat és kimeneteiket rögzíti."))
    screen = directory / "browser-readback.png"
    if browser and screen.exists():
        flow += [PageBreak(), para("WEBES FELÜLET", 10, True, teal), para("Visszaolvasás frissítés után", 21, True),
                 Spacer(1, 8), para(escape(browser["title"])), Spacer(1, 14), Image(str(screen), width=495, height=330)]
    if external:
        proof = directory / external["screenshot"]
        width, height = ImageReader(str(proof)).getSize()
        flow += [Spacer(1, 12), para("A külön böngészőből megnyitott nyilvános nézet", 13, True), Spacer(1, 6),
                 Image(str(proof), width=495, height=495 * height / width)]


def footer(canvas, doc):
    canvas.setFont("Body", 8)
    canvas.setFillColor(ink)
    canvas.drawString(48, 30, "DroneLog   /   Felhőszámítás")
    canvas.drawRightString(A4[0] - 48, 30, str(doc.page))


output = (directory or (root / "docs")) / "DroneLog_Projektjelentes.pdf"
doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=47, rightMargin=47, topMargin=43, bottomMargin=51,
                        title="DroneLog – projektjelentés", author="DroneLog")
doc.build(flow, onFirstPage=footer, onLaterPages=footer)
print(output)
