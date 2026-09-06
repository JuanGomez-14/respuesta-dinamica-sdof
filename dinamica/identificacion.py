"""
================================================================================
 dinamica.identificacion — Propiedades dinámicas a partir de datos medidos
================================================================================

Problema típico de laboratorio: el profesor entrega una tabla tiempo-
desplazamiento de un ensayo de vibración libre (prueba de "pull-back") y se
pide identificar el periodo natural y la fracción de amortiguamiento.

El procedimiento es el clásico:

    1. detectar los picos positivos de la señal;
    2. el periodo amortiguado T_D es la separación media entre picos sucesivos;
    3. la fracción de amortiguamiento sale del decremento logarítmico

           delta = (1/n) * ln(u_i / u_(i+n))
           zeta  = delta / sqrt(4*pi^2 + delta^2)

       promediado sobre todas las parejas de picos consecutivos.

Nota sobre T_D frente a T_n: lo que se mide entre picos es el periodo
AMORTIGUADO. El periodo natural se recupera con T_n = T_D * sqrt(1 - zeta^2).
Para los amortiguamientos usuales en estructuras (zeta < 10 %) la diferencia es
inferior al 0.5 %, pero la corrección se aplica de todos modos porque es exacta
y gratuita.

UNIDADES: t [s]; u en cualquier unidad coherente (el resultado no depende de
ella, porque el decremento logarítmico usa un cociente de amplitudes).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .sistema import zeta_por_decremento_logaritmico

__all__ = ["Pico", "Identificacion", "detectar_picos", "identificar"]


@dataclass(frozen=True)
class Pico:
    """Un máximo local de la señal medida."""
    indice: int
    t: float
    u: float


@dataclass
class Identificacion:
    """Resultado de identificar las propiedades desde una señal medida.

    Atributos
    ---------
    picos     : lista de :class:`Pico` detectados
    T_D       : periodo amortiguado medio entre picos sucesivos [s]
    T_n       : periodo natural, T_D*sqrt(1-zeta^2) [s]
    zeta      : fracción de amortiguamiento identificada [-]
    delta     : decremento logarítmico medio [-]
    n_parejas : número de parejas de picos usadas para el promedio
    detalle   : texto del procedimiento, para transcribir al desarrollo
    """
    picos: list[Pico] = field(default_factory=list)
    T_D: float | None = None
    T_n: float | None = None
    zeta: float | None = None
    delta: float | None = None
    n_parejas: int = 0
    detalle: str = ""

    @property
    def omega_n(self) -> float | None:
        """Frecuencia natural circular [rad/s], si se pudo identificar."""
        return None if not self.T_n else 2.0 * math.pi / self.T_n

    @property
    def f_n(self) -> float | None:
        """Frecuencia natural cíclica [Hz], si se pudo identificar."""
        return None if not self.T_n else 1.0 / self.T_n


def detectar_picos(t, u, prominencia: float | None = None) -> list[Pico]:
    """Detecta los máximos locales POSITIVOS de la señal ``u(t)``.

    Usa ``scipy.signal.find_peaks`` con un criterio de prominencia, en lugar de
    la simple comparación con los dos vecinos: sobre datos experimentales con
    ruido, la comparación ingenua reporta decenas de picos espurios y arruina
    tanto el periodo como el decremento logarítmico.

    Si no se indica ``prominencia``, se toma el 5 % del rango de la señal.

    >>> import numpy as np
    >>> t = np.linspace(0, 4, 2001)
    >>> u = np.exp(-0.05 * 2 * np.pi * t) * np.cos(2 * np.pi * t)
    >>> picos = detectar_picos(t, u)
    >>> len(picos)                            # picos interiores en t = 1, 2, 3
    3
    >>> round(picos[1].t - picos[0].t, 3)     # periodo ~ 1 s
    1.0
    """
    from scipy.signal import find_peaks

    t = np.asarray(t, dtype=float)
    u = np.asarray(u, dtype=float)
    if t.size != u.size:
        raise ValueError("Los vectores t y u deben tener la misma longitud.")
    if t.size < 5:
        raise ValueError("Se requieren al menos 5 puntos para identificar picos.")

    if prominencia is None:
        rango = float(np.max(u) - np.min(u))
        prominencia = 0.05 * rango if rango > 0 else None

    indices, _ = find_peaks(u, prominence=prominencia)
    # Solo interesan los picos positivos: el decremento logarítmico compara
    # amplitudes del mismo signo.
    return [Pico(int(i), float(t[i]), float(u[i])) for i in indices if u[i] > 0]


def identificar(t, u, prominencia: float | None = None) -> Identificacion:
    """Identifica T_n y zeta de un ensayo de vibración libre.

    Devuelve una :class:`Identificacion`; los campos quedan en ``None`` cuando
    los datos no permiten estimarlos (por ejemplo, menos de dos picos, o picos
    que no decaen porque la señal ya está en estado estacionario).

    Sobre una señal sintética de zeta = 5 % y T_n = 0.5 s:

    >>> import numpy as np
    >>> zeta, Tn = 0.05, 0.5
    >>> wn = 2 * np.pi / Tn
    >>> wd = wn * np.sqrt(1 - zeta**2)
    >>> t = np.linspace(0, 5, 5001)
    >>> u = np.exp(-zeta * wn * t) * np.cos(wd * t)
    >>> r = identificar(t, u)
    >>> round(r.zeta, 4)
    0.05
    >>> round(r.T_n, 4)
    0.5
    """
    picos = detectar_picos(t, u, prominencia)
    resultado = Identificacion(picos=picos)

    if len(picos) < 2:
        resultado.detalle = (
            f"Se detectaron {len(picos)} pico(s) positivo(s); se requieren al "
            "menos 2 para estimar el periodo. Acote el rango de tiempo a la "
            "parte con vibración libre, o revise la calidad de los datos.")
        return resultado

    # --- Periodo amortiguado: separación media entre picos sucesivos --------
    separaciones = [b.t - a.t for a, b in zip(picos, picos[1:])]
    T_D = sum(separaciones) / len(separaciones)
    resultado.T_D = T_D

    # --- Amortiguamiento: decremento logarítmico promediado ----------------
    deltas = [math.log(a.u / b.u) for a, b in zip(picos, picos[1:]) if a.u > b.u > 0]
    if deltas:
        delta = sum(deltas) / len(deltas)
        resultado.delta = delta
        resultado.n_parejas = len(deltas)
        # delta = ln(u1/u2)  ->  u1/u2 = exp(delta); se reusa la función del motor.
        resultado.zeta = zeta_por_decremento_logaritmico(math.exp(delta), 1.0)
        # T_D es el periodo AMORTIGUADO; el natural corrige por sqrt(1-zeta^2).
        resultado.T_n = T_D * math.sqrt(1.0 - resultado.zeta ** 2)
        resultado.detalle = (
            f"{len(picos)} picos detectados. "
            f"T_D = {T_D:.5g} s (media de {len(separaciones)} separaciones). "
            f"δ = {delta:.5g} (media de {len(deltas)} parejas de picos). "
            f"ζ = δ/√(4π²+δ²) = {resultado.zeta:.5g}. "
            f"T_n = T_D·√(1-ζ²) = {resultado.T_n:.5g} s.")
    else:
        resultado.T_n = T_D
        resultado.detalle = (
            f"{len(picos)} picos detectados y T_D = {T_D:.5g} s, pero las "
            "amplitudes no decaen de forma monótona, así que no se pudo estimar "
            "ζ por decremento logarítmico. ¿La señal está en estado "
            "estacionario en vez de vibración libre?")
    return resultado
