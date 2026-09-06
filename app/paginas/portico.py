"""
Pestaña «Pórtico → K»: constructor de la rigidez lateral equivalente.

Idealización de edificio de cortante: dentro de cada nivel las columnas y
riostras trabajan en PARALELO; los niveles se combinan en SERIE.

La sección de una columna puede ser numérica (inercia o b×h conocidas) o
SIMBÓLICA: marcando b y/o h como coeficiente de la incógnita ``x``, la rigidez
queda como polinomio en x y se puede despejar la dimensión que produce una
rigidez objetivo. Es lo que pide el problema clásico de "sección mínima".
"""

from __future__ import annotations

import streamlit as st

from dinamica import formatear_polinomio, resolver_x_para_rigidez

from ..estado import (CONDICIONES_ETIQUETA, UNIDADES_AREA, UNIDADES_E,
                      UNIDADES_I, UNIDADES_LONGITUD, Columna, Nivel, Proyecto,
                      Riostra)
from ..widgets import campo_con_unidad, fila_de_resultados, lista_editable


def _usar_como_rigidez(proyecto: Proyecto) -> None:
    """Pasa la rigidez del sistema a modo «pórtico», modelo y widget a la vez."""
    proyecto.rigidez_modo = "portico"
    st.session_state["rig_modo"] = "portico"


def aplicar_x(proyecto: Proyecto, K_objetivo: float, clave_mensaje: str,
              clave_widget: str = "portico_x") -> None:
    """Despeja x para ``K_objetivo`` y lo deja aplicado en el modelo y el widget.

    Se usa como callback de ``on_click`` desde esta pestaña y también desde las
    de Amplificación y Transmisibilidad: los callbacks son el único punto donde
    Streamlit permite escribir la clave de un widget ya existente.
    """
    try:
        x, procedimiento = resolver_x_para_rigidez(proyecto.polinomios(),
                                                   K_objetivo)
    except ValueError as exc:
        st.session_state[clave_mensaje] = ("error", str(exc))
        return
    proyecto.x_actual = x
    st.session_state[clave_widget] = x
    st.session_state[clave_mensaje] = ("ok", x, procedimiento)


def mostrar_mensaje_x(clave_mensaje: str) -> None:
    """Muestra el resultado del último despeje de x, si lo hubo."""
    mensaje = st.session_state.get(clave_mensaje)
    if not mensaje:
        return
    if mensaje[0] == "error":
        st.error(mensaje[1])
    else:
        _, x, procedimiento = mensaje
        st.success(f"**x = {x:.6g} m = {x * 100:.4g} cm**")
        st.caption(procedimiento)


def dibujar(proyecto: Proyecto) -> None:
    st.subheader("Rigidez lateral equivalente de un pórtico")
    st.caption(
        "Hipótesis de edificio de cortante: vigas infinitamente rígidas a "
        "flexión (los nudos no rotan) y columnas axialmente inextensibles, de "
        "modo que cada columna es un resorte lateral puro. Dentro de un nivel "
        "los elementos van en **paralelo**; los niveles, en **serie**.")

    lista_editable(
        proyecto.niveles,
        _render_nivel,
        clave="nivel",
        etiqueta_nuevo="Agregar nivel",
        crear_nuevo=lambda: Nivel(nombre=f"Nivel {len(proyecto.niveles) + 1}"),
        titulo=lambda nivel, i: f"{nivel.nombre}",
        minimo=1)

    st.divider()
    _resultado(proyecto)


