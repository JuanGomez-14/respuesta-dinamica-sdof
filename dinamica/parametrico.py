"""
Análisis paramétrico: efecto sistemático de las variables que gobiernan la
respuesta dinámica (masa, rigidez, amortiguamiento, relación de frecuencias,
amplitud y duración de la carga, condiciones iniciales).

Todas las funciones devuelven un :class:`ResultadoBarrido`, que contiene la
tabla de resultados lista para graficar, imprimir o exportar a CSV.

Métricas registradas para cada valor del parámetro
--------------------------------------------------
    u_max     desplazamiento máximo |u|max          [m]
    v_max     velocidad máxima                       [m/s]
    a_max     aceleración relativa máxima            [m/s²]
    a_abs_max aceleración absoluta máxima            [m/s²]
    V_max     cortante basal máximo k·|u|max         [N]
    fT_max    fuerza máxima transmitida al apoyo     [N]
    Rd        factor de amplificación dinámica       [-]
    Tn, fn    periodo y frecuencia natural           [s], [Hz]
    beta      relación de frecuencias (si aplica)    [-]
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np

from .cargas import Carga, CargaArmonica, ExcitacionBase
from .sistema import SistemaSDOF
from .solucionadores import Respuesta, resolver, resolver_base

__all__ = ["ResultadoBarrido", "barrido_parametro", "barrido_carga",
           "barrido_sismico", "metricas", "sensibilidad"]


# ---------------------------------------------------------------------------
def metricas(respuesta: Respuesta, p0: float | None = None) -> dict:
    """Extrae de una respuesta el conjunto estándar de indicadores."""
    s = respuesta.sistema
    d = {
        "u_max [m]": respuesta.u_max,
        "u_max [mm]": respuesta.u_max * 1e3,
        "v_max [m/s]": respuesta.v_max,
        "a_max [m/s2]": respuesta.a_max,
        "a_abs_max [m/s2]": respuesta.a_abs_max,
        "V_max [kN]": respuesta.cortante_max / 1e3,
        "fT_max [kN]": respuesta.fuerza_transmitida_max / 1e3,
        "t(u_max) [s]": respuesta.t_u_max,
        "Tn [s]": s.T_n,
        "fn [Hz]": s.f_n,
        "zeta [-]": s.zeta,
        "m [kg]": s.masa,
        "k [N/m]": s.rigidez,
    }
    try:
        d["Rd [-]"] = respuesta.factor_amplificacion(p0)
    except Exception:
        d["Rd [-]"] = float("nan")
    return d


@dataclass
class ResultadoBarrido:
    """Tabla de resultados de un barrido paramétrico."""

    parametro: str
    valores: np.ndarray
    filas: list[dict]
    respuestas: list[Respuesta] = field(default_factory=list)
    descripcion: str = ""

    def columna(self, nombre: str) -> np.ndarray:
        """Extrae una columna de la tabla como arreglo de numpy."""
        if nombre not in self.filas[0]:
            raise KeyError(f"Columna '{nombre}' no existe. Disponibles: "
                           f"{list(self.filas[0])}")
        return np.array([f[nombre] for f in self.filas], dtype=float)

    @property
    def columnas(self) -> list[str]:
        return list(self.filas[0])

    def tabla_texto(self, columnas: Sequence[str] | None = None,
                    decimales: int = 4) -> str:
        """Tabla en texto plano lista para imprimir en consola o en el reporte."""
        columnas = list(columnas or ["u_max [mm]", "V_max [kN]", "Rd [-]", "Tn [s]"])
        anchos = [max(len(self.parametro), 12)] + [max(len(c), 12) for c in columnas]
        sep = "  "
        lineas = [sep.join(h.ljust(w) for h, w in zip([self.parametro] + columnas, anchos)),
                  sep.join("-" * w for w in anchos)]
        for val, fila in zip(self.valores, self.filas):
            celdas = [f"{val:.4g}".ljust(anchos[0])]
            for c, w in zip(columnas, anchos[1:]):
                celdas.append(f"{fila[c]:.{decimales}g}".ljust(w))
            lineas.append(sep.join(celdas))
        return "\n".join(lineas)

    def submuestrear(self, paso: int = 2) -> "ResultadoBarrido":
        """Devuelve el mismo barrido tomando una de cada ``paso`` filas.

        Útil para imprimir tablas legibles cuando el barrido tiene muchos puntos
        (la figura se sigue trazando con todos los valores).
        """
        idx = list(range(0, len(self.filas), paso))
        if idx[-1] != len(self.filas) - 1:
            idx.append(len(self.filas) - 1)
        return ResultadoBarrido(
            parametro=self.parametro,
            valores=self.valores[idx],
            filas=[self.filas[i] for i in idx],
            respuestas=[self.respuestas[i] for i in idx] if self.respuestas else [],
            descripcion=self.descripcion,
        )

    def a_csv(self, ruta: str | Path) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow([self.parametro] + self.columnas)
            for val, fila in zip(self.valores, self.filas):
                w.writerow([val] + [fila[c] for c in self.columnas])
        return ruta

    def variacion(self, columna: str = "u_max [mm]") -> dict:
        """Resumen de la variación de una métrica a lo largo del barrido."""
        y = self.columna(columna)
        i_min, i_max = int(np.argmin(y)), int(np.argmax(y))
        return {
            "minimo": float(y[i_min]),
            "valor_parametro_minimo": float(self.valores[i_min]),
            "maximo": float(y[i_max]),
            "valor_parametro_maximo": float(self.valores[i_max]),
            "razon_max_min": float(y[i_max] / y[i_min]) if y[i_min] != 0 else float("inf"),
        }


# ---------------------------------------------------------------------------
#  Barridos sobre las propiedades del SISTEMA
# ---------------------------------------------------------------------------
PARAMETROS_SISTEMA = {
    "masa": "masa",
    "m": "masa",
    "rigidez": "rigidez",
    "k": "rigidez",
    "zeta": "zeta",
    "amortiguamiento": "zeta",
}


def barrido_parametro(sistema: SistemaSDOF, carga: Carga, parametro: str,
                      valores: Iterable[float], guardar_respuestas: bool = True,
                      **kwargs_resolver) -> ResultadoBarrido:
    """Varía una propiedad del sistema y recalcula la respuesta.

    Parámetros
    ----------
    parametro : 'masa' | 'rigidez' | 'zeta'
    valores   : secuencia de valores a evaluar (en SI)
    kwargs_resolver : se pasan a :func:`dinamica.solucionadores.resolver`
                      (t_final, dt, metodo, u0, v0, ...)

    Ejemplo
    -------
    >>> from dinamica import SistemaSDOF, CargaArmonica, barrido_parametro
    >>> s = SistemaSDOF(1000, 1e6, 0.05)
    >>> c = CargaArmonica(p0=1000, omega=20.0)
    >>> r = barrido_parametro(s, c, 'zeta', [0.02, 0.05, 0.10])
    >>> len(r.filas)
    3
    """
    if parametro not in PARAMETROS_SISTEMA:
        raise ValueError(f"Parámetro '{parametro}' no válido. "
                         f"Use: {sorted(set(PARAMETROS_SISTEMA))}")
    attr = PARAMETROS_SISTEMA[parametro]
    valores = np.asarray(list(valores), dtype=float)

    filas, respuestas = [], []
    for val in valores:
        s_i = sistema.con(**{attr: float(val)})
        r = resolver(s_i, carga, **kwargs_resolver)
        fila = metricas(r, p0=getattr(carga, "p0", None))
        if isinstance(carga, CargaArmonica):
            fila["beta [-]"] = carga.omega / s_i.omega_n
        filas.append(fila)
        if guardar_respuestas:
            respuestas.append(r)

    return ResultadoBarrido(parametro=f"{attr}", valores=valores, filas=filas,
                            respuestas=respuestas,
                            descripcion=f"Barrido de {attr} — {carga.descripcion()}")


def barrido_carga(sistema: SistemaSDOF, fabrica_carga: Callable[[float], Carga],
                  valores: Iterable[float], nombre_parametro: str = "parámetro",
                  guardar_respuestas: bool = True,
                  **kwargs_resolver) -> ResultadoBarrido:
    """Varía una propiedad de la CARGA (amplitud, frecuencia, duración...).

    ``fabrica_carga`` es una función que recibe el valor del parámetro y
    devuelve el objeto de carga correspondiente.

    Ejemplo — barrido de la relación de frecuencias:

    >>> from dinamica import SistemaSDOF, CargaArmonica, barrido_carga
    >>> s = SistemaSDOF(1000, 1e6, 0.05)
    >>> f = lambda b: CargaArmonica(p0=1000.0, omega=b*s.omega_n)
    >>> r = barrido_carga(s, f, [0.5, 1.0, 1.5], 'beta')
    >>> round(float(r.columna('Rd [-]')[1]))   # en resonancia Rd ~ 1/(2*zeta)
    10
    """
    valores = np.asarray(list(valores), dtype=float)
    filas, respuestas = [], []
    for val in valores:
        carga = fabrica_carga(float(val))
        r = resolver(sistema, carga, **kwargs_resolver)
        fila = metricas(r, p0=getattr(carga, "p0", None))
        if isinstance(carga, CargaArmonica):
            fila["beta [-]"] = carga.omega / sistema.omega_n
        if getattr(carga, "duracion", None):
            fila["td/Tn [-]"] = carga.duracion / sistema.T_n
        filas.append(fila)
        if guardar_respuestas:
            respuestas.append(r)
    return ResultadoBarrido(parametro=nombre_parametro, valores=valores,
                            filas=filas, respuestas=respuestas,
                            descripcion=f"Barrido de {nombre_parametro}")


def barrido_sismico(sistema: SistemaSDOF, excitacion: ExcitacionBase,
                    parametro: str, valores: Iterable[float],
                    guardar_respuestas: bool = False,
                    **kwargs) -> ResultadoBarrido:
    """Igual que :func:`barrido_parametro` pero con excitación en la base."""
    if parametro not in PARAMETROS_SISTEMA:
        raise ValueError(f"Parámetro '{parametro}' no válido.")
    attr = PARAMETROS_SISTEMA[parametro]
    valores = np.asarray(list(valores), dtype=float)

    filas, respuestas = [], []
    for val in valores:
        s_i = sistema.con(**{attr: float(val)})
        r = resolver_base(s_i, excitacion, **kwargs)
        fila = metricas(r)
        fila["a_abs_max [g]"] = r.a_abs_max / 9.80665
        filas.append(fila)
        if guardar_respuestas:
            respuestas.append(r)
    return ResultadoBarrido(parametro=attr, valores=valores, filas=filas,
                            respuestas=respuestas,
                            descripcion=f"Barrido sísmico de {attr} — {excitacion.nombre}")


# ---------------------------------------------------------------------------
def sensibilidad(resultado: ResultadoBarrido, columna: str = "u_max [mm]",
                 referencia: float | None = None) -> np.ndarray:
    """Variación porcentual de una métrica respecto al valor de referencia.

    Si no se indica ``referencia`` se toma el primer valor del barrido.
    """
    y = resultado.columna(columna)
    ref = y[0] if referencia is None else referencia
    return 100.0 * (y - ref) / ref
