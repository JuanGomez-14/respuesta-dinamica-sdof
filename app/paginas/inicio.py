"""
Portada: orienta según lo que el ejercicio pide hallar.

No es un asistente que encierre al usuario — las pestañas se navegan libremente.
Es solo un índice por objetivo, porque un enunciado rara vez dice "esto es un
problema de transmisibilidad": dice "qué dimensión deben tener las columnas
para que solo se transmita el 30 % de la fuerza".
"""

from __future__ import annotations

import streamlit as st

from ..estado import Proyecto

GUIA = [
    ("Tengo la geometría del pórtico y necesito su rigidez K",
     "Pórtico → K",
     "Arme los niveles con sus columnas y riostras. Si la dimensión de la "
     "sección es la incógnita, márquela como coeficiente de x."),
    ("Me dan una tabla del ensayo (t, u) y piden Tₙ y ζ",
     "Vibración libre",
     "Suba el Excel o pegue los datos: se detectan los picos y se calcula el "
     "periodo y el amortiguamiento por decremento logarítmico."),
    ("Hay una máquina o carga que oscila con frecuencia conocida",
     "Carga armónica",
     "Respuesta total y permanente, R_d y ángulo de fase."),
    ("Hay un golpe, una explosión o un impacto breve",
     "Carga impulsiva",
     "Pulsos rectangular, triangular, medio seno o exponencial, contrastados "
     "con la aproximación de impulso."),
    ("Tengo un registro sísmico o una señal cualquiera",
     "Excitación arbitraria",
     "Integración por Newmark de la señal, y espectro de respuesta del registro."),
    ("Piden que el desplazamiento dinámico no supere N veces el estático",
     "Amplificación R_d",
     "R_d objetivo = N. De los dos β resultantes, el mayor da la sección mínima."),
    ("Piden aislar: que solo se transmita un % de la fuerza o la aceleración",
     "Transmisibilidad",
     "TR objetivo = ese porcentaje. Aislar siempre exige β > √2."),
    ("Necesito estimar ζ de una curva de respuesta medida",
     "Barra lateral → Calcular ζ",
     "Método del ancho de banda de media potencia, dentro del panel de "
     "amortiguamiento."),
]


def dibujar(proyecto: Proyecto) -> None:
    st.subheader("¿Qué necesita hallar?")
    st.caption("Un índice por objetivo. Las pestañas de arriba se pueden usar "
               "en cualquier orden; esto solo indica por dónde empezar.")

    for pregunta, destino, explicacion in GUIA:
        with st.container(border=True):
            st.markdown(f"**{pregunta}**")
            st.markdown(f"→ pestaña **{destino}**")
            st.caption(explicacion)

    st.divider()
    st.markdown("### Cómo funciona esta herramienta")
    st.markdown(
        """
La **barra lateral** define el sistema (masa, rigidez, amortiguamiento) y
alimenta **todas** las pestañas a la vez. No hay que copiar valores de un lado a
otro: si cambia la altura de una columna en *Pórtico → K* y tiene la rigidez en
modo «desde el pórtico», ωₙ, las curvas y las respuestas se actualizan solas.

Cada valor derivado muestra debajo **cómo se obtuvo**, con la expresión
evaluada, para que pueda transcribirlo al desarrollo escrito del ejercicio.

Las unidades se eligen campo por campo (GPa, cm⁴, kN/m…). Internamente todo se
convierte a SI coherente —kg, N/m, N, m, s— así que no hay factores de 1000
escondidos.
""")

    if proyecto.problemas():
        st.warning("El sistema todavía no está bien definido: "
                   + " ".join(proyecto.problemas()))
    else:
        s = proyecto.sistema()
        st.success(
            f"Sistema actual: m = {s.masa:,.4g} kg · k = {s.rigidez:,.4g} N/m · "
            f"ζ = {s.zeta * 100:.4g} %  →  Tₙ = {s.T_n:.4f} s, "
            f"ωₙ = {s.omega_n:.4f} rad/s")
