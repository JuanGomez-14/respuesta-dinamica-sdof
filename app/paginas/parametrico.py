"""
Pestaña «Análisis paramétrico»: cómo cambia la respuesta al variar un dato.

Responde la pregunta de diseño "¿qué pasa si…?": si la masa crece un 20 %, si
el amortiguamiento real resulta ser la mitad del supuesto, si la máquina gira
más rápido. Barre un parámetro y tabula la respuesta máxima para cada valor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from dinamica import (CargaArmonica, barrido_carga, barrido_parametro,
                      hz_a_rad_s, rpm_a_rad_s)

from ..estado import Proyecto
from ..widgets import figura

PARAMETROS = {
    "masa": ("Masa m [kg]", "kg"),
    "rigidez": ("Rigidez k [N/m]", "N/m"),
    "zeta": ("Amortiguamiento ζ [-]", ""),
    "omega": ("Frecuencia de la carga ω [rad/s]", "rad/s"),
}


def dibujar(proyecto: Proyecto) -> None:
    if proyecto.problemas():
        st.warning("Complete la definición del sistema en la barra lateral.")
        return

    s = proyecto.sistema()
    st.subheader("Análisis paramétrico")
    st.caption("Se barre un parámetro manteniendo los demás fijos y se tabula "
               "la respuesta máxima. Útil para justificar decisiones de diseño "
               "y para ver a qué dato es sensible el resultado.")

    st.markdown("**Carga armónica de referencia**")
    col_p0, col_w, col_wu = st.columns(3)
    p0 = col_p0.number_input("Amplitud p₀ [N]", value=1600.0, format="%.3f",
                             key="par_p0")
    valor_w = col_w.number_input("Frecuencia de la carga", value=3.0,
                                 min_value=1e-9, format="%.5f", key="par_w")
    unidad_w = col_wu.selectbox("Unidad", ["rad/s", "Hz", "rpm"], key="par_wu")
    omega = {"rad/s": lambda v: v, "Hz": hz_a_rad_s,
             "rpm": rpm_a_rad_s}[unidad_w](valor_w)

    st.markdown("**Parámetro a barrer**")
    parametro = st.selectbox("Parámetro", list(PARAMETROS),
                             format_func=lambda p: PARAMETROS[p][0],
                             key="par_cual")

    actual = {"masa": s.masa, "rigidez": s.rigidez,
              "zeta": s.zeta, "omega": omega}[parametro]
    col_min, col_max, col_n = st.columns(3)
    desde = col_min.number_input("Desde", value=float(actual) * 0.5,
                                 format="%.6g", key="par_desde")
    hasta = col_max.number_input("Hasta", value=float(actual) * 1.5,
                                 format="%.6g", key="par_hasta")
    puntos = col_n.number_input("Número de valores", value=25, min_value=3,
                                max_value=200, step=1, key="par_n")

    if hasta <= desde:
        st.error("El valor final debe ser mayor que el inicial.")
        return
    if parametro == "zeta" and (desde < 0 or hasta >= 1):
        st.error("El amortiguamiento debe cumplir 0 ≤ ζ < 1.")
        return
    if parametro in ("masa", "rigidez", "omega") and desde <= 0:
        st.error("Este parámetro debe ser positivo.")
        return

    valores = np.linspace(desde, hasta, int(puntos))
    carga = CargaArmonica(p0=p0, omega=omega)
    t_final = 20 * s.T_n

    with st.spinner("Calculando el barrido..."):
        if parametro == "omega":
            resultado = barrido_carga(
                s, lambda w: CargaArmonica(p0=p0, omega=w), valores,
                nombre_parametro="omega", guardar_respuestas=False,
                t_final=t_final)
        else:
            resultado = barrido_parametro(
                s, carga, parametro, valores, guardar_respuestas=False,
                t_final=t_final)

    # Las filas del barrido no traen la columna del parámetro barrido: los
    # valores viven en resultado.valores. Se antepone para poder graficar.
    etiqueta_x = PARAMETROS[parametro][0]
    tabla = pd.DataFrame(resultado.filas)
    tabla.insert(0, etiqueta_x, list(resultado.valores))
    st.dataframe(tabla, hide_index=True)

    columnas_y = [c for c in tabla.columns
                  if c != etiqueta_x and pd.api.types.is_numeric_dtype(tabla[c])]
    if columnas_y:
        predeterminada = ("u_max [mm]" if "u_max [mm]" in columnas_y
                          else columnas_y[0])
        elegida = st.selectbox("Magnitud a graficar", columnas_y,
                               index=columnas_y.index(predeterminada), key="par_y")
        figura([(tabla[etiqueta_x], tabla[elegida], elegida)],
               etiqueta_x, elegida)

    st.download_button(
        "Descargar la tabla (CSV)",
        tabla.to_csv(index=False).encode("utf-8"),
        file_name=f"barrido_{parametro}.csv", mime="text/csv")
