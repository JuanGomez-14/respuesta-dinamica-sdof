"""
Generador del REPORTE TÉCNICO en formato PDF.

Ejecuta los dos casos de estudio, recoge los resultados numéricos y las figuras
producidas por el motor de cálculo y arma un documento PDF con la estructura
exigida por la guía del proyecto de aula (sección 5.2):

    descripción de cada caso · idealización estructural · hipótesis adoptadas ·
    propiedades dinámicas · metodología de análisis · resultados principales ·
    representaciones gráficas · análisis paramétrico · factores de amplificación
    dinámica · transmisibilidad · verificación de los resultados ·
    interpretación física y estructural · conclusiones

Uso:
    python -m reporte.generar_reporte
    python main.py reporte
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

from dinamica import G, Rd, transmisibilidad

SALIDA = Path("salidas/Reporte-Tecnico-Respuesta-Dinamica.pdf")
ROJO = colors.HexColor("#C8102E")
AZUL = colors.HexColor("#12263A")
GRIS = colors.HexColor("#F2F2F2")


# ===========================================================================
#  Tipografía y estilos
# ===========================================================================
def _registrar_fuentes() -> str:
    """Registra DejaVu (incluida con matplotlib) para poder escribir β, ζ, ω, →."""
    base = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pdfmetrics.registerFont(TTFont("DejaVu", base / "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", base / "DejaVuSans-Bold.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVu-Obl", base / "DejaVuSans-Oblique.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVuMono", base / "DejaVuSansMono.ttf"))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                       italic="DejaVu-Obl", boldItalic="DejaVu-Bold")
    return "DejaVu"


def _estilos() -> dict:
    F = _registrar_fuentes()
    base = getSampleStyleSheet()
    e = {}
    e["cuerpo"] = ParagraphStyle("cuerpo", parent=base["BodyText"], fontName=F,
                                 fontSize=9.5, leading=13.5, alignment=TA_JUSTIFY,
                                 spaceAfter=6)
    e["titulo1"] = ParagraphStyle("t1", fontName="DejaVu-Bold", fontSize=15,
                                  leading=19, textColor=ROJO, spaceBefore=14,
                                  spaceAfter=8)
    e["titulo2"] = ParagraphStyle("t2", fontName="DejaVu-Bold", fontSize=12,
                                  leading=15, textColor=AZUL, spaceBefore=10,
                                  spaceAfter=5)
    e["titulo3"] = ParagraphStyle("t3", fontName="DejaVu-Bold", fontSize=10.5,
                                  leading=13, textColor=colors.black,
                                  spaceBefore=8, spaceAfter=3)
    e["pie"] = ParagraphStyle("pie", fontName="DejaVu-Obl", fontSize=8.2,
                              leading=10.5, alignment=TA_CENTER,
                              textColor=colors.HexColor("#444444"), spaceAfter=10)
    e["mono"] = ParagraphStyle("mono", fontName="DejaVuMono", fontSize=7.0,
                               leading=8.6, spaceAfter=6)
    e["celda"] = ParagraphStyle("celda", fontName="DejaVu", fontSize=8, leading=10)
    e["celda_b"] = ParagraphStyle("celdab", fontName="DejaVu-Bold", fontSize=8,
                                  leading=10, textColor=colors.white)
    e["portada_titulo"] = ParagraphStyle("pt", fontName="DejaVu-Bold", fontSize=21,
                                         leading=26, alignment=TA_CENTER,
                                         textColor=AZUL, spaceAfter=10)
    e["portada_sub"] = ParagraphStyle("ps", fontName="DejaVu", fontSize=12.5,
                                      leading=17, alignment=TA_CENTER,
                                      textColor=ROJO, spaceAfter=6)
    e["portada_txt"] = ParagraphStyle("px", fontName="DejaVu", fontSize=10.5,
                                      leading=15, alignment=TA_CENTER)
    e["nota"] = ParagraphStyle("nota", parent=e["cuerpo"], fontSize=8.6,
                               leading=11.5, leftIndent=10, rightIndent=10,
                               textColor=colors.HexColor("#333333"))
    return e


# ===========================================================================
#  Constructores de contenido
# ===========================================================================
class Reporte:
    def __init__(self):
        self.E = _estilos()
        self.flujo: list = []
        self.n_fig = 0
        self.n_tab = 0

    # ---------- texto ----------
    def p(self, texto: str, estilo: str = "cuerpo"):
        self.flujo.append(Paragraph(texto, self.E[estilo]))

    def h1(self, texto: str):
        self.flujo.append(Paragraph(texto, self.E["titulo1"]))

    def h2(self, texto: str):
        self.flujo.append(Paragraph(texto, self.E["titulo2"]))

    def h3(self, texto: str):
        self.flujo.append(Paragraph(texto, self.E["titulo3"]))

    def lista(self, items: list[str]):
        estilo = ParagraphStyle("vineta", parent=self.E["cuerpo"],
                                leftIndent=14, bulletIndent=2, spaceAfter=5)
        for it in items:
            self.flujo.append(Paragraph(it, estilo, bulletText="•"))

    def espacio(self, h: float = 0.35):
        self.flujo.append(Spacer(1, h * cm))

    def salto(self):
        self.flujo.append(PageBreak())

    def bloque_codigo(self, texto: str):
        seguro = (texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                  .replace(" ", "&nbsp;").replace("\n", "<br/>"))
        t = Table([[Paragraph(seguro, self.E["mono"])]], colWidths=[16.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F7F7")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        self.flujo.append(t)
        self.espacio(0.25)

    def agrupar_desde(self, indice: int):
        """Agrupa lo añadido desde ``indice`` para que no se parta entre páginas."""
        grupo = self.flujo[indice:]
        del self.flujo[indice:]
        self.flujo.append(KeepTogether(grupo))

    def nota(self, texto: str):
        t = Table([[Paragraph(texto, self.E["nota"])]], colWidths=[16.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBF3F4")),
            ("LINEBEFORE", (0, 0), (0, -1), 2.5, ROJO),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        self.flujo.append(t)
        self.espacio(0.25)

    # ---------- tablas ----------
    def tabla(self, encabezados: list[str], filas: list[list], anchos=None,
              pie: str | None = None, tam: float = 8.0):
        self.n_tab += 1
        est_h = ParagraphStyle("h", parent=self.E["celda_b"], fontSize=tam)
        est_c = ParagraphStyle("c", parent=self.E["celda"], fontSize=tam)
        datos = [[Paragraph(str(h), est_h) for h in encabezados]]
        datos += [[Paragraph(str(c), est_c) for c in fila] for fila in filas]
        t = Table(datos, colWidths=anchos, repeatRows=1, hAlign="CENTER")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ROJO),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        self.flujo.append(t)
        if pie:
            self.flujo.append(Paragraph(f"Tabla {self.n_tab}. {pie}", self.E["pie"]))
        else:
            self.espacio(0.3)

    # ---------- figuras ----------
    def figura(self, ruta: str | Path, pie: str, ancho: float = 15.5):
        ruta = Path(ruta)
        if not ruta.exists():
            self.p(f"[figura no encontrada: {ruta}]")
            return
        self.n_fig += 1
        from PIL import Image as PILImage
        try:
            w, h = PILImage.open(ruta).size
        except Exception:                                  # pragma: no cover
            w, h = 1600, 900
        ancho_cm = ancho * cm
        alto_cm = ancho_cm * h / w
        maximo = 19.0 * cm
        if alto_cm > maximo:
            alto_cm, ancho_cm = maximo, maximo * w / h
        img = Image(str(ruta), width=ancho_cm, height=alto_cm)
        img.hAlign = "CENTER"
        self.flujo.append(KeepTogether([
            img, Paragraph(f"Figura {self.n_fig}. {pie}", self.E["pie"])]))


# ===========================================================================
#  Plantilla de página (encabezado, pie y numeración)
# ===========================================================================
def _decorar(canvas, doc):
    canvas.saveState()
    canvas.setFont("DejaVu", 7.5)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(2.2 * cm, A4[1] - 1.25 * cm,
                      "Universidad de Medellín · Dinámica de Estructuras · "
                      "Laboratorio Computacional de Respuesta Dinámica")
    canvas.setStrokeColor(ROJO)
    canvas.setLineWidth(0.8)
    canvas.line(2.2 * cm, A4[1] - 1.4 * cm, A4[0] - 2.2 * cm, A4[1] - 1.4 * cm)
    canvas.line(2.2 * cm, 1.5 * cm, A4[0] - 2.2 * cm, 1.5 * cm)
    canvas.drawRightString(A4[0] - 2.2 * cm, 1.1 * cm, f"Página {doc.page}")
    canvas.drawString(2.2 * cm, 1.1 * cm, "Reporte técnico — Proyecto de aula 2026")
    canvas.restoreState()


def _portada(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(ROJO)
    canvas.rect(0, A4[1] - 1.1 * cm, A4[0], 1.1 * cm, stroke=0, fill=1)
    canvas.rect(0, 0, A4[0], 0.7 * cm, stroke=0, fill=1)
    canvas.restoreState()


# ===========================================================================
#  Contenido del reporte
# ===========================================================================
def construir(R1: dict, R2: dict) -> Reporte:
    rep = Reporte()
    s1, c1 = R1["sistema"], R1["carga"]
    s2 = R2["sistema"]
    f1 = R1.get("figuras", {})
    f2 = R2.get("figuras", {})

    # ---------------------------------------------------------------- portada
    rep.espacio(2.2)
    rep.p("UNIVERSIDAD DE MEDELLÍN", "portada_sub")
    rep.p("Facultad de Ingeniería · Programa de Ingeniería Civil", "portada_txt")
    rep.espacio(1.4)
    rep.p("LABORATORIO COMPUTACIONAL<br/>DE RESPUESTA DINÁMICA", "portada_titulo")
    rep.espacio(0.5)
    rep.p("Reporte técnico del proyecto de aula", "portada_sub")
    rep.p("Análisis de la respuesta dinámica de sistemas de un grado de libertad "
          "sometidos a cargas armónicas, impulsivas y excitaciones arbitrarias",
          "portada_txt")
    rep.espacio(1.6)
    rep.tabla(
        ["Concepto", "Descripción"],
        [["Asignatura", "Dinámica de Estructuras"],
         ["Programa", "Ingeniería Civil"],
         ["Entregables", "Plataforma de cálculo (paquete <b>dinamica</b>) y este reporte técnico"],
         ["Casos de estudio",
          "1) Entrepiso industrial con máquina rotativa (carga armónica)<br/>"
          "2) Tanque elevado bajo sismo (excitación arbitraria) e impacto (carga impulsiva)"],
         ["Motor de cálculo",
          "Python 3 · integración directa de Newmark · interpolación exacta · "
          "Duhamel · soluciones analíticas de verificación"],
         ["Unidades", "Sistema Internacional (kg, N, m, s); resultados en mm, kN y g"]],
        anchos=[3.6 * cm, 12.4 * cm])
    rep.espacio(1.2)
    rep.p("Medellín, Colombia · 2026", "portada_txt")
    rep.flujo.append(NextPageTemplate("normal"))
    rep.salto()

    # ------------------------------------------------------------- 1. objetivo
    rep.h1("1. Objetivo y alcance")
    rep.p("Este reporte presenta los resultados obtenidos con la plataforma de cálculo "
          "desarrollada para evaluar la respuesta dinámica de sistemas estructurales de un "
          "grado de libertad (SDOF) sometidos a cargas armónicas, cargas impulsivas y "
          "excitaciones dinámicas arbitrarias. El propósito no es únicamente obtener "
          "resultados numéricos, sino verificar su coherencia, interpretar las tendencias "
          "observadas e identificar las variables que controlan la respuesta, con miras a "
          "establecer estrategias de control del comportamiento estructural.")
    rep.p("Se resuelven dos casos de estudio. En el primero, una plataforma industrial de "
          "acero soporta un ventilador cuyo desbalance genera una fuerza armónica; el "
          "problema es de <b>servicio y vibraciones</b> y se encuentra en condición de "
          "resonancia. En el segundo, un tanque de agua elevado se analiza ante un "
          "acelerograma (excitación arbitraria integrada con el método de Newmark) y ante "
          "una carga impulsiva; el problema es de <b>resistencia y desplazamientos</b>.")

    rep.h2("1.1 Estructura del documento")
    rep.lista([
        "<b>Sección 2</b>: descripción de la plataforma de cálculo y de los métodos implementados.",
        "<b>Sección 3</b>: verificación del motor (contraste con soluciones analíticas, "
        "equilibrio dinámico, balance de energía y convergencia).",
        "<b>Sección 4</b>: caso 1 — carga armónica, amplificación dinámica y transmisibilidad.",
        "<b>Sección 5</b>: caso 2 — excitación sísmica arbitraria y carga impulsiva.",
        "<b>Sección 6</b>: conclusiones generales.",
    ])

    # -------------------------------------------------------- 2. la plataforma
    rep.h1("2. Plataforma o motor de cálculo")
    rep.p("La herramienta se implementó como un paquete de Python denominado "
          "<b>dinamica</b>, organizado en módulos independientes. El diseño busca que la "
          "plataforma sea <b>general</b>: los dos casos de estudio son sólo dos archivos de "
          "datos que la utilizan, y cualquier otro sistema puede analizarse sin modificar "
          "el núcleo de cálculo.")
    rep.tabla(
        ["Módulo", "Responsabilidad"],
        [["<b>unidades</b>", "Constantes y conversión de unidades (t, kN, mm, GPa, cm⁴, rpm, g → SI)."],
         ["<b>sistema</b>", "Clase <b>SistemaSDOF</b> (m, k, ζ) y propiedades derivadas (ωn, Tn, c, ωD). "
                            "Idealización: resortes en serie/paralelo, rigidez de columnas, "
                            "sistemas equivalentes de masa distribuida (Rayleigh), "
                            "identificación de ζ por decremento logarítmico o ancho de banda."],
         ["<b>cargas</b>", "Catálogo de excitaciones: armónica, barrido de frecuencias, pulsos "
                           "(rectangular, triangular, medio seno, exponencial), escalón, rampa, "
                           "serie temporal arbitraria y excitación en la base."],
         ["<b>solucionadores</b>", "Newmark directo (β, γ), interpolación exacta de la excitación, "
                                   "integral de Duhamel y soluciones analíticas cerradas."],
         ["<b>frecuencia</b>", "Rd, Rv, Ra, ángulo de fase, transmisibilidad y diseño de aislamiento."],
         ["<b>espectros</b>", "Espectros de respuesta sísmicos (Sd, PSv, PSa) y espectros de choque."],
         ["<b>parametrico</b>", "Barridos automáticos de masa, rigidez, amortiguamiento, "
                                "frecuencia, amplitud y duración de la carga."],
         ["<b>verificacion</b>", "Residual de la ecuación de movimiento, balance de energía, "
                                 "comparación con soluciones de referencia y convergencia."],
         ["<b>graficos</b>", "Figuras normalizadas con título, ejes rotulados y unidades."],
         ["<b>io_senales</b>", "Lectura de señales (CSV, TXT, PEER .AT2), corrección de línea base, "
                               "filtrado, remuestreo y generación de registros sintéticos."]],
        anchos=[3.2 * cm, 12.8 * cm],
        pie="Organización de la plataforma de cálculo desarrollada.")

    rep.h2("2.1 Formulación implementada")
    rep.p("La ecuación de movimiento del sistema de un grado de libertad es")
    rep.bloque_codigo("m·u''(t) + c·u'(t) + k·u(t) = p(t)      [u' = velocidad, u'' = aceleración]")
    rep.p("con ω<sub>n</sub> = √(k/m), T<sub>n</sub> = 2π/ω<sub>n</sub>, "
          "c<sub>cr</sub> = 2·m·ω<sub>n</sub> y ζ = c/c<sub>cr</sub>. Para excitación en la "
          "base la carga efectiva es p<sub>ef</sub>(t) = −m·ü<sub>g</sub>(t) y la respuesta "
          "u(t) obtenida es el desplazamiento <b>relativo</b> a la base; la aceleración "
          "absoluta se recupera como ü<sub>t</sub> = ü + ü<sub>g</sub>.")
    rep.h3("Método de Newmark directo (integración paso a paso)")
    rep.p("Se implementó la formulación incremental con rigidez efectiva:")
    rep.bloque_codigo(
        "k_ef = k + (γ/(β·Δt))·c + m/(β·Δt²)\n"
        "Dp_ef,i = Dp_i + [m/(b·Dt) + (g/b)·c]·v_i + [m/(2b) + Dt·(g/(2b) - 1)·c]·a_i\n"
        "Du_i    = Dp_ef,i / k_ef\n"
        "Dv_i    = (g/(b·Dt))·Du_i - (g/b)·v_i + Dt·(1 - g/(2b))·a_i\n"
        "Da_i    = Du_i/(b·Dt²) - v_i/(b·Dt) - a_i/(2b)\n\n"
        "  D = incremento (delta) ; b = beta ; g = gamma ; v = velocidad ; a = aceleración")
    rep.p("Por defecto se emplea la familia de <b>aceleración promedio</b> (γ = 1/2, "
          "β = 1/4), incondicionalmente estable. También están disponibles la aceleración "
          "lineal (β = 1/6, estable si Δt ≤ 0.551·T<sub>n</sub>) y la diferencia central "
          "(β = 0, estable si Δt ≤ T<sub>n</sub>/π); la plataforma verifica el límite de "
          "estabilidad y avisa cuando el paso de tiempo es inadmisible.")
    rep.h3("Métodos de referencia para verificación")
    rep.lista([
        "<b>Interpolación exacta</b>: solución cerrada suponiendo que la carga varía "
        "linealmente dentro de cada paso; es exacta para cargas definidas punto a punto y "
        "sirve como patrón contra el cual se mide el error de Newmark.",
        "<b>Integral de Duhamel</b>: evaluación numérica de la superposición de respuestas "
        "a impulsos elementales.",
        "<b>Soluciones analíticas cerradas</b>: vibración libre, respuesta armónica total "
        "(transitoria + permanente), resonancia no amortiguada y pulsos clásicos con sus "
        "fases forzada y libre.",
    ])
    rep.nota("<b>Unidades.</b> Todo el cálculo interno se realiza en SI coherente "
             "(kg, N/m, N·s/m, N, m, s, rad/s). La entrada admite unidades usuales de "
             "ingeniería mediante conversores explícitos (t, tonf, kN, mm, GPa, cm⁴, rpm, "
             "g, gal) y la salida se presenta en mm, kN, m/s² y g. Este control explícito "
             "de unidades evita el error más frecuente en este tipo de análisis.")

    _i22 = len(rep.flujo)
    rep.h2("2.2 Uso de la plataforma")
    rep.p("La misma herramienta se puede usar de cuatro formas, todas equivalentes "
          "porque comparten el mismo núcleo de cálculo. La primera es un "
          "<b>menú interactivo por consola</b> que solicita los datos uno a uno, "
          "indica la unidad esperada de cada variable, admite unidades de ingeniería "
          "(30 t, 8500 kN/m, 3692 cm⁴, 0.25 g) convirtiéndolas automáticamente a SI, "
          "e interpreta el resultado (avisa si el sistema quedó en resonancia, en zona "
          "de aislamiento o si el pulso está en régimen impulsivo).")
    rep.bloque_codigo(
        "# 1) Menú interactivo (pide los datos uno por uno)\n"
        "python main.py            # sin argumentos abre el menú\n"
        "python menu.py            # equivalente\n\n"
        "# 2) Desde la línea de comandos (para repetir un cálculo de una sola vez)\n"
        "python main.py armonica --masa 24000 --rigidez 8.27e6 --zeta 0.02 \\\n"
        "                        --p0 1600 --rpm 180 --tfinal 25\n"
        "python main.py arbitraria --masa 80545 --periodo 0.77 --zeta 0.05 \\\n"
        "                        --archivo registro.csv --unidad g\n\n"
        "# 3) Desde la interfaz gráfica interactiva\n"
        "streamlit run app_streamlit.py\n\n"
        "# 4) Desde un script de Python (máxima flexibilidad)\n"
        "from dinamica import SistemaSDOF, CargaArmonica, resolver\n"
        "s = SistemaSDOF(masa=24_000, rigidez=8.27e6, zeta=0.02)\n"
        "r = resolver(s, CargaArmonica(p0=1600, omega=18.85), t_final=25)\n"
        "print(r.resumen())")
    rep.agrupar_desde(_i22)

    rep.salto()

    # ----------------------------------------------- 3. verificación del motor
    rep.h1("3. Verificación del motor de cálculo")
    rep.p("Antes de aplicar la herramienta a los casos de estudio se comprobó su "
          "funcionamiento mediante cuatro tipos de verificación independientes.")

    rep.h2("3.1 Contraste con soluciones analíticas")
    rep.tabla(
        ["Problema", "Solución analítica", "Resultado numérico", "Error"],
        [["Carga armónica, β = %.3f, ζ = %.2f (caso 1)" % (R1["beta"], s1.zeta),
          "%.4f mm" % (R1["u_max_analitica"] * 1e3),
          "%.4f mm" % (R1["u_max_newmark"] * 1e3),
          "%.4f %%" % (R1["error_pico_newmark"] * 100)],
         ["Amplitud permanente (p₀/k)·R<sub>d</sub>",
          "%.4f mm" % (R1["u_permanente"] * 1e3),
          "%.4f mm" % (R1["u_permanente_medida"] * 1e3),
          "%.4f %%" % (R1["error_amplitud_permanente"] * 100)],
         ["Pulso triangular sin amortiguamiento (caso 2B): solución cerrada "
          "(fase forzada + fase libre) vs. interpolación exacta",
          "%.4f mm" % (R2["impulso"]["respuesta_analitica"].u_max * 1e3),
          "%.4f mm" % (R2["impulso"]["u_max_sin_amortiguamiento"] * 1e3),
          "%.5f %%" % (R2["impulso"]["error_sin_amortiguamiento"] * 100)],
         ["Pulso triangular con ζ = 5 %: Newmark vs. interpolación exacta",
          "%.4f mm" % (R2["impulso"]["respuesta_exacta"].u_max * 1e3),
          "%.4f mm" % (R2["impulso"]["u_max"] * 1e3),
          "%.5f %%" % (R2["impulso"]["error_newmark"] * 100)],
         ["Excitación arbitraria (sismo): Newmark vs. interpolación exacta",
          "%.4f mm" % (R2["respuesta_sismo_exacta"].u_max * 1e3),
          "%.4f mm" % (R2["respuesta_sismo"].u_max * 1e3),
          "%.4f %%" % (R2["verificacion_sismo"].comparaciones[0]["error_pico [-]"] * 100)],
         ["S<sub>d</sub>(T<sub>n</sub>) del espectro (barrido independiente de 90 "
          "periodos) vs. |u|<sub>máx</sub> de la historia de Newmark",
          "%.4f mm" % (R2["espectro_en_Tn"]["Sd [m]"] * 1e3),
          "%.4f mm" % (R2["respuesta_sismo"].u_max * 1e3),
          "%.4f %%" % (R2["error_espectro_vs_historia"] * 100)],
         ["Aproximación impulsiva u ≈ I/(m·ω<sub>n</sub>)",
          "%.4f mm" % (R2["impulso"]["u_aproximacion_impulsiva"] * 1e3),
          "%.4f mm" % (R2["impulso"]["respuesta_analitica"].u_max * 1e3),
          "%.2f %%" % (R2["impulso"]["error_aproximacion"] * 100)]],
        anchos=[6.6 * cm, 3.2 * cm, 3.2 * cm, 2.6 * cm],
        pie="Verificación del motor de cálculo frente a soluciones de referencia.")
    rep.figura(f1.get("verificacion", ""),
               "Superposición de la solución analítica exacta, la interpolación exacta y "
               "el método de Newmark para el caso 1. Las tres curvas son indistinguibles "
               "a escala de dibujo.")

    rep.h2("3.2 Equilibrio dinámico y balance de energía")
    v1 = R2["verificacion_sismo"]
    rep.p("En cada instante se comprueba el residual de la ecuación de movimiento "
          "r(t) = m·a + c·v + k·u − p(t) y, al final del análisis, que la energía "
          "introducida por la carga se reparta entre energía cinética, energía de "
          "deformación y energía disipada por el amortiguador.")
    rep.tabla(
        ["Indicador", "Caso 2A (sismo)", "Caso 2B (impulso)", "Criterio"],
        [["Residual máximo relativo de m·a + c·v + k·u − p",
          "%.2e" % v1.equilibrio["residual_max_relativo [-]"],
          "%.2e" % R2["verificacion_impulso"].equilibrio["residual_max_relativo [-]"],
          "&lt; 1×10⁻⁶"],
         ["Error de cierre del balance energético",
          "%.4f %%" % (v1.energia["error_cierre [-]"] * 100),
          "%.4f %%" % (R2["verificacion_impulso"].energia["error_cierre [-]"] * 100),
          "&lt; 1 %"],
         ["Energía introducida por la excitación",
          "%.1f J" % v1.energia["E_entrada [J]"],
          "%.1f J" % R2["verificacion_impulso"].energia["E_entrada [J]"], "—"],
         ["Energía disipada por amortiguamiento",
          "%.1f J" % v1.energia["E_disipada [J]"],
          "%.1f J" % R2["verificacion_impulso"].energia["E_disipada [J]"], "—"]],
        anchos=[7.0 * cm, 3.2 * cm, 3.2 * cm, 2.2 * cm],
        pie="Coherencia física de la solución numérica.")

    rep.h2("3.3 Convergencia con el paso de tiempo")
    conv = R1["convergencia"]
    filas = []
    for rz, e_p, e_l in zip(conv["razones"], conv["aceleracion_promedio"],
                            conv["aceleracion_lineal"]):
        filas.append([f"T<sub>n</sub>/{round(1/rz):.0f}", f"{rz:.4f}",
                      f"{e_p*100:+.4f} %", f"{e_l*100:+.4f} %"])
    rep.tabla(["Paso de tiempo", "Δt/T<sub>n</sub>",
               "Error, aceleración promedio (β=1/4)",
               "Error, aceleración lineal (β=1/6)"],
              filas, anchos=[3.4 * cm, 3.0 * cm, 5.0 * cm, 5.0 * cm],
              pie="Error del pico de desplazamiento frente a la solución analítica exacta "
                  "(caso 1). Ambos esquemas convergen con orden 2; el error se reduce "
                  "aproximadamente cuatro veces al dividir Δt por dos.")
    rep.figura(f1.get("convergencia", ""),
               "Convergencia del integrador de Newmark. Con Δt = T<sub>n</sub>/100 el error "
               "del pico ya es inferior al 1 %, y con T<sub>n</sub>/200 (valor adoptado en "
               "los análisis) es del orden de 0.1 %.")
    rep.nota("<b>Criterio adoptado.</b> En todos los análisis se usó Δt ≤ T<sub>n</sub>/100 "
             "y, para excitaciones registradas, adicionalmente Δt ≤ Δt<sub>señal</sub>, de "
             "modo que la discretización nunca degrada la información de la excitación.")

    rep.h2("3.4 Pruebas automáticas")
    rep.p("La plataforma incluye 85 pruebas automáticas (<i>pytest</i>) que se ejecutan con "
          "<b>python main.py verificar</b>. Además de los contrastes analíticos, verifican "
          "límites teóricos conocidos: R<sub>d</sub> = 1/(2ζ) en resonancia; TR = 1 en "
          "β = √2 para cualquier ζ; R<sub>d</sub> = 2 para una carga súbita mantenida; "
          "R<sub>d</sub> → 1 cuando β → 0 y R<sub>d</sub> → 0 cuando β ≫ 1; conservación de "
          "energía en vibración libre no amortiguada; identificación del amortiguamiento "
          "por decremento logarítmico; y que una estructura muy rígida se mueva "
          "solidariamente con el terreno.")

    rep.salto()

    # ================================================================= CASO 1
    rep.h1("4. Caso de estudio 1 — Carga armónica")
    rep.h2("4.1 Descripción del caso")
    rep.p("Plataforma industrial de un nivel (6.0 m × 5.0 m) formada por cuatro columnas "
          "de acero y una losa de concreto que actúa como diafragma rígido. Sobre la losa "
          "opera un ventilador centrífugo a %.0f rpm cuyo rotor presenta un desbalance "
          "residual de %.0f kg con una excentricidad de %.0f mm. Se requiere evaluar las "
          "vibraciones de servicio de la plataforma y la fuerza que se transmite a la "
          "cimentación."
          % (R1["datos"]["velocidad_rpm"], R1["datos"]["masa_excentrica"],
             R1["datos"]["excentricidad"] * 1e3))

    rep.h2("4.2 Idealización estructural e hipótesis adoptadas")
    rep.lista([
        "<b>H1.</b> El diafragma es rígido en su plano: los cuatro nudos superiores tienen "
        "el mismo desplazamiento lateral u(t). El sistema queda reducido a <b>un grado de "
        "libertad</b> por dirección de análisis.",
        "<b>H2.</b> Toda la masa (losa, acabados y equipo) se concentra en el nivel de la "
        "losa; la masa de las columnas es despreciable frente a ella.",
        "<b>H3.</b> Las columnas aportan únicamente rigidez lateral por flexión. Con vigas "
        "y losa muy rígidas se comportan como <b>empotradas-empotradas</b>: "
        "k<sub>col</sub> = 12·E·I/L³.",
        "<b>H4.</b> Las cuatro columnas comparten el mismo desplazamiento: trabajan en "
        "<b>paralelo</b> y sus rigideces se suman, k = Σ k<sub>col</sub>.",
        "<b>H5.</b> Amortiguamiento viscoso equivalente ζ = %.0f %% (estructura metálica "
        "sin elementos no estructurales que disipen energía)." % (s1.zeta * 100),
        "<b>H6.</b> Comportamiento elástico y lineal.",
        "<b>H7.</b> La fuerza del desbalance es armónica y proporcional al cuadrado de la "
        "velocidad de giro: p(t) = m<sub>e</sub>·e·ω²·sen(ωt).",
    ])

    rep.h2("4.3 Propiedades dinámicas del sistema equivalente")
    rep.tabla(
        ["Propiedad", "Expresión", "Valor"],
        [["Masa equivalente", "m = m<sub>losa</sub> + m<sub>equipo</sub>",
          f"{s1.masa:,.0f} kg"],
         ["Rigidez de una columna", "k₁ = 12·E·I/L³",
          f"{s1.metadatos['k_por_columna']:,.0f} N/m"],
         ["Rigidez lateral total", "k = 4·k₁", f"{s1.rigidez:,.0f} N/m"],
         ["Frecuencia natural", "ω<sub>n</sub> = √(k/m)", f"{s1.omega_n:.4f} rad/s"],
         ["Frecuencia natural", "f<sub>n</sub> = ω<sub>n</sub>/2π", f"{s1.f_n:.4f} Hz"],
         ["Periodo natural", "T<sub>n</sub> = 2π/ω<sub>n</sub>", f"{s1.T_n:.4f} s"],
         ["Amortiguamiento crítico", "c<sub>cr</sub> = 2·m·ω<sub>n</sub>",
          f"{s1.c_critico:,.0f} N·s/m"],
         ["Amortiguamiento", "c = ζ·c<sub>cr</sub>", f"{s1.amortiguamiento:,.0f} N·s/m"],
         ["Frecuencia de la excitación", "ω = 2π·rpm/60", f"{c1.omega:.4f} rad/s "
          f"({c1.frecuencia_hz:.3f} Hz)"],
         ["Amplitud de la fuerza", "p₀ = m<sub>e</sub>·e·ω²", f"{c1.p0:,.1f} N"],
         ["<b>Relación de frecuencias</b>", "<b>β = ω/ω<sub>n</sub></b>",
          f"<b>{R1['beta']:.4f}</b>"]],
        anchos=[5.0 * cm, 5.0 * cm, 6.0 * cm],
        pie="Propiedades dinámicas del sistema equivalente de un grado de libertad (caso 1).")
    rep.nota("La relación de frecuencias resultante, β = %.4f, sitúa a la máquina "
             "prácticamente <b>en resonancia</b> con la estructura: la frecuencia de "
             "operación (%.3f Hz) casi coincide con la frecuencia natural del entrepiso "
             "(%.3f Hz). Ésta es la condición más desfavorable posible y explica todo el "
             "comportamiento observado."
             % (R1["beta"], c1.frecuencia_hz, s1.f_n))

    rep.h2("4.4 Resultados principales")
    sv = R1["servicio"]
    rep.tabla(
        ["Variable de respuesta", "Valor", "Observación"],
        [["Desplazamiento estático u<sub>st</sub> = p₀/k",
          f"{R1['u_estatico']*1e3:.4f} mm", "referencia de comparación"],
         ["Factor de amplificación dinámica R<sub>d</sub>", f"{R1['Rd']:.2f}",
          f"máximo posible con ζ = {s1.zeta:.2f}: {R1['Rd_maximo_posible']:.2f}"],
         ["Amplitud permanente u₀ = u<sub>st</sub>·R<sub>d</sub>",
          f"{R1['u_permanente']*1e3:.4f} mm",
          f"límite de servicio: {sv['limite_u_mm']:.1f} mm → "
          f"<b>{'cumple' if sv['cumple_u'] else 'NO CUMPLE'}</b>"],
         ["Pico transitorio (Newmark)", f"{R1['u_max_newmark']*1e3:.4f} mm",
          "supera transitoriamente la amplitud permanente"],
         ["Velocidad máxima v₀ = ω·u₀", f"{R1['velocidad_permanente']*1e3:.2f} mm/s",
          "referencia usual de vibración en maquinaria"],
         ["Aceleración máxima a₀ = ω²·u₀",
          f"{R1['aceleracion_permanente']:.3f} m/s² ({sv['a_g']:.4f} g)",
          f"límite de servicio: {sv['limite_a_g']:.3f} g → "
          f"<b>{'cumple' if sv['cumple_a'] else 'NO CUMPLE'}</b>"],
         ["Transmisibilidad TR", f"{R1['TR']:.2f}", "&gt; 1: amplifica hacia la cimentación"],
         ["Fuerza transmitida f<sub>T</sub> = p₀·TR",
          f"{R1['fuerza_transmitida']/1e3:.2f} kN",
          f"la fuerza aplicada es sólo {c1.p0/1e3:.2f} kN"]],
        anchos=[6.2 * cm, 4.2 * cm, 5.6 * cm],
        pie="Resultados del caso 1 en condición de operación permanente.")

    rep.figura(f1.get("historia", ""),
               "Historia completa de respuesta del entrepiso: carga aplicada, "
               "desplazamiento, velocidad y aceleración. Se observa el crecimiento "
               "progresivo de la amplitud hasta alcanzar el régimen permanente, "
               "controlado por el amortiguamiento.")

    rep.h2("4.5 Factor de amplificación dinámica")
    rep.p("El factor de amplificación dinámica relaciona la amplitud dinámica con el "
          "desplazamiento que produciría la misma fuerza aplicada estáticamente:")
    rep.bloque_codigo("R_d = u₀/(p₀/k) = 1/√[(1 − β²)² + (2ζβ)²]")
    rep.p("Su máximo se produce en β = √(1 − 2ζ²) y vale 1/(2ζ√(1 − ζ²)); para "
          "amortiguamientos pequeños, R<sub>d,máx</sub> ≈ 1/(2ζ). Con ζ = %.2f esto "
          "significa una amplificación potencial de %.1f veces, y el sistema analizado "
          "alcanza %.1f veces por estar a β = %.3f."
          % (s1.zeta, R1["Rd_maximo_posible"], R1["Rd"], R1["beta"]))
    rep.figura(f1.get("Rd", ""),
               "Factor de amplificación dinámica en función de la relación de frecuencias "
               "y del amortiguamiento, con el punto de operación de la máquina señalado. "
               "En la vecindad de β = 1 la respuesta queda gobernada exclusivamente por ζ.")

    rep.h2("4.6 Transmisibilidad")
    rep.p("La transmisibilidad mide qué fracción de la fuerza de excitación llega a la "
          "cimentación (o qué fracción del movimiento del apoyo llega a la masa):")
    rep.bloque_codigo("TR = √[1 + (2ζβ)²] / √[(1 − β²)² + (2ζβ)²]")
    rep.p("Todas las curvas pasan por TR = 1 en β = √2 ≈ 1.414, independientemente del "
          "amortiguamiento. Para β &lt; √2 el sistema <b>amplifica</b> y para β &gt; √2 "
          "<b>aísla</b>. Un resultado central del diseño de aislamiento es que, en la zona "
          "de aislamiento, aumentar el amortiguamiento <b>empeora</b> la transmisión de "
          "fuerza, al contrario de lo que ocurre en la zona de amplificación.")
    rep.figura(f1.get("TR", ""),
               "Curva de transmisibilidad con las zonas de amplificación y de aislamiento. "
               "El punto de operación se encuentra en plena zona de amplificación "
               f"(TR = {R1['TR']:.1f}), es decir, la cimentación recibe una fuerza "
               f"{R1['TR']:.0f} veces mayor que la que genera el desbalance.")
    rep.figura(f1.get("fase", ""),
               "Ángulo de fase entre la carga y la respuesta. En resonancia el "
               "desplazamiento se retrasa exactamente 90° respecto a la fuerza: en ese "
               "instante la fuerza aplicada está en fase con la velocidad y, por tanto, "
               "entrega la máxima energía al sistema en cada ciclo.")

    rep.h2("4.7 Análisis paramétrico")
    rep.p("El análisis paramétrico no busca generar más números, sino establecer "
          "tendencias y explicar físicamente el porqué de los cambios observados.")
    filas = []
    for etiqueta, clave in [("Relación de frecuencias β", "beta"),
                            ("Amortiguamiento ζ", "zeta"),
                            ("Rigidez k", "rigidez"), ("Masa m", "masa"),
                            ("Velocidad de la máquina", "rpm")]:
        v = R1["barridos"][clave].variacion("u_max [mm]")
        filas.append([etiqueta, f"{v['minimo']:.3f} mm", f"{v['maximo']:.3f} mm",
                      f"{v['razon_max_min']:.1f}×"])
    rep.tabla(["Variable estudiada", "u<sub>máx</sub> mínimo", "u<sub>máx</sub> máximo",
               "Razón"], filas,
              anchos=[6.0 * cm, 3.4 * cm, 3.4 * cm, 3.2 * cm],
              pie="Rango de variación de la respuesta en cada barrido paramétrico (caso 1).")
    rep.figura(f1.get("barrido_beta", ""),
               "Efecto de la relación de frecuencias. Es, con diferencia, la variable más "
               "influyente: la respuesta varía en dos órdenes de magnitud entre la zona "
               "cuasi-estática (β ≪ 1), la resonancia (β ≈ 1) y la zona inercial (β ≫ 1).")
    rep.figura(f1.get("barrido_zeta", ""),
               "Efecto del amortiguamiento operando en resonancia. Aquí la respuesta es "
               "inversamente proporcional a ζ; fuera de la resonancia su influencia es "
               "mucho menor.")
    rep.figura(f1.get("barrido_k_m", ""),
               "Efecto de la masa y de la rigidez, representado frente al periodo natural "
               "resultante. Ambas variables actúan por el mismo mecanismo: modifican "
               "T<sub>n</sub> y con ello la posición del punto de operación respecto a la "
               "resonancia. Rigidizar desplaza el sistema hacia β &lt; 1; añadir masa lo "
               "desplaza hacia β &gt; 1.")
    rep.figura(f1.get("barrido_rpm", ""),
               "Efecto de la velocidad de operación de la máquina. La curva combina dos "
               "efectos: la fuerza de desbalance crece con ω² y, simultáneamente, β cambia. "
               "El pico se produce cuando la velocidad de giro coincide con la frecuencia "
               "natural.")
    rep.figura(f1.get("limites", ""),
               "Casos límite sin amortiguamiento: resonancia exacta (crecimiento lineal "
               "ilimitado de la amplitud) y batido (β próximo a 1, con intercambio "
               "periódico de energía entre la excitación y el sistema).")
    rep.figura(f1.get("arranque", ""),
               "Arranque de la máquina simulado como un barrido de frecuencias. El paso "
               "por la resonancia produce un pico de "
               f"{R1['arranque']['u_max']*1e3:.2f} mm, sólo el "
               f"{R1['arranque']['razon_vs_permanente']*100:.0f} % de la amplitud que se "
               "alcanzaría operando permanentemente en resonancia: la estructura no "
               "alcanza a desarrollar la amplificación completa.")

    rep.h2("4.8 Estrategias de control de la respuesta")
    ctrl = R1["control"]
    rep.tabla(
        ["Estrategia", "Acción", "Resultado", "Valoración"],
        [["Rigidizar la estructura",
          f"llevar k de {s1.rigidez/1e6:.2f} a {ctrl['rigidizar']['k']/1e6:.2f} MN/m "
          f"({ctrl['rigidizar']['factor_k']:.1f}×) con arriostramientos, "
          f"β pasa de {R1['beta']:.2f} a 0.50",
          f"u₀ = {ctrl['rigidizar']['u']*1e3:.3f} mm "
          f"(−{ctrl['rigidizar']['reduccion']*100:.0f} %)",
          "muy eficaz; requiere intervenir la estructura y verificar la cimentación"],
         ["Aumentar el amortiguamiento",
          "instalar amortiguadores viscosos hasta ζ = 10 %",
          f"u₀ = {ctrl['amortiguar']['u']*1e3:.3f} mm "
          f"(−{ctrl['amortiguar']['reduccion']*100:.0f} %)",
          "eficaz sólo porque se opera en resonancia; no siempre alcanza el límite"],
         ["Aislar la máquina",
          f"montarla sobre resortes de {ctrl['aislar']['k_aislador']/1e3:.0f} kN/m "
          f"(f = {ctrl['aislar']['f_aislador']:.2f} Hz, β = {ctrl['aislar']['beta']:.2f})",
          f"TR = {ctrl['aislar']['TR_objetivo']:.2f} → f<sub>T</sub> = "
          f"{ctrl['aislar']['fuerza_transmitida']/1e3:.2f} kN "
          f"({ctrl['aislar']['eficiencia']:.0f} % de eficiencia)",
          f"exige una deflexión estática de "
          f"{ctrl['aislar']['deflexion_estatica']*1e3:.0f} mm: aislar máquinas lentas "
          f"es geométricamente exigente"],
         ["Modificar la operación",
          "cambiar la velocidad de giro o balancear el rotor",
          "reduce p₀ ∝ ω² y aleja β de 1",
          "suele ser la medida más económica si el proceso lo permite"]],
        anchos=[3.0 * cm, 4.6 * cm, 4.2 * cm, 4.2 * cm],
        pie="Comparación de las estrategias de control de la respuesta (caso 1).")
    rep.figura(f1.get("control", ""),
               "Comparación temporal de las estrategias de control frente a la situación "
               "actual, con el límite de servicio señalado.")

    rep.h2("4.9 Interpretación y conclusiones del caso 1")
    rep.lista([
        "La estructura opera en <b>resonancia</b> (β = %.3f): una fuerza de sólo %.2f kN "
        "—equivalente al %.2f %% del peso soportado— produce una amplitud de %.2f mm y "
        "transmite %.1f kN a la cimentación. El problema no es de resistencia sino de "
        "<b>sintonía de frecuencias</b>."
        % (R1["beta"], c1.p0 / 1e3, 100 * c1.p0 / (s1.masa * G),
           R1["u_permanente"] * 1e3, R1["fuerza_transmitida"] / 1e3),
        "La variable que controla la respuesta es la <b>relación de frecuencias</b>. "
        "Sólo cuando β ≈ 1 el amortiguamiento pasa a ser determinante: en resonancia "
        "R<sub>d</sub> = 1/(2ζ) y la respuesta depende únicamente de él.",
        "Aumentar la rigidez y aumentar la masa producen efectos <b>opuestos</b> en este "
        "caso: rigidizar aleja el sistema de la resonancia hacia la zona cuasi-estática "
        "(β &lt; 1), mientras que añadir masa obliga a atravesar la resonancia antes de "
        "llegar a la zona de aislamiento (β &gt; √2).",
        "La solución recomendada es <b>rigidizar</b> el entrepiso hasta β ≈ 0.5, "
        "complementada con el balanceo del rotor. El aislamiento de la máquina es "
        "conceptualmente correcto pero, por su baja frecuencia de operación, exige una "
        "deflexión estática de %.0f mm, difícil de materializar."
        % (ctrl["aislar"]["deflexion_estatica"] * 1e3),
        "El análisis del arranque muestra que <b>atravesar rápidamente</b> la resonancia "
        "es admisible: el sistema no alcanza a desarrollar la amplitud del régimen "
        "permanente. El peligro está en operar de forma sostenida cerca de β = 1.",
    ])

    rep.salto()

    # ================================================================= CASO 2
    rep.h1("5. Caso de estudio 2 — Excitación arbitraria y carga impulsiva")
    md = s2.metadatos
    d2 = R2["datos"]
    rep.h2("5.1 Descripción del caso")
    rep.p("Tanque de agua elevado apoyado sobre una torre de concreto reforzado de sección "
          "anular de %.1f m de altura (diámetro exterior %.2f m, espesor %.2f m). El tanque "
          "almacena %.0f m³ de agua. Se analizan dos escenarios independientes: (A) un "
          "movimiento sísmico en la base, definido por un acelerograma completo y resuelto "
          "por integración directa de Newmark, y (B) una carga impulsiva horizontal "
          "aplicada al nivel del tanque (impacto idealizado como pulso triangular de "
          "%.0f kN y %.0f ms)."
          % (d2["altura"], d2["diametro_exterior"], d2["espesor_pared"],
             d2["volumen_agua"], d2["p0_impulso"] / 1e3, d2["td_impulso"] * 1e3))

    rep.h2("5.2 Idealización estructural e hipótesis adoptadas")
    rep.lista([
        "<b>H1.</b> La masa del tanque se concentra en el extremo superior; la torre se "
        "idealiza como un <b>voladizo</b> empotrado en la cimentación.",
        "<b>H2.</b> La masa distribuida del fuste se incorpora por el método de Rayleigh "
        "con la forma estática ψ(x) = [3(x/L)² − (x/L)³]/2, que aporta una masa "
        "participante de 33/140 = 0.2357 de la masa total del fuste.",
        "<b>H3.</b> Rigidez lateral del voladizo: k = 3·E·I<sub>ef</sub>/H³.",
        "<b>H4.</b> Se adopta inercia efectiva (fisurada) I<sub>ef</sub> = %.2f·I<sub>g</sub>; "
        "el efecto de esta decisión se cuantifica en el análisis paramétrico "
        "(sección 5.6)." % d2["factor_fisuracion"],
        "<b>H5.</b> Base empotrada: no se considera la interacción suelo-estructura, que "
        "flexibilizaría el sistema y alargaría el periodo.",
        "<b>H6.</b> Amortiguamiento viscoso ζ = %.0f %% (concreto reforzado fisurado)."
        % (s2.zeta * 100),
        "<b>H7.</b> El agua se considera solidaria con la cuba (masa impulsiva total). Un "
        "modelo más refinado separaría la masa convectiva (chapoteo), de periodo mucho más "
        "largo; la hipótesis adoptada es conservadora para el cortante basal.",
        "<b>H8.</b> Comportamiento elástico y lineal.",
    ])

    rep.h2("5.3 Propiedades dinámicas del sistema equivalente")
    rep.tabla(
        ["Propiedad", "Expresión", "Valor"],
        [["Módulo de elasticidad", "E = 4700·√f'c [MPa]", f"{md['E']/1e9:.3f} GPa"],
         ["Inercia bruta de la sección anular", "I<sub>g</sub> = π(D⁴ − d⁴)/64",
          f"{md['I_bruta']:.5f} m⁴"],
         ["Inercia efectiva", f"I<sub>ef</sub> = {d2['factor_fisuracion']:.2f}·I<sub>g</sub>",
          f"{md['I_efectiva']:.5f} m⁴"],
         ["Rigidez lateral", "k = 3·E·I<sub>ef</sub>/H³", f"{s2.rigidez:,.0f} N/m"],
         ["Masa del tanque lleno", "ρ·V + m<sub>cuba</sub>", f"{md['masa_tanque']:,.0f} kg"],
         ["Masa del fuste", "ρ·A·H", f"{md['masa_fuste_total']:,.0f} kg"],
         ["Masa participante del fuste", "(33/140)·m<sub>fuste</sub>",
          f"{md['masa_fuste_total']*33/140:,.0f} kg"],
         ["<b>Masa equivalente</b>", "<b>m* = m<sub>tanque</sub> + 0.2357·m<sub>fuste</sub></b>",
          f"<b>{s2.masa:,.0f} kg</b>"],
         ["Frecuencia natural", "ω<sub>n</sub> = √(k/m*)",
          f"{s2.omega_n:.4f} rad/s ({s2.f_n:.4f} Hz)"],
         ["<b>Periodo natural</b>", "<b>T<sub>n</sub> = 2π/ω<sub>n</sub></b>",
          f"<b>{s2.T_n:.4f} s</b>"],
         ["Amortiguamiento", "c = ζ·2·m*·ω<sub>n</sub>", f"{s2.amortiguamiento:,.0f} N·s/m"]],
        anchos=[5.4 * cm, 5.2 * cm, 5.4 * cm],
        pie="Propiedades dinámicas del sistema equivalente de un grado de libertad (caso 2).")
    vl = R2["vibracion_libre"]
    rep.p("La idealización se verificó con una <b>prueba numérica de vibración libre</b>: "
          "se impone un desplazamiento inicial de 20 mm y se identifican, a partir de la "
          "señal de respuesta, el periodo (%.4f s frente a T<sub>D</sub> = %.4f s teórico, "
          "error %.3f %%) y el amortiguamiento por decremento logarítmico (%.4f frente a "
          "%.4f, error %.3f %%)."
          % (vl["T_identificado"], s2.T_D, vl["error_T"] * 100,
             vl["zeta_identificado"], s2.zeta, vl["error_zeta"] * 100))
    rep.figura(f2.get("vibracion_libre", ""),
               "Prueba de vibración libre del sistema equivalente. El decaimiento "
               "exponencial de los picos permite recuperar el amortiguamiento introducido, "
               "lo que confirma la consistencia interna del modelo.")

    rep.h2("5.4 Parte A — Respuesta ante la excitación sísmica")
    rep.p("La excitación es un acelerograma de %.0f s con paso de %.3f s y aceleración pico "
          "del terreno de %.3f g (PGV = %.1f cm/s y PGD = %.1f cm, obtenidos integrando el "
          "registro). La carga efectiva sobre el sistema es "
          "p<sub>ef</sub>(t) = −m·ü<sub>g</sub>(t) y la respuesta calculada es el "
          "desplazamiento relativo a la base."
          % (R2["excitacion"].duracion, R2["excitacion"].dt, R2["excitacion"].pga / G,
             R2["excitacion"].pgv * 100, R2["excitacion"].pgd * 100))
    rep.nota("<b>Nota sobre el registro empleado.</b> El acelerograma es una señal "
             "<b>sintética reproducible</b> (ruido blanco filtrado con un filtro de "
             "Kanai-Tajimi y modulado con una envolvente de Jennings, semilla fija = "
             "%d), escalada a una PGA de %.2f g. La plataforma admite igualmente registros "
             "reales en formato CSV o PEER (.AT2); basta con sustituir el archivo de "
             "entrada, sin cambiar nada del análisis."
             % (d2["semilla"], d2["pga_objetivo"]))
    rep.figura(f2.get("acelerograma", ""),
               "Acelerograma empleado como excitación en la base.")
    sm = R2["sismo"]
    rep.tabla(
        ["Variable de respuesta", "Valor", "Interpretación"],
        [["Desplazamiento relativo máximo", f"{sm['u_max']*1e3:.2f} mm",
          f"ocurre en t = {sm['t_u_max']:.2f} s"],
         ["Deriva de la torre u/H", f"{sm['deriva']*100:.3f} %",
          "gobierna el daño de elementos frágiles y las tuberías"],
         ["Aceleración absoluta máxima",
          f"{sm['a_abs_max']:.3f} m/s² ({sm['a_abs_max']/G:.3f} g)",
          f"amplificación de {sm['amplificacion_aceleracion']:.2f}× respecto a la PGA"],
         ["Cortante basal máximo V = k·u", f"{sm['cortante_max']/1e3:.1f} kN",
          "fuerza de diseño del fuste y de la cimentación"],
         ["Momento en la base M = V·H", f"{sm['momento_max']/1e3:.0f} kN·m",
          "solicitación de flexión en el arranque del fuste"],
         ["Coeficiente sísmico V/W", f"{sm['coeficiente_sismico']:.3f}",
          "demanda elástica, sin reducción por capacidad de disipación"]],
        anchos=[5.4 * cm, 4.4 * cm, 6.2 * cm],
        pie="Resultados de la respuesta sísmica (caso 2A).")
    rep.figura(f2.get("respuesta_sismica", ""),
               "Respuesta sísmica completa: aceleración del terreno, desplazamiento "
               "relativo, aceleración absoluta de la masa y cortante basal. El sistema "
               "filtra la excitación y responde predominantemente en su propio periodo "
               f"T<sub>n</sub> = {s2.T_n:.2f} s.")
    rep.figura(f2.get("verificacion_sismo", ""),
               "Verificación del integrador ante excitación arbitraria: el método de "
               "Newmark reproduce la solución de interpolación exacta con un error del "
               f"{R2['verificacion_sismo'].comparaciones[0]['error_pico [-]']*100:.3f} % "
               "en el pico.")

    rep.h3("Espectros de respuesta del registro")
    Tp, PSap = R2["periodo_pico_espectro"]
    rep.p("El espectro de respuesta resume, para cada periodo natural, el valor pico de la "
          "respuesta de un sistema de un grado de libertad ante ese registro. Es la "
          "herramienta que conecta el análisis dinámico con el diseño: la fuerza estática "
          "equivalente es f<sub>s</sub> = m·PS<sub>a</sub>. Para el registro empleado, el "
          "máximo de la pseudo-aceleración (ζ = 5 %%) es %.3f g y ocurre en T = %.2f s; en "
          "el periodo de la estructura (%.3f s) el valor espectral es %.3f g."
          % (PSap / G, Tp, s2.T_n, R2["espectro_en_Tn"]["PSa [g]"]))
    rep.figura(f2.get("espectros", ""),
               "Espectros de desplazamiento, pseudo-velocidad y pseudo-aceleración del "
               "registro, para tres niveles de amortiguamiento. La línea vertical señala "
               "el periodo de la estructura analizada.")
    rep.nota("<b>Verificación cruzada.</b> El valor S<sub>d</sub>(T<sub>n</sub>) leído del "
             "espectro (%.2f mm) coincide con el desplazamiento máximo obtenido de la "
             "historia en el tiempo (%.2f mm) con un error del %.3f %%. Ambos cálculos son "
             "independientes: uno barre 90 periodos con el integrador de interpolación "
             "exacta y el otro integra una sola vez con Newmark."
             % (R2["espectro_en_Tn"]["Sd [m]"] * 1e3, sm["u_max"] * 1e3,
                R2["error_espectro_vs_historia"] * 100))

    rep.h2("5.5 Parte B — Respuesta ante la carga impulsiva")
    im = R2["impulso"]
    rep.p("El impacto se idealiza como un pulso triangular decreciente de %.0f kN de "
          "valor pico y %.0f ms de duración, aplicado al nivel del tanque. La relación "
          "entre la duración del pulso y el periodo natural es t<sub>d</sub>/T<sub>n</sub> "
          "= %.4f, muy inferior a 0.25: el problema se encuentra en pleno "
          "<b>régimen impulsivo</b>."
          % (d2["p0_impulso"] / 1e3, d2["td_impulso"] * 1e3, im["td_sobre_Tn"]))
    rep.tabla(
        ["Variable", "Valor", "Comentario"],
        [["Impulso total I = ∫p·dt", f"{im['impulso']:,.0f} N·s",
          "es la magnitud que gobierna la respuesta"],
         ["Desplazamiento estático p₀/k", f"{im['u_estatico']*1e3:.2f} mm",
          "lo que ocurriría si la fuerza se aplicara lentamente"],
         ["Desplazamiento máximo real", f"{im['u_max']*1e3:.3f} mm",
          "el máximo se produce ya en la fase de vibración libre"],
         ["Factor de amplificación R<sub>d</sub>", f"{im['Rd']:.3f}",
          "&lt; 1: la estructura no alcanza a responder al pulso"],
         ["Aproximación impulsiva I/(m·ω<sub>n</sub>)",
          f"{im['u_aproximacion_impulsiva']*1e3:.3f} mm",
          f"error de sólo {im['error_aproximacion']*100:.1f} % frente a la solución exacta"],
         ["Cortante basal máximo", f"{im['cortante_max']/1e3:.1f} kN",
          f"muy inferior al sísmico ({sm['cortante_max']/1e3:.0f} kN)"]],
        anchos=[5.4 * cm, 4.0 * cm, 6.6 * cm],
        pie="Resultados de la carga impulsiva (caso 2B).")
    rep.figura(f2.get("pulso", ""),
               "Respuesta ante la carga impulsiva, separando la fase forzada (t ≤ "
               "t<sub>d</sub>) de la fase de vibración libre. Con pulsos cortos el máximo "
               "ocurre después de que la carga ha desaparecido, y a partir de ese instante "
               "el sistema oscila libremente con su periodo natural.")
    rep.figura(f2.get("verificacion_pulso", ""),
               "Verificación de la respuesta impulsiva: solución analítica cerrada sin "
               "amortiguamiento, interpolación exacta y Newmark. La diferencia entre las "
               "curvas con y sin amortiguamiento aparece sólo en la fase libre, ya que en "
               "un pulso tan corto el amortiguamiento no alcanza a disipar energía.")
    rep.figura(f2.get("espectro_choque", ""),
               "Espectro de choque: factor de amplificación máximo en función de "
               "t<sub>d</sub>/T<sub>n</sub> para distintas formas de pulso. Se distinguen "
               "tres regímenes: impulsivo (t<sub>d</sub>/T<sub>n</sub> &lt; 0.25, "
               "R<sub>d</sub> &lt; 1), de amplificación dinámica "
               "(0.25 &lt; t<sub>d</sub>/T<sub>n</sub> &lt; 1.5, R<sub>d</sub> hasta 2) y "
               "cuasi-estático (t<sub>d</sub>/T<sub>n</sub> ≫ 1).")
    filas = [[n, f"{v['p0']/1e3:.1f} kN", f"{v['u_max']*1e3:.3f} mm"]
             for n, v in R2["formas_pulso"].items()]
    rep.tabla(["Forma del pulso (mismo impulso total)", "Fuerza pico p₀",
               "Desplazamiento máximo"], filas,
              anchos=[7.0 * cm, 4.0 * cm, 5.0 * cm],
              pie="Con pulsos cortos, la respuesta depende del impulso y es prácticamente "
                  "independiente de la forma del pulso, aunque la fuerza pico varíe al doble.")
    rep.figura(f2.get("barrido_td", ""),
               "Efecto de la duración del impulso manteniendo constante la fuerza pico. "
               "La respuesta crece de forma monótona con t<sub>d</sub>/T<sub>n</sub> hasta "
               "estabilizarse en el valor cuasi-estático.")

    rep.h2("5.6 Análisis paramétrico")
    rep.h3("Efecto del amortiguamiento")
    rep.tabla(["ζ [-]", "u<sub>máx</sub> [mm]", "ü<sub>abs,máx</sub> [g]", "V<sub>máx</sub> [kN]"],
              [[f"{f['zeta [-]']:.2f}", f"{f['u_max [mm]']:.2f}",
                f"{f['a_abs_max [g]']:.4f}", f"{f['V_max [kN]']:.1f}"]
               for f in R2["barridos"]["zeta"].filas],
              anchos=[3.0 * cm, 4.0 * cm, 4.5 * cm, 4.5 * cm],
              pie="Efecto del amortiguamiento sobre la respuesta sísmica (caso 2A).")
    rep.figura(f2.get("barrido_zeta", ""),
               "Efecto del amortiguamiento sobre el desplazamiento máximo. La reducción es "
               "importante al principio (del 1 % al 5 %) y presenta rendimientos "
               "decrecientes: duplicar ζ no reduce a la mitad la respuesta ante un sismo, "
               "a diferencia de lo que ocurre en la resonancia armónica del caso 1.")
    rep.h3("Efecto de la rigidez efectiva (grado de fisuración)")
    rep.tabla(["I<sub>ef</sub>/I<sub>g</sub>", "T<sub>n</sub> [s]",
               "u<sub>máx</sub> [mm]", "ü<sub>abs,máx</sub> [g]", "V<sub>máx</sub> [kN]"],
              [[f"{fi:.2f}", f"{f['Tn [s]']:.3f}", f"{f['u_max [mm]']:.2f}",
                f"{f['a_abs_max [g]']:.4f}", f"{f['V_max [kN]']:.1f}"]
               for fi, f in zip(R2["barridos"]["factores_fisuracion"],
                                R2["barridos"]["rigidez"].filas)],
              anchos=[3.2 * cm, 3.2 * cm, 3.2 * cm, 3.4 * cm, 3.0 * cm],
              pie="Sensibilidad de la respuesta al grado de fisuración adoptado para el fuste.")
    rep.figura(f2.get("barrido_rigidez", ""),
               "Efecto de la rigidez efectiva. La respuesta <b>no</b> varía de forma "
               "monótona: al cambiar la rigidez cambia el periodo y, con él, la posición "
               "de la estructura dentro del espectro del registro. Rigidizar reduce los "
               "desplazamientos pero puede <b>aumentar</b> las fuerzas.")
    rep.h3("Efecto del nivel de llenado del tanque")
    rep.tabla(["Llenado", "m* [kg]", "T<sub>n</sub> [s]", "u<sub>máx</sub> [mm]",
               "V<sub>máx</sub> [kN]"],
              [[f"{ll*100:.0f} %", f"{f['m [kg]']:,.0f}", f"{f['Tn [s]']:.3f}",
                f"{f['u_max [mm]']:.2f}", f"{f['V_max [kN]']:.1f}"]
               for ll, f in zip(R2["barridos"]["llenados"],
                                R2["barridos"]["masa"].filas)],
              anchos=[2.8 * cm, 3.4 * cm, 3.0 * cm, 3.4 * cm, 3.4 * cm],
              pie="Efecto del nivel de llenado: la masa modifica simultáneamente la "
                  "demanda inercial y el periodo de la estructura.")
    rep.figura(f2.get("barrido_masa", ""),
               "Cortante basal en función del periodo resultante del nivel de llenado. El "
               "tanque lleno es la condición crítica, pero el crecimiento no es "
               "proporcional a la masa porque el alargamiento del periodo modifica la "
               "demanda espectral.")

    rep.h2("5.7 Control de la respuesta: aislamiento sísmico")
    ais = R2["aislamiento"]
    rep.p("Se evaluó el efecto de un sistema de aislamiento en la base que alargue el "
          "periodo hasta %.1f s con un amortiguamiento del 15 %%."
          % ais["sistema"].T_n)
    rep.tabla(["Variable", "Base empotrada", "Con aislamiento", "Cambio"],
              [["Periodo natural", f"{s2.T_n:.2f} s", f"{ais['sistema'].T_n:.2f} s",
                f"×{ais['sistema'].T_n/s2.T_n:.1f}"],
               ["Cortante basal", f"{sm['cortante_max']/1e3:.1f} kN",
                f"{ais['respuesta'].cortante_max/1e3:.1f} kN",
                f"−{ais['reduccion_cortante']*100:.0f} %"],
               ["Aceleración absoluta", f"{sm['a_abs_max']/G:.3f} g",
                f"{ais['respuesta'].a_abs_max/G:.3f} g",
                f"−{ais['reduccion_aceleracion']*100:.0f} %"],
               ["Desplazamiento", f"{sm['u_max']*1e3:.1f} mm",
                f"{ais['respuesta'].u_max*1e3:.1f} mm",
                f"×{ais['aumento_desplazamiento']:.1f}"]],
              anchos=[4.4 * cm, 3.8 * cm, 3.8 * cm, 3.0 * cm],
              pie="Efecto del aislamiento sísmico: intercambia fuerza por desplazamiento.")
    rep.figura(f2.get("aislamiento", ""),
               "Comparación del desplazamiento relativo con y sin aislamiento. El "
               "aislamiento reduce drásticamente las fuerzas al desplazar la estructura "
               "hacia la zona de periodos largos del espectro, a costa de mayores "
               "desplazamientos que deben acomodarse en la junta.")

    rep.h2("5.8 Interpretación y conclusiones del caso 2")
    rep.lista([
        "La estructura, con T<sub>n</sub> = %.2f s, queda situada en la zona de mayor "
        "demanda del registro: la aceleración absoluta máxima (%.2f g) resulta %.1f veces "
        "la aceleración pico del terreno (%.2f g). La estructura <b>amplifica</b> el "
        "movimiento del suelo."
        % (s2.T_n, sm["a_abs_max"] / G, sm["amplificacion_aceleracion"],
           R2["excitacion"].pga / G),
        "Ante excitación sísmica, la variable que controla la respuesta es la relación "
        "entre el periodo de la estructura y el <b>contenido frecuencial del registro</b>. "
        "Por eso el efecto de la masa y de la rigidez no es monótono: modifican el periodo "
        "y desplazan la estructura dentro del espectro.",
        "El amortiguamiento reduce la respuesta, pero con <b>rendimientos "
        "decrecientes en términos absolutos</b>: pasar de ζ = 1 %% a 5 %% ahorra "
        "%.0f mm de desplazamiento (de %.1f a %.1f mm), mientras que duplicar el "
        "amortiguamiento del 10 %% al 20 %% —una intervención mucho más costosa— sólo "
        "ahorra %.0f mm adicionales (de %.1f a %.1f mm)."
        % (R2["barridos"]["zeta"].columna("u_max [mm]")[0]
           - R2["barridos"]["zeta"].columna("u_max [mm]")[2],
           R2["barridos"]["zeta"].columna("u_max [mm]")[0],
           R2["barridos"]["zeta"].columna("u_max [mm]")[2],
           R2["barridos"]["zeta"].columna("u_max [mm]")[3]
           - R2["barridos"]["zeta"].columna("u_max [mm]")[5],
           R2["barridos"]["zeta"].columna("u_max [mm]")[3],
           R2["barridos"]["zeta"].columna("u_max [mm]")[5]),
        "Ante la carga impulsiva, la variable de control es completamente distinta: lo que "
        "gobierna es el <b>impulso total</b> I = ∫p·dt y no la fuerza pico. Con "
        "t<sub>d</sub>/T<sub>n</sub> = %.3f, tres pulsos de formas y picos muy diferentes "
        "producen prácticamente el mismo desplazamiento máximo."
        % im["td_sobre_Tn"],
        "Rigidizar la estructura tiene efectos <b>contrarios</b> según la excitación: "
        "reduce los desplazamientos sísmicos pero puede aumentar las fuerzas, y en el "
        "problema impulsivo aumenta la respuesta porque acerca t<sub>d</sub>/T<sub>n</sub> "
        "a la zona de amplificación. No existe una medida universalmente favorable: "
        "depende de la relación entre el tiempo característico de la excitación y el "
        "periodo natural.",
        "La condición crítica de diseño es el <b>tanque lleno bajo sismo</b>, con un "
        "cortante basal de %.0f kN (V/W = %.2f, demanda elástica). El impacto analizado "
        "produce solicitaciones un orden de magnitud menores."
        % (sm["cortante_max"] / 1e3, sm["coeficiente_sismico"]),
    ])

    rep.salto()

    # ------------------------------------------------------- 6. conclusiones
    rep.h1("6. Conclusiones generales")
    rep.lista([
        "<b>La respuesta dinámica no depende de la magnitud de la carga, sino de su "
        "relación con las propiedades del sistema.</b> En el caso 1, una fuerza equivalente "
        "al %.2f %% del peso produjo una respuesta %.0f veces mayor que la estática; en el "
        "caso 2, un impacto de %.0f kN produjo una respuesta %.2f veces <b>menor</b> que la "
        "estática. La diferencia está en la relación β = ω/ω<sub>n</sub> y en la relación "
        "t<sub>d</sub>/T<sub>n</sub>."
        % (100 * c1.p0 / (s1.masa * G), R1["Rd"], d2["p0_impulso"] / 1e3, 1 / im["Rd"]),
        "<b>Cada tipo de excitación tiene su parámetro de control.</b> Carga armónica: la "
        "relación de frecuencias β (y el amortiguamiento sólo cuando β ≈ 1). Carga "
        "impulsiva: la relación t<sub>d</sub>/T<sub>n</sub> y el impulso total. Excitación "
        "arbitraria: la posición del periodo natural dentro del contenido frecuencial de "
        "la señal.",
        "<b>El amortiguamiento es decisivo sólo cuando la excitación es sostenida y está "
        "sintonizada</b> con la estructura. En resonancia armónica R<sub>d</sub> = 1/(2ζ); "
        "ante un pulso corto, en cambio, el amortiguamiento casi no interviene, porque no "
        "hay tiempo para disipar energía.",
        "<b>Masa y rigidez no actúan de forma independiente:</b> lo hacen a través de "
        "ω<sub>n</sub> = √(k/m). Cualquier modificación estructural debe evaluarse por el "
        "desplazamiento que produce en el punto de operación, no por su magnitud absoluta.",
        "<b>Aislar es desintonizar, no rigidizar.</b> El aislamiento exige β &gt; √2, es "
        "decir, hacer el sistema <b>más flexible</b> que la excitación. En la zona de "
        "aislamiento, además, un mayor amortiguamiento aumenta la fuerza transmitida.",
        "<b>Todo resultado numérico debe verificarse.</b> En este trabajo cada respuesta se "
        "contrastó con al menos una solución independiente (analítica, interpolación "
        "exacta, espectro de respuesta o límite teórico), se comprobó el residual de la "
        "ecuación de movimiento (&lt; 10⁻¹⁰) y el cierre del balance de energía (&lt; 0.01 %), "
        "y se verificó la convergencia respecto al paso de tiempo.",
        "<b>La plataforma desarrollada es general.</b> Los dos casos resueltos son sólo "
        "archivos de datos que la utilizan; cualquier otro sistema de un grado de libertad "
        "—o idealizable como tal— puede analizarse cambiando únicamente los parámetros de "
        "entrada o el archivo de la señal de excitación.",
    ])

    rep.h2("6.1 Limitaciones del análisis")
    rep.lista([
        "Los modelos son <b>elásticos y lineales</b>: no representan la incursión "
        "inelástica, que en un sismo severo reduciría las fuerzas y aumentaría los "
        "desplazamientos residuales.",
        "El amortiguamiento se supone <b>viscoso y constante</b>; en la realidad depende "
        "del nivel de deformación.",
        "Se analiza <b>un solo grado de libertad</b>: se desprecian los modos superiores y, "
        "en el tanque, el modo convectivo del agua.",
        "El registro sísmico empleado es <b>sintético</b>; para un diseño real deben usarse "
        "registros compatibles con la amenaza sísmica del sitio y con la normativa vigente "
        "(NSR-10 en Colombia).",
        "No se considera la <b>interacción suelo-estructura</b> ni la flexibilidad de la "
        "cimentación.",
    ])

    rep.h2("6.2 Contenido de la entrega")
    rep.tabla(["Archivo o carpeta", "Contenido"],
              [["<b>dinamica/</b>", "Paquete con el motor de cálculo (10 módulos)."],
               ["<b>casos/</b>", "Los dos casos de estudio y los datos de las señales."],
               ["<b>tests/</b>", "85 pruebas automáticas de verificación."],
               ["<b>menu.py</b>", "Menú interactivo por consola (ingreso manual de datos)."],
               ["<b>main.py</b>", "Interfaz de línea de comandos."],
               ["<b>app_streamlit.py</b>", "Interfaz gráfica interactiva."],
               ["<b>reporte/</b>", "Generador de este documento."],
               ["<b>salidas/</b>", "Figuras, historias de respuesta en CSV y este PDF."],
               ["<b>README.md</b>", "Guía completa de instalación, uso y explicación."]],
              anchos=[4.0 * cm, 12.0 * cm],
              pie="Estructura de la entrega.")
    return rep


# ===========================================================================
def generar(salida: Path = SALIDA, R1: dict | None = None,
            R2: dict | None = None) -> Path:
    """Ejecuta los casos (si no se suministran resultados) y escribe el PDF."""
    if R1 is None or R2 is None:
        from casos import caso1_maquinaria, caso2_tanque
        print("Resolviendo el caso 1 (carga armónica)...")
        R1 = caso1_maquinaria.ejecutar()
        print("Resolviendo el caso 2 (sismo e impulso)...")
        R2 = caso2_tanque.ejecutar()

    print("Componiendo el reporte PDF...")
    rep = construir(R1, R2)
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(str(salida), pagesize=A4,
                          leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                          topMargin=2.0 * cm, bottomMargin=2.0 * cm,
                          title="Reporte técnico — Laboratorio Computacional de "
                                "Respuesta Dinámica",
                          author="Proyecto de aula — Dinámica de Estructuras, "
                                 "Universidad de Medellín")
    marco = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="cuerpo")
    doc.addPageTemplates([
        PageTemplate(id="portada", frames=[marco], onPage=_portada),
        PageTemplate(id="normal", frames=[marco], onPage=_decorar),
    ])
    doc.build(rep.flujo)
    return salida


if __name__ == "__main__":
    print(f"\nReporte generado: {generar().resolve()}")
