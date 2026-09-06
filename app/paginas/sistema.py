"""
Barra lateral: definición del sistema de un grado de libertad.

Es el panel permanente que alimenta TODAS las pestañas. Cada magnitud se puede
introducir directamente o deducir de otra cosa, y siempre queda registrado cuál
de los dos caminos se usó.
"""

from __future__ import annotations

import math

import streamlit as st

from dinamica import zeta_por_ancho_de_banda, zeta_por_decremento_logaritmico

from ..estado import UNIDADES_MASA, UNIDADES_RIGIDEZ, Proyecto
from ..widgets import campo_con_unidad, mostrar_procedencia


def _aplicar_zeta(proyecto: Proyecto, zeta: float, procedencia: str,
                  detalle: str) -> None:
    """Fija ζ en el modelo Y en el widget.

    Va como callback de ``on_click`` a propósito: los callbacks corren ANTES de
    que se instancien los widgets del siguiente rerun, que es el único momento
    en que Streamlit permite escribir la clave de un widget. Mutar solo el
    modelo no basta: el valor guardado del widget lo revertiría.
    """
    proyecto.fijar_zeta(zeta, procedencia, detalle)
    st.session_state["sb_zeta"] = zeta * 100


def dibujar(proyecto: Proyecto) -> None:
    """Dibuja la barra lateral completa y actualiza el proyecto en el sitio."""
    with st.sidebar:
        st.header("Sistema de 1 GDL")
        proyecto.nombre = st.text_input("Nombre del sistema", proyecto.nombre)

        _masa(proyecto)
        _rigidez(proyecto)
        _amortiguamiento(proyecto)
        _propiedades(proyecto)


# ---------------------------------------------------------------------------
def _masa(proyecto: Proyecto) -> None:
    st.subheader("Masa")
    proyecto.masa_modo = st.radio(
        "¿Cómo se conoce la masa?",
        ["directa", "carga"],
        format_func=lambda m: {"directa": "Valor directo",
                               "carga": "Desde carga distribuida × área"}[m],
        index=["directa", "carga"].index(proyecto.masa_modo),
        key="masa_modo", horizontal=True)

    if proyecto.masa_modo == "directa":
        proyecto.masa_valor, proyecto.masa_unidad = campo_con_unidad(
            "Masa (o peso)", proyecto.masa_valor, proyecto.masa_unidad,
            UNIDADES_MASA, "sb_masa", formato="%.2f",
            ayuda="Si elige N, kN o kgf se interpreta como PESO y se divide por g.")
    else:
        proyecto.masa_carga = st.number_input(
            "Carga distribuida q [kN/m²]", value=float(proyecto.masa_carga),
            min_value=0.0, format="%.3f", key="sb_q")
        proyecto.masa_area = st.number_input(
            "Área tributaria A [m²]", value=float(proyecto.masa_area),
            min_value=0.0, format="%.3f", key="sb_area")

    mostrar_procedencia(proyecto.masa())


# ---------------------------------------------------------------------------
def _rigidez(proyecto: Proyecto) -> None:
    st.subheader("Rigidez")
    modos = ["directa", "portico", "periodo"]
    # Sin `index=`: esta clave la escriben también los botones «usar este K» y
    # «usar Tₙ identificado». Mezclar un valor por defecto con la escritura por
    # Session State hace que Streamlit avise y que el valor programado se pierda.
    st.session_state.setdefault("rig_modo", proyecto.rigidez_modo)
    proyecto.rigidez_modo = st.radio(
        "¿Cómo se conoce la rigidez?", modos,
        format_func=lambda m: {"directa": "Valor directo",
                               "portico": "Desde el pórtico",
                               "periodo": "Desde el periodo Tₙ"}[m],
        key="rig_modo")

    if proyecto.rigidez_modo == "directa":
        proyecto.rigidez_valor, proyecto.rigidez_unidad = campo_con_unidad(
            "Rigidez k", proyecto.rigidez_valor, proyecto.rigidez_unidad,
            UNIDADES_RIGIDEZ, "sb_k", formato="%.2f")
    elif proyecto.rigidez_modo == "periodo":
        st.session_state.setdefault("sb_Tn", float(proyecto.periodo_objetivo))
        proyecto.periodo_objetivo = st.number_input(
            "Periodo natural Tₙ [s]", min_value=1e-4, format="%.5f", key="sb_Tn")
    else:
        st.caption("Se toma del constructor de la pestaña **Pórtico → K**. "
                   "Cualquier cambio allí se refleja aquí de inmediato.")

    try:
        mostrar_procedencia(proyecto.rigidez())
    except ValueError as exc:
        st.warning(str(exc))


