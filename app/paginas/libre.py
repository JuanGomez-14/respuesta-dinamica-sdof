"""
Pestaña «Vibración libre»: respuesta del sistema soltado desde una posición
inicial, e identificación de Tₙ y ζ a partir de datos medidos.

La segunda mitad es el caso del ensayo de laboratorio: el profesor entrega una
tabla (t, u) y hay que sacar el periodo y el amortiguamiento.
"""

from __future__ import annotations

import io

import numpy as np
import streamlit as st

from dinamica import identificar, leer_csv, vector_tiempo, vibracion_libre
from dinamica.io_senales import leer_excel

from ..estado import Proyecto
from ..widgets import fila_de_resultados, figura


def _usar_periodo(proyecto: Proyecto, T_n: float) -> None:
    """Fija la rigidez a partir del periodo identificado (modelo + widgets)."""
    proyecto.rigidez_modo = "periodo"
    proyecto.periodo_objetivo = T_n
    st.session_state["rig_modo"] = "periodo"
    st.session_state["sb_Tn"] = T_n


def _usar_zeta(proyecto: Proyecto, zeta: float, detalle: str) -> None:
    proyecto.fijar_zeta(zeta, "identificado del ensayo", detalle)
    st.session_state["sb_zeta"] = zeta * 100


def dibujar(proyecto: Proyecto) -> None:
    if proyecto.problemas():
        st.warning("Complete la definición del sistema en la barra lateral.")
        return

    _respuesta(proyecto)
    st.divider()
    _identificacion(proyecto)


# ---------------------------------------------------------------------------
def _respuesta(proyecto: Proyecto) -> None:
    st.subheader("Respuesta en vibración libre")
    s = proyecto.sistema()

    col_u0, col_v0, col_ciclos = st.columns(3)
    u0 = col_u0.number_input("Desplazamiento inicial u₀ [m]", value=0.02,
                             format="%.5f", key="libre_u0")
    v0 = col_v0.number_input("Velocidad inicial v₀ [m/s]", value=0.0,
                             format="%.5f", key="libre_v0")
    ciclos = col_ciclos.number_input("Ciclos a simular", value=10, min_value=1,
                                     step=1, key="libre_ciclos")

    if u0 == 0 and v0 == 0:
        st.info("Con u₀ = 0 y v₀ = 0 el sistema permanece en reposo. "
                "Dele un desplazamiento o una velocidad inicial.")
        return

    t = vector_tiempo(ciclos * s.T_n, s.T_n / 200)
    r = vibracion_libre(s, t, u0=u0, v0=v0)

    fila_de_resultados([
        ("Tₙ", s.T_n, "s"),
        ("T_D (amortiguado)", s.T_D, "s"),
        ("|u|máx", r.u_max, "m"),
        ("Decaimiento por ciclo", f"{np.exp(-2 * np.pi * s.zeta / np.sqrt(1 - s.zeta**2)) * 100:.2f}", "%"),
    ])

    envolvente = u0 and np.exp(-s.zeta * s.omega_n * t) * abs(
        np.hypot(u0, (v0 + s.zeta * s.omega_n * u0) / s.omega_D))
    figura([(t, r.u, "u(t)"),
            (t, envolvente, "envolvente ±"),
            (t, -envolvente, "")],
           "Tiempo t [s]", "Desplazamiento u [m]")


