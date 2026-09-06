"""
Generación de figuras normalizadas.

Todas las figuras incluyen título, identificación de ejes con sus unidades,
leyenda y rejilla, de modo que puedan interpretarse de manera independiente
(requisito 3.3 de la guía del laboratorio).

Las figuras se guardan en ``salidas/figuras`` en formato PNG (200 dpi) y,
opcionalmente, en PDF vectorial.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import matplotlib
matplotlib.use("Agg")            # backend sin ventana (funciona en cualquier equipo)
import matplotlib.pyplot as plt
import numpy as np

from .cargas import Carga, ExcitacionBase
from .espectros import EspectroRespuesta
from .frecuencia import Rd, curva_Rd, curva_TR, curva_fase, transmisibilidad
from .parametrico import ResultadoBarrido
from .solucionadores import Respuesta
from .unidades import G

__all__ = [
    "configurar_estilo", "DIR_FIGURAS", "guardar", "usar_carpeta",
    "graficar_carga", "graficar_historia", "graficar_comparacion",
    "graficar_acelerograma", "graficar_respuesta_sismica",
    "graficar_Rd", "graficar_TR", "graficar_fase",
    "graficar_barrido", "graficar_barridos_multiples", "graficar_espectro",
    "graficar_espectro_choque",
    "graficar_pulso_fases", "graficar_resonancia_y_batido",
    "graficar_convergencia",
]

DIR_FIGURAS = Path("salidas/figuras")

COLORES = ["#C8102E", "#12263A", "#00857C", "#E07A00", "#5A4FCF", "#7A8B99"]


def configurar_estilo() -> None:
    """Estilo gráfico uniforme para todo el laboratorio."""
    plt.rcParams.update({
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.linestyle": ":",
        "legend.framealpha": 0.9,
        "legend.fontsize": 9,
        "lines.linewidth": 1.6,
        "axes.prop_cycle": plt.cycler(color=COLORES),
    })


configurar_estilo()


def usar_carpeta(carpeta: Path | str) -> Path:
    """Cambia la carpeta donde se guardarán las figuras siguientes.

    >>> from dinamica import graficos
    >>> _ = graficos.usar_carpeta("salidas/figuras/caso1")
    """
    global DIR_FIGURAS
    DIR_FIGURAS = Path(carpeta)
    DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    return DIR_FIGURAS


def guardar(fig, nombre: str, carpeta: Path | str | None = None,
            tambien_pdf: bool = False) -> Path:
    """Guarda la figura y devuelve la ruta del PNG generado.

    Si no se indica ``carpeta`` se usa la carpeta activa (``DIR_FIGURAS``,
    modificable con :func:`usar_carpeta`).
    """
    carpeta = Path(carpeta) if carpeta is not None else DIR_FIGURAS
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{nombre}.png"
    fig.savefig(ruta)
    if tambien_pdf:
        fig.savefig(carpeta / f"{nombre}.pdf")
    plt.close(fig)
    return ruta


# ===========================================================================
#  Excitaciones
# ===========================================================================
def graficar_carga(carga: Carga, t: np.ndarray, titulo: str | None = None,
                   nombre_archivo: str | None = None):
    """Grafica la historia de carga p(t) [kN]."""
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.plot(t, carga.muestrear(t) / 1e3, color=COLORES[0])
    ax.set_xlabel("Tiempo t [s]")
    ax.set_ylabel("Carga p(t) [kN]")
    ax.set_title(titulo or f"Excitación: {carga.nombre}")
    ax.axhline(0, color="k", lw=0.6)
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


def graficar_acelerograma(exc: ExcitacionBase, titulo: str | None = None,
                          nombre_archivo: str | None = None):
    """Grafica el acelerograma del terreno con su PGA señalada."""
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.plot(exc.t, exc.ag, color=COLORES[1], lw=1.0)
    i = int(np.argmax(np.abs(exc.ag)))
    ax.plot(exc.t[i], exc.ag[i], "o", color=COLORES[0], ms=5,
            label=f"PGA = {exc.pga:.3f} m/s² ({exc.pga/G:.3f} g)")
    ax.set_xlabel("Tiempo t [s]")
    ax.set_ylabel("Aceleración del terreno $\\ddot{u}_g$ [m/s²]")
    ax.set_title(titulo or f"Excitación en la base: {exc.nombre}")
    ax.legend(loc="upper right")
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


# ===========================================================================
#  Historias de respuesta
# ===========================================================================
def graficar_historia(resp: Respuesta, titulo: str = "Respuesta dinámica",
                      mostrar: Sequence[str] = ("p", "u", "v", "a"),
                      nombre_archivo: str | None = None,
                      marcar_maximo: bool = True):
    """Grafica la carga y las historias de desplazamiento, velocidad y aceleración."""
    paneles = [m for m in mostrar if m != "p" or resp.p is not None]
    n = len(paneles)
    fig, axes = plt.subplots(n, 1, figsize=(8.2, 2.1 * n + 0.8), sharex=True)
    axes = np.atleast_1d(axes)

    for ax, cual in zip(axes, paneles):
        if cual == "p":
            ax.plot(resp.t, resp.p / 1e3, color=COLORES[1])
            ax.set_ylabel("p(t) [kN]")
        elif cual == "u":
            ax.plot(resp.t, resp.u * 1e3, color=COLORES[0])
            ax.set_ylabel("u(t) [mm]")
            if marcar_maximo:
                i = int(np.argmax(np.abs(resp.u)))
                ax.plot(resp.t[i], resp.u[i] * 1e3, "o", color="k", ms=4)
                ax.annotate(f"|u|máx = {resp.u_max*1e3:.2f} mm\n(t = {resp.t[i]:.2f} s)",
                            xy=(resp.t[i], resp.u[i] * 1e3),
                            xytext=(6, 6), textcoords="offset points", fontsize=8)
        elif cual == "v":
            ax.plot(resp.t, resp.v, color=COLORES[2])
            ax.set_ylabel("u'(t) [m/s]")
        elif cual == "a":
            if resp.ag is not None:
                ax.plot(resp.t, resp.aceleracion_absoluta, color=COLORES[3],
                        label="absoluta $\\ddot{u}+\\ddot{u}_g$")
                ax.plot(resp.t, resp.a, color=COLORES[4], lw=1.0, alpha=0.8,
                        label="relativa $\\ddot{u}$")
                ax.legend(loc="upper right", ncol=2)
            else:
                ax.plot(resp.t, resp.a, color=COLORES[3])
            ax.set_ylabel("u''(t) [m/s²]")
        elif cual == "V":
            ax.plot(resp.t, resp.cortante_basal / 1e3, color=COLORES[4])
            ax.set_ylabel("V(t) = k·u [kN]")
        ax.axhline(0, color="k", lw=0.6)

    axes[-1].set_xlabel("Tiempo t [s]")
    s = resp.sistema
    # el subtítulo se reparte en dos líneas para no ensanchar la figura
    axes[0].set_title(f"{titulo}\n{s.nombre}: m = {s.masa:,.0f} kg · k = {s.rigidez:,.0f} N/m\n"
                      f"$T_n$ = {s.T_n:.3f} s · ζ = {s.zeta:.3f} · {resp.metodo}",
                      fontsize=10)
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


def graficar_comparacion(respuestas: Sequence[Respuesta], etiquetas: Sequence[str],
                         titulo: str = "Comparación de respuestas",
                         variable: str = "u", nombre_archivo: str | None = None,
                         estilos: Sequence[str] | None = None):
    """Superpone la misma variable de varias respuestas (comparación/verificación)."""
    fig, ax = plt.subplots(figsize=(8.2, 4.0))
    escala, ylabel = (1e3, "u(t) [mm]") if variable == "u" else (1.0, f"{variable}(t)")
    for i, (r, et) in enumerate(zip(respuestas, etiquetas)):
        y = getattr(r, variable) * escala
        estilo = estilos[i] if estilos else ["-", "--", ":", "-."][i % 4]
        ax.plot(r.t, y, estilo, label=et, color=COLORES[i % len(COLORES)],
                lw=2.2 - 0.5 * i)
    ax.set_xlabel("Tiempo t [s]")
    ax.set_ylabel(ylabel)
    ax.set_title(titulo)
    ax.legend()
    ax.axhline(0, color="k", lw=0.6)
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


def graficar_respuesta_sismica(resp: Respuesta, titulo: str = "Respuesta sísmica",
                               nombre_archivo: str | None = None):
    """Panel completo para excitación en la base: ag, u relativo, aceleración
    absoluta y cortante basal."""
    fig, axes = plt.subplots(4, 1, figsize=(8.4, 9.0), sharex=True)
    axes[0].plot(resp.t, resp.ag, color=COLORES[1], lw=1.0)
    axes[0].set_ylabel("$\\ddot{u}_g$ [m/s²]")
    axes[0].set_title(titulo + f"\n{resp.sistema.nombre}: $T_n$ = {resp.sistema.T_n:.3f} s · "
                               f"ζ = {resp.sistema.zeta:.3f}\n{resp.metodo}", fontsize=10)

    axes[1].plot(resp.t, resp.u * 1e3, color=COLORES[0])
    i = int(np.argmax(np.abs(resp.u)))
    axes[1].plot(resp.t[i], resp.u[i] * 1e3, "ko", ms=4)
    axes[1].annotate(f"|u|máx = {resp.u_max*1e3:.2f} mm", xy=(resp.t[i], resp.u[i] * 1e3),
                     xytext=(6, 6), textcoords="offset points", fontsize=8)
    axes[1].set_ylabel("u relativo [mm]")

    axes[2].plot(resp.t, resp.aceleracion_absoluta / G, color=COLORES[3])
    axes[2].set_ylabel("$\\ddot{u}_t$ absoluta [g]")

    axes[3].plot(resp.t, resp.cortante_basal / 1e3, color=COLORES[4])
    axes[3].set_ylabel("Cortante basal V [kN]")
    axes[3].set_xlabel("Tiempo t [s]")
    for ax in axes:
        ax.axhline(0, color="k", lw=0.6)
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


def graficar_pulso_fases(resp: Respuesta, td: float,
                         titulo: str = "Respuesta ante carga impulsiva",
                         nombre_archivo: str | None = None):
    """Historia de respuesta separando la fase forzada (t <= td) y la fase libre.

    Cuando el pulso es mucho más corto que la ventana de análisis (caso típico
    de una carga impulsiva), el panel superior se dibuja en escala ampliada para
    que la forma del pulso sea visible.
    """
    t_final = float(resp.t[-1])
    ampliar = td < 0.15 * t_final
    t_zoom = min(t_final, max(6.0 * td, 0.05 * t_final)) if ampliar else t_final

    fig, axes = plt.subplots(2, 1, figsize=(8.2, 5.6), sharex=not ampliar)
    axes[0].plot(resp.t, resp.p / 1e3, color=COLORES[0])
    axes[0].fill_between(resp.t, 0, resp.p / 1e3, alpha=0.18, color=COLORES[0])
    axes[0].set_ylabel("p(t) [kN]")
    axes[0].set_title(titulo)
    if ampliar:
        axes[0].set_xlim(0, t_zoom)
        axes[0].set_xlabel("Tiempo t [s]  (escala ampliada: sólo los primeros "
                           f"{t_zoom:.3f} s)")
        axes[0].annotate(f"pulso: t$_d$ = {td:.4f} s", xy=(td, 0),
                         xytext=(12, 18), textcoords="offset points", fontsize=8,
                         arrowprops=dict(arrowstyle="->", lw=0.8))

    axes[1].plot(resp.t, resp.u * 1e3, color=COLORES[2])
    i = int(np.argmax(np.abs(resp.u)))
    axes[1].plot(resp.t[i], resp.u[i] * 1e3, "ko", ms=4)
    axes[1].annotate(f"|u|máx = {resp.u_max*1e3:.2f} mm\nt = {resp.t[i]:.3f} s",
                     xy=(resp.t[i], resp.u[i] * 1e3), xytext=(14, 8),
                     textcoords="offset points", fontsize=8,
                     bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.75",
                               alpha=0.9),
                     arrowprops=dict(arrowstyle="->", lw=0.8))
    axes[1].set_ylabel("u(t) [mm]")
    axes[1].set_xlabel("Tiempo t [s]")

    for ax in axes:
        ax.axvline(td, color="0.35", ls="--", lw=1.0)
        ax.axhline(0, color="k", lw=0.6)

    y0, y1 = axes[1].get_ylim()
    if ampliar:
        # el pulso es una franja estrechísima: se sombrea y se rotula a un lado
        axes[1].axvspan(0, td, color=COLORES[0], alpha=0.18)
        axes[1].text(td + 0.02 * t_final, y0 * 0.85,
                     f"fase forzada (t ≤ t$_d$ = {td:.3f} s)  |  "
                     "el resto es vibración libre",
                     fontsize=8, color="0.3", va="bottom")
    else:
        axes[1].text(td * 0.5, y1 * 0.82, "Fase forzada\n(t ≤ t$_d$)",
                     ha="center", fontsize=8, color="0.3")
        axes[1].text(min(td * 1.6, 0.9 * t_final), y1 * 0.82, "Fase libre\n(t > t$_d$)",
                     ha="center", fontsize=8, color="0.3")
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


# ===========================================================================
#  Curvas en frecuencia
# ===========================================================================
def graficar_Rd(zetas: Iterable[float] = (0.0, 0.02, 0.05, 0.10, 0.20, 0.50),
                beta_max: float = 3.0, titulo: str = "Factor de amplificación dinámica $R_d$",
                nombre_archivo: str | None = None, marcar: dict | None = None):
    """Curvas Rd vs β para varias fracciones de amortiguamiento.

    ``marcar`` permite señalar un punto de operación: {'beta': .., 'zeta': ..,
    'texto': ..}
    """
    beta, curvas = curva_Rd(list(zetas), beta_max=beta_max)
    # el eje se ajusta para que el punto de operación siempre sea visible
    y_max = 10.5
    if marcar:
        y_max = max(y_max, 1.25 * float(Rd(marcar["beta"], marcar["zeta"])))
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    for i, (z, y) in enumerate(curvas.items()):
        ax.plot(beta, np.clip(y, 0, y_max * 1.05), label=f"ζ = {z*100:.0f} %",
                color=COLORES[i % len(COLORES)])
    ax.axvline(1.0, color=COLORES[0], ls=":", lw=1.2)
    ax.text(1.04, 0.52 * y_max, "Resonancia\n(β = 1)", color=COLORES[0], fontsize=8)
    ax.axhline(1.0, color="0.5", lw=0.8, ls="--")
    ax.text(0.85 * beta_max, 1.0 + 0.02 * y_max, "$R_d$ = 1 (respuesta estática)",
            fontsize=8, color="0.4", ha="right")
    if marcar:
        b, z = marcar["beta"], marcar["zeta"]
        rd = float(Rd(b, z))
        ax.plot(b, rd, "k*", ms=13, zorder=5)
        ax.annotate(marcar.get("texto", f"β={b:.2f}, $R_d$={rd:.2f}"),
                    xy=(b, rd), xytext=(45, -6), textcoords="offset points",
                    fontsize=9, arrowprops=dict(arrowstyle="->", lw=0.8),
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.7", alpha=0.95))
    ax.set_xlim(0, beta_max)
    ax.set_ylim(0, y_max)
    ax.set_xlabel("Relación de frecuencias  β = ω/ω$_n$  [-]")
    ax.set_ylabel("Factor de amplificación $R_d$ = u$_0$/(p$_0$/k)  [-]")
    ax.set_title(titulo)
    ax.legend(title="Amortiguamiento")
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


def graficar_TR(zetas: Iterable[float] = (0.02, 0.05, 0.10, 0.20, 0.50),
                beta_max: float = 4.0, titulo: str = "Transmisibilidad del sistema (TR)",
                nombre_archivo: str | None = None, marcar: dict | None = None):
    """Curvas de transmisibilidad con las zonas de amplificación y aislamiento."""
    beta, curvas = curva_TR(list(zetas), beta_max=beta_max)
    y_max = 6.0
    if marcar:
        y_max = max(y_max, 1.25 * float(transmisibilidad(marcar["beta"], marcar["zeta"])))
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.axvspan(0, np.sqrt(2), color=COLORES[0], alpha=0.06)
    ax.axvspan(np.sqrt(2), beta_max, color=COLORES[2], alpha=0.08)
    for i, (z, y) in enumerate(curvas.items()):
        ax.plot(beta, np.clip(y, 0, y_max * 1.05), label=f"ζ = {z*100:.0f} %",
                color=COLORES[i % len(COLORES)])
    ax.axvline(np.sqrt(2), color=COLORES[2], ls="--", lw=1.4)
    ax.text(np.sqrt(2) + 0.05, 0.45 * y_max, "β = √2\ninicio del\naislamiento",
            color=COLORES[2], fontsize=8)
    ax.axhline(1.0, color="0.4", lw=0.9, ls="--")
    ax.text(0.12, 0.75 * y_max, "AMPLIFICACIÓN\nTR > 1", color=COLORES[0],
            fontsize=9, weight="bold")
    ax.text(beta_max - 1.2, 0.06 * y_max, "AISLAMIENTO\nTR < 1", color=COLORES[2],
            fontsize=9, weight="bold")
    if marcar:
        b, z = marcar["beta"], marcar["zeta"]
        tr = float(transmisibilidad(b, z))
        ax.plot(b, tr, "k*", ms=13, zorder=5)
        ax.annotate(marcar.get("texto", f"β={b:.2f}, TR={tr:.3f}"),
                    xy=(b, tr), xytext=(45, -6), textcoords="offset points",
                    fontsize=9, arrowprops=dict(arrowstyle="->", lw=0.8),
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.7", alpha=0.95))
    ax.set_xlim(0, beta_max)
    ax.set_ylim(0, y_max)
    ax.set_xlabel("Relación de frecuencias  β = ω/ω$_n$  [-]")
    ax.set_ylabel("Transmisibilidad TR = f$_T$/p$_0$  [-]")
    ax.set_title(titulo)
    ax.legend(title="Amortiguamiento")
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


def graficar_fase(zetas: Iterable[float] = (0.0, 0.05, 0.20, 0.50),
                  beta_max: float = 3.0,
                  titulo: str = "Ángulo de fase de la respuesta permanente",
                  nombre_archivo: str | None = None):
    """Curvas del ángulo de fase φ vs β."""
    beta, curvas = curva_fase(list(zetas), beta_max=beta_max)
    fig, ax = plt.subplots(figsize=(8.0, 3.8))
    for i, (z, y) in enumerate(curvas.items()):
        ax.plot(beta, y, label=f"ζ = {z*100:.0f} %", color=COLORES[i % len(COLORES)])
    ax.axvline(1.0, color="0.4", ls=":", lw=1.0)
    ax.axhline(90, color="0.4", ls=":", lw=1.0)
    ax.text(1.12, 12, "En resonancia la respuesta\nse retrasa 90° respecto a p(t)",
            fontsize=8, color="0.35")
    ax.set_xlabel("Relación de frecuencias  β = ω/ω$_n$  [-]")
    ax.set_ylabel("Ángulo de fase φ [°]")
    ax.set_ylim(0, 180)
    ax.set_yticks([0, 45, 90, 135, 180])
    ax.set_title(titulo)
    ax.legend()
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


def graficar_resonancia_y_batido(resp_resonancia: Respuesta, resp_batido: Respuesta,
                                 ust: float, wn: float,
                                 nombre_archivo: str | None = None):
    """Reproduce la figura clásica: resonancia pura (envolvente lineal) y batido."""
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 6.0))
    t = resp_resonancia.t
    axes[0].plot(t, resp_resonancia.u * 1e3, color=COLORES[0],
                 label="Resonancia (β = 1, ζ = 0)")
    env = 0.5 * ust * wn * t * 1e3
    axes[0].plot(t, env, "k--", lw=0.9, label="Envolvente lineal ±(p$_0$/2k)·ω$_n$t")
    axes[0].plot(t, -env, "k--", lw=0.9)
    axes[0].set_ylabel("u(t) [mm]")
    axes[0].set_title("Respuesta en resonancia: crecimiento lineal ilimitado (ζ = 0)")
    axes[0].legend(loc="upper left")

    t2 = resp_batido.t
    axes[1].plot(t2, resp_batido.u * 1e3, color=COLORES[2],
                 label=resp_batido.etiqueta or "Batido (β ≈ 1, ζ = 0)")
    axes[1].set_xlabel("Tiempo t [s]")
    axes[1].set_ylabel("u(t) [mm]")
    axes[1].set_title("Fenómeno de batido: β cercano a 1 pero distinto de 1")
    axes[1].legend(loc="upper left")
    for ax in axes:
        ax.axhline(0, color="k", lw=0.6)
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


# ===========================================================================
#  Barridos paramétricos y espectros
# ===========================================================================
def graficar_barrido(resultado: ResultadoBarrido, columna_y: str = "u_max [mm]",
                     etiqueta_x: str | None = None, titulo: str | None = None,
                     escala_log: bool = False, nombre_archivo: str | None = None,
                     columna_x: str | None = None):
    """Grafica una métrica del barrido frente al parámetro variado."""
    x = resultado.valores if columna_x is None else resultado.columna(columna_x)
    y = resultado.columna(columna_y)
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.plot(x, y, "o-", color=COLORES[0], ms=4)
    if escala_log:
        ax.set_xscale("log")
    ax.set_xlabel(etiqueta_x or (columna_x or resultado.parametro))
    ax.set_ylabel(columna_y)
    ax.set_title(titulo or resultado.descripcion)
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


def graficar_barridos_multiples(resultados: Sequence[ResultadoBarrido],
                                etiquetas: Sequence[str],
                                columna_y: str = "u_max [mm]",
                                etiqueta_x: str = "parámetro",
                                titulo: str = "Análisis paramétrico",
                                nombre_archivo: str | None = None,
                                columna_x: str | None = None):
    """Superpone varias curvas paramétricas en una sola figura."""
    fig, ax = plt.subplots(figsize=(7.8, 4.4))
    for i, (r, et) in enumerate(zip(resultados, etiquetas)):
        x = r.valores if columna_x is None else r.columna(columna_x)
        ax.plot(x, r.columna(columna_y), "o-", ms=3.5, label=et,
                color=COLORES[i % len(COLORES)])
    ax.set_xlabel(etiqueta_x)
    ax.set_ylabel(columna_y)
    ax.set_title(titulo)
    ax.legend()
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


def graficar_espectro(espectros: Sequence[EspectroRespuesta],
                      titulo: str = "Espectros de respuesta elásticos",
                      marcar_T: float | None = None,
                      nombre_archivo: str | None = None):
    """Espectros Sd, PSv y PSa para distintas fracciones de amortiguamiento."""
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0))
    for i, esp in enumerate(espectros):
        c = COLORES[i % len(COLORES)]
        axes[0].plot(esp.T, esp.Sd * 1e3, color=c, label=f"ζ = {esp.zeta*100:.0f} %")
        axes[1].plot(esp.T, esp.PSv, color=c)
        axes[2].plot(esp.T, esp.PSa / G, color=c)
    for ax, ylab, tit in zip(
            axes,
            ["S$_d$ [mm]", "PS$_v$ [m/s]", "PS$_a$ [g]"],
            ["Espectro de desplazamiento", "Espectro de pseudo-velocidad",
             "Espectro de pseudo-aceleración"]):
        ax.set_xlabel("Periodo natural T$_n$ [s]")
        ax.set_ylabel(ylab)
        ax.set_title(tit)
        if marcar_T:
            ax.axvline(marcar_T, color="0.35", ls="--", lw=1.0)
    axes[0].legend()
    fig.suptitle(titulo, fontweight="bold")
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


def graficar_espectro_choque(datos: dict, titulo: str = "Espectro de choque",
                             marcar: dict | None = None,
                             nombre_archivo: str | None = None):
    """Rd,max frente a td/Tn para distintos tipos de pulso.

    ``datos`` = {'rectangular': (razones, Rmax), 'triangular': (...), ...}
    """
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    for i, (nombre, (x, y)) in enumerate(datos.items()):
        ax.semilogx(x, y, label=nombre, color=COLORES[i % len(COLORES)])
    ax.set_ylim(0, 2.45)
    ax.axhline(2.0, color="0.4", ls="--", lw=0.9)
    ax.text(0.052, 2.07, "Límite dinámico R$_d$ = 2 (carga súbita mantenida)",
            fontsize=8, color="0.35")
    if marcar:
        ax.plot(marcar["x"], marcar["y"], "k*", ms=13, zorder=5)
        ax.annotate(marcar.get("texto", ""), xy=(marcar["x"], marcar["y"]),
                    xytext=(14, 34), textcoords="offset points", fontsize=9,
                    arrowprops=dict(arrowstyle="->", lw=0.8),
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.7", alpha=0.9))
    ax.set_xlabel("Relación duración/periodo  t$_d$/T$_n$  [-]")
    ax.set_ylabel("Factor de amplificación máximo  R$_d$ = |u|$_{máx}$·k/p$_0$  [-]")
    ax.set_title(titulo)
    ax.legend(title="Tipo de pulso")
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig


def graficar_convergencia(dts: Sequence[float], errores: dict,
                          titulo: str = "Convergencia del integrador numérico",
                          nombre_archivo: str | None = None):
    """Error relativo del pico frente al paso de tiempo (verificación numérica)."""
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    for i, (nombre, err) in enumerate(errores.items()):
        ax.loglog(dts, np.abs(err) * 100, "o-", label=nombre,
                  color=COLORES[i % len(COLORES)], ms=4)
    ax.set_xlabel("Paso de tiempo Δt/T$_n$ [-]")
    ax.set_ylabel("Error relativo en |u|$_{máx}$ [%]")
    ax.set_title(titulo)
    ax.legend()
    fig.tight_layout()
    return guardar(fig, nombre_archivo) if nombre_archivo else fig
