"""
Catálogo de excitaciones dinámicas p(t) y de excitaciones en la base.

Todas las cargas son objetos con un método ``p(t)`` vectorizado (acepta un
escalar o un arreglo de tiempos y devuelve la fuerza en newton).

Familias implementadas
----------------------
1. Armónicas          : CargaArmonica, CargaChirp (barrido de frecuencias)
2. Impulsivas         : PulsoRectangular, PulsoTriangular, PulsoSemiseno,
                        PulsoExponencial (tipo explosión), Escalon, Rampa
3. Arbitrarias        : CargaArbitraria (vector tiempo + vector fuerza),
                        ExcitacionBase (vector tiempo + aceleración del terreno)

Convención de signos: p(t) positiva actúa en la misma dirección que u(t).
Para excitación en la base, la carga efectiva es  p_ef(t) = -m * ug''(t)
y la respuesta calculada u(t) es el desplazamiento RELATIVO a la base.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "Carga",
    "CargaArmonica",
    "CargaChirp",
    "PulsoRectangular",
    "PulsoTriangular",
    "PulsoSemiseno",
    "PulsoExponencial",
    "Escalon",
    "Rampa",
    "CargaArbitraria",
    "CargaNula",
    "ExcitacionBase",
    "suma_de_cargas",
]


# ===========================================================================
#  Clase base
# ===========================================================================
class Carga:
    """Interfaz común de todas las excitaciones.

    Cada subclase define, según corresponda:
        nombre    : etiqueta descriptiva
        p0        : amplitud de referencia [N]
        duracion  : duración del pulso td [s] (sólo cargas impulsivas)

    (Estos atributos NO se declaran aquí con valor por defecto para no
    interferir con el orden de los campos de las subclases ``dataclass``.)
    """

    def p(self, t):  # pragma: no cover - interfaz
        raise NotImplementedError

    # azúcar sintáctico: la carga se puede llamar como una función
    def __call__(self, t):
        return self.p(t)

    def muestrear(self, t: np.ndarray) -> np.ndarray:
        """Evalúa la carga sobre el vector de tiempos ``t`` [s] -> fuerza [N]."""
        t = np.asarray(t, dtype=float)
        return np.asarray(self.p(t), dtype=float)

    def descripcion(self) -> str:
        return self.nombre

    def __add__(self, otra: "Carga") -> "Carga":
        return suma_de_cargas(self, otra)


# ===========================================================================
#  1. Cargas armónicas
# ===========================================================================
@dataclass
class CargaArmonica(Carga):
    """Carga armónica  p(t) = p0 * sin(w*t + fase)   (o coseno).

    Parámetros
    ----------
    p0    : amplitud de la fuerza [N]
    omega : frecuencia circular de excitación [rad/s]
    fase  : desfase [rad]
    tipo  : 'sin' (por defecto) o 'cos'
    t_inicio : instante en que comienza a actuar la carga [s]
    """

    p0: float
    omega: float
    fase: float = 0.0
    tipo: str = "sin"
    t_inicio: float = 0.0
    nombre: str = "Carga armónica"

    @property
    def frecuencia_hz(self) -> float:
        return self.omega / (2.0 * math.pi)

    @property
    def periodo(self) -> float:
        return 2.0 * math.pi / self.omega

    def p(self, t):
        t = np.asarray(t, dtype=float)
        tau = t - self.t_inicio
        f = np.sin if self.tipo == "sin" else np.cos
        return np.where(tau >= 0.0, self.p0 * f(self.omega * tau + self.fase), 0.0)

    def descripcion(self) -> str:
        return (f"p(t) = {self.p0:,.1f} N · {self.tipo}({self.omega:.3f}·t) ; "
                f"f = {self.frecuencia_hz:.3f} Hz ; T = {self.periodo:.3f} s")


@dataclass
class CargaChirp(Carga):
    """Barrido de frecuencias (chirp lineal): simula el arranque/parada de una
    máquina que atraviesa la resonancia.

        p(t) = p0 * sin( 2*pi * (f0*t + (f1-f0)/(2*T) * t^2) )

    Muy útil para mostrar el paso por resonancia y el crecimiento/decaimiento
    de la amplitud.
    """

    p0: float
    f0: float          # frecuencia inicial [Hz]
    f1: float          # frecuencia final [Hz]
    T: float           # duración del barrido [s]
    nombre: str = "Barrido de frecuencias (chirp)"

    def p(self, t):
        t = np.asarray(t, dtype=float)
        tt = np.clip(t, 0.0, self.T)
        fase = 2.0 * math.pi * (self.f0 * tt + (self.f1 - self.f0) / (2.0 * self.T) * tt ** 2)
        return np.where((t >= 0) & (t <= self.T), self.p0 * np.sin(fase), 0.0)

    def frecuencia_instantanea(self, t):
        t = np.asarray(t, dtype=float)
        return self.f0 + (self.f1 - self.f0) * np.clip(t, 0, self.T) / self.T

    def descripcion(self) -> str:
        return (f"Chirp: p0={self.p0:,.1f} N, f: {self.f0:.2f} -> {self.f1:.2f} Hz "
                f"en {self.T:.1f} s")


# ===========================================================================
#  2. Cargas impulsivas
# ===========================================================================
@dataclass
class PulsoRectangular(Carga):
    """Pulso rectangular: p = p0 para 0 <= t <= td ; 0 en el resto."""

    p0: float
    duracion: float
    nombre: str = "Pulso rectangular"

    def p(self, t):
        t = np.asarray(t, dtype=float)
        return np.where((t >= 0.0) & (t <= self.duracion), self.p0, 0.0)

    @property
    def impulso(self) -> float:
        """Impulso total I = integral de p dt [N*s]."""
        return self.p0 * self.duracion

    def descripcion(self) -> str:
        return f"Pulso rectangular p0={self.p0:,.1f} N, td={self.duracion:.4f} s"


@dataclass
class PulsoTriangular(Carga):
    """Pulso triangular.

    tipo = 'decreciente' : p(0)=p0 y decrece linealmente hasta 0 en td
                           (modelo clásico de una explosión idealizada)
    tipo = 'creciente'   : p(0)=0 y crece linealmente hasta p0 en td
    tipo = 'simetrico'   : sube hasta p0 en td/2 y baja hasta 0 en td
    """

    p0: float
    duracion: float
    tipo: str = "decreciente"
    nombre: str = "Pulso triangular"

    def p(self, t):
        t = np.asarray(t, dtype=float)
        td = self.duracion
        dentro = (t >= 0.0) & (t <= td)
        if self.tipo == "decreciente":
            valor = self.p0 * (1.0 - t / td)
        elif self.tipo == "creciente":
            valor = self.p0 * (t / td)
        elif self.tipo == "simetrico":
            valor = np.where(t <= td / 2.0,
                             self.p0 * (2.0 * t / td),
                             self.p0 * (2.0 - 2.0 * t / td))
        else:
            raise ValueError("tipo debe ser 'decreciente', 'creciente' o 'simetrico'")
        return np.where(dentro, valor, 0.0)

    @property
    def impulso(self) -> float:
        return 0.5 * self.p0 * self.duracion

    def descripcion(self) -> str:
        return (f"Pulso triangular ({self.tipo}) p0={self.p0:,.1f} N, "
                f"td={self.duracion:.4f} s")


@dataclass
class PulsoSemiseno(Carga):
    """Medio ciclo de seno: p(t) = p0*sin(pi*t/td) para 0 <= t <= td."""

    p0: float
    duracion: float
    nombre: str = "Pulso medio seno"

    def p(self, t):
        t = np.asarray(t, dtype=float)
        dentro = (t >= 0.0) & (t <= self.duracion)
        return np.where(dentro, self.p0 * np.sin(math.pi * t / self.duracion), 0.0)

    @property
    def impulso(self) -> float:
        return 2.0 * self.p0 * self.duracion / math.pi

    def descripcion(self) -> str:
        return f"Pulso medio seno p0={self.p0:,.1f} N, td={self.duracion:.4f} s"


@dataclass
class PulsoExponencial(Carga):
    """Pulso tipo onda de choque (Friedlander simplificada):

        p(t) = p0 * (1 - t/td) * exp(-alfa*t/td)     para 0 <= t <= td

    Con alfa = 0 se recupera el pulso triangular decreciente.
    """

    p0: float
    duracion: float
    alfa: float = 1.8
    nombre: str = "Pulso exponencial (Friedlander)"

    def p(self, t):
        t = np.asarray(t, dtype=float)
        td = self.duracion
        dentro = (t >= 0.0) & (t <= td)
        valor = self.p0 * (1.0 - t / td) * np.exp(-self.alfa * t / td)
        return np.where(dentro, valor, 0.0)

    def descripcion(self) -> str:
        return (f"Pulso Friedlander p0={self.p0:,.1f} N, td={self.duracion:.4f} s, "
                f"alfa={self.alfa}")


@dataclass
class Escalon(Carga):
    """Carga escalón: p = p0 para t >= 0 (carga súbita mantenida)."""

    p0: float
    nombre: str = "Carga escalón"

    def p(self, t):
        t = np.asarray(t, dtype=float)
        return np.where(t >= 0.0, self.p0, 0.0)

    def descripcion(self) -> str:
        return f"Escalón p0={self.p0:,.1f} N"


@dataclass
class Rampa(Carga):
    """Carga rampa: crece linealmente de 0 a p0 en tr y luego se mantiene."""

    p0: float
    t_rampa: float
    nombre: str = "Carga rampa"

    def p(self, t):
        t = np.asarray(t, dtype=float)
        return np.where(t < 0.0, 0.0,
                        np.where(t <= self.t_rampa, self.p0 * t / self.t_rampa, self.p0))

    def descripcion(self) -> str:
        return f"Rampa hasta p0={self.p0:,.1f} N en tr={self.t_rampa:.3f} s"


# ===========================================================================
#  3. Cargas arbitrarias
# ===========================================================================
@dataclass
class CargaArbitraria(Carga):
    """Carga definida por una serie temporal (vector de tiempo + vector de fuerza).

    Fuera del intervalo definido la carga vale cero. Entre puntos se interpola
    linealmente, que es exactamente la hipótesis del integrador de
    interpolación exacta y consistente con Newmark.
    """

    t_datos: np.ndarray
    p_datos: np.ndarray
    nombre: str = "Carga arbitraria"
    factor_escala: float = 1.0

    def __post_init__(self) -> None:
        self.t_datos = np.asarray(self.t_datos, dtype=float).ravel()
        self.p_datos = np.asarray(self.p_datos, dtype=float).ravel()
        if self.t_datos.size != self.p_datos.size:
            raise ValueError("Los vectores de tiempo y de carga deben tener igual tamaño.")
        if np.any(np.diff(self.t_datos) <= 0):
            raise ValueError("El vector de tiempo debe ser estrictamente creciente.")

    def p(self, t):
        t = np.asarray(t, dtype=float)
        return self.factor_escala * np.interp(t, self.t_datos, self.p_datos,
                                              left=0.0, right=0.0)

    @property
    def p0(self) -> float:  # amplitud máxima en valor absoluto
        return float(np.max(np.abs(self.p_datos)) * self.factor_escala)

    @property
    def duracion(self) -> float:
        return float(self.t_datos[-1] - self.t_datos[0])

    def descripcion(self) -> str:
        return (f"Serie temporal con {self.t_datos.size} puntos, "
                f"duración {self.duracion:.2f} s, |p|max = {self.p0:,.1f} N")


class CargaNula(Carga):
    """Ausencia de carga: p(t) = 0 (para estudiar vibración libre)."""

    nombre = "Vibración libre (p = 0)"
    p0 = 0.0

    def p(self, t):
        return np.zeros_like(np.asarray(t, dtype=float))


@dataclass
class _SumaCargas(Carga):
    componentes: tuple
    nombre: str = "Suma de cargas"

    def p(self, t):
        total = np.zeros_like(np.asarray(t, dtype=float))
        for c in self.componentes:
            total = total + c.p(t)
        return total

    def descripcion(self) -> str:
        return " + ".join(c.descripcion() for c in self.componentes)


def suma_de_cargas(*cargas: Carga) -> Carga:
    """Superposición de varias cargas actuando simultáneamente."""
    return _SumaCargas(componentes=tuple(cargas))


# ===========================================================================
#  Excitación en la base (sismo, vibración del soporte)
# ===========================================================================
@dataclass
class ExcitacionBase:
    """Excitación sísmica definida por el acelerograma del terreno ug''(t).

    Atributos
    ---------
    t   : vector de tiempo [s]
    ag  : vector de aceleración del terreno [m/s^2]

    La carga efectiva sobre el sistema SDOF es  p_ef(t) = -m*ug''(t),
    y la respuesta u(t) obtenida es el desplazamiento RELATIVO a la base.
    """

    t: np.ndarray
    ag: np.ndarray
    nombre: str = "Excitación en la base"
    metadatos: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.t = np.asarray(self.t, dtype=float).ravel()
        self.ag = np.asarray(self.ag, dtype=float).ravel()
        if self.t.size != self.ag.size:
            raise ValueError("t y ag deben tener el mismo número de puntos.")

    @property
    def dt(self) -> float:
        return float(self.t[1] - self.t[0])

    @property
    def duracion(self) -> float:
        return float(self.t[-1] - self.t[0])

    @property
    def pga(self) -> float:
        """Aceleración pico del terreno |ug''|max [m/s^2]."""
        return float(np.max(np.abs(self.ag)))

    @property
    def velocidad_terreno(self) -> np.ndarray:
        """Velocidad del terreno [m/s], por integración trapezoidal del registro."""
        dt = np.diff(self.t)
        return np.concatenate(([0.0], np.cumsum(0.5 * dt * (self.ag[1:] + self.ag[:-1]))))

    @property
    def desplazamiento_terreno(self) -> np.ndarray:
        """Desplazamiento del terreno [m], por doble integración del registro."""
        v = self.velocidad_terreno
        dt = np.diff(self.t)
        return np.concatenate(([0.0], np.cumsum(0.5 * dt * (v[1:] + v[:-1]))))

    @property
    def pgv(self) -> float:
        """Velocidad pico del terreno |ug'|max [m/s]."""
        return float(np.max(np.abs(self.velocidad_terreno)))

    @property
    def pgd(self) -> float:
        """Desplazamiento pico del terreno |ug|max [m]."""
        return float(np.max(np.abs(self.desplazamiento_terreno)))

    def carga_efectiva(self, masa: float) -> CargaArbitraria:
        """Devuelve p_ef(t) = -m*ug''(t) como carga arbitraria [N]."""
        return CargaArbitraria(self.t, -masa * self.ag,
                               nombre=f"Carga efectiva sísmica ({self.nombre})")

    def escalar_a_pga(self, pga_objetivo: float) -> "ExcitacionBase":
        """Devuelve una copia escalada linealmente a la PGA objetivo [m/s^2]."""
        factor = pga_objetivo / self.pga
        return ExcitacionBase(self.t, self.ag * factor,
                              nombre=f"{self.nombre} escalado x{factor:.3f}",
                              metadatos=dict(self.metadatos, factor_escala=factor))

    def descripcion(self) -> str:
        return (f"{self.nombre}: {self.t.size} puntos, dt={self.dt:.4f} s, "
                f"duración={self.duracion:.2f} s, PGA={self.pga:.3f} m/s² "
                f"({self.pga/9.80665:.3f} g), PGV={self.pgv*100:.1f} cm/s, "
                f"PGD={self.pgd*100:.1f} cm")
