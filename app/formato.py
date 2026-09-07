"""
Formato de números para la interfaz.

Dos problemas distintos, con dos soluciones distintas:

**Campos de entrada.** Streamlit exige una cadena de formato tipo printf y, si
no se le da, usa ``%0.2f``: escribir 24 se ve como «24,00» y 0.34 como
«0,34000». Con :data:`FORMATO_ENTRADA` el campo muestra lo que el usuario
escribió —24 se ve «24»— sin dejar de admitir decimales cuando los hay, y sin
irse a notación científica con valores grandes como una rigidez de 8 266 635.

**Textos de salida.** Un resultado como ``12236.6`` es difícil de leer de un
vistazo. :func:`numero` lo escribe «12.237», con separador de miles y sin
decimales que no aportan.

Convención de separadores: miles con punto y decimales con coma, que es la
colombiana y además la que ya usan los campos de Streamlit al renderizarse con
la configuración regional del navegador. Así la barra lateral es coherente
consigo misma.
"""

from __future__ import annotations

import math

__all__ = ["FORMATO_ENTRADA", "numero", "con_unidad", "compacto"]

# %.10g: hasta 10 cifras significativas, sin ceros de relleno y sin pasar a
# notación científica salvo en valores realmente extremos.
FORMATO_ENTRADA = "%.10g"


CIFRAS_SIGNIFICATIVAS = 4


def _decimales_automaticos(magnitud: float) -> int:
    """Decimales necesarios para mostrar 4 cifras significativas.

    El criterio son las cifras significativas y no un número fijo de decimales,
    porque en esta herramienta conviven magnitudes de escalas muy distintas: una
    rigidez de 8 266 636 N/m no necesita decimales, pero un desplazamiento de
    0,0003829 m se convertiría en 0,0004 y perdería justo la información útil.
    """
    if magnitud == 0:
        return 0
    decimales = CIFRAS_SIGNIFICATIVAS - 1 - math.floor(math.log10(magnitud))
    return max(0, decimales)


def numero(valor, decimales: int | None = None) -> str:
    """Formatea un número para leerlo de un vistazo.

    >>> numero(12236.6)
    '12.237'
    >>> numero(8266635.57)
    '8.266.636'
    >>> numero(24.0)
    '24'
    >>> numero(0.34)
    '0,34'
    >>> numero(0.05678, 4)
    '0,0568'

    Los valores extremos pasan a notación científica, porque un número con
    quince ceros no se lee mejor con puntos de miles:

    >>> numero(3.5e-7)
    '3,5e-07'

    Los no numéricos no revientan: se muestran como un guion.

    >>> numero(float('nan')), numero(None)
    ('—', '—')
    """
    if valor is None:
        return "—"
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(valor):
        return "—"

    magnitud = abs(valor)
    if magnitud != 0 and (magnitud >= 1e12 or magnitud < 1e-4):
        texto = f"{valor:.6g}"
        return texto.replace(".", ",")

    if decimales is None:
        decimales = _decimales_automaticos(magnitud)

    texto = f"{valor:,.{decimales}f}"
    if "." in texto:                      # los decimales de relleno no aportan
        texto = texto.rstrip("0").rstrip(".")
    # De la convención inglesa (miles ",", decimales ".") a la colombiana.
    return texto.translate(str.maketrans({",": ".", ".": ","}))


def con_unidad(valor, unidad: str, decimales: int | None = None) -> str:
    """Igual que :func:`numero`, con la unidad pegada al final.

    >>> con_unidad(12236.6, "kg")
    '12.237 kg'
    >>> con_unidad(0.34, "s")
    '0,34 s'
    """
    texto = numero(valor, decimales)
    return f"{texto} {unidad}".strip()


# Equivalencias hacia una unidad mayor, para no leer siete dígitos seguidos.
# (unidad_original, factor, unidad_grande)
_ESCALAS = [
    ("N/m", 1e3, "kN/m"),
    ("N", 1e3, "kN"),
    ("kg", 1e3, "t"),
    ("Pa", 1e9, "GPa"),
    ("N·s/m", 1e3, "kN·s/m"),
]


def compacto(valor: float, unidad: str) -> str:
    """Escribe el valor en una unidad mayor cuando el número es largo.

    Un valor como 8 266 600 N/m obliga a contar dígitos; los mismos datos en
    kN/m se leen de un vistazo. Solo se cambia de unidad si el número lo pide
    (a partir de cuatro dígitos) y si el resultado no queda demasiado pequeño.

    >>> compacto(8266600, "N/m")
    '8.267 kN/m'
    >>> compacto(24000, "kg")
    '24 t'

    Si el número ya es cómodo, se deja como está:

    >>> compacto(150, "N")
    '150 N'
    >>> compacto(0.34, "s")
    '0,34 s'
    """
    for original, factor, grande in _ESCALAS:
        if unidad == original and abs(valor) >= 1e4:
            escalado = valor / factor
            if abs(escalado) >= 1:
                return f"{numero(escalado)} {grande}"
    return con_unidad(valor, unidad)
