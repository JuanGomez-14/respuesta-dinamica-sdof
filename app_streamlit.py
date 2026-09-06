"""
Plataforma de cálculo de respuesta dinámica — interfaz gráfica.

Punto de entrada delgado: crea el proyecto compartido, dibuja la barra lateral
y despacha cada pestaña. Toda la lógica vive en el paquete ``app``.

Ejecución:
    streamlit run app_streamlit.py

o, más fácil, un doble clic en «Abrir herramienta.command» (macOS) o
«Abrir herramienta.bat» (Windows), que se encarga de instalar lo necesario.
"""

from __future__ import annotations

import streamlit as st

from app.estado import Proyecto, proyecto_por_defecto
from app.paginas import (amplificacion, arbitraria, armonica, impulsiva,
                         inicio, libre, parametrico, portico, sistema,
                         transmisibilidad)

st.set_page_config(page_title="Respuesta dinámica SDOF · UdeM",
                   page_icon="📈", layout="wide")

PESTANAS = [
    ("🧭 Inicio", inicio),
    ("🏛 Pórtico → K", portico),
    ("🔔 Vibración libre", libre),
    ("🔁 Carga armónica", armonica),
    ("💥 Carga impulsiva", impulsiva),
    ("📈 Excitación arbitraria", arbitraria),
    ("📊 Amplificación R_d", amplificacion),
    ("🛡 Transmisibilidad", transmisibilidad),
    ("🎛 Paramétrico", parametrico),
]


def obtener_proyecto() -> Proyecto:
    """El proyecto compartido, creado una sola vez por sesión."""
    if "proyecto" not in st.session_state:
        st.session_state["proyecto"] = proyecto_por_defecto()
    return st.session_state["proyecto"]


def main() -> None:
    st.title("Laboratorio computacional de respuesta dinámica")
    st.caption("Universidad de Medellín · Ingeniería Civil · Dinámica de "
               "Estructuras — sistemas de un grado de libertad. "
               "Todos los cálculos internos en SI coherente (kg, N/m, N, m, s).")

    proyecto = obtener_proyecto()
    sistema.dibujar(proyecto)

    for pestana, modulo in zip(st.tabs([nombre for nombre, _ in PESTANAS]),
                               [m for _, m in PESTANAS]):
        with pestana:
            modulo.dibujar(proyecto)


if __name__ == "__main__":
    main()
