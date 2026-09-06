"""
Definición del sistema de un grado de libertad (SDOF) y herramientas de
idealización estructural (paso de un sistema de múltiples grados de libertad
a un sistema equivalente de un grado de libertad).

Ecuación de movimiento gobernante:

        m * u''(t) + c * u'(t) + k * u(t) = p(t)

con:
        wn = sqrt(k/m)                  frecuencia natural circular [rad/s]
        Tn = 2*pi/wn                    periodo natural [s]
        c_cr = 2*m*wn = 2*sqrt(k*m)     amortiguamiento crítico [N*s/m]
        z = c/c_cr                      fracción de amortiguamiento crítico [-]
        wD = wn*sqrt(1 - z^2)           frecuencia natural amortiguada [rad/s]
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from .unidades import G, fmt

__all__ = [
    "SistemaSDOF",
    "rigidez_serie",
    "rigidez_paralelo",
    "rigidez_columna",
    "rigidez_portico_columnas",
    "masa_desde_peso",
    "sdof_equivalente_voladizo",
    "sdof_equivalente_viga_simple",
    "zeta_por_decremento_logaritmico",
    "zeta_por_ancho_de_banda",
]


# ===========================================================================
#  Sistema de un grado de libertad
# ===========================================================================
@dataclass
class SistemaSDOF:
    """Sistema masa-resorte-amortiguador de un grado de libertad.

    Parámetros (todos en SI)
    ------------------------
    masa    : masa del sistema, m [kg]
    rigidez : rigidez lateral del sistema, k [N/m]
    zeta    : fracción de amortiguamiento crítico, z [-] (0.05 = 5 %)
    nombre  : etiqueta descriptiva para gráficas y reportes

    Ejemplo
    -------
    >>> s = SistemaSDOF(masa=30_000, rigidez=12.0e6, zeta=0.05)
    >>> round(s.T_n, 4)
    0.3142
    """

    masa: float
    rigidez: float
    zeta: float = 0.05
    nombre: str = "Sistema SDOF"
    metadatos: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.masa <= 0:
            raise ValueError("La masa debe ser positiva (kg).")
        if self.rigidez <= 0:
            raise ValueError("La rigidez debe ser positiva (N/m).")
        if self.zeta < 0:
            raise ValueError("La fracción de amortiguamiento no puede ser negativa.")
        if self.zeta >= 1.0:
            # No es un error físico, pero el laboratorio trabaja con sistemas
            # subamortiguados; se avisa explícitamente.
            raise ValueError(
                "zeta >= 1 corresponde a un sistema crítica o sobreamortiguado; "
                "este laboratorio analiza sistemas subamortiguados (0 <= zeta < 1)."
            )

    # ---------------- propiedades dinámicas -----------------------------
    @property
    def omega_n(self) -> float:
        """Frecuencia natural circular wn [rad/s]."""
        return math.sqrt(self.rigidez / self.masa)

    @property
    def f_n(self) -> float:
        """Frecuencia natural cíclica fn [Hz]."""
        return self.omega_n / (2.0 * math.pi)

    @property
    def T_n(self) -> float:
        """Periodo natural Tn [s]."""
        return 2.0 * math.pi / self.omega_n

    @property
    def c_critico(self) -> float:
        """Amortiguamiento crítico c_cr = 2*m*wn [N*s/m]."""
        return 2.0 * self.masa * self.omega_n

    @property
    def amortiguamiento(self) -> float:
        """Coeficiente de amortiguamiento viscoso c [N*s/m]."""
        return self.zeta * self.c_critico

    # alias corto muy usado en las formulaciones
    c = amortiguamiento

    @property
    def omega_D(self) -> float:
        """Frecuencia natural amortiguada wD [rad/s]."""
        return self.omega_n * math.sqrt(1.0 - self.zeta ** 2)

    @property
    def T_D(self) -> float:
        """Periodo natural amortiguado TD [s]."""
        return 2.0 * math.pi / self.omega_D

    @property
    def peso(self) -> float:
        """Peso del sistema W = m*g [N]."""
        return self.masa * G

    # ---------------- utilidades ----------------------------------------
    def desplazamiento_estatico(self, p0: float) -> float:
        """Desplazamiento estático u_st = p0/k [m] producido por la fuerza p0 [N]."""
        return p0 / self.rigidez

    def beta(self, omega: float) -> float:
        """Relación de frecuencias beta = w/wn para una excitación de frecuencia w."""
        return omega / self.omega_n

    def con(self, **cambios) -> "SistemaSDOF":
        """Devuelve una copia del sistema modificando los parámetros indicados.

        Es la base del análisis paramétrico:

        >>> s = SistemaSDOF(1000, 1e6, 0.05)
        >>> s2 = s.con(zeta=0.10)
        >>> s2.zeta
        0.1
        """
        datos = dict(
            masa=self.masa,
            rigidez=self.rigidez,
            zeta=self.zeta,
            nombre=self.nombre,
            metadatos=dict(self.metadatos),
        )
        datos.update(cambios)
        return SistemaSDOF(**datos)

    def propiedades(self) -> dict:
        """Diccionario con todas las propiedades dinámicas (para tablas/reportes)."""
        return {
            "m [kg]": self.masa,
            "k [N/m]": self.rigidez,
            "c [N*s/m]": self.amortiguamiento,
            "c_cr [N*s/m]": self.c_critico,
            "zeta [-]": self.zeta,
            "wn [rad/s]": self.omega_n,
            "fn [Hz]": self.f_n,
            "Tn [s]": self.T_n,
            "wD [rad/s]": self.omega_D,
            "TD [s]": self.T_D,
            "W = m*g [N]": self.peso,
        }

    def resumen(self) -> str:
        """Bloque de texto con las propiedades dinámicas del sistema."""
        lineas = [f"--- {self.nombre} ---"]
        for clave, valor in self.propiedades().items():
            lineas.append(f"  {clave:<14s} = {fmt(valor, 4)}")
        return "\n".join(lineas)

    # ---------------- constructores alternativos -------------------------
    @classmethod
    def desde_periodo(cls, masa: float, T_n: float, zeta: float = 0.05,
                      nombre: str = "Sistema SDOF") -> "SistemaSDOF":
        """Construye el sistema a partir de la masa y del periodo natural."""
        wn = 2.0 * math.pi / T_n
        return cls(masa=masa, rigidez=masa * wn ** 2, zeta=zeta, nombre=nombre)

    @classmethod
    def desde_frecuencia(cls, masa: float, f_n: float, zeta: float = 0.05,
                         nombre: str = "Sistema SDOF") -> "SistemaSDOF":
        """Construye el sistema a partir de la masa y de la frecuencia natural [Hz]."""
        wn = 2.0 * math.pi * f_n
        return cls(masa=masa, rigidez=masa * wn ** 2, zeta=zeta, nombre=nombre)

    def __str__(self) -> str:  # pragma: no cover - presentación
        return (f"{self.nombre}: m={fmt(self.masa,1)} kg, k={fmt(self.rigidez,1)} N/m, "
                f"zeta={self.zeta:.3f}, Tn={self.T_n:.4f} s, fn={self.f_n:.3f} Hz")


# ===========================================================================
#  Asociación de resortes (idealización estructural)
# ===========================================================================
def rigidez_paralelo(*rigideces: float | Iterable[float]) -> float:
    """Rigidez equivalente de resortes en PARALELO: k_eq = suma(k_i).

    Elementos en paralelo comparten el MISMO desplazamiento (p. ej. las
    columnas de un pórtico con diafragma rígido).

    >>> rigidez_paralelo(1.0, 2.0, 3.0)
    6.0
    """
    valores = _aplanar(rigideces)
    return float(sum(valores))


def rigidez_serie(*rigideces: float | Iterable[float]) -> float:
    """Rigidez equivalente de resortes en SERIE: 1/k_eq = suma(1/k_i).

    Elementos en serie comparten la MISMA fuerza y sus deformaciones se suman
    (p. ej. estructura + sistema de aislamiento + flexibilidad del suelo).

    >>> rigidez_serie(2.0, 2.0)
    1.0
    """
    valores = _aplanar(rigideces)
    if any(k <= 0 for k in valores):
        raise ValueError("Todas las rigideces deben ser positivas.")
    return 1.0 / sum(1.0 / k for k in valores)


def _aplanar(args) -> list[float]:
    valores: list[float] = []
    for a in args:
        if isinstance(a, (int, float)):
            valores.append(float(a))
        else:
            valores.extend(float(x) for x in a)
    if not valores:
        raise ValueError("Debe suministrar al menos una rigidez.")
    return valores


# ===========================================================================
#  Rigidez lateral de elementos típicos
# ===========================================================================
CONDICIONES_COLUMNA = {
    # condición de apoyo            : coeficiente en  k = coef*E*I/L^3
    "empotrada-empotrada": 12.0,   # ambos extremos con giro impedido (viga rígida)
    "empotrada-articulada": 3.0,   # base empotrada y cabeza libre de girar
    "voladizo": 3.0,               # sinónimo del anterior (columna en voladizo)
}


def rigidez_columna(E: float, I: float, L: float,
                    condicion: str = "empotrada-empotrada",
                    n: int = 1) -> float:
    """Rigidez lateral de ``n`` columnas iguales [N/m].

    k = n * coef * E * I / L^3

    Parámetros
    ----------
    E : módulo de elasticidad [Pa]
    I : inercia de la sección respecto al eje de flexión [m^4]
    L : altura libre de la columna [m]
    condicion : 'empotrada-empotrada' (coef=12) o 'voladizo' (coef=3)
    n : número de columnas iguales trabajando en paralelo

    >>> round(rigidez_columna(200e9, 1e-4, 3.0, n=4) / 1e6, 3)
    35.556
    """
    if condicion not in CONDICIONES_COLUMNA:
        raise ValueError(
            f"Condición '{condicion}' no válida. Use: {list(CONDICIONES_COLUMNA)}"
        )
    coef = CONDICIONES_COLUMNA[condicion]
    return n * coef * E * I / L ** 3


def rigidez_portico_columnas(columnas: Iterable[dict]) -> float:
    """Rigidez lateral total de un pórtico con diafragma rígido.

    ``columnas`` es una lista de diccionarios con las llaves de
    :func:`rigidez_columna`; todas las columnas trabajan en PARALELO.

    >>> k = rigidez_portico_columnas([
    ...     dict(E=200e9, I=1e-4, L=3.0, n=2),
    ...     dict(E=200e9, I=2e-4, L=3.0, n=2)])
    >>> round(k/1e6, 3)
    53.333
    """
    return rigidez_paralelo([rigidez_columna(**c) for c in columnas])


def masa_desde_peso(W: float, g: float = G) -> float:
    """Convierte un peso W [N] en masa m = W/g [kg]."""
    return W / g


# ===========================================================================
#  Sistemas equivalentes de un grado de libertad (masa distribuida)
# ===========================================================================
def sdof_equivalente_voladizo(E: float, I: float, L: float, masa_lineal: float,
                              masa_concentrada: float = 0.0, zeta: float = 0.05,
                              nombre: str = "SDOF equivalente (voladizo)") -> SistemaSDOF:
    """Sistema equivalente de 1 GDL para un voladizo con masa distribuida.

    Se emplea el método de Rayleigh con la función de forma estática del
    voladizo bajo carga lateral en la punta:

        psi(x) = (3*(x/L)^2 - (x/L)^3)/2 ,   psi(L) = 1

    Con esa forma se obtienen las propiedades generalizadas referidas al
    desplazamiento de la punta:

        k* = 3*E*I/L^3
        m* = 0.2357 * (masa_lineal * L)  +  masa_concentrada

    (el coeficiente 33/140 = 0.2357 es el clásico de la masa participante de
    un voladizo con masa uniformemente distribuida).

    Parámetros
    ----------
    masa_lineal : masa por unidad de longitud del elemento [kg/m]
    masa_concentrada : masa adicional en la punta [kg] (tanque, equipo, etc.)
    """
    k_eq = 3.0 * E * I / L ** 3
    m_eq = (33.0 / 140.0) * masa_lineal * L + masa_concentrada
    s = SistemaSDOF(masa=m_eq, rigidez=k_eq, zeta=zeta, nombre=nombre)
    s.metadatos.update(
        factor_masa_participante=33.0 / 140.0,
        masa_distribuida_total=masa_lineal * L,
        masa_concentrada=masa_concentrada,
        forma_modal="psi(x) = (3(x/L)^2 - (x/L)^3)/2",
    )
    return s


def sdof_equivalente_viga_simple(E: float, I: float, L: float, masa_lineal: float,
                                 masa_concentrada: float = 0.0, zeta: float = 0.02,
                                 nombre: str = "SDOF equivalente (viga simple)") -> SistemaSDOF:
    """Sistema equivalente de 1 GDL para una viga simplemente apoyada.

    Referido al desplazamiento del centro de la luz, con forma senoidal
    psi(x) = sin(pi*x/L):

        k* = pi^4*E*I/(2*L^3)  = 48.70*E*I/L^3
        m* = 0.5*(masa_lineal*L) + masa_concentrada
    """
    k_eq = math.pi ** 4 * E * I / (2.0 * L ** 3)
    m_eq = 0.5 * masa_lineal * L + masa_concentrada
    s = SistemaSDOF(masa=m_eq, rigidez=k_eq, zeta=zeta, nombre=nombre)
    s.metadatos.update(
        factor_masa_participante=0.5,
        forma_modal="psi(x) = sin(pi x/L)",
    )
    return s


# ===========================================================================
#  Identificación del amortiguamiento a partir de mediciones
# ===========================================================================
def zeta_por_decremento_logaritmico(u1: float, u2: float, n_ciclos: int = 1) -> float:
    """Fracción de amortiguamiento a partir del decremento logarítmico.

        delta = (1/n) * ln(u1/u2)      ->     z = delta / sqrt(4*pi^2 + delta^2)

    ``u1`` y ``u2`` son dos picos del mismo signo separados ``n_ciclos`` ciclos
    en un ensayo de vibración libre.

    >>> round(zeta_por_decremento_logaritmico(10.0, 10.0*math.exp(-0.3142)), 3)
    0.05
    """
    if u1 <= 0 or u2 <= 0:
        raise ValueError("Los picos deben ser positivos.")
    delta = math.log(u1 / u2) / n_ciclos
    return delta / math.sqrt(4.0 * math.pi ** 2 + delta ** 2)


def zeta_por_ancho_de_banda(f_a: float, f_b: float, f_resonancia: float) -> float:
    """Fracción de amortiguamiento por el método del ancho de banda de media potencia.

        z = (f_b - f_a) / (2*f_resonancia)

    donde f_a y f_b son las frecuencias en las que la amplitud vale
    1/sqrt(2) veces la amplitud máxima (resonante).
    """
    return (f_b - f_a) / (2.0 * f_resonancia)