# ---------------------------------------------------------------------------
def _render_nivel(nivel: Nivel, clave: str) -> None:
    try:
        st.caption(f"K de este piso: **{nivel.expresion()} N/m**")
    except ValueError as exc:
        st.warning(str(exc))

    st.markdown("**Columnas**")
    lista_editable(
        nivel.columnas, _render_columna,
        clave=f"{clave}_col",
        etiqueta_nuevo="Agregar columna",
        crear_nuevo=lambda: Columna(nombre=f"Columna {len(nivel.columnas) + 1}"),
        titulo=lambda c, i: f"{c.nombre}",
        subtitulo=lambda c: c.descripcion(),
        expandido=False)

    st.markdown("**Riostras (diagonales)**")
    if not nivel.riostras:
        st.caption("Sin riostras en este nivel.")
    lista_editable(
        nivel.riostras, _render_riostra,
        clave=f"{clave}_rio",
        etiqueta_nuevo="Agregar riostra",
        crear_nuevo=lambda: Riostra(nombre=f"Riostra {len(nivel.riostras) + 1}"),
        titulo=lambda r, i: f"{r.nombre}",
        subtitulo=lambda r: r.descripcion(),
        expandido=False)


def _render_columna(col: Columna, clave: str) -> None:
    col.n = int(st.number_input(
        "Número de columnas iguales", value=int(col.n), min_value=1, step=1,
        key=f"{clave}_n", help="Trabajan en paralelo: la rigidez se multiplica."))

    col.E, col.E_unidad = campo_con_unidad(
        "Módulo de elasticidad E", col.E, col.E_unidad, UNIDADES_E,
        f"{clave}_E", formato="%.4f")
    col.H, col.H_unidad = campo_con_unidad(
        "Altura libre H", col.H, col.H_unidad, UNIDADES_LONGITUD,
        f"{clave}_H", formato="%.4f", minimo=1e-9)

    condiciones = list(CONDICIONES_ETIQUETA)
    col.condicion = st.selectbox(
        "Condición de apoyo", condiciones,
        index=condiciones.index(col.condicion),
        format_func=lambda c: CONDICIONES_ETIQUETA[c], key=f"{clave}_cond")

    col.modo_seccion = st.radio(
        "¿Cómo se define la sección?", ["I", "bh"],
        format_func=lambda m: {"I": "Inercia I directa",
                               "bh": "Rectangular b×h  (I = b·h³/12)"}[m],
        index=["I", "bh"].index(col.modo_seccion),
        key=f"{clave}_modo", horizontal=True)

    if col.modo_seccion == "I":
        col.I, col.I_unidad = campo_con_unidad(
            "Inercia I", col.I, col.I_unidad, UNIDADES_I, f"{clave}_I",
            formato="%.5f", minimo=1e-12)
    else:
        izquierda, derecha = st.columns(2)
        with izquierda:
            col.b = st.number_input("b (ancho)", value=float(col.b),
                                    min_value=1e-9, format="%.5f", key=f"{clave}_b")
            col.b_simbolica = st.checkbox(
                "b es coeficiente de x", value=col.b_simbolica, key=f"{clave}_bs",
                help="Marcado, el valor multiplica a la incógnita: b = valor·x")
        with derecha:
            col.h = st.number_input("h (peralte)", value=float(col.h),
                                    min_value=1e-9, format="%.5f", key=f"{clave}_h")
            col.h_simbolica = st.checkbox(
                "h es coeficiente de x", value=col.h_simbolica, key=f"{clave}_hs")
        col.bh_unidad = st.selectbox(
            "Unidad de b y h", UNIDADES_LONGITUD,
            index=UNIDADES_LONGITUD.index(col.bh_unidad), key=f"{clave}_bhu")

        if col.b_simbolica and col.h_simbolica:
            st.info("Con **b y h simbólicas**, I = b·h³/12 queda de **grado 4** "
                    "en x (no de grado 2). Para una columna cuadrada de lado x, "
                    "escriba b = h = 1.")

    try:
        st.caption(f"Aporte: **{formatear_polinomio(col.polinomio())} N/m**")
    except ValueError as exc:
        st.error(str(exc))


