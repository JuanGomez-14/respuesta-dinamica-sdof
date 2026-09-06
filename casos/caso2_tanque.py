"""
================================================================================
 CASO DE ESTUDIO 2 — EXCITACIÓN ARBITRARIA (SISMO) Y CARGA IMPULSIVA
 Tanque de agua elevado sobre torre de concreto reforzado
================================================================================

DESCRIPCIÓN
-----------
Tanque de almacenamiento de agua apoyado sobre una torre de concreto reforzado
de sección anular (fuste hueco) de 12 m de altura. El tanque, cuando está
lleno, contiene 60 m³ de agua. La estructura se analiza ante dos excitaciones
independientes:

    (A) un movimiento sísmico en la base definido por un acelerograma
        (excitación dinámica arbitraria -> integración numérica de Newmark);
    (B) una carga impulsiva horizontal aplicada al nivel del tanque
        (impacto/explosión idealizada como pulso triangular decreciente).

IDEALIZACIÓN (múltiples grados de libertad -> un grado de libertad)
-------------------------------------------------------------------
H1. La masa del tanque está concentrada en el extremo superior del fuste; la
    torre se idealiza como un voladizo (empotrado en la cimentación).
H2. La masa distribuida del fuste se incorpora mediante el método de Rayleigh
    con la forma estática del voladizo ψ(x) = [3(x/L)² - (x/L)³]/2, lo que
    aporta una masa participante de 33/140 = 0.2357 de la masa total del fuste.
H3. Rigidez lateral del voladizo: k = 3·E·I_ef/H³.
H4. Se emplea inercia efectiva (fisurada) I_ef = 0.70·I_g para el fuste de
    concreto, según la práctica usual de análisis sísmico de elementos
    sometidos a flexo-compresión (se estudia paramétricamente entre 0.35 y 1.0).
H5. La cimentación es rígida (base empotrada); no se considera interacción
    suelo-estructura (se discute su efecto en el análisis paramétrico).
H6. Amortiguamiento viscoso ζ = 5 % (concreto reforzado fisurado).
H7. El agua se considera solidaria con el tanque (masa impulsiva total). Un
    análisis más refinado separaría la masa convectiva (chapoteo/sloshing),
    que tiene un periodo mucho más largo; esta simplificación es conservadora
    para el cortante basal.
H8. Comportamiento elástico lineal.

Ejecución:  python -m casos.caso2_tanque
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from dinamica import (G, PulsoRectangular, PulsoSemiseno, PulsoTriangular,
                      SistemaSDOF, barrido_carga, barrido_sismico,
                      espectro_choque, espectro_respuesta, graficos,
                      generar_registro_sintetico, interpolacion_exacta,
                      periodos_logaritmicos, resolver, resolver_base,
                      respuesta_pulso, sdof_equivalente_voladizo,
                      vector_tiempo, vibracion_libre,
                      zeta_por_decremento_logaritmico)
from dinamica.graficos import (graficar_acelerograma, graficar_barrido,
                               graficar_comparacion, graficar_espectro,
                               graficar_espectro_choque, graficar_historia,
                               graficar_pulso_fases, graficar_respuesta_sismica)
from dinamica.verificacion import verificar_todo

# ===========================================================================
#  DATOS DE ENTRADA
# ===========================================================================
DATOS = dict(
    # --- torre (fuste de concreto de sección anular) ---------------------
    altura=12.0,                 # m    altura libre del fuste
    diametro_exterior=1.50,      # m
    espesor_pared=0.20,          # m
    fc=28.0e6,                   # Pa   resistencia del concreto f'c
    densidad_concreto=2400.0,    # kg/m3
    factor_fisuracion=0.70,      # -    I_efectiva / I_bruta
    zeta=0.05,                   # -
    # --- tanque -----------------------------------------------------------
    volumen_agua=60.0,           # m3
    densidad_agua=1000.0,        # kg/m3
    masa_estructura_tanque=15_000.0,   # kg  cuba, cubierta y accesorios
    # --- excitación sísmica ----------------------------------------------
    pga_objetivo=0.20,           # g    aceleración pico del terreno
    duracion_registro=30.0,      # s
    dt_registro=0.005,           # s
    semilla=2026,                # -    reproducibilidad del registro sintético
    # --- carga impulsiva --------------------------------------------------
    p0_impulso=150e3,            # N    fuerza pico del impacto
    td_impulso=0.05,             # s    duración del impulso
)

CARPETA = Path("salidas/figuras/caso2")


# ===========================================================================
def construir_sistema(datos: dict = DATOS) -> SistemaSDOF:
    """Idealiza la torre + tanque como un sistema equivalente de 1 GDL."""
    D, e = datos["diametro_exterior"], datos["espesor_pared"]
    d = D - 2.0 * e
    I_bruta = math.pi * (D ** 4 - d ** 4) / 64.0
    area = math.pi * (D ** 2 - d ** 2) / 4.0
    masa_lineal = area * datos["densidad_concreto"]
    E = 4700.0 * math.sqrt(datos["fc"] / 1e6) * 1e6      # ACI/NSR-10: E = 4700·√f'c [MPa]
    I_ef = datos["factor_fisuracion"] * I_bruta
    m_tanque = datos["volumen_agua"] * datos["densidad_agua"] + datos["masa_estructura_tanque"]

    s = sdof_equivalente_voladizo(E=E, I=I_ef, L=datos["altura"],
                                  masa_lineal=masa_lineal,
                                  masa_concentrada=m_tanque, zeta=datos["zeta"],
                                  nombre="Tanque elevado (SDOF equivalente)")
    s.metadatos.update(E=E, I_bruta=I_bruta, I_efectiva=I_ef, area_fuste=area,
                       masa_lineal_fuste=masa_lineal, masa_tanque=m_tanque,
                       masa_fuste_total=masa_lineal * datos["altura"],
                       altura=datos["altura"])
    return s


def construir_excitacion(datos: dict = DATOS):
    """Acelerograma de diseño (registro sintético reproducible)."""
    return generar_registro_sintetico(
        duracion=datos["duracion_registro"], dt=datos["dt_registro"],
        pga_objetivo=datos["pga_objetivo"] * G, semilla=datos["semilla"],
        nombre=f"Registro sintético PGA={datos['pga_objetivo']:.2f} g")


# ===========================================================================
def ejecutar(datos: dict = DATOS, generar_figuras: bool = True) -> dict:
    R: dict = {"datos": dict(datos)}
    sistema = construir_sistema(datos)
    R["sistema"] = sistema
    H = datos["altura"]

    # -------------------------------------------------------------------
    # 0. Verificación de la idealización: prueba de vibración libre
    #    (se "tira" del tanque 20 mm y se suelta)
    # -------------------------------------------------------------------
    t_libre = vector_tiempo(6.0, sistema.T_n / 200)
    r_libre = vibracion_libre(sistema, t_libre, u0=0.020)
    # identificación del periodo y del amortiguamiento a partir de la señal
    picos = _picos_positivos(r_libre.t, r_libre.u)
    T_identificado = float(np.mean(np.diff(picos[:, 0]))) if len(picos) > 2 else float("nan")
    zeta_identificado = zeta_por_decremento_logaritmico(picos[0, 1], picos[3, 1], 3) \
        if len(picos) > 3 else float("nan")
    R["vibracion_libre"] = dict(respuesta=r_libre, T_identificado=T_identificado,
                                zeta_identificado=zeta_identificado,
                                error_T=abs(T_identificado - sistema.T_D) / sistema.T_D,
                                error_zeta=abs(zeta_identificado - sistema.zeta) / sistema.zeta)

    # ===================================================================
    #  PARTE A — EXCITACIÓN SÍSMICA (arbitraria, método de Newmark)
    # ===================================================================
    exc = construir_excitacion(datos)
    R["excitacion"] = exc

    r_sismo = resolver_base(sistema, exc, metodo="newmark")
    r_sismo_exacta = resolver_base(sistema, exc, metodo="exacta")
    R["respuesta_sismo"] = r_sismo
    R["respuesta_sismo_exacta"] = r_sismo_exacta

    R["sismo"] = dict(
        u_max=r_sismo.u_max, t_u_max=r_sismo.t_u_max,
        v_max=r_sismo.v_max,
        a_abs_max=r_sismo.a_abs_max,
        cortante_max=r_sismo.cortante_max,
        momento_max=r_sismo.cortante_max * H,
        deriva=r_sismo.u_max / H,
        coeficiente_sismico=r_sismo.cortante_max / (sistema.masa * G),
        amplificacion_aceleracion=r_sismo.a_abs_max / exc.pga,
    )

    # verificación numérica completa
    R["verificacion_sismo"] = verificar_todo(
        r_sismo, {"interpolación exacta": r_sismo_exacta})

    # -------------------------------------------------------------------
    # A.2 Espectros de respuesta del registro
    # -------------------------------------------------------------------
    periodos = periodos_logaritmicos(0.05, 4.0, 90)
    # se añade el periodo exacto de la estructura para poder comparar el valor
    # espectral con el pico de la historia en el tiempo sin error de interpolación
    periodos = np.unique(np.append(periodos, sistema.T_n))
    espectros = [espectro_respuesta(exc, zeta=z, periodos=periodos)
                 for z in (0.02, 0.05, 0.10)]
    R["espectros"] = espectros
    esp5 = espectros[1]
    valores_Tn = esp5.en_periodo(sistema.T_n)
    R["espectro_en_Tn"] = valores_Tn
    # verificación cruzada: Sd(Tn) del espectro == |u|max de la historia
    R["error_espectro_vs_historia"] = abs(valores_Tn["Sd [m]"] - r_sismo.u_max) / r_sismo.u_max
    R["periodo_pico_espectro"] = esp5.PSa_maxima

    # -------------------------------------------------------------------
    # A.3 Análisis paramétrico sísmico
    # -------------------------------------------------------------------
    zetas = np.array([0.01, 0.02, 0.05, 0.10, 0.15, 0.20])
    barr_zeta = barrido_sismico(sistema, exc, "zeta", zetas)
    factores_fis = np.array([0.35, 0.50, 0.70, 0.85, 1.0])
    k_bruta = sistema.rigidez / datos["factor_fisuracion"]
    barr_k = barrido_sismico(sistema, exc, "rigidez", factores_fis * k_bruta)
    # llenado del tanque: vacío (sólo estructura) -> lleno
    llenados = np.array([0.0, 0.25, 0.50, 0.75, 1.0])
    masas = np.array([sistema.metadatos["masa_fuste_total"] * 33 / 140
                      + datos["masa_estructura_tanque"]
                      + f * datos["volumen_agua"] * datos["densidad_agua"]
                      for f in llenados])
    barr_masa = barrido_sismico(sistema, exc, "masa", masas)
    R["barridos"] = dict(zeta=barr_zeta, rigidez=barr_k, masa=barr_masa,
                         factores_fisuracion=factores_fis, llenados=llenados)

    # -------------------------------------------------------------------
    # A.4 Estrategia de control: aislamiento sísmico de la base
    # -------------------------------------------------------------------
    T_aislado = 2.5
    s_aislado = SistemaSDOF.desde_periodo(masa=sistema.masa, T_n=T_aislado,
                                          zeta=0.15, nombre="Con aislamiento sísmico")
    r_aislado = resolver_base(s_aislado, exc, metodo="newmark")
    R["aislamiento"] = dict(
        sistema=s_aislado, respuesta=r_aislado,
        reduccion_cortante=1 - r_aislado.cortante_max / r_sismo.cortante_max,
        reduccion_aceleracion=1 - r_aislado.a_abs_max / r_sismo.a_abs_max,
        aumento_desplazamiento=r_aislado.u_max / r_sismo.u_max,
    )

    # ===================================================================
    #  PARTE B — CARGA IMPULSIVA
    # ===================================================================
    pulso = PulsoTriangular(p0=datos["p0_impulso"], duracion=datos["td_impulso"],
                            tipo="decreciente",
                            nombre="Impacto en el tanque (pulso triangular)")
    R["pulso"] = pulso
    dt_p = min(pulso.duracion / 200.0, sistema.T_n / 200.0)
    t_p = vector_tiempo(6.0 * sistema.T_n, dt_p)
    r_pulso = resolver(sistema, pulso, t_final=6.0 * sistema.T_n, dt=dt_p,
                       metodo="newmark")
    r_pulso_exacta = interpolacion_exacta(sistema, t_p, pulso.muestrear(t_p))
    # solución analítica cerrada (sistema no amortiguado)
    s0 = sistema.con(zeta=0.0)
    r_pulso_analitica = respuesta_pulso(s0, pulso, t_p)

    # verificación adicional: el MISMO pulso resuelto sin amortiguamiento con el
    # integrador numérico debe reproducir la solución cerrada analítica
    r_pulso_num_sin_amort = interpolacion_exacta(s0, t_p, pulso.muestrear(t_p))

    impulso = pulso.impulso
    u_aprox_impulsiva = impulso / (sistema.masa * sistema.omega_n)
    R["impulso"] = dict(
        respuesta=r_pulso, respuesta_exacta=r_pulso_exacta,
        respuesta_analitica=r_pulso_analitica,
        u_max=r_pulso.u_max, u_estatico=pulso.p0 / sistema.rigidez,
        Rd=r_pulso.u_max * sistema.rigidez / pulso.p0,
        td_sobre_Tn=pulso.duracion / sistema.T_n,
        impulso=impulso,
        u_aproximacion_impulsiva=u_aprox_impulsiva,
        error_aproximacion=abs(r_pulso_analitica.u_max - u_aprox_impulsiva)
        / r_pulso_analitica.u_max,
        cortante_max=r_pulso.cortante_max,
        error_newmark=abs(r_pulso.u_max - r_pulso_exacta.u_max) / r_pulso_exacta.u_max,
        u_max_sin_amortiguamiento=r_pulso_num_sin_amort.u_max,
        error_sin_amortiguamiento=abs(r_pulso_num_sin_amort.u_max
                                      - r_pulso_analitica.u_max) / r_pulso_analitica.u_max,
    )
    R["verificacion_impulso"] = verificar_todo(
        r_pulso, {"interpolación exacta": r_pulso_exacta})

    # B.2 espectros de choque
    choques = {
        "Rectangular": espectro_choque("rectangular", zeta=0.0),
        "Triangular decreciente": espectro_choque("triangular", zeta=0.0),
        "Medio seno": espectro_choque("semiseno", zeta=0.0),
        "Triangular con ζ = 5 %": espectro_choque("triangular", zeta=sistema.zeta),
    }
    R["espectros_choque"] = choques

    # B.3 efecto de la duración del impulso (manteniendo p0)
    razones_td = np.logspace(-1.2, 0.8, 40)
    barr_td = barrido_carga(
        sistema,
        lambda r: PulsoTriangular(p0=pulso.p0, duracion=r * sistema.T_n),
        razones_td, "td/Tn",
        t_final=8.0 * sistema.T_n, dt=sistema.T_n / 400, guardar_respuestas=False)
    R["barridos"]["duracion_pulso"] = barr_td

    # B.4 efecto de la forma del pulso con el mismo impulso total
    formas = {}
    for nombre, fabrica in [
            ("Rectangular", lambda I, td: PulsoRectangular(I / td, td)),
            ("Triangular", lambda I, td: PulsoTriangular(2 * I / td, td)),
            ("Medio seno", lambda I, td: PulsoSemiseno(math.pi * I / (2 * td), td))]:
        c = fabrica(impulso, pulso.duracion)
        rr = resolver(sistema, c, t_final=6.0 * sistema.T_n, dt=dt_p, metodo="newmark")
        formas[nombre] = dict(carga=c, respuesta=rr, u_max=rr.u_max, p0=c.p0)
    R["formas_pulso"] = formas

    # -------------------------------------------------------------------
    if generar_figuras:
        R["figuras"] = _figuras(R)
    return R


# ===========================================================================
def _picos_positivos(t: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Devuelve los máximos locales positivos [(t, u), ...] de una señal."""
    idx = np.where((u[1:-1] > u[:-2]) & (u[1:-1] > u[2:]) & (u[1:-1] > 0))[0] + 1
    return np.column_stack([t[idx], u[idx]])