# ---------------------------------------------------------------------------
def _amortiguamiento(proyecto: Proyecto) -> None:
    st.subheader("Amortiguamiento")
    st.session_state.setdefault("sb_zeta", proyecto.zeta_valor * 100)
    porcentaje = st.number_input(
        "ζ [% del crítico]", min_value=0.0, max_value=99.0, step=0.5,
        format="%.4f", key="sb_zeta")
    # Si el usuario mueve el número a mano, la procedencia vuelve a "directa".
    if abs(porcentaje / 100 - proyecto.zeta_valor) > 1e-12:
        proyecto.fijar_zeta(porcentaje / 100, "directa")

    with st.expander("Calcular ζ a partir de un ensayo"):
        _zeta_decremento(proyecto)
        st.divider()
        _zeta_ancho_de_banda(proyecto)

    mostrar_procedencia(proyecto.zeta())


def _zeta_decremento(proyecto: Proyecto) -> None:
    st.markdown("**Decremento logarítmico** (dos picos de vibración libre)")
    col_a, col_b, col_n = st.columns(3)
    u1 = col_a.number_input("Pico uₙ", value=12.0, min_value=1e-9,
                            format="%.5f", key="dec_u1")
    u2 = col_b.number_input("Pico uₙ₊ₘ", value=8.4, min_value=1e-9,
                            format="%.5f", key="dec_u2")
    m = col_n.number_input("Ciclos m", value=1, min_value=1, step=1, key="dec_m")

    if u2 >= u1:
        st.info("El segundo pico debe ser menor: en vibración libre la amplitud decae.")
        return
    delta = math.log(u1 / u2) / m
    zeta = zeta_por_decremento_logaritmico(u1, u2, int(m))
    st.caption(f"δ = ln({u1:g}/{u2:g})/{int(m)} = {delta:.5g}  →  "
               f"ζ = δ/√(4π²+δ²) = {zeta:.5g} ({zeta * 100:.4g} %)")
    st.button("Usar este ζ", key="dec_usar", width="stretch",
              on_click=_aplicar_zeta,
              args=(proyecto, zeta, "decremento logarítmico",
                    f"δ = ln({u1:g}/{u2:g})/{int(m)} = {delta:.5g}; "
                    f"ζ = δ/√(4π²+δ²) = {zeta:.5g} ({zeta * 100:.4g} %)"))


def _zeta_ancho_de_banda(proyecto: Proyecto) -> None:
    st.markdown("**Ancho de banda de media potencia** (de una curva de respuesta)")
    col_a, col_b, col_r = st.columns(3)
    f_a = col_a.number_input("f₁ [Hz]", value=1.90, min_value=0.0,
                             format="%.5f", key="ab_fa")
    f_b = col_b.number_input("f₂ [Hz]", value=2.10, min_value=0.0,
                             format="%.5f", key="ab_fb")
    f_r = col_r.number_input("f resonante [Hz]", value=2.00, min_value=1e-9,
                             format="%.5f", key="ab_fr")
    if f_b <= f_a:
        st.info("f₂ debe ser mayor que f₁.")
        return
    zeta = zeta_por_ancho_de_banda(f_a, f_b, f_r)
    st.caption(f"ζ = (f₂−f₁)/(2·f_r) = ({f_b:g}−{f_a:g})/(2·{f_r:g}) = "
               f"{zeta:.5g} ({zeta * 100:.4g} %)")
    st.button("Usar este ζ", key="ab_usar", width="stretch",
              on_click=_aplicar_zeta,
              args=(proyecto, zeta, "ancho de banda de media potencia",
                    f"ζ = (f₂−f₁)/(2·f_r) = ({f_b:g}−{f_a:g})/(2·{f_r:g}) "
                    f"= {zeta:.5g}"))


# ---------------------------------------------------------------------------
def _propiedades(proyecto: Proyecto) -> None:
    st.subheader("Propiedades derivadas")
    fallas = proyecto.problemas()
    if fallas:
        for falla in fallas:
            st.error(falla)
        return

    s = proyecto.sistema()
    st.markdown(
        f"""
| | |
|---|---|
| ωₙ | {s.omega_n:,.4f} rad/s |
| fₙ | {s.f_n:,.4f} Hz |
| Tₙ | {s.T_n:,.4f} s |
| ω_D | {s.omega_D:,.4f} rad/s |
| c | {s.amortiguamiento:,.1f} N·s/m |
| c_cr | {s.c_critico:,.1f} N·s/m |
| m | {s.masa:,.1f} kg |
| k | {s.rigidez:,.1f} N/m |
""")