# ---------------------------------------------------------------------------
def _identificacion(proyecto: Proyecto) -> None:
    st.subheader("Identificar Tₙ y ζ desde datos medidos")
    st.caption("Suba la tabla del ensayo (Excel o CSV) o pegue los pares (t, u). "
               "Se detectan los picos, se promedia el periodo entre picos "
               "sucesivos y se calcula ζ por decremento logarítmico.")

    origen = st.radio("Origen de los datos", ["archivo", "pegar", "ejemplo"],
                      format_func=lambda o: {"archivo": "Subir archivo",
                                             "pegar": "Pegar datos",
                                             "ejemplo": "Señal de ejemplo"}[o],
                      horizontal=True, key="iden_origen")

    datos = None
    if origen == "archivo":
        archivo = st.file_uploader("Archivo con columnas t, u",
                                   type=["xlsx", "xls", "csv"], key="iden_file")
        if archivo is not None:
            datos = _leer_archivo(archivo)
    elif origen == "pegar":
        texto = st.text_area("Pares (t, u), uno por línea",
                             placeholder="0.00, 0.0200\n0.02, 0.0185\n...",
                             height=150, key="iden_texto")
        datos = _leer_texto(texto)
    else:
        datos = _senal_de_ejemplo()
        st.caption("Vibración libre sintética con ζ = 4 % y Tₙ = 0.45 s "
                   "(más ruido), para probar la herramienta.")

    if datos is None:
        return
    t, u = datos

    col_min, col_max = st.columns(2)
    t_min = col_min.number_input("t mínimo a analizar [s]", value=float(t[0]),
                                 format="%.4f", key="iden_tmin", min_value=None)
    t_max = col_max.number_input("t máximo a analizar [s]", value=float(t[-1]),
                                 format="%.4f", key="iden_tmax", min_value=None)
    dentro = (t >= t_min) & (t <= t_max)
    if dentro.sum() < 5:
        st.error("Quedan menos de 5 puntos en ese rango de tiempo.")
        return
    t, u = t[dentro], u[dentro]

    try:
        r = identificar(t, u)
    except ValueError as exc:
        st.error(str(exc))
        return

    figura([(t, u, "datos medidos")], "Tiempo t [s]", "u",
           puntos=[([p.t for p in r.picos], [p.u for p in r.picos],
                    f"{len(r.picos)} picos detectados")] if r.picos else None)

    if r.T_n is None:
        st.warning(r.detalle)
        return

    fila_de_resultados([
        ("T_D medido", r.T_D, "s"),
        ("Tₙ identificado", r.T_n, "s"),
        ("fₙ", r.f_n, "Hz"),
        ("ωₙ", r.omega_n, "rad/s"),
        ("ζ identificado", f"{r.zeta * 100:.4g}" if r.zeta else "—", "%"),
    ])
    st.caption(r.detalle)

    if r.picos:
        st.table([{"#": i + 1, "t [s]": f"{p.t:.4f}", "u": f"{p.u:.6g}",
                   "Δt al anterior [s]": (f"{p.t - r.picos[i-1].t:.4f}"
                                          if i else "—")}
                  for i, p in enumerate(r.picos)])

    st.markdown("**Aplicar al sistema**")
    col_t, col_z = st.columns(2)
    col_t.button("Usar Tₙ identificado (fija la rigidez)", width="stretch",
                 key="iden_usar_T", on_click=_usar_periodo,
                 args=(proyecto, r.T_n))
    if r.zeta is not None:
        col_z.button("Usar ζ identificado", width="stretch", key="iden_usar_z",
                     on_click=_usar_zeta, args=(proyecto, r.zeta, r.detalle))


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
    t, u = [], []
    for linea in texto.strip().splitlines():
        partes = linea.replace(",", " ").replace(";", " ").split()
        if len(partes) < 2:
            continue
        try:
            t.append(float(partes[0]))
            u.append(float(partes[1]))
        except ValueError:
            continue  # encabezados y comentarios
    if len(t) < 5:
        st.error("Se necesitan al menos 5 pares (t, u) numéricos.")
        return None
    return np.asarray(t), np.asarray(u)


def _senal_de_ejemplo():
    zeta, Tn = 0.04, 0.45
    wn = 2 * np.pi / Tn
    wd = wn * np.sqrt(1 - zeta ** 2)
    t = np.linspace(0, 4.0, 801)
    u = 0.025 * np.exp(-zeta * wn * t) * np.cos(wd * t)
    u = u + np.random.default_rng(7).normal(0, 2e-5, u.size)
    return t, u
