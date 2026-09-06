"""
Respuesta en el dominio de la frecuencia: factores de amplificación dinámica,
ángulo de fase, transmisibilidad y diseño de aislamiento de vibraciones.

Notación
--------
    beta = w/wn   relación entre la frecuencia de excitación y la natural [-]
    z             fracción de amortiguamiento crítico [-]

Factores de respuesta (Chopra, cap. 3):
    Rd = u0 / (p0/k)                    = 1/sqrt[(1-b²)² + (2 z b)²]
    Rv = u0_vel / (p0/sqrt(km))         = b * Rd
    Ra = u0_acel / (p0/m)               = b² * Rd
    fase phi = atan2(2 z b, 1 - b²)     (retraso de u respecto a p)

Transmisibilidad (idéntica para fuerza transmitida a la base y para
transmisión de movimiento de la base a la masa):
    TR = sqrt[1 + (2 z b)²] / sqrt[(1-b²)² + (2 z b)²]

Propiedades notables:
    * Rd máximo en  b = sqrt(1 - 2z²)  con  Rd_max = 1/(2 z sqrt(1-z²))
    * TR = 1 exactamente en  b = sqrt(2)  para cualquier z
    * b > sqrt(2)  => aislamiento (TR < 1)
    * b < sqrt(2)  => amplificación (TR > 1)
"""

from __future__ import annotations

import math

import numpy as np

__all__ = [
    "Rd", "Rv", "Ra", "angulo_fase", "transmisibilidad",
    "beta_resonante", "Rd_maximo", "transmisibilidad_maxima",
    "beta_para_transmisibilidad", "eficiencia_aislamiento",
    "curva_Rd", "curva_TR", "curva_fase",
    "amplitud_permanente", "fuerza_transmitida_maxima",
    "fuerza_desbalance", "rigidez_para_beta",
    "energia_disipada_por_ciclo",
]


# ---------------------------------------------------------------------------
# Factores de respuesta
# ---------------------------------------------------------------------------
def Rd(beta, zeta: float):
    """Factor de amplificación dinámica de DESPLAZAMIENTO.

    Rd = u0/(p0/k) = 1/sqrt[(1-β²)² + (2ζβ)²]

    >>> round(float(Rd(1.0, 0.05)), 3)   # en resonancia Rd ≈ 1/(2ζ)
    10.0
    """
    beta = np.asarray(beta, dtype=float)
    den = np.sqrt((1.0 - beta ** 2) ** 2 + (2.0 * zeta * beta) ** 2)
    with np.errstate(divide="ignore"):
        r = np.where(den == 0.0, np.inf, 1.0 / den)
    return r if r.ndim else float(r)


def Rv(beta, zeta: float):
    """Factor de amplificación de VELOCIDAD:  Rv = β·Rd."""
    beta = np.asarray(beta, dtype=float)
    return beta * Rd(beta, zeta)


def Ra(beta, zeta: float):
    """Factor de amplificación de ACELERACIÓN:  Ra = β²·Rd."""
    beta = np.asarray(beta, dtype=float)
    return beta ** 2 * Rd(beta, zeta)


def angulo_fase(beta, zeta: float):
    """Ángulo de fase phi [rad] con que la respuesta se retrasa respecto a la carga.

    phi = atan2(2ζβ, 1-β²)  ∈ (0, π).
    En resonancia (β=1) vale exactamente π/2 = 90° para cualquier ζ > 0.
    """
    beta = np.asarray(beta, dtype=float)
    return np.arctan2(2.0 * zeta * beta, 1.0 - beta ** 2)


def transmisibilidad(beta, zeta: float):
    """Transmisibilidad TR (fuerza a la base o movimiento de la base a la masa).

    TR = sqrt[1+(2ζβ)²] / sqrt[(1-β²)² + (2ζβ)²]

    >>> round(float(transmisibilidad(math.sqrt(2), 0.10)), 6)
    1.0
    """
    beta = np.asarray(beta, dtype=float)
    num = np.sqrt(1.0 + (2.0 * zeta * beta) ** 2)
    den = np.sqrt((1.0 - beta ** 2) ** 2 + (2.0 * zeta * beta) ** 2)
    with np.errstate(divide="ignore"):
        tr = np.where(den == 0.0, np.inf, num / den)
    return tr if tr.ndim else float(tr)


# ---------------------------------------------------------------------------
# Valores notables
# ---------------------------------------------------------------------------
def beta_resonante(zeta: float) -> float:
    """β en que Rd es máximo:  β = sqrt(1-2ζ²)  (existe si ζ < 1/sqrt(2))."""
    if zeta >= 1.0 / math.sqrt(2.0):
        return 0.0
    return math.sqrt(1.0 - 2.0 * zeta ** 2)