def _render_riostra(rio: Riostra, clave: str) -> None:
    rio.n = int(st.number_input("Número de riostras iguales", value=int(rio.n),
                                min_value=1, step=1, key=f"{clave}_n"))
    rio.A, rio.A_unidad = campo_con_unidad(
        "Área A", rio.A, rio.A_unidad, UNIDADES_AREA, f"{clave}_A",
        formato="%.5f", minimo=1e-12)
    rio.E, rio.E_unidad = campo_con_unidad(
        "Módulo E", rio.E, rio.E_unidad, UNIDADES_E, f"{clave}_E", formato="%.4f")

    izquierda, derecha = st.columns(2)
    rio.L_h = izquierda.number_input("Proyección horizontal L_h", value=float(rio.L_h),
                                     min_value=1e-9, format="%.4f", key=f"{clave}_Lh")
    rio.L_v = derecha.number_input("Proyección vertical L_v", value=float(rio.L_v),
                                   min_value=1e-9, format="%.4f", key=f"{clave}_Lv")
    rio.L_unidad = st.selectbox("Unidad de L_h y L_v", UNIDADES_LONGITUD,
                                index=UNIDADES_LONGITUD.index(rio.L_unidad),
                                key=f"{clave}_Lu")
    st.caption("L_r = √(L_h² + L_v²);  k = (A·E/L_r)·cos²θ,  cos θ = L_h/L_r")
    try:
        st.caption(f"Aporte: **{formatear_polinomio(rio.polinomio())} N/m**")
    except ValueError as exc:
        st.error(str(exc))


# ---------------------------------------------------------------------------
def _resultado(proyecto: Proyecto) -> None:
    st.subheader("Rigidez equivalente K")

    try:
        polinomios = proyecto.polinomios()
    except ValueError as exc:
        st.error(str(exc))
        return

    simbolico = proyecto.es_simbolico()

    tabla = [{"Nivel": nivel.nombre, "K de piso [N/m]": formatear_polinomio(poli)}
             for nivel, poli in zip(proyecto.niveles, polinomios)]
    st.table(tabla)

    if simbolico:
        st.info("Hay secciones en función de **x**. Elija un valor de x para "
                "evaluar K, o despeje la x que produce una rigidez objetivo.")
        st.session_state.setdefault("portico_x", float(proyecto.x_actual))
        proyecto.x_actual = st.number_input(
            "Valor de x [m]", min_value=1e-9, format="%.5f", key="portico_x")

    try:
        K = proyecto.rigidez_portico()
    except ValueError as exc:
        st.error(str(exc))
        return

    fila_de_resultados([
        ("K equivalente", K, "N/m"),
        ("K equivalente", K / 1e3, "kN/m"),
        ("Niveles en serie", len(proyecto.niveles), ""),
    ])

    if len(proyecto.niveles) == 2:
        st.caption("Con dos niveles en serie: K = (K₁·K₂)/(K₁+K₂)")

    if proyecto.rigidez_modo != "portico":
        st.button("Usar este K como rigidez del sistema", type="primary",
                  key="portico_usar_k", on_click=_usar_como_rigidez,
                  args=(proyecto,))
    else:
        st.success("Este K es el que está alimentando todas las demás pestañas.")

    if simbolico:
        st.divider()
        _despejar_x(proyecto)


def _despejar_x(proyecto: Proyecto) -> None:
    st.markdown("**Despejar x para una rigidez objetivo**")
    izquierda, derecha = st.columns([2, 1])
    objetivo = izquierda.number_input(
        "K objetivo", value=float(proyecto.rigidez_portico()), min_value=1e-9,
        format="%.4f", key="portico_Kobj")
    unidad = derecha.selectbox("Unidad", ["N/m", "kN/m"], key="portico_Kobj_u")

    K_SI = objetivo * (1e3 if unidad == "kN/m" else 1.0)
    st.button("Calcular x", key="portico_resolver", on_click=aplicar_x,
              args=(proyecto, K_SI, "portico_msg"))
    mostrar_mensaje_x("portico_msg")
