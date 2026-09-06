"""
Unidades y constantes del laboratorio.

CONVENCIÓN GENERAL DEL MOTOR DE CÁLCULO
---------------------------------------
Internamente TODO se maneja en el Sistema Internacional (SI) coherente:

    masa .......................... kg
    rigidez ....................... N/m
    amortiguamiento ............... N*s/m
    fuerza ........................ N
    longitud / desplazamiento ..... m
    velocidad ..................... m/s
    aceleración ................... m/s^2
    tiempo ........................ s
    frecuencia circular ........... rad/s
    frecuencia ciclica ............ Hz  (1 Hz = 1 ciclo/s)
    módulo de elasticidad ......... Pa = N/m^2
    inercia de sección ............ m^4

Las funciones de conversión de este módulo permiten ingresar datos en las
unidades usuales de ingeniería civil (toneladas, kN, mm, GPa, cm^4, rpm, g)
y presentar los resultados en unidades legibles (mm, kN, %g).

Regla de oro: *convertir en la entrada, calcular en SI, convertir en la salida.*
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Constantes físicas
# ---------------------------------------------------------------------------
G = 9.80665  # aceleración de la gravedad [m/s^2]

# ---------------------------------------------------------------------------
# Factores de conversión ->  (multiplicar el valor por el factor para pasar a SI)
# ---------------------------------------------------------------------------
FACTORES_A_SI = {
    # masa -> kg
    "kg": 1.0,
    "t": 1.0e3,          # tonelada métrica
    "ton": 1.0e3,
    "Mg": 1.0e3,
    "kg*s2/m": 1.0,      # (unidad técnica, equivalente numérico a kg en SI)
    # fuerza -> N
    "N": 1.0,
    "kN": 1.0e3,
    "MN": 1.0e6,
    "kgf": G,
    "tonf": 1.0e3 * G,
    # longitud -> m
    "m": 1.0,
    "cm": 1.0e-2,
    "mm": 1.0e-3,
    # rigidez -> N/m
    "N/m": 1.0,
    "kN/m": 1.0e3,
    "kN/mm": 1.0e6,
    "tonf/m": 1.0e3 * G,
    # presión / módulo -> Pa
    "Pa": 1.0,
    "kPa": 1.0e3,
    "MPa": 1.0e6,
    "GPa": 1.0e9,
    # inercia -> m^4
    "m4": 1.0,
    "cm4": 1.0e-8,
    "mm4": 1.0e-12,
    # área -> m^2
    "m2": 1.0,
    "cm2": 1.0e-4,
    "mm2": 1.0e-6,
    # aceleración -> m/s^2
    "m/s2": 1.0,
    "cm/s2": 1.0e-2,
    "gal": 1.0e-2,       # 1 gal = 1 cm/s^2
    "g": G,
}


def a_si(valor: float, unidad: str) -> float:
    """Convierte ``valor`` expresado en ``unidad`` a unidades SI coherentes.

    >>> a_si(30, "t")        # 30 toneladas -> kg
    30000.0
    >>> round(a_si(0.25, "g"), 4)   # 0.25 g -> m/s^2
    2.4517
    """
    try:
        return float(valor) * FACTORES_A_SI[unidad]
    except KeyError as exc:  # pragma: no cover - mensaje de ayuda
        raise KeyError(
            f"Unidad '{unidad}' no reconocida. Disponibles: "
            f"{sorted(FACTORES_A_SI)}"
        ) from exc


def desde_si(valor: float, unidad: str) -> float:
    """Convierte un valor en SI a la ``unidad`` indicada (operación inversa)."""
    return float(valor) / FACTORES_A_SI[unidad]


# ---------------------------------------------------------------------------
# Conversiones de frecuencia
# ---------------------------------------------------------------------------
def rpm_a_rad_s(rpm: float) -> float:
    """Revoluciones por minuto -> frecuencia circular [rad/s]."""
    return 2.0 * math.pi * rpm / 60.0


def rpm_a_hz(rpm: float) -> float:
    """Revoluciones por minuto -> frecuencia cíclica [Hz]."""
    return rpm / 60.0


def hz_a_rad_s(f: float) -> float:
    return 2.0 * math.pi * f


def rad_s_a_hz(w: float) -> float:
    return w / (2.0 * math.pi)


# ---------------------------------------------------------------------------
# Ayudas de presentación
# ---------------------------------------------------------------------------
def m_a_mm(x: float) -> float:
    return x * 1.0e3


def n_a_kn(x: float) -> float:
    return x * 1.0e-3


def ms2_a_g(x: float) -> float:
    return x / G


def fmt(valor: float, decimales: int = 3) -> str:
    """Formato numérico compacto y legible para tablas y reportes."""
    if valor == 0:
        return "0"
    a = abs(valor)
    if a >= 1e5 or a < 1e-3:
        return f"{valor:.{decimales}e}"
    return f"{valor:,.{decimales}f}"


TABLA_UNIDADES = """\
ENTRADAS (lo que usted ingresa)              SALIDAS (lo que entrega el motor)
------------------------------------------   ----------------------------------------
masa m .................. kg  (o t con a_si) desplazamiento u(t) ......... m  (y mm)
rigidez k ............... N/m                velocidad u'(t) ............. m/s
fracción de amort. z .... adimensional       aceleración u''(t) .......... m/s^2 (y g)
carga p(t) .............. N                  fuerza elástica f_s = k*u ... N  (y kN)
aceleración del suelo ... m/s^2 (o g)        cortante basal V ............ N  (y kN)
tiempo t ................ s                  factores Rd, Rv, Ra, TR ..... adimensional
frecuencia w ............ rad/s (o Hz, rpm)  periodo Tn .................. s
"""
