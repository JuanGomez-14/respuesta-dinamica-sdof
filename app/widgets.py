"""
Widgets reutilizables de la interfaz.

La pieza importante es :func:`lista_editable`: un mismo componente sirve para
niveles, columnas y riostras, y es lo que da la editabilidad (renombrar,
reordenar, duplicar, eliminar) sin repetir código en cada página.

Sobre reordenar: Streamlit no ofrece arrastrar y soltar de forma nativa, así que
se usan botones ↑↓. Cubre el caso real (mover un nivel un puesto) sin agregar
dependencias de terceros.
"""

from __future__ import annotations

import copy
from typing import Callable

import matplotlib.pyplot as plt
import streamlit as st

from .formato import FORMATO_ENTRADA, numero
from .estado import Magnitud

__all__ = ["campo_con_unidad", "lista_editable", "tarjeta_resultado",
           "fila_de_resultados", "mostrar_procedencia", "figura", "COLORES"]

COLORES = ["#C8102E", "#12263A", "#00857C", "#E07A00", "#5A4FCF"]


def campo_con_unidad(etiqueta: str, valor: float, unidad: str,
                     unidades: list[str], clave: str, *,
                     ayuda: str | None = None,
                     formato: str = FORMATO_ENTRADA,
                     minimo: float | None = 0.0) -> tuple[float, str]:
    """Número + selector de unidad, uno al lado del otro.

    Devuelve ``(valor, unidad)`` tal como los escribió el usuario. **La
    conversión a SI no ocurre aquí**, sino al derivar el sistema en
    :mod:`app.estado`, para que exista un solo lugar donde se convierte.
    """
    col_valor, col_unidad = st.columns([2, 1])
    nuevo_valor = col_valor.number_input(
        etiqueta, value=float(valor), key=f"{clave}_v", help=ayuda,
        format=formato, min_value=minimo, step=None)
    indice = unidades.index(unidad) if unidad in unidades else 0
    nueva_unidad = col_unidad.selectbox(
        "Unidad", unidades, index=indice, key=f"{clave}_u",
        label_visibility="hidden")
    return float(nuevo_valor), nueva_unidad


def _mover(lista: list, desde: int, hacia: int) -> None:
    lista.insert(hacia, lista.pop(desde))


def lista_editable(elementos: list, render: Callable[[object, str], None], *,
                   clave: str,
                   etiqueta_nuevo: str = "Agregar",
                   crear_nuevo: Callable[[], object] | None = None,
                   titulo: Callable[[object, int], str] | None = None,
                   subtitulo: Callable[[object], str] | None = None,
                   minimo: int = 0,
                   expandido: bool = True) -> None:
    """Lista de elementos con renombrar, reordenar, duplicar y eliminar.

    Parámetros
    ----------
    elementos : la lista a editar (se modifica en el sitio)
    render    : ``render(elemento, clave)`` dibuja los campos propios del elemento
    crear_nuevo : fábrica del elemento que agrega el botón "Agregar"
    titulo    : ``titulo(elemento, indice)`` -> encabezado del expander
    subtitulo : ``subtitulo(elemento)`` -> resumen de una línea bajo el encabezado
    minimo    : número mínimo de elementos; por debajo se desactiva "Eliminar"
    """
    for indice, elemento in enumerate(elementos):
        encabezado = (titulo(elemento, indice) if titulo
                      else getattr(elemento, "nombre", f"Elemento {indice + 1}"))
        clave_elemento = f"{clave}_{getattr(elemento, 'id', indice)}"

        with st.expander(encabezado, expanded=expandido):
            if hasattr(elemento, "nombre"):
                elemento.nombre = st.text_input(
                    "Nombre", value=elemento.nombre, key=f"{clave_elemento}_nombre")
            if subtitulo:
                st.caption(subtitulo(elemento))

            render(elemento, clave_elemento)

            st.markdown("")
            arriba, abajo, duplicar, eliminar = st.columns(4)
            if arriba.button("↑ Subir", key=f"{clave_elemento}_arriba",
                             disabled=indice == 0, width="stretch"):
                _mover(elementos, indice, indice - 1)
                st.rerun()
            if abajo.button("↓ Bajar", key=f"{clave_elemento}_abajo",
                            disabled=indice == len(elementos) - 1,
                            width="stretch"):
                _mover(elementos, indice, indice + 1)
                st.rerun()
            if duplicar.button("⧉ Duplicar", key=f"{clave_elemento}_dup",
                               width="stretch"):
                copia = copy.deepcopy(elemento)
                if hasattr(copia, "id"):
                    from .estado import _nuevo_id
                    copia.id = _nuevo_id()
                if hasattr(copia, "nombre"):
                    copia.nombre = f"{copia.nombre} (copia)"
                elementos.insert(indice + 1, copia)
                st.rerun()
            if eliminar.button("🗑 Eliminar", key=f"{clave_elemento}_del",
                               disabled=len(elementos) <= minimo,
                               width="stretch"):
                elementos.pop(indice)
                st.rerun()

    if crear_nuevo is not None:
        if st.button(f"➕ {etiqueta_nuevo}", key=f"{clave}_nuevo"):
            elementos.append(crear_nuevo())
            st.rerun()


