"""
================================================================================
 CASO DE ESTUDIO 1 — CARGA ARMÓNICA
 Entrepiso industrial de acero que soporta un ventilador centrífugo
================================================================================

DESCRIPCIÓN
-----------
Plataforma industrial de un nivel (planta 6.0 m x 5.0 m) construida con cuatro
columnas de acero empotradas en la base y en la losa, y una losa maciza de
concreto sobre lámina colaborante que actúa como diafragma rígido. Sobre la
losa se instala un ventilador centrífugo cuyo rotor presenta un desbalance
residual y que opera a velocidad constante.

IDEALIZACIÓN (múltiples grados de libertad -> un grado de libertad)
-------------------------------------------------------------------
H1. El diafragma es infinitamente rígido en su plano: los cuatro nudos
    superiores tienen el mismo desplazamiento lateral u(t) -> UN grado de
    libertad por dirección de análisis.
H2. Toda la masa (losa + acabados + equipo) se concentra en el nivel de la
    losa; la masa de las columnas es despreciable frente a ella (< 5 %).
H3. Las columnas aportan sólo rigidez lateral; se desprecia la deformación
    axial y por cortante. Con vigas/losa muy rígidas, cada columna se
    comporta como empotrada-empotrada: k_col = 12·E·I/L³.
H4. Las cuatro columnas comparten el mismo desplazamiento -> trabajan en
    PARALELO: k = Σ k_col.
H5. Amortiguamiento viscoso equivalente ζ = 2 % (estructura metálica soldada
    sin elementos no estructurales que disipen energía).
H6. Comportamiento elástico lineal (las amplitudes esperadas son pequeñas).
H7. La fuerza del desbalance es armónica: p(t) = m_e·e·ω²·sin(ωt), aplicada
    horizontalmente en el nivel de la losa.

Ejecución:  python -m casos.caso1_maquinaria
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from dinamica import (G, CargaArmonica, CargaChirp, Rd, Rd_maximo, SistemaSDOF,
                      amplitud_permanente, barrido_carga, barrido_parametro,
                      beta_para_transmisibilidad, eficiencia_aislamiento,
                      fuerza_desbalance, graficos, resolver, respuesta_armonica,
                      rigidez_columna, rigidez_para_beta, rpm_a_rad_s,
                      transmisibilidad, vector_tiempo, vibracion_libre)
from dinamica.graficos import (graficar_Rd, graficar_TR, graficar_barrido,
                               graficar_barridos_multiples, graficar_comparacion,
                               graficar_fase, graficar_historia,
                               graficar_resonancia_y_batido)

# ===========================================================================
#  DATOS DE ENTRADA  (modifíquelos aquí: es el único bloque que cambia)
# ===========================================================================
DATOS = dict(
    # --- estructura ---------------------------------------------------
    masa_losa=18_000.0,          # kg   losa + acabados + carga viva permanente
    masa_equipo=6_000.0,         # kg   ventilador + base metálica
    E_acero=200e9,               # Pa   módulo de elasticidad del acero
    I_columna=3.692e-5,          # m^4  inercia fuerte del perfil (HEA 200)
    L_columna=3.50,              # m    altura libre entre empotramientos
    n_columnas=4,                # -    columnas iguales en paralelo
    zeta=0.02,                   # -    fracción de amortiguamiento crítico
    # --- máquina ------------------------------------------------------
    velocidad_rpm=180.0,         # rpm  velocidad de operación del ventilador
    masa_excentrica=30.0,        # kg   masa desbalanceada del rotor
    excentricidad=0.15,          # m    excentricidad del desbalance
    # --- criterios de servicio (valores de referencia habituales) ------
    limite_desplazamiento=1.0,   # mm   amplitud máxima tolerada por el equipo
    limite_aceleracion=0.05,     # g    confort/servicio en plataforma industrial
    TR_objetivo=0.20,            # -    transmisibilidad objetivo si se aísla
)

CARPETA = Path("salidas/figuras/caso1")


# ===========================================================================
def construir_sistema(datos: dict = DATOS) -> SistemaSDOF:
    """Construye el sistema equivalente de 1 GDL a partir de los datos físicos."""
    k = rigidez_columna(E=datos["E_acero"], I=datos["I_columna"],
                        L=datos["L_columna"], condicion="empotrada-empotrada",
                        n=datos["n_columnas"])
    m = datos["masa_losa"] + datos["masa_equipo"]
    s = SistemaSDOF(masa=m, rigidez=k, zeta=datos["zeta"],
                    nombre="Entrepiso industrial (SDOF equivalente)")
    s.metadatos.update(
        k_por_columna=k / datos["n_columnas"],
        n_columnas=datos["n_columnas"],
        idealizacion="4 columnas empotradas-empotradas en paralelo + diafragma rígido",
    )
    return s


def construir_carga(sistema: SistemaSDOF, datos: dict = DATOS) -> CargaArmonica:
    """Fuerza armónica producida por el desbalance del rotor."""
    w = rpm_a_rad_s(datos["velocidad_rpm"])
    p0 = fuerza_desbalance(datos["masa_excentrica"], datos["excentricidad"], w)
    return CargaArmonica(p0=p0, omega=w,
                         nombre=f"Desbalance del ventilador ({datos['velocidad_rpm']:.0f} rpm)")


# ===========================================================================
def ejecutar(datos: dict = DATOS, generar_figuras: bool = True) -> dict:
    """Resuelve el caso completo y devuelve un diccionario con los resultados."""
    R: dict = {"datos": dict(datos)}
    sistema = construir_sistema(datos)
    carga = construir_carga(sistema, datos)
    beta = sistema.beta(carga.omega)
    R["sistema"] = sistema
    R["carga"] = carga
    R["beta"] = beta

    # -------------------------------------------------------------------
    # 1. Propiedades dinámicas y verificación del estado de resonancia
    # -------------------------------------------------------------------
    Rd_op = float(Rd(beta, sistema.zeta))
    TR_op = float(transmisibilidad(beta, sistema.zeta))
    u_st = carga.p0 / sistema.rigidez
    u_perm = amplitud_permanente(carga.p0, sistema.rigidez, beta, sistema.zeta)
    acel_perm = (carga.omega ** 2) * u_perm
    R.update(
        Rd=Rd_op, TR=TR_op, u_estatico=u_st, u_permanente=u_perm,
        aceleracion_permanente=acel_perm,
        velocidad_permanente=carga.omega * u_perm,
        fuerza_transmitida=carga.p0 * TR_op,
        Rd_maximo_posible=Rd_maximo(sistema.zeta),
    )

    # -------------------------------------------------------------------
    # 2. Respuesta en el tiempo (Newmark) y verificación contra la solución
    #    analítica exacta
    # -------------------------------------------------------------------
    t_final = 25.0
    dt = sistema.T_n / 200.0
    t = vector_tiempo(t_final, dt)
    r_newmark = resolver(sistema, carga, t_final=t_final, dt=dt, metodo="newmark")
    r_analitica = respuesta_armonica(sistema, carga, t)
    r_exacta = resolver(sistema, carga, t_final=t_final, dt=dt, metodo="exacta")

    error_pico = abs(r_newmark.u_max - r_analitica.u_max) / r_analitica.u_max
    error_rms = float(np.sqrt(np.mean((r_newmark.u - r_analitica.u) ** 2))
                      / np.sqrt(np.mean(r_analitica.u ** 2)))
    R.update(respuesta=r_newmark, respuesta_analitica=r_analitica,
             respuesta_exacta=r_exacta,
             error_pico_newmark=error_pico, error_rms_newmark=error_rms,
             u_max_newmark=r_newmark.u_max, u_max_analitica=r_analitica.u_max)

    # verificación adicional: amplitud permanente medida en el último tramo
    ventana = r_newmark.recortar(0.8 * t_final, t_final)
    R["u_permanente_medida"] = ventana.u_max
    R["error_amplitud_permanente"] = abs(ventana.u_max - u_perm) / u_perm

    # -------------------------------------------------------------------
    # 3. Estudio de convergencia del paso de tiempo
    # -------------------------------------------------------------------
    razones = np.array([1/5, 1/10, 1/20, 1/50, 1/100, 1/200, 1/500])
    err_prom, err_lineal = [], []
    for rz in razones:
        dti = sistema.T_n * rz
        ti = vector_tiempo(t_final, dti)
        ref = respuesta_armonica(sistema, carga, ti).u_max
        up = resolver(sistema, carga, t_final=t_final, dt=dti, metodo="newmark",
                      familia="aceleracion_promedio").u_max
        ul = resolver(sistema, carga, t_final=t_final, dt=dti, metodo="newmark",
                      familia="aceleracion_lineal").u_max
        err_prom.append((up - ref) / ref)
        err_lineal.append((ul - ref) / ref)
    R["convergencia"] = dict(razones=razones,
                             aceleracion_promedio=np.array(err_prom),
                             aceleracion_lineal=np.array(err_lineal))

    # -------------------------------------------------------------------
    # 4. Análisis paramétrico
    # -------------------------------------------------------------------
    # 4.1 relación de frecuencias (barriendo la velocidad de la máquina)
    betas = np.linspace(0.1, 3.0, 60)
    barr_beta = barrido_carga(
        sistema,
        lambda b: CargaArmonica(p0=carga.p0, omega=b * sistema.omega_n),
        betas, "beta = w/wn", t_final=40.0, dt=sistema.T_n / 100, guardar_respuestas=False)
    # 4.2 amortiguamiento
    zetas = np.array([0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20])
    barr_zeta = barrido_parametro(sistema, carga, "zeta", zetas,
                                  t_final=60.0, dt=sistema.T_n / 100,
                                  guardar_respuestas=False)
    # 4.3 rigidez (rigidización con arriostramientos)
    factores_k = np.array([0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0])
    barr_k = barrido_parametro(sistema, carga, "rigidez",
                               factores_k * sistema.rigidez,
                               t_final=40.0, dt=sistema.T_n / 100,
                               guardar_respuestas=False)
    # 4.4 masa (lastre adicional sobre la losa)
    factores_m = np.array([0.6, 0.8, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0])
    barr_m = barrido_parametro(sistema, carga, "masa", factores_m * sistema.masa,
                               t_final=40.0, dt=sistema.T_n / 100,
                               guardar_respuestas=False)
    # 4.5 amplitud de la excitación (velocidad de operación: p0 ~ w^2)
    velocidades = np.linspace(60, 300, 40)          # rpm
    def carga_rpm(rpm):
        w = rpm_a_rad_s(rpm)
        return CargaArmonica(p0=fuerza_desbalance(datos["masa_excentrica"],
                                                  datos["excentricidad"], w), omega=w)
    barr_rpm = barrido_carga(sistema, carga_rpm, velocidades, "velocidad [rpm]",
                             t_final=40.0, dt=sistema.T_n / 100,
                             guardar_respuestas=False)
    R["barridos"] = dict(beta=barr_beta, zeta=barr_zeta, rigidez=barr_k,
                         masa=barr_m, rpm=barr_rpm,
                         factores_k=factores_k, factores_m=factores_m)

    # -------------------------------------------------------------------
    # 5. Estrategias de control de la respuesta
    # -------------------------------------------------------------------
    # (a) rigidizar: llevar beta a 0.5  (sintonía "rígida", wn = 2w)
    k_rig = rigidez_para_beta(sistema.masa, carga.omega, 0.5)
    s_rig = sistema.con(rigidez=k_rig, nombre="Entrepiso rigidizado (β = 0.5)")
    u_rig = amplitud_permanente(carga.p0, k_rig, 0.5, sistema.zeta)
    # (b) amortiguar: ζ = 10 % con amortiguadores viscosos
    s_amo = sistema.con(zeta=0.10, nombre="Entrepiso con amortiguadores (ζ = 10 %)")
    u_amo = amplitud_permanente(carga.p0, sistema.rigidez, beta, 0.10)
    # (c) aislar la máquina sobre resortes para TR objetivo
    zeta_aislador = 0.05
    beta_aisl = beta_para_transmisibilidad(datos["TR_objetivo"], zeta_aislador)
    f_aislador = carga.frecuencia_hz / beta_aisl
    k_aislador = datos["masa_equipo"] * (2 * math.pi * f_aislador) ** 2
    delta_estatica = datos["masa_equipo"] * G / k_aislador
    R["control"] = dict(
        rigidizar=dict(k=k_rig, factor_k=k_rig / sistema.rigidez, u=u_rig,
                       Tn=s_rig.T_n, beta=0.5,
                       reduccion=1 - u_rig / u_perm),
        amortiguar=dict(zeta=0.10, u=u_amo, reduccion=1 - u_amo / u_perm),
        aislar=dict(TR_objetivo=datos["TR_objetivo"], beta=beta_aisl,
                    f_aislador=f_aislador, k_aislador=k_aislador,
                    deflexion_estatica=delta_estatica,
                    eficiencia=eficiencia_aislamiento(datos["TR_objetivo"]),
                    fuerza_transmitida=carga.p0 * datos["TR_objetivo"]),
        sistemas=dict(rigidizado=s_rig, amortiguado=s_amo),
    )

    # -------------------------------------------------------------------
    # 6. Arranque de la máquina: paso por resonancia (barrido de frecuencias)
    # -------------------------------------------------------------------
    T_arranque = 40.0
    chirp = CargaChirp(p0=carga.p0, f0=0.2, f1=2.0 * sistema.f_n, T=T_arranque)
    r_arranque = resolver(sistema, chirp, t_final=T_arranque + 10.0,
                          dt=sistema.T_n / 100, metodo="newmark")
    R["arranque"] = dict(respuesta=r_arranque, carga=chirp,
                         u_max=r_arranque.u_max,
                         razon_vs_permanente=r_arranque.u_max / u_perm)

    # -------------------------------------------------------------------
    # 7. Casos límite didácticos: resonancia pura y batido (ζ = 0)
    # -------------------------------------------------------------------
    s0 = sistema.con(zeta=0.0)
    t_lim = vector_tiempo(25.0, sistema.T_n / 200)
    r_res = respuesta_armonica(s0, CargaArmonica(p0=carga.p0, omega=s0.omega_n), t_lim)
    r_bat = respuesta_armonica(s0, CargaArmonica(p0=carga.p0, omega=0.85 * s0.omega_n),
                               t_lim, etiqueta="Batido (β = 0.85, ζ = 0)")
    R["limites"] = dict(resonancia=r_res, batido=r_bat)

    # -------------------------------------------------------------------
    # 8. Verificación de criterios de servicio
    # -------------------------------------------------------------------
    R["servicio"] = dict(
        u_mm=u_perm * 1e3, limite_u_mm=datos["limite_desplazamiento"],
        cumple_u=u_perm * 1e3 <= datos["limite_desplazamiento"],
        a_g=acel_perm / G, limite_a_g=datos["limite_aceleracion"],
        cumple_a=acel_perm / G <= datos["limite_aceleracion"],
        v_mms=carga.omega * u_perm * 1e3,
    )

    # -------------------------------------------------------------------
    # 9. Figuras
    # -------------------------------------------------------------------
    if generar_figuras:
        R["figuras"] = _figuras(R)
    return R


# ===========================================================================
def _figuras(R: dict) -> dict:
    sistema = R["sistema"]
    beta = R["beta"]
    figs = {}
    graficos.usar_carpeta(CARPETA)

    # se grafica una ventana de 8 s para que los ciclos sean legibles
    figs["historia"] = graficar_historia(
        R["respuesta"].recortar(0.0, 8.0),
        titulo="Caso 1 — Respuesta ante la carga armónica de la máquina (primeros 8 s)",
        mostrar=("p", "u", "v", "a"), nombre_archivo="c1_historia")

    figs["verificacion"] = graficar_comparacion(
        [R["respuesta_analitica"].recortar(0.0, 6.0),
         R["respuesta"].recortar(0.0, 6.0),
         R["respuesta_exacta"].recortar(0.0, 6.0)],
        ["Analítica exacta", "Newmark (β=1/4, γ=1/2)", "Interpolación exacta"],
        titulo=("Caso 1 — Verificación del motor de cálculo: "
                f"error en el pico = {R['error_pico_newmark']*100:.4f} %"),
        nombre_archivo="c1_verificacion")

    figs["Rd"] = graficar_Rd(
        zetas=(0.01, 0.02, 0.05, 0.10, 0.20),
        titulo="Caso 1 — Factor de amplificación dinámica y punto de operación",
        marcar=dict(beta=beta, zeta=sistema.zeta,
                    texto=f"Operación: β={beta:.3f}, ζ={sistema.zeta:.2f}\n$R_d$={R['Rd']:.1f}"),
        nombre_archivo="c1_Rd")

    figs["TR"] = graficar_TR(
        zetas=(0.02, 0.05, 0.10, 0.20, 0.50),
        titulo="Caso 1 — Transmisibilidad: la máquina opera en la zona de amplificación",
        marcar=dict(beta=beta, zeta=sistema.zeta,
                    texto=f"β={beta:.3f} → TR={R['TR']:.1f}"),
        nombre_archivo="c1_TR")

    figs["fase"] = graficar_fase(nombre_archivo="c1_fase")

    figs["barrido_beta"] = graficar_barrido(
        R["barridos"]["beta"], "u_max [mm]", etiqueta_x="Relación de frecuencias β = ω/ω$_n$",
        titulo="Caso 1 — Efecto de la relación de frecuencias sobre el desplazamiento máximo",
        nombre_archivo="c1_barrido_beta")

    figs["barrido_zeta"] = graficar_barrido(
        R["barridos"]["zeta"], "u_max [mm]",
        etiqueta_x="Fracción de amortiguamiento crítico ζ [-]",
        titulo="Caso 1 — Efecto del amortiguamiento (operando en resonancia)",
        nombre_archivo="c1_barrido_zeta")

    figs["barrido_k_m"] = graficar_barridos_multiples(
        [R["barridos"]["rigidez"], R["barridos"]["masa"]],
        ["Variación de la rigidez k", "Variación de la masa m"],
        columna_y="u_max [mm]", columna_x="Tn [s]",
        etiqueta_x="Periodo natural resultante T$_n$ [s]",
        titulo="Caso 1 — Efecto de la masa y de la rigidez (a través del periodo natural)",
        nombre_archivo="c1_barrido_km")

    figs["barrido_rpm"] = graficar_barrido(
        R["barridos"]["rpm"], "u_max [mm]", etiqueta_x="Velocidad de operación [rpm]",
        titulo=("Caso 1 — Efecto de la velocidad de la máquina "
                "(la fuerza crece con ω² y además cambia β)"),
        nombre_archivo="c1_barrido_rpm")

    figs["arranque"] = graficar_historia(
        R["arranque"]["respuesta"],
        titulo="Caso 1 — Arranque: barrido de frecuencias que atraviesa la resonancia",
        mostrar=("p", "u"), nombre_archivo="c1_arranque")

    figs["limites"] = graficar_resonancia_y_batido(
        R["limites"]["resonancia"], R["limites"]["batido"],
        ust=R["u_estatico"], wn=sistema.omega_n, nombre_archivo="c1_limites")

    figs["convergencia"] = graficos.graficar_convergencia(
        R["convergencia"]["razones"],
        {"Newmark aceleración promedio (β=1/4)": R["convergencia"]["aceleracion_promedio"],
         "Newmark aceleración lineal (β=1/6)": R["convergencia"]["aceleracion_lineal"]},
        titulo="Caso 1 — Convergencia del integrador frente a la solución analítica",
        nombre_archivo="c1_convergencia")

    # comparación de las estrategias de control
    figs["control"] = _figura_control(R)
    return figs


def _figura_control(R: dict):
    import matplotlib.pyplot as plt
    from dinamica.graficos import COLORES, guardar

    sistema, carga = R["sistema"], R["carga"]
    t = vector_tiempo(12.0, sistema.T_n / 200)
    casos = [
        ("Situación actual (β=%.2f, ζ=%.0f%%)" % (R["beta"], sistema.zeta * 100), sistema),
        ("Con amortiguadores (ζ=10 %)", R["control"]["sistemas"]["amortiguado"]),
        ("Rigidizado (β=0.5)", R["control"]["sistemas"]["rigidizado"]),
    ]
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    for i, (etq, s) in enumerate(casos):
        r = respuesta_armonica(s, carga, t)
        ax.plot(t, r.u * 1e3, label=f"{etq} — |u|máx = {r.u_max*1e3:.2f} mm",
                color=COLORES[i % len(COLORES)])
    ax.axhline(R["datos"]["limite_desplazamiento"], color="k", ls="--", lw=1.0)
    ax.axhline(-R["datos"]["limite_desplazamiento"], color="k", ls="--", lw=1.0)
    ax.text(0.2, R["datos"]["limite_desplazamiento"] * 1.15,
            f"Límite de servicio ± {R['datos']['limite_desplazamiento']:.1f} mm", fontsize=8)
    ax.set_xlabel("Tiempo t [s]")
    ax.set_ylabel("u(t) [mm]")
    ax.set_title("Caso 1 — Comparación de las estrategias de control de la respuesta")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    return guardar(fig, "c1_control", carpeta=CARPETA)


# ===========================================================================
def imprimir_informe(R: dict) -> str:
    """Genera el informe de consola del caso (también se usa en el reporte PDF)."""
    s, c = R["sistema"], R["carga"]
    d = R["datos"]
    ctrl = R["control"]
    L = []
    A = L.append
    A("=" * 78)
    A("CASO 1 — ENTREPISO INDUSTRIAL CON MÁQUINA ROTATIVA (CARGA ARMÓNICA)")
    A("=" * 78)
    A("")
    A("1) IDEALIZACIÓN Y PROPIEDADES DEL SISTEMA EQUIVALENTE DE 1 GDL")
    A(f"   Masa concentrada en la losa      m  = {s.masa:,.0f} kg "
      f"({d['masa_losa']:,.0f} losa + {d['masa_equipo']:,.0f} equipo)")
    A(f"   Rigidez por columna              k1 = {s.metadatos['k_por_columna']:,.0f} N/m "
      f"= 12·E·I/L³")
    A(f"   Rigidez lateral total (paralelo) k  = {s.rigidez:,.0f} N/m "
      f"= {d['n_columnas']} × k1")
    A(f"   Amortiguamiento                  c  = {s.amortiguamiento:,.1f} N·s/m "
      f"(ζ = {s.zeta:.3f}; c_cr = {s.c_critico:,.0f} N·s/m)")
    A(f"   Frecuencia natural               ωn = {s.omega_n:.4f} rad/s ; "
      f"fn = {s.f_n:.4f} Hz ; Tn = {s.T_n:.4f} s")
    A("")
    A("2) EXCITACIÓN")
    A(f"   {c.descripcion()}")
    A(f"   p0 = m_e·e·ω² = {d['masa_excentrica']:.0f} kg × {d['excentricidad']:.3f} m × "
      f"({c.omega:.3f} rad/s)² = {c.p0:,.1f} N")
    A(f"   Relación de frecuencias β = ω/ωn = {R['beta']:.4f}   "
      f"({'RESONANCIA' if abs(R['beta']-1) < 0.15 else 'fuera de resonancia'})")
    A("")
    A("3) RESPUESTA")
    A(f"   Desplazamiento estático  u_st = p0/k          = {R['u_estatico']*1e3:.4f} mm")
    A(f"   Factor de amplificación  Rd                   = {R['Rd']:.3f} "
      f"(máximo posible con ζ={s.zeta:.2f}: {R['Rd_maximo_posible']:.3f})")
    A(f"   Amplitud permanente      u0 = u_st·Rd         = {R['u_permanente']*1e3:.4f} mm")
    A(f"   Pico transitorio (Newmark)                    = {R['u_max_newmark']*1e3:.4f} mm")
    A(f"   Velocidad                v0 = ω·u0            = {R['velocidad_permanente']*1e3:.2f} mm/s")
    A(f"   Aceleración              a0 = ω²·u0           = {R['aceleracion_permanente']:.4f} m/s² "
      f"= {R['aceleracion_permanente']/G:.4f} g")
    A(f"   Transmisibilidad         TR                   = {R['TR']:.3f}")
    A(f"   Fuerza transmitida a la cimentación  fT = p0·TR = {R['fuerza_transmitida']/1e3:.2f} kN "
      f"(la carga aplicada es sólo {c.p0/1e3:.2f} kN)")
    A("")
    A("4) VERIFICACIÓN DEL MOTOR DE CÁLCULO")
    A(f"   |u|máx analítica exacta   = {R['u_max_analitica']*1e3:.6f} mm")
    A(f"   |u|máx Newmark (Δt=Tn/200)= {R['u_max_newmark']*1e3:.6f} mm  "
      f"→ error = {R['error_pico_newmark']*100:.5f} %")
    A(f"   Error RMS de toda la historia                = {R['error_rms_newmark']*100:.5f} %")
    A(f"   Amplitud permanente medida vs. teórica       → error = "
      f"{R['error_amplitud_permanente']*100:.4f} %")
    A("")
    A("5) VERIFICACIÓN DE CRITERIOS DE SERVICIO")
    sv = R["servicio"]
    A(f"   Desplazamiento  {sv['u_mm']:.3f} mm  vs. límite {sv['limite_u_mm']:.2f} mm  → "
      f"{'CUMPLE' if sv['cumple_u'] else 'NO CUMPLE'}")
    A(f"   Aceleración     {sv['a_g']:.4f} g   vs. límite {sv['limite_a_g']:.3f} g   → "
      f"{'CUMPLE' if sv['cumple_a'] else 'NO CUMPLE'}")
    A(f"   Velocidad pico  {sv['v_mms']:.2f} mm/s  (referencia ISO 10816 para maquinaria)")
    A("")
    A("6) ANÁLISIS PARAMÉTRICO (resumen)")
    for nombre, clave, col in [("Relación de frecuencias β", "beta", "u_max [mm]"),
                               ("Amortiguamiento ζ", "zeta", "u_max [mm]"),
                               ("Rigidez k", "rigidez", "u_max [mm]"),
                               ("Masa m", "masa", "u_max [mm]")]:
        v = R["barridos"][clave].variacion(col)
        A(f"   {nombre:<26s}: u_máx entre {v['minimo']:.3f} y {v['maximo']:.3f} mm "
          f"(razón {v['razon_max_min']:.1f}×)")
    A("")
    A("7) ESTRATEGIAS DE CONTROL DE LA RESPUESTA")
    A(f"   (a) Rigidizar hasta β=0.5: k = {ctrl['rigidizar']['k']:,.0f} N/m "
      f"({ctrl['rigidizar']['factor_k']:.2f}× la actual) → u0 = {ctrl['rigidizar']['u']*1e3:.3f} mm "
      f"(reducción {ctrl['rigidizar']['reduccion']*100:.1f} %)")
    A(f"   (b) Amortiguadores ζ=10 %: u0 = {ctrl['amortiguar']['u']*1e3:.3f} mm "
      f"(reducción {ctrl['amortiguar']['reduccion']*100:.1f} %)")
    A(f"   (c) Aislar la máquina con TR={ctrl['aislar']['TR_objetivo']:.2f}: "
      f"β_aislador = {ctrl['aislar']['beta']:.2f} → f_aislador = "
      f"{ctrl['aislar']['f_aislador']:.3f} Hz, k = {ctrl['aislar']['k_aislador']/1e3:.1f} kN/m, "
      f"deflexión estática = {ctrl['aislar']['deflexion_estatica']*1e3:.0f} mm")
    A(f"       → fuerza transmitida {ctrl['aislar']['fuerza_transmitida']/1e3:.2f} kN "
      f"(eficiencia {ctrl['aislar']['eficiencia']:.0f} %)")
    A("")
    A("8) ARRANQUE DE LA MÁQUINA (paso por resonancia)")
    A(f"   |u|máx durante el barrido de frecuencias = {R['arranque']['u_max']*1e3:.3f} mm "
      f"({R['arranque']['razon_vs_permanente']*100:.1f} % de la amplitud permanente en resonancia)")
    A("   → Atravesar rápidamente la resonancia produce amplitudes MENORES que operar en ella.")
    A("=" * 78)
    return "\n".join(L)


def main() -> dict:
    R = ejecutar()
    print(imprimir_informe(R))
    print(f"\nFiguras generadas en: {CARPETA.resolve()}")
    return R


if __name__ == "__main__":
    main()
