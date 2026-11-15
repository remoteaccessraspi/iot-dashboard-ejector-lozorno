#!/usr/bin/env python3
"""Prevádzkový prehľad teplôt, tlakov a alarmov. Výstup je PDF vedľa tohto súboru."""

from pathlib import Path

from reportlab.lib.colors import Color, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
pdfmetrics.registerFont(TTFont("DejaVu", FONT))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", FONT_BOLD))

NAVY = Color(41 / 255, 71 / 255, 92 / 255)
INK = Color(0.12, 0.14, 0.16)
MUTED = Color(0.28, 0.31, 0.34)
LINE = Color(0.78, 0.80, 0.82)
ROW = Color(0.95, 0.96, 0.96)
OUT = Path(__file__).with_suffix(".pdf")
DATE = "15. november 2026"


def P(text, style):
    return Paragraph(text, style)


def styles():
    base = dict(fontName="DejaVu", textColor=INK)
    return {
        "h1": ParagraphStyle("h1", fontName="DejaVu-Bold", fontSize=14, leading=17, textColor=INK, spaceAfter=1),
        "lead": ParagraphStyle("lead", fontSize=8.5, leading=11, spaceAfter=6, textColor=MUTED, fontName="DejaVu"),
        "h2": ParagraphStyle("h2", fontName="DejaVu-Bold", fontSize=11, leading=14, textColor=INK, spaceBefore=7, spaceAfter=2),
        "body": ParagraphStyle("body", fontSize=8.5, leading=11.2, alignment=TA_LEFT, spaceAfter=2, **base),
        "bullet": ParagraphStyle("bullet", fontSize=8.5, leading=11.2, leftIndent=10, bulletIndent=0, spaceAfter=0.5, **base),
        "th": ParagraphStyle("th", fontName="DejaVu-Bold", fontSize=8, leading=10, textColor=white),
        "td": ParagraphStyle("td", fontName="DejaVu", fontSize=7.6, leading=9.6, textColor=INK),
        "tdkey": ParagraphStyle("tdkey", fontName="DejaVu", fontSize=7.4, leading=9.4, textColor=MUTED),
    }


def table(header, rows, widths):
    s = styles()
    data = [[P(cell, s["th"]) for cell in header]]
    for row in rows:
        data.append([P(row[0], s["td"]), P(row[1], s["tdkey"]), P(row[2], s["td"])])
    sheet = Table(data, colWidths=widths, repeatRows=1)
    sheet.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BACKGROUND", (0, 1), (-1, -1), white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, ROW]),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return sheet


