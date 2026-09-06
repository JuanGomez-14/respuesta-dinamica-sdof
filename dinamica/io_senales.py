"""
Entrada/salida de señales: lectura de excitaciones arbitrarias definidas por el
usuario y generación de registros sintéticos para pruebas.

Formatos soportados
-------------------
* CSV / TXT de dos columnas  ->  ``leer_csv``
      tiempo, valor            (valor = aceleración, desplazamiento o fuerza)
* Formato PEER NGA (.AT2)    ->  ``leer_peer_at2``
      cabecera de 4 líneas + NPTS/DT + valores en g
* Serie de DESPLAZAMIENTOS del terreno -> ``derivar_aceleracion``

Utilidades
----------
* ``corregir_linea_base``  : elimina la deriva de un acelerograma
* ``filtrar_paso_alto``    : filtro Butterworth de fase cero
* ``remuestrear``          : cambia el paso de tiempo por interpolación lineal
* ``generar_registro_sintetico`` : acelerograma artificial tipo sismo
  (ruido blanco filtrado con filtro de Kanai-Tajimi + envolvente de Jennings),
  reproducible mediante ``semilla``.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

from .cargas import CargaArbitraria, ExcitacionBase
from .unidades import a_si

__all__ = [
    "leer_csv", "leer_peer_at2", "escribir_csv",
    "corregir_linea_base", "filtrar_paso_alto", "remuestrear",
    "derivar_aceleracion", "generar_registro_sintetico",
    "excitacion_desde_csv", "carga_desde_csv",
]


# ===========================================================================
#  Lectura
# ===========================================================================
def leer_csv(ruta: str | Path, columna_tiempo: int = 0, columna_valor: int = 1,
             separador: str = ",", saltar_filas: int = 0,
             unidad_valor: str = "m/s2") -> tuple[np.ndarray, np.ndarray]:
    """Lee un archivo de dos columnas (tiempo, valor).

    Las líneas que empiezan por '#' o que no se puedan convertir a número se
    ignoran (permite encabezados). ``unidad_valor`` convierte automáticamente
    a SI (por ejemplo 'g', 'gal', 'cm/s2', 'mm').

    Devuelve (t [s], valores [SI]).
    """
    t_list: list[float] = []
    v_list: list[float] = []
    with open(ruta, "r", encoding="utf-8-sig") as fh:
        for i, linea in enumerate(fh):
            if i < saltar_filas:
                continue
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            partes = [p for p in linea.replace(";", separador).split(separador) if p != ""]
            if len(partes) <= max(columna_tiempo, columna_valor):
                partes = linea.split()
            try:
                t_list.append(float(partes[columna_tiempo]))
                v_list.append(float(partes[columna_valor]))
            except (ValueError, IndexError):
                continue   # encabezado u otra línea no numérica
    if not t_list:
        raise ValueError(f"No se encontraron datos numéricos en {ruta}")
    t = np.array(t_list, dtype=float)
    v = np.array(v_list, dtype=float) * a_si(1.0, unidad_valor)
    return t, v


def leer_peer_at2(ruta: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Lee un acelerograma en formato PEER NGA (.AT2). Devuelve (t [s], ag [m/s²]).

    La cuarta línea contiene 'NPTS=   xxxx, DT=   x.xxxx SEC' y los valores
    están dados en fracción de g.
    """
    lineas = Path(ruta).read_text(encoding="utf-8", errors="ignore").splitlines()
    npts = dt = None
    inicio = 0
    for i, ln in enumerate(lineas[:10]):
        if "NPTS" in ln.upper():
            texto = ln.upper().replace("=", " ").replace(",", " ")
            campos = texto.split()
            npts = int(float(campos[campos.index("NPTS") + 1]))
            dt = float(campos[campos.index("DT") + 1])
            inicio = i + 1
            break
    if npts is None:
        raise ValueError("No se encontró la línea con NPTS y DT (formato PEER .AT2)")
    valores: list[float] = []
    for ln in lineas[inicio:]:
        valores.extend(float(x) for x in ln.split())
    ag = np.array(valores[:npts], dtype=float) * 9.80665   # g -> m/s²
    t = dt * np.arange(ag.size)
    return t, ag


