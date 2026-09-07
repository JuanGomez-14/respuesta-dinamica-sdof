"""
Pestaña «Amplificación R_d»: curvas, β para un R_d objetivo y diseño de la
sección mínima de columna.

R_d(β,ζ) = 1/√[(1−β²)² + (2ζβ)²]

El problema de diseño clásico: "el desplazamiento dinámico no debe superar N
veces el estático" es exactamente R_d objetivo = N. Eso da dos β; para la
sección MÍNIMA se usa el β MAYOR, porque ωₙ = w/β decrece al crecer β, y con él
la rigidez K = ωₙ²·m y la sección que la produce.
"""

from __future__ import annotations

import math

import streamlit as st

from dinamica import Rd_maximo, beta_para_Rd, beta_resonante, curva_Rd

from ..formato import FORMATO_ENTRADA
from ..estado import Proyecto
from ..widgets import fila_de_resultados, figura
from .portico import aplicar_x, mostrar_mensaje_x


def _usar_media_potencia(maximo: float) -> None:
    st.session_state["rd_obj"] = maximo / math.sqrt(2)

ZETAS = [0.02, 0.05, 0.10, 0.20, 0.50]


def dibujar(proyecto: Proyecto) -> None:
    st.subheader("Factor de amplificación dinámica R_d")
    st.caption("R_d(β,ζ) = 1/√[(1−β²)² + (2ζβ)²],  con β = ω/ωₙ.")

    zeta_objetivo = st.number_input(
        "ζ para los cálculos [%]", value=float(proyecto.zeta_valor * 100),
        min_value=0.0, max_value=99.0, format=FORMATO_ENTRADA, key="rd_zeta") / 100

    _calculadora_beta(proyecto, zeta_objetivo)
    st.divider()
    _grafica(proyecto, zeta_objetivo)
    st.divider()
    _diseno(proyecto)


# ---------------------------------------------------------------------------
def _calculadora_beta(proyecto: Proyecto, zeta: float) -> None:
    st.markdown("**β asociados a un R_d objetivo**")

    maximo = Rd_maximo(zeta) if zeta > 0 else float("inf")
    col_obj, col_media = st.columns([2, 1])
    st.session_state.setdefault("rd_obj", 3.0)
    objetivo = col_obj.number_input(
        "R_d objetivo", min_value=1e-6, format=FORMATO_ENTRADA, key="rd_obj")
    with col_media:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.button("Usar R_máx/√2", width="stretch", key="rd_media",
                  help="Método del ancho de banda de media potencia",
                  disabled=zeta <= 0 or not math.isfinite(maximo),
                  on_click=_usar_media_potencia, args=(maximo,))

    if zeta > 0:
        st.caption(f"Para ζ = {zeta * 100:.4g} %, R_máx = {maximo:.5g} en "
                   f"β_r = {beta_resonante(zeta):.5g}.")

    try:
        raices = beta_para_Rd(objetivo, zeta)
    except ValueError as exc:
        st.error(str(exc))
        st.session_state.pop("rd_betas", None)
        return

    st.session_state["rd_betas"] = raices

    if len(raices) == 2:
        b1, b2 = raices
        fila_de_resultados([
            ("β₁ (rama baja)", b1, ""),
            ("β₂ (rama alta)", b2, ""),
            ("β₂ − β₁", b2 - b1, ""),
            ("(β₂−β₁)/2", (b2 - b1) / 2, ""),
        ])
        st.caption(
            "Si el R_d objetivo es R_máx/√2, entonces (β₂−β₁)/2 ≈ ζ: ese es el "
            "método del ancho de banda de media potencia. La igualdad es "
            "aproximada y solo vale para ζ pequeño.")
    else:
        st.info("Con R_d objetivo < 1 solo existe un β físico: la otra raíz de "
                "la cuadrática da β² < 0. Este β cae en la zona de aislamiento.")
        fila_de_resultados([("β (única solución física)", raices[0], "")])


def _grafica(proyecto: Proyecto, zeta: float) -> None:
    seleccionados = st.multiselect(
        "Curvas a mostrar (ζ)", ZETAS, default=[0.02, 0.05, 0.10, 0.20],
        format_func=lambda z: f"{z * 100:.0f} %", key="rd_curvas")

    betas, curvas = curva_Rd(seleccionados or [zeta])
    series = [(betas, curvas[z], f"ζ = {z * 100:.0f} %") for z in (seleccionados or [zeta])]

    puntos = []
    raices = st.session_state.get("rd_betas")
    if raices:
        objetivo = float(st.session_state.get("rd_obj", 3.0))
        puntos.append(([b for b in raices], [objetivo] * len(raices),
                       f"β para R_d = {objetivo:.3g}"))
    if not proyecto.problemas():
        s = proyecto.sistema()
        st.caption(f"El sistema actual tiene ωₙ = {s.omega_n:.4f} rad/s; el β "
                   "depende de la frecuencia de la carga que use en cada pestaña.")

    figura(series, "β = ω/ωₙ", "R_d", puntos=puntos,
           clave="graf_rd")


# ---------------------------------------------------------------------------
def _diseno(proyecto: Proyecto) -> None:
    st.markdown("### Diseño: sección mínima de columna")
    st.caption(
        "Para «el desplazamiento dinámico debe ser a lo sumo N veces el "
        "estático», tome R_d objetivo = N arriba. De los dos β resultantes, el "
        "**mayor** da la sección mínima: ωₙ = w/β es menor, luego K = ωₙ²·m es "
        "menor y la sección requerida también.")

    raices = st.session_state.get("rd_betas")
    if not raices:
        st.info("Primero calcule los β arriba.")
        return
    if proyecto.problemas():
        st.warning("Complete la definición del sistema en la barra lateral.")
        return

    col_beta, col_w = st.columns(2)
    eleccion = col_beta.selectbox(
        "β a usar", list(range(len(raices))),
        format_func=lambda i: (f"β = {raices[i]:.5g}"
                               + (" (el mayor → sección mínima)"
                                  if i == len(raices) - 1 and len(raices) > 1
                                  else "")),
        index=len(raices) - 1, key="rd_beta_elegido")
    beta = raices[eleccion]

    w = col_w.number_input("w — frecuencia de la carga aplicada [rad/s]",
                           value=float(st.session_state.get("rd_w", 20.0)),
                           min_value=1e-9, format=FORMATO_ENTRADA, key="rd_w")

    s = proyecto.sistema()
    omega_n = w / beta
    K = omega_n ** 2 * s.masa

    fila_de_resultados([
        ("ωₙ = w/β", omega_n, "rad/s"),
        ("Tₙ resultante", 2 * math.pi / omega_n, "s"),
        ("K = ωₙ²·m", K, "N/m"),
        ("K", K / 1e3, "kN/m"),
    ])
    st.caption(f"Con m = {s.masa:,.4g} kg y β = {beta:.5g}: "
               f"ωₙ = {w:.5g}/{beta:.5g} = {omega_n:.5g} rad/s, "
               f"K = {omega_n:.5g}²·{s.masa:.6g} = {K:.6g} N/m")

    st.markdown("**Dimensión de la columna que produce ese K**")
    if not proyecto.es_simbolico():
        st.info("Para despejar una dimensión, marque b y/o h como coeficiente "
                "de x en la pestaña **Pórtico → K** (para una columna cuadrada "
                "de lado x, ponga b = h = 1 y marque ambas).")
        return

    st.button("Calcular la dimensión x", key="rd_resolver",
              on_click=aplicar_x, args=(proyecto, K, "rd_msg"))
    mostrar_mensaje_x("rd_msg")
