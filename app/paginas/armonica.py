"""
Pestaña «Carga armónica»: respuesta ante p(t) = p₀·sen(ωt + φ).

Se resuelve la respuesta TOTAL por integración numérica y se superpone la
solución analítica de estado estacionario. La diferencia entre ambas es el
transitorio, que el amortiguamiento extingue: verlas juntas es la mejor manera
de entender por qué el diseño se hace con la permanente.
"""

from __future__ import annotations

import math

import numpy as np
import streamlit as st

from dinamica import (CargaArmonica, Rd, angulo_fase, hz_a_rad_s,
                      resolver, respuesta_permanente_armonica, rpm_a_rad_s,
                      vector_tiempo)

from ..formato import FORMATO_ENTRADA
from ..estado import Proyecto
from ..widgets import fila_de_resultados, figura


def dibujar(proyecto: Proyecto) -> None:
    if proyecto.problemas():
        st.warning("Complete la definición del sistema en la barra lateral.")
        return

    s = proyecto.sistema()
    st.subheader("Carga armónica  p(t) = p₀·sen(ω·t)")

    col_p0, col_frec, col_unidad = st.columns([2, 2, 2])
    p0 = col_p0.number_input("Amplitud p₀ [N]", value=1600.0, format=FORMATO_ENTRADA,
                             key="arm_p0")
    valor_frec = col_frec.number_input("Frecuencia de excitación", value=3.0,
                                       min_value=1e-9, format=FORMATO_ENTRADA, key="arm_w")
    unidad_frec = col_unidad.selectbox("Unidad", ["rad/s", "Hz", "rpm"],
                                       key="arm_wu")

    omega = {"rad/s": lambda v: v,
             "Hz": hz_a_rad_s,
             "rpm": rpm_a_rad_s}[unidad_frec](valor_frec)

    col_ciclos, col_res = st.columns(2)
    ciclos = col_ciclos.number_input("Periodos naturales a simular", value=15,
                                     min_value=1, step=1, key="arm_ciclos")
    puntos = col_res.number_input("Puntos por periodo", value=200, min_value=20,
                                  step=20, key="arm_res")

    beta = omega / s.omega_n
    carga = CargaArmonica(p0=p0, omega=omega)
    t = vector_tiempo(ciclos * s.T_n, s.T_n / puntos)
    r = resolver(s, carga, t_final=t[-1], dt=t[1] - t[0])
    permanente = respuesta_permanente_armonica(s, carga, t)

    factor = float(Rd(beta, s.zeta))
    u_estatico = p0 / s.rigidez
    fase = float(angulo_fase(beta, s.zeta))

    fila_de_resultados([
        ("β = ω/ωₙ", beta, ""),
        ("R_d", factor, ""),
        ("u estático", u_estatico, "m"),
        ("u permanente", u_estatico * factor, "m"),
        ("Ángulo de fase φ", math.degrees(fase), "°"),
    ])

    _diagnostico(beta, s.zeta, s.omega_n, omega)

    figura([(t, r.p, "p(t)")], "Tiempo t [s]", "Carga p [N]",
           clave="graf_arm_carga")
    figura([(t, r.u, "u(t) total (numérica)"),
            (t, permanente.u, "u(t) permanente (analítica)")],
           "Tiempo t [s]", "Desplazamiento u [m]", clave="graf_arm_resp")

    # Verificación: la amplitud numérica del último tramo debe coincidir con la
    # analítica una vez extinguido el transitorio.
    ultimo = t >= t[-1] - 2 * s.T_n
    u_num = float(np.max(np.abs(r.u[ultimo])))
    u_ana = u_estatico * factor
    error = abs(u_num - u_ana) / u_ana * 100 if u_ana else float("nan")
    st.markdown("**Verificación contra la solución analítica**")
    st.table([{
        "Cantidad": "Amplitud en estado estacionario |u| [m]",
        "Numérica (Newmark)": f"{u_num:.6g}",
        "Analítica": f"{u_ana:.6g}",
        "Error relativo": f"{error:.3g} %",
    }])
    if error > 5:
        st.warning("El error supera el 5 %: probablemente el transitorio aún no "
                   "se extingue. Aumente los periodos simulados o el ζ.")

    st.divider()
    _consulta_puntual(t, r.u)


def _diagnostico(beta: float, zeta: float, wn: float, omega: float) -> None:
    if abs(beta - 1) < 0.02 and zeta < 0.01:
        st.error(
            "**Resonancia** (β ≈ 1 con ζ ≈ 0): sin amortiguamiento la amplitud "
            "crece linealmente con el tiempo y no existe estado estacionario. "
            "La 'amplitud permanente' de arriba no tiene sentido físico aquí.")
    elif zeta < 0.01 and abs(beta - 1) < 0.2:
        periodo_batido = 2 * math.pi / abs(wn - omega)
        st.info(
            f"**Batido**: β = {beta:.3f} está cerca de 1 con ζ muy bajo. El "
            f"periodo de batido es ≈ {periodo_batido:.3g} s; simule al menos ese "
            "tiempo para verlo completo.")
    elif beta > math.sqrt(2):
        st.success(f"β = {beta:.3f} > √2: zona de aislamiento, la respuesta es "
                   "menor que el desplazamiento estático.")


def _consulta_puntual(t, u) -> None:
    st.markdown("**Consultar u en un instante**")
    izquierda, derecha = st.columns([2, 3])
    instante = izquierda.number_input("t [s]", value=float(t[-1] / 2),
                                      format=FORMATO_ENTRADA, key="arm_query",
                                      min_value=float(t[0]), max_value=float(t[-1]))
    derecha.metric(f"u(t = {instante:.4f} s)",
                   f"{np.interp(instante, t, u):.6g} m")