def Rd_maximo(zeta: float) -> float:
    """Valor máximo de Rd:  1/(2ζ·sqrt(1-ζ²)).  Para ζ pequeño ≈ 1/(2ζ)."""
    if zeta == 0:
        return float("inf")
    if zeta >= 1.0 / math.sqrt(2.0):
        return 1.0
    return 1.0 / (2.0 * zeta * math.sqrt(1.0 - zeta ** 2))


def transmisibilidad_maxima(zeta: float) -> tuple[float, float]:
    """(β_pico, TR_pico) de la curva de transmisibilidad.

    El pico ocurre en β² = [sqrt(1+8ζ²) - 1]/(4ζ²).
    """
    if zeta == 0:
        return 1.0, float("inf")
    b2 = (math.sqrt(1.0 + 8.0 * zeta ** 2) - 1.0) / (4.0 * zeta ** 2)
    b = math.sqrt(b2)
    return b, float(transmisibilidad(b, zeta))


def beta_para_transmisibilidad(TR_objetivo: float, zeta: float,
                               beta_max: float = 50.0) -> float:
    """Relación de frecuencias mínima necesaria para lograr una TR objetivo (<1).

    Se resuelve numéricamente TR(β) = TR_objetivo en la rama de aislamiento
    (β > sqrt(2)). Es la herramienta de diseño de un sistema de aislamiento:
    conocida la frecuencia de la máquina, β define la rigidez máxima admisible
    de los apoyos.
    """
    if TR_objetivo >= 1.0:
        raise ValueError("Para aislar se requiere TR objetivo < 1.")
    from scipy.optimize import brentq

    f = lambda b: float(transmisibilidad(b, zeta)) - TR_objetivo
    b_lo = math.sqrt(2.0) + 1e-9
    if f(beta_max) > 0:
        raise ValueError("TR objetivo inalcanzable en el rango de β analizado; "
                         "reduzca el amortiguamiento o flexibilice el apoyo.")
    return float(brentq(f, b_lo, beta_max, xtol=1e-12))


def eficiencia_aislamiento(TR: float) -> float:
    """Eficiencia de aislamiento en % :  E = (1 - TR)*100."""
    return (1.0 - TR) * 100.0


def rigidez_para_beta(masa: float, omega: float, beta_objetivo: float) -> float:
    """Rigidez k necesaria para que la relación de frecuencias sea β_objetivo.

        β = w/wn  ->  wn = w/β  ->  k = m·wn² = m·(w/β)²
    """
    wn = omega / beta_objetivo
    return masa * wn ** 2


# ---------------------------------------------------------------------------
# Curvas para graficar
# ---------------------------------------------------------------------------
def curva_Rd(zetas, beta_max: float = 3.0, n: int = 1200):
    """Devuelve (beta, {zeta: Rd}) para graficar el factor de amplificación."""
    beta = np.linspace(0.0, beta_max, n)
    return beta, {z: Rd(beta, z) for z in zetas}


def curva_TR(zetas, beta_max: float = 3.0, n: int = 1200):
    """Devuelve (beta, {zeta: TR}) para graficar la transmisibilidad."""
    beta = np.linspace(0.0, beta_max, n)
    return beta, {z: transmisibilidad(beta, z) for z in zetas}


def curva_fase(zetas, beta_max: float = 3.0, n: int = 1200):
    """Devuelve (beta, {zeta: fase en grados})."""
    beta = np.linspace(0.0, beta_max, n)
    return beta, {z: np.degrees(angulo_fase(beta, z)) for z in zetas}


# ---------------------------------------------------------------------------
# Magnitudes físicas derivadas
# ---------------------------------------------------------------------------
def amplitud_permanente(p0: float, k: float, beta: float, zeta: float) -> float:
    """Amplitud del régimen permanente:  u0 = (p0/k)·Rd  [m]."""
    return (p0 / k) * float(Rd(beta, zeta))


def fuerza_transmitida_maxima(p0: float, beta: float, zeta: float) -> float:
    """Amplitud de la fuerza transmitida a la cimentación:  fT0 = p0·TR [N]."""
    return p0 * float(transmisibilidad(beta, zeta))


def fuerza_desbalance(masa_excentrica: float, excentricidad: float,
                      omega: float) -> float:
    """Amplitud de la fuerza centrífuga de una masa desbalanceada rotatoria.

        p0 = m_e · e · w²      [N]

    Depende del CUADRADO de la velocidad de giro: al duplicar las rpm la
    fuerza se cuadruplica.
    """
    return masa_excentrica * excentricidad * omega ** 2


def energia_disipada_por_ciclo(c: float, omega: float, u0: float) -> float:
    """Energía disipada por el amortiguador viscoso en un ciclo:  E_D = π·c·w·u0² [J]."""
    return math.pi * c * omega * u0 ** 2


