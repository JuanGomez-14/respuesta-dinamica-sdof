"""
Pestaña «Excitación arbitraria»: una señal cualquiera, pegada o leída de un
archivo, integrada por Newmark.

La señal puede ser una fuerza aplicada p(t) o una aceleración del terreno üg(t).
En el segundo caso la fuerza efectiva es p_ef = −m·üg y el desplazamiento
calculado es RELATIVO a la base, que es lo que produce esfuerzos en la
estructura.
"""

from __future__ import annotations

import io

import numpy as np
import streamlit as st

from dinamica import (CargaArbitraria, ExcitacionBase, espectro_respuesta,
                      generar_registro_sintetico, leer_csv,
                      periodos_logaritmicos, resolver, resolver_base)
from dinamica.io_senales import leer_excel

from ..estado import Proyecto
from ..widgets import fila_de_resultados, figura


def dibujar(proyecto: Proyecto) -> None:
    if proyecto.problemas():
        st.warning("Complete la definición del sistema en la barra lateral.")
        return

    s = proyecto.sistema()
    st.subheader("Excitación arbitraria")

    tipo = st.radio(
        "¿Qué representa la señal?", ["aceleracion", "fuerza"],
        format_func=lambda t: {"aceleracion": "Aceleración del terreno üg(t)",
                               "fuerza": "Fuerza aplicada p(t)"}[t],
        horizontal=True, key="arb_tipo")

    unidad = "m/s2"
    if tipo == "aceleracion":
        unidad = st.selectbox("Unidad de la aceleración",
                              ["m/s2", "g", "gal", "cm/s2"], key="arb_unidad")

    origen = st.radio("Origen de la señal", ["ejemplo", "archivo", "pegar"],
                      format_func=lambda o: {"ejemplo": "Registro de ejemplo",
                                             "archivo": "Subir archivo",
                                             "pegar": "Pegar datos"}[o],
                      horizontal=True, key="arb_origen")

    datos = None
    if origen == "ejemplo":
        datos = _registro_de_ejemplo()
        st.caption("Registro sintético tipo sismo, generado por el motor.")
        unidad = "m/s2"
    elif origen == "archivo":
        archivo = st.file_uploader("Archivo con columnas t, valor",
                                   type=["xlsx", "xls", "csv"], key="arb_file")
        if archivo is not None:
            datos = _leer_archivo(archivo)
    else:
        texto = st.text_area("Pares (t, valor), uno por línea", height=150,
                             placeholder="0.00, 0.000\n0.02, 0.153\n...",
                             key="arb_texto")
        datos = _leer_texto(texto)

    if datos is None:
        return
    t, y = datos

    col_u0, col_v0 = st.columns(2)
    u0 = col_u0.number_input("u₀ [m]", value=0.0, format="%.5f", key="arb_u0")
    v0 = col_v0.number_input("v₀ [m/s]", value=0.0, format="%.5f", key="arb_v0")

    dt = float(t[1] - t[0])
    if not np.allclose(np.diff(t), dt, rtol=0.05):
        st.warning("El paso de tiempo de la señal no es uniforme; se usa el "
                   "intervalo entre los dos primeros puntos para todo el análisis.")

    from dinamica import a_si
    if tipo == "aceleracion":
        ag = np.asarray([a_si(v, unidad) for v in y])
        excitacion = ExcitacionBase(t=np.asarray(t), ag=ag)
        r = resolver_base(s, excitacion, dt=dt, u0=u0, v0=v0)
    else:
        r = resolver(s, CargaArbitraria(np.asarray(t), np.asarray(y)),
                     t_final=float(t[-1]), dt=dt, u0=u0, v0=v0)

    relacion = dt / s.T_n
    fila_de_resultados([
        ("Δt de la señal", dt, "s"),
        ("Δt / Tₙ", relacion, ""),
        ("|u|máx relativo", r.u_max, "m"),
        ("Ocurre en t", r.t_u_max, "s"),
        ("Cortante basal máx", r.cortante_max / 1e3, "kN"),
    ])

    if relacion > 0.1:
        st.warning(f"Δt/Tₙ = {relacion:.3g} es grande. La regla práctica es "
                   "Δt ≤ Tₙ/10, idealmente Tₙ/20. Remuestree la señal para "
                   "ganar precisión.")
    else:
        st.success(f"Δt/Tₙ = {relacion:.3g}: paso adecuado para la integración.")

    etiqueta = "üg(t)" if tipo == "aceleracion" else "p(t)"
    figura([(t, y, etiqueta)], "Tiempo t [s]",
           f"Aceleración [{unidad}]" if tipo == "aceleracion" else "Carga [N]")
    figura([(r.t, r.u, "u(t) relativo")], "Tiempo t [s]", "Desplazamiento u [m]")

    if tipo == "aceleracion":
        st.divider()
        _espectro(excitacion, s)


def _espectro(excitacion, sistema) -> None:
    st.markdown("**Espectro de respuesta del registro**")
    st.caption("Máxima respuesta de una familia de sistemas de 1 GDL con el "
               "mismo ζ, en función de su periodo. La línea vertical marca el "
               "periodo del sistema actual.")
    if not st.checkbox("Calcular espectro (tarda unos segundos)", key="arb_esp"):
        return
    periodos = periodos_logaritmicos(0.05, 3.0, 80)
    espectro = espectro_respuesta(excitacion, zeta=sistema.zeta, periodos=periodos)
    figura([(espectro.periodos, espectro.Sd, "S_d")],
           "Periodo T [s]", "S_d [m]", vertical=sistema.T_n)


# ---------------------------------------------------------------------------
def _leer_archivo(archivo):
    nombre = archivo.name.lower()
    try:
        if nombre.endswith(".csv"):
            return leer_csv(io.StringIO(archivo.getvalue().decode("utf-8-sig")))
        return leer_excel(io.BytesIO(archivo.getvalue()))
    except Exception as exc:
        st.error(f"No se pudo leer el archivo: {exc}")
        return None


def _leer_texto(texto: str):
    if not texto or not texto.strip():
        return None
    t, y = [], []
    for linea in texto.strip().splitlines():
        partes = linea.replace(",", " ").replace(";", " ").split()
        if len(partes) < 2:
            continue
        try:
            t.append(float(partes[0]))
            y.append(float(partes[1]))
        except ValueError:
            continue
    if len(t) < 3:
        st.error("Se necesitan al menos 3 pares (t, valor) numéricos.")
        return None
    return np.asarray(t), np.asarray(y)


@st.cache_data(show_spinner=False)
def _registro_de_ejemplo():
    registro = generar_registro_sintetico()
    return np.asarray(registro.t), np.asarray(registro.ag)
