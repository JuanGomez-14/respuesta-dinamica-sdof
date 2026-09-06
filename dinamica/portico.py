"""
================================================================================
 dinamica.portico — Rigidez lateral de pórticos idealizados como "edificio de
                    cortante", con secciones numéricas o simbólicas
================================================================================

Hipótesis de la idealización (edificio de cortante)
---------------------------------------------------
    * las vigas son infinitamente rígidas a flexión: los nudos no rotan;
    * las columnas son axialmente inextensibles;

de modo que cada columna se comporta como un resorte lateral puro:

    k_columna = 12*E*I/H^3   (doblemente empotrada)
    k_columna =  3*E*I/H^3   (empotrada-libre / voladizo)

Las columnas y riostras de un mismo nivel trabajan en PARALELO
(K_piso = sum k_i) y los niveles se combinan en SERIE
(1/K_s = sum 1/K_piso,i).

Secciones simbólicas
--------------------
En los problemas de diseño la dimensión de la columna es la incógnita: se pide
"la sección mínima tal que K sea al menos ...". Para eso la rigidez se maneja
como POLINOMIO en una dimensión simbólica ``x``, representado como un
diccionario ``{potencia: coeficiente}``:

    >>> poli = rigidez_columna_polinomio(E=200e9, H=3.0, b=1.0, h=1.0,
    ...                                  b_simbolica=True, h_simbolica=True)
    >>> sorted(poli)          # I = b*h^3/12 con ambas simbólicas -> grado 4
    [4]

Un polinomio de grado 0 es simplemente un número: el camino numérico y el
simbólico son el mismo código.

UNIDADES: SI coherente.  E [Pa] · I [m^4] · H, b, h, L [m] · A [m^2] · k [N/m].
La dimensión simbólica ``x`` se interpreta en metros.
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping

from .sistema import rigidez_serie

__all__ = [
    "CONDICIONES", "rigidez_columna_polinomio", "rigidez_riostra",
    "sumar_polinomios", "evaluar_polinomio", "formatear_polinomio",
    "es_monomio", "rigidez_serie_niveles", "resolver_x_para_rigidez",
]

# Coeficiente de 12EI/H^3 o 3EI/H^3 según la condición de apoyo de la columna.
CONDICIONES = {
    "empotrada-empotrada": 12.0,
    "voladizo": 3.0,
}

# Polinomio = {potencia: coeficiente}.  Los coeficientes por debajo de esta
# tolerancia se descartan al combinar, para que el grado no crezca por ruido
# de punto flotante.
_TOL_COEF = 1e-12


# ===========================================================================
#  Construcción de polinomios de rigidez
# ===========================================================================
def rigidez_columna_polinomio(E: float, H: float,
                              condicion: str = "empotrada-empotrada",
                              *,
                              I: float | None = None,
                              b: float | None = None,
                              h: float | None = None,
                              b_simbolica: bool = False,
                              h_simbolica: bool = False,
                              n: int = 1) -> dict[int, float]:
    """Rigidez lateral de ``n`` columnas iguales, como polinomio en ``x``.

    La sección se define de una de dos maneras excluyentes:

    * ``I`` — inercia dada directamente [m^4]; el resultado es de grado 0.
    * ``b`` y ``h`` — sección rectangular, ``I = b*h^3/12``.  Marcando
      ``b_simbolica`` y/o ``h_simbolica``, el valor pasado actúa como
      COEFICIENTE de ``x`` (``h = 1.5*x`` se escribe ``h=1.5,
      h_simbolica=True``).  El grado resultante es ``1*b_simb + 3*h_simb``.

    Parámetros
    ----------
    E : módulo de elasticidad [Pa]
    H : altura libre de la columna [m]
    condicion : 'empotrada-empotrada' (coef=12) o 'voladizo' (coef=3)
    n : número de columnas iguales en paralelo

    Columna numérica: reproduce exactamente 12*E*I/H^3.

    >>> poli = rigidez_columna_polinomio(200e9, 3.0, I=1e-4)
    >>> round(poli[0] / 1e6, 3)
    8.889

    Sección cuadrada simbólica b = h = x  ->  I = x^4/12, grado 4:

    >>> poli = rigidez_columna_polinomio(200e9, 3.0, b=1.0, h=1.0,
    ...                                  b_simbolica=True, h_simbolica=True)
    >>> sorted(poli)
    [4]
    >>> round(evaluar_polinomio(poli, 0.30) / 1e6, 3)   # x = 30 cm
    60.0
    """
    if condicion not in CONDICIONES:
        raise ValueError(
            f"Condición '{condicion}' no válida. Use: {list(CONDICIONES)}")
    if H <= 0:
        raise ValueError("La altura H de la columna debe ser positiva (m).")
    if E <= 0:
        raise ValueError("El módulo de elasticidad E debe ser positivo (Pa).")
    if n <= 0:
        raise ValueError("El número de columnas debe ser al menos 1.")

    if I is not None:
        if b is not None or h is not None:
            raise ValueError(
                "Defina la sección por inercia I o por b y h, no por ambas.")
        if I <= 0:
            raise ValueError("La inercia I debe ser positiva (m^4).")
        coef_I, grado = float(I), 0
    else:
        if b is None or h is None:
            raise ValueError(
                "Para una sección rectangular se requieren b y h (o bien I).")
        if b <= 0 or h <= 0:
            raise ValueError("Las dimensiones b y h deben ser positivas.")
        # I = b*h^3/12.  Si b y/o h son coeficientes de x, sus potencias suman.
        coef_I = b * h ** 3 / 12.0
        grado = (1 if b_simbolica else 0) + (3 if h_simbolica else 0)

    k = n * CONDICIONES[condicion] * E * coef_I / H ** 3
    return {grado: k}


def rigidez_riostra(A: float, E: float, L_h: float, L_v: float) -> dict[int, float]:
    """Aporte de rigidez lateral de una riostra diagonal, como polinomio grado 0.

    La diagonal solo aporta la componente horizontal de su rigidez axial:

        L_r = sqrt(L_h^2 + L_v^2)          (Pitágoras)
        k   = (A*E/L_r) * cos^2(theta),     cos(theta) = L_h/L_r

    Parámetros
    ----------
    A   : área de la sección de la riostra [m^2]
    E   : módulo de elasticidad de la riostra [Pa]
    L_h : proyección horizontal de la diagonal [m]
    L_v : proyección vertical de la diagonal [m]

    Diagonal 3-4-5 (L_r = 5 m), con A*E/L_r = 1 N/m y cos^2 = (4/5)^2 = 0.64:

    >>> k = rigidez_riostra(A=5.0/200e9, E=200e9, L_h=4.0, L_v=3.0)
    >>> round(k[0], 6)
    0.64
    """
    if A <= 0 or E <= 0:
        raise ValueError("El área A y el módulo E de la riostra deben ser positivos.")
    if L_h <= 0 or L_v <= 0:
        raise ValueError("Las proyecciones L_h y L_v deben ser positivas (m).")

    L_r = math.hypot(L_h, L_v)
    cos_theta = L_h / L_r
    return {0: (A * E / L_r) * cos_theta ** 2}


# ===========================================================================
#  Álgebra de polinomios
# ===========================================================================
def sumar_polinomios(polinomios: Iterable[Mapping[int, float]]) -> dict[int, float]:
    """Suma polinomios: combinación en PARALELO de elementos de un mismo nivel.

    >>> sumar_polinomios([{0: 100.0}, {0: 50.0}, {2: 7.0}])
    {0: 150.0, 2: 7.0}
    """
    total: dict[int, float] = {}
    for poli in polinomios:
        for potencia, coef in poli.items():
            total[potencia] = total.get(potencia, 0.0) + float(coef)
    return {p: c for p, c in sorted(total.items()) if abs(c) > _TOL_COEF}


def evaluar_polinomio(poli: Mapping[int, float], x: float) -> float:
    """Evalúa el polinomio en un valor numérico de ``x`` [m].

    >>> evaluar_polinomio({0: 10.0, 2: 3.0}, 2.0)
    22.0
    """
    return sum(coef * x ** potencia for potencia, coef in poli.items())


def es_monomio(poli: Mapping[int, float]) -> bool:
    """¿El polinomio tiene un solo término? Habilita el despeje en forma cerrada.

    >>> es_monomio({4: 3.0}), es_monomio({0: 1.0, 4: 3.0})
    (True, False)
    """
    return len(poli) == 1


def formatear_polinomio(poli: Mapping[int, float], variable: str = "x") -> str:
    """Representación legible, para mostrar el procedimiento al usuario.

    >>> formatear_polinomio({0: 1500.0, 4: 2.5})
    '1500 + 2.5·x⁴'
    """
    if not poli:
        return "0"
    superindices = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    partes = []
    for potencia, coef in sorted(poli.items()):
        num = f"{coef:.6g}"
        if potencia == 0:
            partes.append(num)
        elif potencia == 1:
            partes.append(f"{num}·{variable}")
        else:
            partes.append(f"{num}·{variable}{str(potencia).translate(superindices)}")
    return " + ".join(partes)


# ===========================================================================
#  Combinación de niveles y despeje de la incógnita
# ===========================================================================
def rigidez_serie_niveles(niveles: Iterable[Mapping[int, float]], x: float) -> float:
    """Rigidez lateral equivalente K_s [N/m] de varios niveles en SERIE.

    Cada nivel es el polinomio de rigidez de piso ya combinado en paralelo.
    Se evalúa en ``x`` y se combinan con :func:`dinamica.sistema.rigidez_serie`.

    Dos niveles idénticos en serie dan la mitad de la rigidez de uno:

    >>> rigidez_serie_niveles([{0: 1000.0}, {0: 1000.0}], x=0.0)
    500.0
    """
    valores = [evaluar_polinomio(poli, x) for poli in niveles]
    if not valores:
        raise ValueError("Se requiere al menos un nivel.")
    if any(v <= 0 for v in valores):
        raise ValueError(
            f"Con x = {x:g} m algún nivel resultó con rigidez de piso <= 0; "
            "revise las dimensiones de la sección.")
    return rigidez_serie(valores)


def resolver_x_para_rigidez(niveles: Iterable[Mapping[int, float]],
                            K_objetivo: float,
                            *, x_max: float = 1.0e4) -> tuple[float, str]:
    """Despeja la dimensión ``x`` [m] que produce la rigidez ``K_objetivo`` [N/m].

    Devuelve ``(x, procedimiento)``, donde ``procedimiento`` describe cómo se
    obtuvo el valor, para poder transcribirlo al desarrollo del ejercicio.

    Estrategia
    ----------
    * Si hay UN solo nivel y su polinomio es un monomio ``C*x^n``, se despeja en
      forma cerrada:  ``x = (K/C)^(1/n)``.
    * Si TODOS los niveles son monomios de la MISMA potencia ``n``, la serie se
      reduce igual a un monomio, porque
      ``1/(C1 x^n) + 1/(C2 x^n) = (1/C1 + 1/C2) x^-n``; también hay forma cerrada.
    * En cualquier otro caso se usa bisección. ``K_s(x)`` es estrictamente
      creciente en ``x`` (todos los coeficientes son positivos), de modo que la
      raíz es única y la bisección converge.

    Forma cerrada, un nivel con sección cuadrada simbólica:

    >>> poli = rigidez_columna_polinomio(200e9, 3.0, b=1.0, h=1.0,
    ...                                  b_simbolica=True, h_simbolica=True, n=4)
    >>> K = evaluar_polinomio(poli, 0.35)
    >>> x, como = resolver_x_para_rigidez([poli], K)
    >>> round(x, 6)
    0.35
    >>> como.startswith('forma cerrada')
    True

    Viaje de ida y vuelta con dos niveles distintos (bisección):

    >>> a = rigidez_columna_polinomio(200e9, 3.0, b=1.0, h=1.0,
    ...                               b_simbolica=True, h_simbolica=True)
    >>> b = rigidez_columna_polinomio(200e9, 4.0, b=1.0, h=1.0,
    ...                               b_simbolica=True, h_simbolica=True)
    >>> K = rigidez_serie_niveles([a, b], 0.42)
    >>> x, _ = resolver_x_para_rigidez([a, b], K)
    >>> round(x, 6)
    0.42
    """
    niveles = list(niveles)
    if not niveles:
        raise ValueError("Se requiere al menos un nivel.")
    if K_objetivo <= 0:
        raise ValueError("La rigidez objetivo debe ser positiva (N/m).")

    # --- Camino en forma cerrada -------------------------------------------
    if all(es_monomio(p) for p in niveles):
        potencias = {next(iter(p)) for p in niveles}
        if len(potencias) == 1:
            n = potencias.pop()
            if n > 0:
                # Serie de monomios de igual potencia -> monomio de esa potencia.
                C = rigidez_serie([next(iter(p.values())) for p in niveles])
                x = (K_objetivo / C) ** (1.0 / n)
                if x > x_max:
                    raise ValueError(
                        f"La rigidez objetivo {K_objetivo:.6g} N/m exigiría "
                        f"x = {x:.6g} m, que excede el límite x_max = {x_max:g} m. "
                        "Revise que sea físicamente alcanzable.")
                return x, (f"forma cerrada: K(x) = {C:.6g}·x^{n} = "
                           f"{K_objetivo:.6g} N/m  ->  "
                           f"x = (K/{C:.6g})^(1/{n}) = {x:.6g} m")

    # --- Camino numérico: bisección ----------------------------------------
    def K_de(x: float) -> float:
        return rigidez_serie_niveles(niveles, x)

    if all(next(iter(p)) == 0 for p in niveles if es_monomio(p)) and \
            all(max(p) == 0 for p in niveles):
        raise ValueError(
            "Ningún nivel depende de x: la rigidez es constante y no hay nada "
            "que despejar. Marque b y/o h como simbólicas.")

    lo, hi = 1e-9, 1e-9
    K_hi = K_de(hi)
    pasos = 0
    while K_hi < K_objetivo and hi < x_max:
        lo, hi = hi, hi * 4.0
        K_hi = K_de(hi)
        pasos += 1
        if pasos > 200:  # pragma: no cover - salvaguarda
            break
    if K_hi < K_objetivo:
        raise ValueError(
            f"La rigidez objetivo {K_objetivo:.6g} N/m no se alcanza ni con "
            f"x = {x_max:g} m. Revise que sea físicamente alcanzable.")

    for _ in range(200):
        medio = 0.5 * (lo + hi)
        if K_de(medio) < K_objetivo:
            lo = medio
        else:
            hi = medio
        if hi - lo < 1e-14 * max(1.0, hi):
            break
    x = 0.5 * (lo + hi)
    return x, (f"bisección: x = {x:.6g} m  ->  verificación K(x) = "
               f"{K_de(x):.6g} N/m (objetivo {K_objetivo:.6g} N/m)")