# ===========================================================================
def _figuras(R: dict) -> dict:
    graficos.usar_carpeta(CARPETA)
    figs = {}
    sistema = R["sistema"]

    figs["acelerograma"] = graficar_acelerograma(
        R["excitacion"], titulo="Caso 2 — Acelerograma de diseño empleado",
        nombre_archivo="c2_acelerograma")

    figs["respuesta_sismica"] = graficar_respuesta_sismica(
        R["respuesta_sismo"], titulo="Caso 2A — Respuesta del tanque ante el sismo",
        nombre_archivo="c2_respuesta_sismica")

    figs["verificacion_sismo"] = graficar_comparacion(
        [R["respuesta_sismo_exacta"], R["respuesta_sismo"]],
        ["Interpolación exacta (referencia)", "Newmark (aceleración promedio)"],
        titulo="Caso 2A — Verificación del integrador ante excitación arbitraria",
        nombre_archivo="c2_verificacion_sismo")

    figs["espectros"] = graficar_espectro(
        R["espectros"], titulo="Caso 2A — Espectros de respuesta del registro empleado",
        marcar_T=sistema.T_n, nombre_archivo="c2_espectros")

    figs["barrido_zeta"] = graficar_barrido(
        R["barridos"]["zeta"], "u_max [mm]",
        etiqueta_x="Fracción de amortiguamiento crítico ζ [-]",
        titulo="Caso 2A — Efecto del amortiguamiento sobre el desplazamiento máximo",
        nombre_archivo="c2_barrido_zeta")

    figs["barrido_rigidez"] = graficar_barrido(
        R["barridos"]["rigidez"], "u_max [mm]", columna_x="Tn [s]",
        etiqueta_x="Periodo natural T$_n$ [s] (según el grado de fisuración)",
        titulo="Caso 2A — Efecto de la rigidez efectiva (fisuración) del fuste",
        nombre_archivo="c2_barrido_rigidez")

    figs["barrido_masa"] = graficar_barrido(
        R["barridos"]["masa"], "V_max [kN]", columna_x="Tn [s]",
        etiqueta_x="Periodo natural T$_n$ [s] (según el nivel de llenado)",
        titulo="Caso 2A — Efecto del nivel de llenado del tanque sobre el cortante basal",
        nombre_archivo="c2_barrido_masa")

    figs["aislamiento"] = graficar_comparacion(
        [R["respuesta_sismo"], R["aislamiento"]["respuesta"]],
        [f"Base empotrada (Tn = {sistema.T_n:.2f} s)",
         f"Con aislamiento (Tn = {R['aislamiento']['sistema'].T_n:.2f} s, ζ = 15 %)"],
        titulo="Caso 2A — Efecto del aislamiento sísmico sobre el desplazamiento relativo",
        nombre_archivo="c2_aislamiento")

    figs["pulso"] = graficar_pulso_fases(
        R["impulso"]["respuesta"], R["pulso"].duracion,
        titulo=("Caso 2B — Respuesta ante la carga impulsiva "
                f"(t$_d$/T$_n$ = {R['impulso']['td_sobre_Tn']:.3f})"),
        nombre_archivo="c2_pulso")

    figs["verificacion_pulso"] = graficar_comparacion(
        [R["impulso"]["respuesta_analitica"], R["impulso"]["respuesta_exacta"],
         R["impulso"]["respuesta"]],
        ["Analítica cerrada (ζ = 0)", "Interpolación exacta (ζ = 5 %)",
         "Newmark (ζ = 5 %)"],
        titulo="Caso 2B — Verificación de la respuesta impulsiva",
        nombre_archivo="c2_verificacion_pulso")

    figs["espectro_choque"] = graficar_espectro_choque(
        R["espectros_choque"],
        titulo="Caso 2B — Espectro de choque: amplificación según la duración del pulso",
        marcar=dict(x=R["impulso"]["td_sobre_Tn"], y=R["impulso"]["Rd"],
                    texto=f"Caso analizado\nt$_d$/T$_n$={R['impulso']['td_sobre_Tn']:.3f}\n"
                          f"$R_d$={R['impulso']['Rd']:.3f}"),
        nombre_archivo="c2_espectro_choque")

    figs["barrido_td"] = graficar_barrido(
        R["barridos"]["duracion_pulso"], "u_max [mm]",
        etiqueta_x="Relación de duración t$_d$/T$_n$ [-]",
        titulo="Caso 2B — Efecto de la duración del impulso (p$_0$ constante)",
        escala_log=True, nombre_archivo="c2_barrido_td")

    figs["vibracion_libre"] = graficar_historia(
        R["vibracion_libre"]["respuesta"],
        titulo=("Caso 2 — Prueba de vibración libre (u$_0$ = 20 mm): "
                "identificación de T$_n$ y ζ"),
        mostrar=("u", "v"), nombre_archivo="c2_vibracion_libre")

    return figs


