"""
Pestaña «Carga impulsiva»: pulsos de corta duración.

Además de la respuesta numérica se contrasta contra la aproximación
impulso–cantidad de movimiento, u_max ≈ I/(m·ωₙ), que solo vale cuando el pulso
es corto frente al periodo natural. Ver el error crecer con t_d/Tₙ es la mejor
forma de entender el límite de esa aproximación.
"""

from __future__ import annotations

import numpy as np
import streamlit as st

from dinamica import (PulsoExponencial, PulsoRectangular, PulsoSemiseno,
                      PulsoTriangular, resolver)

from ..formato import FORMATO_ENTRADA
from ..estado import Proyecto
from ..widgets import fila_de_resultados, figura

FORMAS = {
    "rectangular": ("Rectangular", lambda p0, td: PulsoRectangular(p0, td)),
    "triangular": ("Triangular decreciente",
                   lambda p0, td: PulsoTriangular(p0, td, tipo="decreciente")),
    "semiseno": ("Medio seno", lambda p0, td: PulsoSemiseno(p0, td)),
    "exponencial": ("Exponencial (Friedlander)",
                    lambda p0, td: PulsoExponencial(p0, td)),
}

# Área bajo el pulso, como fracción de p0*td, para el impulso total.
FRACCION_IMPULSO = {"rectangular": 1.0, "triangular": 0.5,
                    "semiseno": 2 / np.pi, "exponencial": None}


def dibujar(proyecto: Proyecto) -> None:
    if proyecto.problemas():
        st.warning("Complete la definición del sistema en la barra lateral.")
        return

    s = proyecto.sistema()
    st.subheader("Carga impulsiva")

    forma = st.radio("Forma del pulso", list(FORMAS),
                     format_func=lambda f: FORMAS[f][0],
                     horizontal=True, key="imp_forma")

    col_p0, col_td, col_ciclos = st.columns(3)
    p0 = col_p0.number_input("Amplitud p₀ [N]", value=150_000.0, format=FORMATO_ENTRADA,
                             key="imp_p0")
    td = col_td.number_input("Duración t_d [s]", value=0.05, min_value=1e-6,
                             format=FORMATO_ENTRADA, key="imp_td")
    ciclos = col_ciclos.number_input("Ciclos libres tras el pulso", value=6,
                                     min_value=1, step=1, key="imp_ciclos")

    carga = FORMAS[forma][1](p0, td)
    t_final = td + ciclos * s.T_n
    dt = min(s.T_n / 200, td / 60)
    r = resolver(s, carga, t_final=t_final, dt=dt)

    # Impulso real: se integra el pulso numéricamente, así vale para cualquier forma.
    impulso = float(np.trapezoid(r.p, r.t)) if hasattr(np, "trapezoid") \
        else float(np.trapz(r.p, r.t))
    u_aprox = impulso / (s.masa * s.omega_n)
    relacion = td / s.T_n

    fila_de_resultados([
        ("Impulso I = ∫p dt", impulso, "N·s"),
        ("t_d / Tₙ", relacion, ""),
        ("|u|máx numérico", r.u_max, "m"),
        ("u máx aproximado", u_aprox, "m"),
        ("Ocurre en t", r.t_u_max, "s"),
    ])

    figura([(r.t, r.p, "p(t)")], "Tiempo t [s]", "Carga p [N]",
           clave="graf_imp_carga")
    figura([(r.t, r.u, "u(t)")], "Tiempo t [s]", "Desplazamiento u [m]",
           clave="graf_imp_resp")

    error = abs(r.u_max - u_aprox) / u_aprox * 100 if u_aprox else float("nan")
    st.markdown("**Verificación contra impulso–cantidad de movimiento**")
    st.table([{
        "Cantidad": "Desplazamiento máximo |u| [m]",
        "Numérica (Newmark)": f"{r.u_max:.6g}",
        "Aproximación I/(m·ωₙ)": f"{u_aprox:.6g}",
        "Error relativo": f"{error:.3g} %",
    }])

    if relacion < 0.1:
        st.success(
            f"t_d/Tₙ = {relacion:.4g} ≪ 1: el pulso termina antes de que la "
            "estructura alcance a responder, así que la aproximación de impulso "
            "es representativa.")
    else:
        st.warning(
            f"t_d/Tₙ = {relacion:.4g} no es pequeño frente a 1: la estructura "
            "responde DURANTE el pulso y la aproximación de impulso pierde "
            "validez. Use la solución numérica.")

    st.divider()
    st.markdown("**Consultar u en un instante**")
    izquierda, derecha = st.columns([2, 3])
    instante = izquierda.number_input(
        "t [s]", value=float(r.t[-1] / 2), format=FORMATO_ENTRADA, key="imp_query",
        min_value=float(r.t[0]), max_value=float(r.t[-1]))
    derecha.metric(f"u(t = {instante:.4f} s)",
                   f"{np.interp(instante, r.t, r.u):.6g} m")