def draw_page(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(16 * mm, height - 14 * mm, width - 16 * mm, height - 14 * mm)
    canvas.setFillColor(INK)
    canvas.setFont("DejaVu", 8)
    canvas.drawString(16 * mm, height - 12 * mm, "Ejector Lozorno")
    canvas.drawRightString(width - 16 * mm, height - 12 * mm, "Teploty, tlaky, alarmy")
    canvas.line(16 * mm, 12 * mm, width - 16 * mm, 12 * mm)
    canvas.setFillColor(MUTED)
    canvas.drawString(16 * mm, 7.5 * mm, DATE)
    canvas.drawRightString(width - 16 * mm, 7.5 * mm, str(doc.page))
    canvas.restoreState()


def build():
    s = styles()
    usable = A4[0] - 32 * mm
    story = [
        P("Teploty, tlaky, alarmy a warningy", s["h1"]),
        P("Krátky popis toho, kde sa nastavujú hranice a ako na ne systém reaguje. Cyklus čítania je 5 s.", s["lead"]),
        P("Kde sa čo nastavuje", s["h2"]),
        P("Čísla sú v YAML. Po ich zmene treba reštartovať služby príkazom <b>sudo ./restart_all.sh</b>. Heslo databázy a pošta sa čítajú pri použití, tie reštart nepotrebujú.", s["body"]),
        table(
            ["Čo", "Súbor a kľúč", "Teraz"],
            [
                ["Ako dlho musia obe teploty držať, kým je štart povolený", "ck_3083es_8ch.yaml<br/>start.hold_s", "120 s"],
                ["Ako dlho musí teplota ostať mimo vypínacej hranice, kým menič zastaví", "ck_3083es_8ch.yaml<br/>start.stop_hold_s", "15 s"],
                ["Stred t_gen_in, kanál t3. Štart je od stredu plus hysteréza, stop pod stredom mínus hysteréza.", "channels.t3.ready_min", "80 °C"],
                ["Hysteréza t_gen_in. Pri nule sú obe hrany na 80 °C.", "channels.t3.ready_hyst", "1 °C"],
                ["Stred t_cond_in, kanál t6. Štart je pod stredom mínus hysteréza, stop nad stredom plus hysteréza keď menič nie je stabilný.", "channels.t6.ready_max", "28 °C"],
                ["Stred t_cond_in pri stabilnom INVT. Stop je nad stredom plus hysteréza, teraz nad 31 °C.", "channels.t6.ready_max_stable", "30 °C"],
                ["Hysteréza t_cond_in. Posúva štart aj obe stop hrany.", "channels.t6.ready_hyst", "1 °C"],
                ["Stred t_evap_in, kanál t1. Stop je pod stredom mínus hysteréza, obnova nad stredom plus hysteréza.", "channels.t1.ready_min", "18 °C"],
                ["Hysteréza t_evap_in. Pásmo medzi hranicami drží posledný stav.", "channels.t1.ready_hyst", "1 °C"],
                ["Prah kavitácie, signál p_gen_prim_from_frq", "invt_gd20.yaml<br/>cavitation.min_kpa", "750 kPa"],
                ["Ako dlho musí tlak ostať pod prahom na strope otáčok", "cavitation.confirm_s", "10 s"],
                ["Strop frekvencie, pri ktorom otáčky už tlak nedorovnajú", "cavitation.frequency_limit_hz", "45 Hz"],
                ["Povolený prúd slučky i6, i7 a i8", "common.yaml<br/>alarms.loop_low_ma, loop_high_ma", "3,5–21 mA"],
                ["Koľko cyklov bez odpovede je výpadok komunikácie", "common.yaml<br/>alarms.comm_fail_cycles", "3"],
                ["Najvyššia veková hranica vzorky teploty pre štart a polohy ventilu pre STOP pri zatvorenom ventile", "common.yaml<br/>alarms.ready_max_age_s", "10 s"],
                ["Medzera medzi vzorkami, ktorá ešte nezlomí držanie", "common.yaml<br/>alarms.ready_max_gap_s", "15 s"],
                ["Najvyššia veková hranica vzorky meniča pri kavitácii", "common.yaml<br/>alarms.cavitation_max_age_s", "15 s"],
                ["Ako ďaleko do histórie hľadať dosiahnutie 750 kPa", "common.yaml<br/>alarms.cavitation_arm_lookback_s", "3 h"],
                ["Nečinnosť, po ktorej sa servis sám zatvorí", "common.yaml<br/>hmi.service_idle_min", "30 min"],
                ["Prah STOP podľa skutočného otvorenia ventilu. 0 % = úplne zatvorený. na = vypnuté.", "em2rs_556.yaml<br/>valve.closed_stop_percent", "0 %"],
                ["Príjemcovia alarmového mailu", "emails.yaml<br/>recipients", "zoznam"],
            ],
            [usable * 0.50, usable * 0.34, usable * 0.16],
        ),
        P("Štart meniča", s["h2"]),
        P("RUN je povolený, až keď naraz platí všetko toto:", s["body"]),
        P("• t_gen_in je aspoň 80 °C plus ready_hyst. Pri ready_hyst 1 je to aspoň 81 °C. Presne 81 °C už stačí.", s["bullet"]),
        P("• t_cond_in je pod 28 °C mínus ready_hyst. Pri ready_hyst 1 je to pod 27 °C. Presne 27 °C ešte nestačí.", s["bullet"]),
        P("• Obe hranice držia bez prerušenia 2 minúty. t_evap_in bežné RUN neblokuje.", s["bullet"]),
        P("• Posledná vzorka teploty nie je staršia ako ready_max_age_s, teraz 10 s. Medzera nad ready_max_gap_s, teraz 15 s, čas začína odznova.", s["bullet"]),
        Spacer(1, 2),
        P("Kým to neplatí, bežné tlačidlo RUN je sivé a vypnuté. Na úvodnej karte je NOT READY. Povel sa neuloží na neskôr: keď teploty podmienku splnia, RUN treba stlačiť znova. STOP ide vždy. Servisný beh tieto teploty obchádza.", s["body"]),
        P("Chýbajúca teplota, hodnota −999 alebo výpadok modulu CK-3083 podmienku nespĺňa.", s["body"]),
        P("Servisný beh", s["h2"]),
        P("Servis sa otvára na úvodnej karte tlačidlom Service. Heslo je v secrets.yaml, kľúč hmi.service_password. Prázdne heslo znamená, že stačí Open. V menu pribudnú karty zariadení a Close service. Ack na červenej lište je len v servise. Po 30 minútach bez dotyku sa servis sám zatvorí a obraz sa vráti na hlavnú kartu.", s["body"]),
        P("Kým je servis otvorený, tlačidlo štartu má nápis RUN in service mode. Rovnaký povel je na karte meniča. Tento beh obchádza teplotnú podmienku aj blokovanie od alarmu. Externý stop S4 ostáva: rozopnutý spínač menič nespustí.", s["body"]),
        P("Počas servisného behu nepríde automatický STOP. Studený výparník, studený generátor, horúci kondenzátor, expanzný ventil na 0 %, studená kavitácia ani teplá kavitácia menič nezastavia. Studený výparník, studený generátor a horúci kondenzátor ostanú žltý warning. Teplá kavitácia ostane červený alarm a odíde mail. Žlté warningy ostávajú. Čakajúci štart po teplote aj po ventile sa zruší.", s["body"]),
        P("STOP z karty servisný beh ukončí. Keď sa servis zatvorí a príčina zastavenia ešte trvá, najbližší cyklus menič zastaví podľa bežných pravidiel.", s["body"]),
        P("Teplotné warningy", s["h2"]),
        P("Warning je žltý, je na spodku karty a nemá tlačidlo Ack. Warning kondenzátora zmizne, až keď t_cond_in klesne pod 27 °C. Bez stability meniča ostáva v pásme 27 až 29 °C. Pri stabilnom INVT smie t_cond_in ísť až do 31 °C a warning aj STOP prídu až nad 31 °C. Pri výpadku vzorky teplôt warning kondenzátora zmizne. Warning výparníka zmizne nad 19 °C a v pásme 17 až 19 °C ostáva. Warning generátora zmizne až vtedy, keď obe štartovacie teploty držia 2 minúty. Výpadok vzorky ho nezmaže.", s["body"]),
        table(
            ["Warning", "Kedy vznikne", "Čo systém urobí"],
            [
                [
                    "t_gen_in pod 80 °C mínus ready_hyst",
                    "Až keď je pod touto hranicou súvisle 15 s. Pri ready_hyst 1 je to pod 79 °C.",
                    "Ak menič beží mimo servisu, dostane STOP. Sám sa zapne, až keď obe štartovacie teploty držia 2 minúty. V servise ostane len warning a menič beží ďalej.",
                ],
                [
                    "t_evap_in pod 18 °C mínus ready_hyst",
                    "Až keď je pod touto hranicou súvisle 15 s. Pri ready_hyst 1 je to pod 17 °C. Medzi 17 a 19 °C ostáva posledný stav.",
                    "Ak menič beží mimo servisu, dostane STOP. Sám sa zapne, až keď je t_evap_in nad 19 °C súvisle 2 minúty a zároveň držia ostatné štartovacie podmienky. Servisný štart túto hranicu neberie. Neplatná vzorka automatický štart nepustí.",
                ],
                [
                    "t_cond_in nad ready_max alebo ready_max_stable plus ready_hyst",
                    "Bez stability nad 29 °C súvisle 15 s. Pri stabilnom INVT (PID v pásme) až nad 31 °C súvisle 15 s.",
                    "Ak menič beží mimo servisu, dostane STOP. Sám sa zapne, až keď obe teploty držia štartovaciu podmienku 2 minúty. Štart ostáva pod 27 °C.",
                ],
            ],
            [usable * 0.24, usable * 0.34, usable * 0.42],
        ),
        Spacer(1, 3),
        P("Automatický štart príde po zastavení od studeného výparníka, od studeného generátora, od horúceho kondenzátora, po kavitácii pri studenom generátore, alebo po zatvorení expanzného ventilu na 0 %. Pri ventile musí t_cond_in najprv prekročiť vypínaciu hranicu a až potom znova splniť štart. Parkovanie ventilu na 50 % štart nespustí. STOP z karty, externý stop na S4 a porucha meniča túto obnovu zrušia a stroj ostane stáť.", s["body"]),
        P("Keď menič už stojí a teplota je mimo hranice, warning sa ukáže, ale stroj sa sám nespustí.", s["body"]),
        P("Povel STOP sa zapíše až na konci cyklu, v ktorom podmienka platí. Menič ho dostane pri ďalšom čítaní, asi o 5 s, a dobieha podľa svojho času spomalenia.", s["body"]),
        P("Tlak a kavitácia", s["h2"]),
        P("Rozhoduje <b>p_gen_prim_from_frq</b>, čiže AI2 meniča. Tlak p_gen_prim zo slučky i6 je iný snímač a túto hranicu nespúšťa. p_evap_prim a p_cond_prim sa merajú, na štart ani na kavitáciu sa nepoužívajú.", s["body"]),
        P("Červený alarm Cavitation vznikne, keď naraz platí:", s["body"]),
        P("• Menič beží, je online a nemá vlastnú poruchu. Vzorka meniča nie je staršia ako cavitation_max_age_s, teraz 15 s.", s["bullet"]),
        P("• Tlak AI2 už bol aspoň 750 kPa v tejto jazde, alebo v histórii za cavitation_arm_lookback_s, teraz 3 hodiny.", s["bullet"]),
        P("• AI2 potom klesne pod 750 kPa a frekvencia dosiahne strop 45 Hz. Register má krok 0,01 Hz, preto sa berie už od 44,98 Hz.", s["bullet"]),
        P("• Oboje trvá 10 s.", s["bullet"]),
        P("• t_gen_in je aspoň 80 °C. Hysteréza túto hranicu neposúva. Ak teplota v tej chvíli chýba, berie sa to tiež ako alarm pre obsluhu.", s["bullet"]),
        Spacer(1, 2),
        P("Mimo servisu menič dostane STOP. Lišta ostane hore, kým obsluha v servise nestlačí Ack a príčina nezmizne. Až potom ide ručné RUN, a aj to len keď teploty dovoľujú štart. V servisnom behu ostane červený alarm aj mail, menič sa však nezastaví.", s["body"]),
        P("Ak je v okamihu kavitácie t_gen_in pod 80 °C, červený alarm nevznikne. Mimo servisu sa menič len zastaví a po návrate oboch štartovacích teplôt na 2 minúty sa sám spustí. V servise sa nezastaví.", s["body"]),
        P("Rozbeh pod 750 kPa, kým frekvencia strop nedosiahla, alarm nie je. Po zastavení tlak spadne na dno. Ani to kavitácia nie je.", s["body"]),
        P("Ostatné hlásenia", s["h2"]),
        P("Červený alarm je hore pod menu. Kým nie je potvrdený a príčina trvá, bežné RUN nejde. Žltý warning je dole na karte.", s["body"]),
        table(
            ["Hlásenie", "Kedy", "Reakcia"],
            [
                ["Výpadok komunikácie", "Tri cykly bez odpovede, asi 15 s.", "Alarm. Menič a modul prúdovej slučky blokujú RUN. Modul teplôt a ventil nie."],
                ["Porucha meniča", "Stav FAULT alebo nenulový kód poruchy.", "Alarm. Štart až keď porucha zmizne a obsluha ju potvrdí."],
                ["Prúdová slučka i6, i7, i8", "Prúd mimo 3,5–21 mA a vzorka nie je staršia ako 10 s.", "Pri behu alarm a blokuje RUN. Pri státí len warning."],
                ["Porucha ventilu EM2RS", "Pohon ventilu hlási alarm.", "Alarm. Čerpadlo nezastaví."],
                ["Externý stop S4", "Rozopnutý bezpečnostný vstup meniča.", "Nie je alarm. Menič zastaví voľnobehom. RUN nejde, kým sa spínač nezopne."],
            ],
            [usable * 0.24, usable * 0.36, usable * 0.40],
        ),
        Spacer(1, 3),
        P("Po každom STOP odíde expanzný ventil na parkovacích 50 %. Do automatického dolaďovania sa vráti, až keď menič znova beží a regulácia sedí pri žiadanom tlaku.", s["body"]),
        P("0 % znamená, že expanzný ventil je úplne zatvorený. Prah automatického STOP je valve.closed_stop_percent, teraz 0 %. Keď počas behu skutočné otvorenie klesne na túto hodnotu alebo pod ňu, menič dostane STOP. Hodnota „na“ tento stop vypne. Žiadaná poloha ani následné parkovanie na 50 % tento stop nespúšťajú a ani ho nezrušia. Opätovný štart čaká, kým t_cond_in prekročí 29 °C a potom spolu s t_gen_in znova vydrží štartovaciu podmienku 2 minúty. Kým je t_evap_in na nízkej strane alebo vzorka chýba, ani tento štart neprejde. Ručný STOP, S4, porucha meniča a kavitácia ho zrušia. Blokujúci alarm ho len pozdrží: po Ack a odznení príčiny menič nabehne sám. Servisný beh pri zatvorenom ventile nezastavuje.", s["body"]),
        P("Alarmové maily", s["h2"]),
        P("Červený alarm odíde raz, v okamihu vzniku. Žltý warning mail nespúšťa. Ten istý alarm, kým trvá, sa znova neposiela. Keď sa warning zmení na alarm, mail odíde.", s["body"]),
        P("Predmet je ALARM, meno stroja a kód. V texte je zdroj, zariadenie, správa, detail, čas a či alarm blokuje chod. Na správu sa neodpovedá.", s["body"]),
        P("Príjemca je teraz remote.access.raspi@gmail.com, zoznam je v config/emails.yaml. Odosielateľ a prihlásenie k pošte sú v config/secrets.yaml, sekcia smtp. Oba súbory sa čítajú pri odoslaní, reštart služieb netreba. Sú dva pokusy. Keď pošta neprejde, alarm na karte ostane a chyba je v denníku mastera.", s["body"]),
    ]
    doc = BaseDocTemplate(
        str(OUT),
        pagesize=A4,
        title="Ejector Lozorno — teploty, tlaky, alarmy a warningy",
        author="Ejector Lozorno",
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body", showBoundary=0)
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=draw_page)])
    doc.build(story)
    print(OUT)


if __name__ == "__main__":
    build()