# ===========================================================================
def imprimir_informe(R: dict) -> str:
    s = R["sistema"]
    d = R["datos"]
    md = s.metadatos
    L = []
    A = L.append
    A("=" * 78)
    A("CASO 2 — TANQUE ELEVADO: EXCITACIÓN SÍSMICA ARBITRARIA Y CARGA IMPULSIVA")
    A("=" * 78)
    A("")
    A("1) IDEALIZACIÓN Y PROPIEDADES DEL SISTEMA EQUIVALENTE DE 1 GDL")
    A(f"   Módulo de elasticidad  E = 4700·√f'c   = {md['E']/1e9:.3f} GPa")
    A(f"   Inercia bruta          I_g            = {md['I_bruta']:.5f} m⁴")
    A(f"   Inercia efectiva       I_ef = {d['factor_fisuracion']:.2f}·I_g = {md['I_efectiva']:.5f} m⁴")
    A(f"   Rigidez del voladizo   k = 3·E·I_ef/H³ = {s.rigidez:,.0f} N/m")
    A(f"   Masa del tanque (lleno)                = {md['masa_tanque']:,.0f} kg")
    A(f"   Masa total del fuste                   = {md['masa_fuste_total']:,.0f} kg "
      f"(participa 33/140 = {md['masa_fuste_total']*33/140:,.0f} kg)")
    A(f"   Masa equivalente       m*              = {s.masa:,.0f} kg")
    A(f"   Amortiguamiento        c               = {s.amortiguamiento:,.0f} N·s/m "
      f"(ζ = {s.zeta:.3f})")
    A(f"   Periodo natural        Tn              = {s.T_n:.4f} s "
      f"(fn = {s.f_n:.4f} Hz ; ωn = {s.omega_n:.4f} rad/s)")
    vl = R["vibracion_libre"]
    A(f"   Verificación por vibración libre: T identificado = {vl['T_identificado']:.4f} s "
      f"(error {vl['error_T']*100:.3f} %), ζ identificado = {vl['zeta_identificado']:.4f} "
      f"(error {vl['error_zeta']*100:.3f} %)")
    A("")
    A("2) PARTE A — RESPUESTA SÍSMICA (excitación arbitraria, método de Newmark)")
    A(f"   {R['excitacion'].descripcion()}")
    A(f"   (PGV = {R['excitacion'].pgv*100:.1f} cm/s ; PGD = {R['excitacion'].pgd*100:.1f} cm, "
      f"obtenidos por integración del registro)")
    sm = R["sismo"]
    A(f"   Desplazamiento relativo máximo      |u|máx  = {sm['u_max']*1e3:.2f} mm "
      f"(t = {sm['t_u_max']:.2f} s)")
    A(f"   Deriva de la torre                  u/H     = {sm['deriva']*100:.4f} %")
    A(f"   Aceleración absoluta máxima         |ü_t|máx = {sm['a_abs_max']:.3f} m/s² "
      f"= {sm['a_abs_max']/G:.3f} g")
    A(f"   Amplificación respecto al terreno   ü_t/PGA = {sm['amplificacion_aceleracion']:.2f}")
    A(f"   Cortante basal máximo               V = k·u = {sm['cortante_max']/1e3:.1f} kN")
    A(f"   Momento en la base                  M = V·H = {sm['momento_max']/1e3:.1f} kN·m")
    A(f"   Coeficiente sísmico                 V/W     = {sm['coeficiente_sismico']:.4f}")
    A("")
    A("   Espectro de respuesta del registro (ζ = 5 %), evaluado en Tn:")
    for clave, valor in R["espectro_en_Tn"].items():
        A(f"      {clave:<16s} = {valor:.5f}")
    A(f"   Verificación cruzada Sd(Tn) vs. |u|máx de la historia: error = "
      f"{R['error_espectro_vs_historia']*100:.4f} %")
    Tp, PSap = R["periodo_pico_espectro"]
    A(f"   Pico del espectro de pseudo-aceleración: T = {Tp:.3f} s, PSa = {PSap/G:.3f} g")
    A("")
    A(R["verificacion_sismo"].texto())
    A("")
    A("3) ANÁLISIS PARAMÉTRICO SÍSMICO")
    for etiqueta, clave, col in [("Amortiguamiento ζ", "zeta", "u_max [mm]"),
                                 ("Rigidez efectiva (fisuración)", "rigidez", "u_max [mm]"),
                                 ("Nivel de llenado (masa)", "masa", "V_max [kN]")]:
        b = R["barridos"][clave]
        v = b.variacion(col)
        A(f"   {etiqueta:<32s}: {col} entre {v['minimo']:.3f} y {v['maximo']:.3f} "
          f"(razón {v['razon_max_min']:.2f}×)")
    A("   Tabla — efecto del amortiguamiento:")
    A(_indentar(R["barridos"]["zeta"].tabla_texto(
        ["u_max [mm]", "a_abs_max [g]", "V_max [kN]", "Tn [s]"])))
    A("   Tabla — efecto de la fisuración (rigidez efectiva):")
    A(_indentar(R["barridos"]["rigidez"].tabla_texto(
        ["Tn [s]", "u_max [mm]", "a_abs_max [g]", "V_max [kN]"])))
    A("   Tabla — efecto del nivel de llenado del tanque:")
    A(_indentar(R["barridos"]["masa"].tabla_texto(
        ["Tn [s]", "u_max [mm]", "a_abs_max [g]", "V_max [kN]"])))
    A("")
    ais = R["aislamiento"]
    A("4) CONTROL DE LA RESPUESTA SÍSMICA: AISLAMIENTO DE BASE")
    A(f"   Al alargar el periodo de {s.T_n:.2f} s a {ais['sistema'].T_n:.2f} s con ζ = 15 %:")
    A(f"      cortante basal      : {R['respuesta_sismo'].cortante_max/1e3:.1f} kN → "
      f"{ais['respuesta'].cortante_max/1e3:.1f} kN "
      f"(reducción {ais['reduccion_cortante']*100:.1f} %)")
    A(f"      aceleración absoluta: reducción {ais['reduccion_aceleracion']*100:.1f} %")
    A(f"      desplazamiento      : aumenta {ais['aumento_desplazamiento']:.2f}× "
      f"({ais['respuesta'].u_max*1e3:.1f} mm) → debe preverse la junta sísmica")
    A("")
    A("5) PARTE B — CARGA IMPULSIVA")
    im = R["impulso"]
    A(f"   {R['pulso'].descripcion()}")
    A(f"   Impulso total          I = ∫p·dt        = {im['impulso']:,.0f} N·s")
    A(f"   Relación de duración   td/Tn            = {im['td_sobre_Tn']:.4f} "
      f"(régimen {'IMPULSIVO' if im['td_sobre_Tn'] < 0.25 else 'de amplificación'})")
    A(f"   Desplazamiento estático u_st = p0/k     = {im['u_estatico']*1e3:.3f} mm")
    A(f"   Desplazamiento máximo   |u|máx          = {im['u_max']*1e3:.3f} mm")
    A(f"   Factor de amplificación Rd = |u|máx·k/p0 = {im['Rd']:.4f}  (< 1: la estructura "
      f"'no alcanza' a responder al pulso)")
    A(f"   Aproximación impulsiva  u ≈ I/(m·ωn)    = {im['u_aproximacion_impulsiva']*1e3:.3f} mm "
      f"(error {im['error_aproximacion']*100:.2f} % frente a la solución cerrada)")
    A(f"   Cortante basal máximo                   = {im['cortante_max']/1e3:.1f} kN")
    A(f"   Error de Newmark frente a la interpolación exacta = {im['error_newmark']*100:.5f} %")
    A("")
    A(R["verificacion_impulso"].texto())
    A("")
    A("   Efecto de la FORMA del pulso manteniendo el mismo impulso total:")
    for nombre, info in R["formas_pulso"].items():
        A(f"      {nombre:<14s}: p0 = {info['p0']/1e3:7.1f} kN → |u|máx = "
          f"{info['u_max']*1e3:.3f} mm")
    A("   → Con pulsos cortos (td << Tn) lo que gobierna es el IMPULSO, no la forma.")
    A("")
    A("6) TABLA — EFECTO DE LA DURACIÓN DEL PULSO")
    A(_indentar(R["barridos"]["duracion_pulso"].submuestrear(4).tabla_texto(
        ["u_max [mm]", "Rd [-]", "V_max [kN]", "Tn [s]"])))
    A("=" * 78)
    return "\n".join(L)


def _indentar(texto: str, espacios: int = 6) -> str:
    pre = " " * espacios
    return "\n".join(pre + ln for ln in texto.splitlines())


def main() -> dict:
    R = ejecutar()
    print(imprimir_informe(R))
    print(f"\nFiguras generadas en: {CARPETA.resolve()}")
    return R


if __name__ == "__main__":
    main()
