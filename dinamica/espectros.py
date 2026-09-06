"""
Espectros de respuesta.

1. Espectro de respuesta sísmico
   Para un acelerograma dado ug''(t) se resuelve un sistema de 1 GDL para un
   barrido de periodos naturales Tn y se registran los valores pico:

        Sd(Tn, z)  = |u|max                        (desplazamiento espectral)
        PSv(Tn, z) = wn·Sd                         (pseudo-velocidad)
        PSa(Tn, z) = wn²·Sd                        (pseudo-aceleración)
        Sa_abs     = |u'' + ug''|max               (aceleración absoluta real)

   La fuerza estática equivalente es  fs = m·PSa  y el cortante basal
   V = m·PSa, lo que conecta el análisis dinámico con el diseño.

2. Espectro de choque (shock spectrum) de cargas impulsivas
   Relación entre el factor de amplificación máximo Rd,max y la relación
   td/Tn entre la duración del pulso y el periodo natural. Es la herramienta
   central para interpretar cargas impulsivas:

        td/Tn << 1  -> respuesta gobernada por el IMPULSO (Rd pequeño)
        td/Tn ~ 0.5-1 -> zona de máxima amplificación
        td/Tn >> 1  -> comportamiento cuasi-estático (Rd -> 1 o 2)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .cargas import Carga, ExcitacionBase, PulsoRectangular, PulsoSemiseno, \
    PulsoTriangular
from .sistema import SistemaSDOF
from .solucionadores import interpolacion_exacta, newmark, vector_tiempo

__all__ = ["EspectroRespuesta", "espectro_respuesta", "espectro_choque",
           "periodos_logaritmicos"]


def periodos_logaritmicos(T_min: float = 0.02, T_max: float = 4.0,
                          n: int = 120) -> np.ndarray:
    """Barrido de periodos espaciados logarítmicamente [s]."""
    return np.logspace(math.log10(T_min), math.log10(T_max), n)


@dataclass
class EspectroRespuesta:
    """Resultado del espectro de respuesta para una fracción de amortiguamiento."""

    T: np.ndarray        # periodos [s]
    Sd: np.ndarray       # desplazamiento espectral [m]
    PSv: np.ndarray      # pseudo-velocidad [m/s]
    PSa: np.ndarray      # pseudo-aceleración [m/s^2]
    Sa_abs: np.ndarray   # aceleración absoluta máxima [m/s^2]
    zeta: float
    nombre: str = ""

    @property
    def PSa_g(self) -> np.ndarray:
        return self.PSa / 9.80665

    def en_periodo(self, T: float) -> dict:
        """Valores espectrales interpolados para un periodo dado."""
        return {
            "T [s]": T,
            "Sd [m]": float(np.interp(T, self.T, self.Sd)),
            "PSv [m/s]": float(np.interp(T, self.T, self.PSv)),
            "PSa [m/s2]": float(np.interp(T, self.T, self.PSa)),
            "PSa [g]": float(np.interp(T, self.T, self.PSa)) / 9.80665,
            "Sa_abs [m/s2]": float(np.interp(T, self.T, self.Sa_abs)),
        }

    @property
    def PSa_maxima(self) -> tuple[float, float]:
        """(T, PSa) del pico del espectro de pseudo-aceleración."""
        i = int(np.argmax(self.PSa))
        return float(self.T[i]), float(self.PSa[i])


def espectro_respuesta(excitacion: ExcitacionBase, zeta: float = 0.05,
                       periodos: np.ndarray | None = None,
                       metodo: str = "exacta") -> EspectroRespuesta:
    """Calcula el espectro de respuesta elástico de un acelerograma.

    Para cada periodo se resuelve la ecuación de movimiento con excitación
    p_ef = -m·ug''. Se usa masa unitaria (los resultados Sd, PSv, PSa no
    dependen de la masa). El paso de integración se refina a Tn/20 como
    máximo para garantizar precisión en periodos cortos.
    """
    if periodos is None:
        periodos = periodos_logaritmicos()
    periodos = np.asarray(periodos, dtype=float)

    Sd = np.zeros_like(periodos)
    Sa_abs = np.zeros_like(periodos)

    for i, T in enumerate(periodos):
        sistema = SistemaSDOF.desde_periodo(masa=1.0, T_n=T, zeta=zeta)
        dt = min(excitacion.dt, T / 20.0)
        t = vector_tiempo(excitacion.duracion + 5.0 * T, dt,
                          t_inicial=float(excitacion.t[0]))
        ag = np.interp(t, excitacion.t, excitacion.ag, left=0.0, right=0.0)
        p = -sistema.masa * ag
        if metodo == "exacta":
            r = interpolacion_exacta(sistema, t, p, ag=ag)
        else:
            r = newmark(sistema, t, p, ag=ag)
        Sd[i] = r.u_max
        Sa_abs[i] = r.a_abs_max

    wn = 2.0 * math.pi / periodos
    return EspectroRespuesta(T=periodos, Sd=Sd, PSv=wn * Sd, PSa=wn ** 2 * Sd,
                             Sa_abs=Sa_abs, zeta=zeta,
                             nombre=excitacion.nombre)


def espectro_choque(tipo_pulso: str = "rectangular",
                    zeta: float = 0.0,
                    razones: np.ndarray | None = None,
                    puntos_por_periodo: int = 400) -> tuple[np.ndarray, np.ndarray]:
    """Espectro de choque: Rd,max frente a td/Tn para un pulso dado.

    Parámetros
    ----------
    tipo_pulso : 'rectangular' | 'triangular' | 'semiseno'
    zeta       : fracción de amortiguamiento (0 = caso clásico no amortiguado)
    razones    : vector de td/Tn a evaluar

    Devuelve
    --------
    (razones, Rd_max) donde Rd_max = |u|max·k/p0 (adimensional).

    El análisis se extiende 2 periodos naturales después del pulso para
    capturar el máximo, que en pulsos cortos ocurre en la fase de vibración
    libre.
    """
    if razones is None:
        razones = np.logspace(-1.3, 0.9, 160)   # 0.05 a ~8
    razones = np.asarray(razones, dtype=float)

    Tn = 1.0                       # se fija Tn = 1 s (resultado adimensional)
    sistema = SistemaSDOF.desde_periodo(masa=1.0, T_n=Tn, zeta=zeta)
    p0 = 1.0
    Rmax = np.zeros_like(razones)

    for i, r in enumerate(razones):
        td = r * Tn
        if tipo_pulso == "rectangular":
            carga: Carga = PulsoRectangular(p0=p0, duracion=td)
        elif tipo_pulso == "triangular":
            carga = PulsoTriangular(p0=p0, duracion=td, tipo="decreciente")
        elif tipo_pulso == "semiseno":
            carga = PulsoSemiseno(p0=p0, duracion=td)
        else:
            raise ValueError("tipo_pulso debe ser 'rectangular', 'triangular' o 'semiseno'")

        dt = min(td, Tn) / puntos_por_periodo
        t = vector_tiempo(td + 2.5 * Tn, dt)
        resp = interpolacion_exacta(sistema, t, carga.muestrear(t))
        Rmax[i] = resp.u_max * sistema.rigidez / p0

    return razones, Rmax