# ---------------------------------------------------------------------------
# Betas asociados a un objetivo (problemas de diseño y ancho de banda)
# ---------------------------------------------------------------------------
def beta_para_Rd(Rd_objetivo: float, zeta: float) -> tuple[float, ...]:
    """Relaciones de frecuencia β que producen una amplificación Rd objetivo.

    Partiendo de  Rd = 1/sqrt((1-b^2)^2 + (2*z*b)^2)  y llamando x = b^2, la
    condición Rd(b) = Rd_objetivo es una CUADRÁTICA en x:

        x^2 + (4*z^2 - 2)*x + (1 - 1/Rd^2) = 0

    Devuelve las raíces β >= 0 ordenadas de menor a mayor:

    * si ``Rd_objetivo > 1`` hay dos, β1 < 1 < β2, a ambos lados de la
      resonancia (zona de amplificación);
    * si ``Rd_objetivo < 1`` solo una es físicamente real (β > sqrt(2), zona de
      aislamiento); la otra raíz da x < 0 y se descarta.

    Aplicación principal: método del ancho de banda de media potencia, donde con
    ``Rd_objetivo = Rd_maximo(zeta)/sqrt(2)`` se cumple  (β2 - β1)/2 ~= zeta.

    La identidad (β2 - β1)/2 ~= zeta es aproximada; para zeta = 5 % el error es
    de ~0.2 %, que es justamente la incertidumbre del método:

    >>> b1, b2 = beta_para_Rd(Rd_maximo(0.05) / math.sqrt(2), 0.05)
    >>> round((b2 - b1) / 2, 3)
    0.05
    >>> round(float(Rd(b2, 0.05)), 6) == round(Rd_maximo(0.05) / math.sqrt(2), 6)
    True

    Con Rd < 1 solo sobrevive la rama de aislamiento:

    >>> raices = beta_para_Rd(0.5, 0.05)
    >>> len(raices), raices[0] > math.sqrt(2)
    (1, True)
    """
    if Rd_objetivo <= 0:
        raise ValueError("El Rd objetivo debe ser positivo.")
    if zeta < 0:
        raise ValueError("La fracción de amortiguamiento no puede ser negativa.")

    b_coef = 4.0 * zeta ** 2 - 2.0
    c_coef = 1.0 - 1.0 / Rd_objetivo ** 2
    discriminante = b_coef ** 2 - 4.0 * c_coef
    if discriminante < 0:
        raise ValueError(
            f"Rd objetivo {Rd_objetivo:.4g} inalcanzable con zeta = {zeta:.4g} "
            f"(el máximo posible es {Rd_maximo(zeta):.4g}).")

    raiz = math.sqrt(discriminante)
    equis = [(-b_coef - raiz) / 2.0, (-b_coef + raiz) / 2.0]
    return tuple(sorted(math.sqrt(x) for x in equis if x >= 0.0))


def betas_para_transmisibilidad(TR_objetivo: float, zeta: float) -> tuple[float, ...]:
    """Relaciones de frecuencia β que producen una transmisibilidad TR objetivo.

    A diferencia de :func:`beta_para_transmisibilidad` — que solo devuelve la
    rama de aislamiento y exige TR < 1 — esta resuelve la cuadrática completa y
    admite también TR > 1.  Con x = b^2:

        TR^2 * x^2 + [(2*z)^2*(TR^2 - 1) - 2*TR^2] * x + (TR^2 - 1) = 0

    >>> raices = betas_para_transmisibilidad(0.3, 0.05)
    >>> len(raices), round(float(transmisibilidad(raices[0], 0.05)), 6)
    (1, 0.3)

    Con TR > 1 aparecen las dos ramas alrededor de la resonancia:

    >>> b1, b2 = betas_para_transmisibilidad(1.5, 0.10)
    >>> b1 < 1 < b2
    True
    """
    if TR_objetivo <= 0:
        raise ValueError("La TR objetivo debe ser positiva.")
    if zeta < 0:
        raise ValueError("La fracción de amortiguamiento no puede ser negativa.")

    TR2 = TR_objetivo ** 2
    a_coef = TR2
    b_coef = 4.0 * zeta ** 2 * (TR2 - 1.0) - 2.0 * TR2
    c_coef = TR2 - 1.0

    discriminante = b_coef ** 2 - 4.0 * a_coef * c_coef
    if discriminante < 0:
        raise ValueError(
            f"TR objetivo {TR_objetivo:.4g} inalcanzable con zeta = {zeta:.4g}.")

    raiz = math.sqrt(discriminante)
    equis = [(-b_coef - raiz) / (2.0 * a_coef), (-b_coef + raiz) / (2.0 * a_coef)]
    return tuple(sorted(math.sqrt(x) for x in equis if x >= 0.0))
