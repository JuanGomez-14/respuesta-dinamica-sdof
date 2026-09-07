"""
Pestaña «Transmisibilidad»: curvas TR, β para un TR objetivo y diseño de
aislamiento.

TR(β,ζ) = √[1+(2ζβ)²] / √[(1−β²)² + (2ζβ)²]

Ojo con la confusión frecuente: la ecuación de TR NO es la de R_d. Aislar
(TR < 1) exige β > √2, sin excepción, y en esa zona MÁS amortiguamiento empeora
el aislamiento en vez de mejorarlo.
"""

from __future__ import annotations

import math

import streamlit as st

from dinamica import (betas_para_transmisibilidad, curva_TR,
                      eficiencia_aislamiento, rigidez_serie, transmisibilidad)

from ..formato import FORMATO_ENTRADA
from ..estado import Proyecto
from ..widgets import fila_de_resultados, figura
from .portico import aplicar_x, mostrar_mensaje_x

ZETAS = [0.02, 0.05, 0.10, 0.20, 0.50]


def dibujar(proyecto: Proyecto) -> None:
    st.subheader("Transmisibilidad TR")
    st.caption("TR(β,ζ) = √[1+(2ζβ)²] / √[(1−β²)² + (2ζβ)²]. "
               "La zona de aislamiento (TR < 1) empieza en β = √2 ≈ 1.414.")

    zeta = st.number_input("ζ para los cálculos [%]",
                           value=float(proyecto.zeta_valor * 100),
                           min_value=0.0, max_value=99.0, format=FORMATO_ENTRADA,
                           key="tr_zeta") / 100

    _calculadora_beta(zeta)
    st.divider()
    _grafica(zeta)
    st.divider()
    _diseno_aislamiento(proyecto, zeta)


# ---------------------------------------------------------------------------
def _calculadora_beta(zeta: float) -> None:
    st.markdown("**β asociados a un TR objetivo**")
    objetivo = st.number_input("TR objetivo", value=0.30, min_value=1e-6,
                               format=FORMATO_ENTRADA, key="tr_obj")
    try:
        raices = betas_para_transmisibilidad(objetivo, zeta)
    except ValueError as exc:
        st.error(str(exc))
        st.session_state.pop("tr_betas", None)
        return

    st.session_state["tr_betas"] = raices
    if len(raices) == 2:
        b1, b2 = raices
        fila_de_resultados([("β₁ (rama baja)", b1, ""),
                            ("β₂ (rama alta)", b2, ""),
                            ("β₂ − β₁", b2 - b1, "")])
        st.info("Con TR > 1 hay dos soluciones, ambas por debajo de β = √2: "
                "son puntos de AMPLIFICACIÓN, no de aislamiento.")
    else:
        fila_de_resultados([
            ("β (única solución física)", raices[0], ""),
            ("Eficiencia de aislamiento", eficiencia_aislamiento(objetivo), "%"),
        ])
        if objetivo < 1:
            st.success(f"β = {raices[0]:.5g} > √2: zona de aislamiento. Se "
                       f"transmite el {objetivo * 100:.3g} % de la fuerza.")


def _grafica(zeta: float) -> None:
    seleccionados = st.multiselect(
        "Curvas a mostrar (ζ)", ZETAS, default=[0.02, 0.05, 0.10, 0.20],
        format_func=lambda z: f"{z * 100:.0f} %", key="tr_curvas")

    lista = seleccionados or [zeta]
    betas, curvas = curva_TR(lista)
    series = [(betas, curvas[z], f"ζ = {z * 100:.0f} %") for z in lista]

    puntos = []
    raices = st.session_state.get("tr_betas")
    if raices:
        objetivo = float(st.session_state.get("tr_obj", 0.3))
        puntos.append((list(raices), [objetivo] * len(raices),
                       f"β para TR = {objetivo:.3g}"))

    figura(series, "β = ω/ωₙ", "TR", vertical=math.sqrt(2),
           puntos=puntos, clave="graf_tr")
    st.caption("Note que pasado β = √2 las curvas se INVIERTEN: más "
               "amortiguamiento da peor aislamiento. Es el compromiso clásico "
               "entre controlar la resonancia al arrancar la máquina y aislar "
               "en régimen.")