def tarjeta_resultado(etiqueta: str, valor, unidad: str = "",
                      ayuda: str | None = None) -> None:
    """Una métrica destacada.

    """
    texto = valor if isinstance(valor, str) else numero(valor)
    st.metric(etiqueta, f"{texto} {unidad}".strip(), help=ayuda)


def fila_de_resultados(items: list[tuple]) -> None:
    """Fila de métricas: lista de ``(etiqueta, valor, unidad)``."""
    if not items:
        return
    for columna, item in zip(st.columns(len(items)), items):
        etiqueta, valor, *resto = item
        with columna:
            tarjeta_resultado(etiqueta, valor, resto[0] if resto else "")


def mostrar_procedencia(magnitud: Magnitud, etiqueta: str = "") -> None:
    """Muestra el rastro de cómo se obtuvo un valor, para copiarlo al taller."""
    if not magnitud.detalle:
        return
    prefijo = f"**{etiqueta}** · " if etiqueta else ""
    st.caption(f"{prefijo}{magnitud.detalle}")


def _restablecer_ejes(clave_x: str, x: str, clave_y: str, y: str) -> None:
    """Devuelve los ejes a su nombre original.

    Como callback de ``on_click``, no en el cuerpo del script: Streamlit solo
    deja escribir la clave de un widget antes de que este se instancie, y los
    callbacks corren justo ahí, al principio del siguiente rerun.
    """
    st.session_state[clave_x] = x
    st.session_state[clave_y] = y


def _nombres_de_ejes(clave: str, xlabel: str, ylabel: str) -> tuple[str, str]:
    """Controles para renombrar los ejes, junto a la propia gráfica.

    Los nombres viven en el estado del widget: la clave del ``text_input`` ES
    el almacenamiento, así que el valor persiste entre reruns sin necesidad de
    sincronizar nada con el modelo.
    """
    clave_x, clave_y = f"{clave}_ejex", f"{clave}_ejey"
    st.session_state.setdefault(clave_x, xlabel)
    st.session_state.setdefault(clave_y, ylabel)

    with st.popover("✏️ Nombres de los ejes"):
        st.text_input("Eje horizontal", key=clave_x)
        st.text_input("Eje vertical", key=clave_y)
        st.button("Restablecer", key=f"{clave}_ejes_reset",
                  on_click=_restablecer_ejes,
                  args=(clave_x, xlabel, clave_y, ylabel))

    return st.session_state[clave_x], st.session_state[clave_y]


def figura(series: list[tuple], xlabel: str, ylabel: str, *, clave: str,
           titulo: str = "", logx: bool = False, logy: bool = False,
           vertical: float | None = None,
           puntos: list[tuple] | None = None):
    """Gráfica de líneas con el estilo de la plataforma.

    ``series`` es una lista de ``(x, y, etiqueta)``; ``puntos`` una lista de
    ``(x, y, etiqueta)`` que se dibujan como marcadores destacados.

    ``clave`` identifica la gráfica y debe ser única en toda la aplicación:
    es la que separa los nombres de ejes de una gráfica de los de otra.
    """
    xlabel, ylabel = _nombres_de_ejes(clave, xlabel, ylabel)

    fig, ax = plt.subplots(figsize=(9, 3.6))
    for indice, (x, y, etiqueta) in enumerate(series):
        ax.plot(x, y, label=etiqueta, lw=1.6,
                color=COLORES[indice % len(COLORES)])
    for indice, (x, y, etiqueta) in enumerate(puntos or []):
        ax.plot(x, y, "o", ms=9, label=etiqueta,
                color=COLORES[(indice + 3) % len(COLORES)], zorder=5)
    if vertical is not None:
        ax.axvline(vertical, ls="--", lw=1.2, color="#888",
                   label=f"β = {vertical:.3f}")
    if logx:
        ax.set_xscale("log")
    if logy:
        ax.set_yscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if titulo:
        ax.set_title(titulo)
    ax.grid(alpha=0.3)
    if len(series) + len(puntos or []) > 1 or vertical is not None:
        ax.legend(fontsize=8)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)