def excitacion_desde_csv(ruta: str | Path, unidad_valor: str = "g",
                         nombre: str | None = None, **kwargs) -> ExcitacionBase:
    """Construye una :class:`ExcitacionBase` a partir de un CSV (t, aceleración)."""
    t, ag = leer_csv(ruta, unidad_valor=unidad_valor, **kwargs)
    return ExcitacionBase(t, ag, nombre=nombre or Path(ruta).stem)


def carga_desde_csv(ruta: str | Path, unidad_valor: str = "N",
                    nombre: str | None = None, **kwargs) -> CargaArbitraria:
    """Construye una :class:`CargaArbitraria` a partir de un CSV (t, fuerza)."""
    t, p = leer_csv(ruta, unidad_valor=unidad_valor, **kwargs)
    return CargaArbitraria(t, p, nombre=nombre or Path(ruta).stem)


def escribir_csv(ruta: str | Path, t: np.ndarray, v: np.ndarray,
                 encabezado: tuple[str, str] = ("t [s]", "valor")) -> Path:
    """Guarda una señal de dos columnas en CSV."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(encabezado)
        for ti, vi in zip(t, v):
            w.writerow([f"{ti:.6f}", f"{vi:.8f}"])
    return ruta


# ===========================================================================
#  Procesamiento
# ===========================================================================
def corregir_linea_base(t: np.ndarray, ag: np.ndarray, grado: int = 1) -> np.ndarray:
    """Corrección de línea base: resta un polinomio ajustado por mínimos cuadrados.

    Evita que la doble integración del acelerograma produzca derivas
    artificiales de velocidad y desplazamiento del terreno.
    """
    coef = np.polyfit(t, ag, grado)
    return ag - np.polyval(coef, t)


def filtrar_paso_alto(ag: np.ndarray, dt: float, f_corte: float = 0.1,
                      orden: int = 4) -> np.ndarray:
    """Filtro Butterworth paso alto de fase cero (filtfilt)."""
    from scipy.signal import butter, filtfilt

    fs = 1.0 / dt
    b, a = butter(orden, f_corte / (fs / 2.0), btype="highpass")
    return filtfilt(b, a, ag)


def remuestrear(t: np.ndarray, v: np.ndarray, dt_nuevo: float) -> tuple[np.ndarray, np.ndarray]:
    """Remuestrea la señal a un paso uniforme ``dt_nuevo`` por interpolación lineal."""
    t_nuevo = np.arange(t[0], t[-1] + 1e-12, dt_nuevo)
    return t_nuevo, np.interp(t_nuevo, t, v)


def derivar_aceleracion(t: np.ndarray, ug: np.ndarray) -> np.ndarray:
    """Obtiene la aceleración del terreno a partir del DESPLAZAMIENTO del terreno.

    Se aplica doble derivación numérica de segundo orden. Útil cuando la señal
    disponible es un registro de desplazamientos, como permite el enunciado del
    laboratorio ('un vector de tiempo y un vector de aceleraciones o
    desplazamientos').
    """
    v = np.gradient(ug, t, edge_order=2)
    return np.gradient(v, t, edge_order=2)


# ===========================================================================
#  Generación de un registro sintético reproducible
# ===========================================================================
def generar_registro_sintetico(duracion: float = 30.0, dt: float = 0.01,
                               pga_objetivo: float = 0.25 * 9.80665,
                               f_suelo: float = 2.5, zeta_suelo: float = 0.6,
                               t_subida: float = 2.0, t_meseta: float = 10.0,
                               decaimiento: float = 0.25,
                               semilla: int = 2026,
                               nombre: str = "Registro sintético (Kanai-Tajimi)"
                               ) -> ExcitacionBase:
    """Genera un acelerograma artificial reproducible para pruebas y ejemplos.

    Procedimiento
    -------------
    1. Ruido blanco gaussiano (semilla fija -> resultados repetibles).
    2. Filtro de Kanai-Tajimi (modelo del suelo como un oscilador de 1 GDL de
       frecuencia ``f_suelo`` y amortiguamiento ``zeta_suelo``), que da al
       registro un contenido frecuencial realista.
    3. Envolvente de Jennings (subida cuadrática, meseta y decaimiento
       exponencial) para reproducir la no estacionariedad del sismo.
    4. Corrección de línea base + filtro paso alto (0.25 Hz), que elimina la
       deriva de baja frecuencia y produce velocidades y desplazamientos del
       terreno realistas al integrar el registro.
    5. Escalado a la PGA objetivo.

    ADVERTENCIA: es una señal ARTIFICIAL de demostración; para un trabajo
    definitivo conviene sustituirla por un registro real (por ejemplo un
    archivo .AT2 de la base PEER, leído con ``leer_peer_at2``).
    """
    rng = np.random.default_rng(semilla)
    n = int(round(duracion / dt)) + 1
    t = dt * np.arange(n)

    ruido = rng.standard_normal(n)

    # --- filtro de Kanai-Tajimi resuelto como un oscilador de 1 GDL --------
    wg = 2.0 * math.pi * f_suelo
    zg = zeta_suelo
    x = np.zeros(n)
    v = np.zeros(n)
    for i in range(n - 1):        # integración explícita sencilla (paso muy fino)
        acc = ruido[i] - 2.0 * zg * wg * v[i] - wg ** 2 * x[i]
        v[i + 1] = v[i] + dt * acc
        x[i + 1] = x[i] + dt * v[i + 1]
    ag = 2.0 * zg * wg * v + wg ** 2 * x     # salida del filtro K-T

    # --- envolvente de Jennings ------------------------------------------
    env = np.ones(n)
    subida = t < t_subida
    env[subida] = (t[subida] / t_subida) ** 2
    caida = t > (t_subida + t_meseta)
    env[caida] = np.exp(-decaimiento * (t[caida] - (t_subida + t_meseta)))
    ag = ag * env

    # --- corrección y escalado -------------------------------------------
    ag = corregir_linea_base(t, ag, grado=1)
    ag = filtrar_paso_alto(ag, dt, f_corte=0.25)
    ag = ag * (pga_objetivo / np.max(np.abs(ag)))

    exc = ExcitacionBase(t, ag, nombre=nombre)
    exc.metadatos.update(semilla=semilla, f_suelo=f_suelo, zeta_suelo=zeta_suelo,
                         sintetico=True)
    return exc


def leer_excel(ruta, hoja=0, columna_t: int = 0, columna_y: int = 1):
    """Lee una serie temporal (t, y) de un archivo Excel (.xlsx / .xls).

    Complementa a :func:`leer_csv` para el caso habitual en el curso: el
    profesor entrega la tabla del ensayo en una hoja de cálculo.

    Se descartan las filas cuyas celdas no sean numéricas, de modo que los
    encabezados y las notas al pie no estorban.

    Parámetros
    ----------
    ruta      : ruta del archivo
    hoja      : nombre o índice de la hoja (por defecto, la primera)
    columna_t : índice de la columna de tiempo [s]
    columna_y : índice de la columna de la magnitud medida

    Devuelve ``(t, y)`` como arreglos de numpy.
    """
    import numpy as _np
    import pandas as _pd

    tabla = _pd.read_excel(ruta, sheet_name=hoja, header=None)
    if tabla.shape[1] <= max(columna_t, columna_y):
        raise ValueError(
            f"La hoja tiene {tabla.shape[1]} columna(s); se requieren al menos "
            f"{max(columna_t, columna_y) + 1} para leer (t, y).")

    t = _pd.to_numeric(tabla.iloc[:, columna_t], errors="coerce")
    y = _pd.to_numeric(tabla.iloc[:, columna_y], errors="coerce")
    validas = t.notna() & y.notna()
    if not validas.any():
        raise ValueError(
            "No se encontró ninguna fila con dos valores numéricos. Revise que "
            "las columnas de tiempo y medida sean las correctas.")
    return _np.asarray(t[validas], dtype=float), _np.asarray(y[validas], dtype=float)