# ---------------------------------------------------------------------------
def _diseno_aislamiento(proyecto: Proyecto, zeta: float) -> None:
    st.markdown("### Diseño de aislamiento")
    st.caption(
        "Caso típico: ¿qué rigidez deben tener los apoyos para que solo se "
        "transmita un porcentaje dado de la excitación? Con el β de aislamiento, "
        "ω_aislada = w/β fija la rigidez total del conjunto aislado.")

    if proyecto.problemas():
        st.warning("Complete la definición del sistema en la barra lateral.")
        return

    col_tr, col_w, col_n = st.columns(3)
    objetivo = col_tr.number_input("TR objetivo", value=0.30, min_value=1e-9,
                                   max_value=0.999999, format=FORMATO_ENTRADA,
                                   key="iso_tr")
    w = col_w.number_input("w — frecuencia de la excitación [rad/s]",
                           value=20.0, min_value=1e-9, format=FORMATO_ENTRADA, key="iso_w")
    n_apoyos = col_n.number_input("Número de aisladores", value=4, min_value=1,
                                  step=1, key="iso_n")

    try:
        raices = betas_para_transmisibilidad(objetivo, zeta)
    except ValueError as exc:
        st.error(str(exc))
        return
    beta = raices[-1]
    if beta <= math.sqrt(2):
        st.error("El β obtenido no está en la zona de aislamiento (β > √2). "
                 "Revise el TR objetivo.")
        return

    s = proyecto.sistema()
    omega_aislada = w / beta
    K_total = omega_aislada ** 2 * s.masa
    K_por_apoyo = K_total / n_apoyos

    fila_de_resultados([
        ("β de aislamiento", beta, ""),
        ("ω del conjunto aislado", omega_aislada, "rad/s"),
        ("T del conjunto aislado", 2 * math.pi / omega_aislada, "s"),
        ("K total requerida", K_total, "N/m"),
        (f"K de cada uno de los {int(n_apoyos)}", K_por_apoyo, "N/m"),
    ])

    st.table([
        {"Cantidad": "β para TR objetivo", "Valor": f"{beta:.6g}"},
        {"Cantidad": "ω_aislada = w/β", "Valor": f"{omega_aislada:.6g} rad/s"},
        {"Cantidad": "m (de la barra lateral)", "Valor": f"{s.masa:,.6g} kg"},
        {"Cantidad": "K_total = ω_aislada²·m", "Valor": f"{K_total:.6g} N/m"},
        {"Cantidad": f"K_apoyo = K_total/{int(n_apoyos)}",
         "Valor": f"{K_por_apoyo:.6g} N/m"},
        {"Cantidad": "TR verificada",
         "Valor": f"{float(transmisibilidad(beta, zeta)):.6g}"},
    ])

    st.markdown("**Estructura aislada sobre un pórtico**")
    st.caption(
        "Si los aisladores se montan sobre un pórtico, ambos trabajan en SERIE: "
        "1/K_total = 1/K_aisladores + 1/K_pórtico. Conocidas K_total y la de los "
        "aisladores, se despeja la del pórtico.")

    K_aisladores = st.number_input(
        "K del conjunto de aisladores [N/m]", value=float(K_total * 2),
        min_value=1e-9, format=FORMATO_ENTRADA, key="iso_ka",
        help="Debe ser mayor que K_total: en serie, el conjunto siempre es más "
             "flexible que cualquiera de sus partes.")

    if K_aisladores <= K_total:
        st.error(
            f"K de los aisladores ({K_aisladores:,.6g} N/m) debe ser MAYOR que "
            f"K_total ({K_total:,.6g} N/m). En una combinación en serie la "
            "rigidez resultante es siempre menor que la de cada componente, así "
            "que con este valor no existe un K_pórtico positivo.")
        return

    K_portico = (K_total * K_aisladores) / (K_aisladores - K_total)
    st.success(f"**K del pórtico = {K_portico:,.6g} N/m = "
               f"{K_portico / 1e3:,.6g} kN/m**")
    st.caption(f"K_p = (K_total·K_a)/(K_a − K_total) = "
               f"({K_total:.6g}·{K_aisladores:.6g})/"
               f"({K_aisladores:.6g} − {K_total:.6g}) = {K_portico:.6g} N/m  "
               f"[verificación en serie: {rigidez_serie([K_aisladores, K_portico]):.6g} N/m]")

    if proyecto.es_simbolico():
        st.button("Calcular la dimensión x del pórtico", key="iso_resolver",
                  on_click=aplicar_x, args=(proyecto, K_portico, "iso_msg"))
        mostrar_mensaje_x("iso_msg")
