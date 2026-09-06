"""
Solucionadores de la ecuación de movimiento de un sistema de 1 GDL.

    m u'' + c u' + k u = p(t)

Métodos implementados
---------------------
NUMÉRICOS (sirven para cualquier excitación)
  * ``newmark``               : método de Newmark directo (β, γ). Por defecto
                                aceleración promedio (γ=1/2, β=1/4),
                                incondicionalmente estable. También
                                aceleración lineal (β=1/6) y diferencia
                                central (γ=1/2, β=0, explícito).
  * ``interpolacion_exacta``  : solución exacta para excitación interpolada
                                linealmente (Chopra, tabla 5.2.1). Se usa como
                                patrón de referencia para verificar Newmark.
  * ``duhamel_numerica``      : integral de Duhamel evaluada numéricamente.

ANALÍTICOS (verificación y comprensión física)
  * ``vibracion_libre``
  * ``respuesta_armonica``    : solución exacta transitoria + permanente
  * ``respuesta_permanente_armonica``
  * ``respuesta_pulso``       : solución exacta no amortiguada de pulsos
                                rectangular / triangular / medio seno
                                (fase forzada + fase libre)

Todos devuelven un objeto :class:`Respuesta` con t, u, u', u'' y utilidades
(valores máximos, fuerzas, cortante basal, aceleración absoluta...).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .cargas import Carga, CargaArbitraria, ExcitacionBase, PulsoRectangular, \
    PulsoSemiseno, PulsoTriangular, CargaArmonica
from .sistema import SistemaSDOF

__all__ = [
    "Respuesta",
    "newmark",
    "interpolacion_exacta",
    "duhamel_numerica",
    "vibracion_libre",
    "respuesta_armonica",
    "respuesta_permanente_armonica",
    "respuesta_pulso",
    "resolver",
    "resolver_base",
    "vector_tiempo",
    "dt_recomendado",
]


# ===========================================================================
#  Contenedor de resultados
# ===========================================================================
@dataclass
class Respuesta:
    """Historia de respuesta en el tiempo de un sistema SDOF.

    Atributos
    ---------
    t   : tiempo [s]
    u   : desplazamiento [m]   (RELATIVO a la base si hubo excitación sísmica)
    v   : velocidad [m/s]
    a   : aceleración [m/s^2]  (relativa si hubo excitación sísmica)
    p   : carga aplicada [N]
    ag  : aceleración del terreno [m/s^2] (None si la excitación no es sísmica)
    """

    t: np.ndarray
    u: np.ndarray
    v: np.ndarray
    a: np.ndarray
    sistema: SistemaSDOF
    p: np.ndarray | None = None
    ag: np.ndarray | None = None
    metodo: str = ""
    etiqueta: str = ""
    metadatos: dict = field(default_factory=dict)

    # ---------- magnitudes derivadas ------------------------------------
    @property
    def fuerza_elastica(self) -> np.ndarray:
        """f_S(t) = k*u(t) [N]. Es también el cortante basal del sistema."""
        return self.sistema.rigidez * self.u

    @property
    def fuerza_amortiguamiento(self) -> np.ndarray:
        """f_D(t) = c*u'(t) [N]."""
        return self.sistema.amortiguamiento * self.v

    @property
    def fuerza_transmitida(self) -> np.ndarray:
        """Fuerza transmitida al apoyo f_T = k*u + c*u' [N]."""
        return self.fuerza_elastica + self.fuerza_amortiguamiento

    @property
    def cortante_basal(self) -> np.ndarray:
        """Cortante en la base V(t) = k*u(t) [N]."""
        return self.fuerza_elastica

    @property
    def aceleracion_absoluta(self) -> np.ndarray:
        """Aceleración total u''_t = u'' + ug''  [m/s^2].

        Si no hay excitación en la base coincide con la aceleración relativa.
        """
        if self.ag is None:
            return self.a
        return self.a + self.ag

    # ---------- valores pico --------------------------------------------
    @property
    def u_max(self) -> float:
        """Máximo valor absoluto del desplazamiento |u|max [m]."""
        return float(np.max(np.abs(self.u)))

    @property
    def v_max(self) -> float:
        return float(np.max(np.abs(self.v)))

    @property
    def a_max(self) -> float:
        return float(np.max(np.abs(self.a)))

    @property
    def a_abs_max(self) -> float:
        return float(np.max(np.abs(self.aceleracion_absoluta)))

    @property
    def t_u_max(self) -> float:
        """Instante en que ocurre el desplazamiento máximo [s]."""
        return float(self.t[int(np.argmax(np.abs(self.u)))])

    @property
    def cortante_max(self) -> float:
        return float(np.max(np.abs(self.cortante_basal)))

    @property
    def fuerza_transmitida_max(self) -> float:
        return float(np.max(np.abs(self.fuerza_transmitida)))

    def factor_amplificacion(self, p0: float | None = None) -> float:
        """Factor de amplificación dinámica Rd = |u|max / (p0/k).

        Si ``p0`` no se indica se toma el máximo de la carga aplicada.
        """
        if p0 is None:
            if self.p is None:
                raise ValueError("No hay carga registrada para estimar p0.")
            p0 = float(np.max(np.abs(self.p)))
        if p0 == 0:
            return float("nan")
        return self.u_max / (p0 / self.sistema.rigidez)

    # ---------- utilidades ----------------------------------------------
    def en(self, t_consulta: float) -> dict:
        """Interpola la respuesta en un instante dado."""
        return {
            "t": t_consulta,
            "u": float(np.interp(t_consulta, self.t, self.u)),
            "v": float(np.interp(t_consulta, self.t, self.v)),
            "a": float(np.interp(t_consulta, self.t, self.a)),
        }

    def recortar(self, t_ini: float, t_fin: float) -> "Respuesta":
        """Devuelve una subventana temporal de la respuesta."""
        m = (self.t >= t_ini) & (self.t <= t_fin)
        return Respuesta(
            t=self.t[m], u=self.u[m], v=self.v[m], a=self.a[m],
            sistema=self.sistema,
            p=None if self.p is None else self.p[m],
            ag=None if self.ag is None else self.ag[m],
            metodo=self.metodo, etiqueta=self.etiqueta,
            metadatos=dict(self.metadatos),
        )

    def resumen(self) -> str:
        s = self.sistema
        lineas = [
            f"Respuesta [{self.metodo}] {self.etiqueta}",
            f"  |u|max          = {self.u_max*1000:.4f} mm  (t = {self.t_u_max:.4f} s)",
            f"  |u'|max         = {self.v_max:.4f} m/s",
            f"  |u''|max        = {self.a_max:.4f} m/s²",
            f"  |V|max = k|u|max= {self.cortante_max/1000:.4f} kN",
            f"  |fT|max         = {self.fuerza_transmitida_max/1000:.4f} kN",
        ]
        if self.ag is not None:
            lineas.append(f"  |u''_abs|max    = {self.a_abs_max:.4f} m/s² "
                          f"({self.a_abs_max/9.80665:.4f} g)")
        lineas.append(f"  Sistema: Tn = {s.T_n:.4f} s, zeta = {s.zeta:.4f}")
        return "\n".join(lineas)

    def a_csv(self, ruta: str) -> str:
        """Exporta la historia de respuesta a un archivo CSV."""
        import csv
        with open(ruta, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["t [s]", "u [m]", "v [m/s]", "a [m/s2]", "p [N]",
                        "fs=k*u [N]", "ag [m/s2]", "a_abs [m/s2]"])
            p = self.p if self.p is not None else np.zeros_like(self.t)
            ag = self.ag if self.ag is not None else np.zeros_like(self.t)
            for i in range(self.t.size):
                w.writerow([self.t[i], self.u[i], self.v[i], self.a[i], p[i],
                            self.fuerza_elastica[i], ag[i],
                            self.aceleracion_absoluta[i]])
        return ruta


# ===========================================================================
#  Utilidades de discretización temporal
# ===========================================================================
def dt_recomendado(sistema: SistemaSDOF, puntos_por_periodo: int = 100,
                   dt_maximo: float | None = None) -> float:
    """Paso de tiempo recomendado: Tn/puntos_por_periodo.

    Como referencia: el método de la aceleración lineal es estable si
    dt <= 0.551*Tn y la diferencia central si dt <= Tn/pi; con 20 puntos por
    periodo el error de periodo del método de aceleración promedio es < 3 %.
    Aquí se usan 100 puntos por periodo por defecto (muy seguro).
    """
    dt = sistema.T_n / puntos_por_periodo
    if dt_maximo is not None:
        dt = min(dt, dt_maximo)
    return dt


def vector_tiempo(t_final: float, dt: float, t_inicial: float = 0.0) -> np.ndarray:
    """Vector de tiempo uniforme [s] que incluye el extremo final."""
    n = int(round((t_final - t_inicial) / dt))
    return t_inicial + dt * np.arange(n + 1)


# ===========================================================================
#  1. Newmark directo
# ===========================================================================
FAMILIAS_NEWMARK = {
    "aceleracion_promedio": (0.5, 0.25),   # regla trapezoidal, incondicionalmente estable
    "aceleracion_lineal": (0.5, 1.0 / 6.0),  # estable si dt <= 0.551*Tn
    "diferencia_central": (0.5, 0.0),      # explícito, estable si dt <= Tn/pi
    "fox_goodwin": (0.5, 1.0 / 12.0),
}


def newmark(sistema: SistemaSDOF, t: np.ndarray, p: np.ndarray,
            u0: float = 0.0, v0: float = 0.0,
            gamma: float = 0.5, beta: float = 0.25,
            familia: str | None = None,
            ag: np.ndarray | None = None,
            etiqueta: str = "") -> Respuesta:
    """Integración directa por el método de Newmark.

    Formulación incremental de rigidez efectiva (Chopra, tabla 5.4.2):

        k_ef = k + (gamma/(beta*dt))*c + m/(beta*dt^2)
        dp_ef_i = dp_i + [m/(beta*dt) + (gamma/beta)*c]*v_i
                       + [m/(2*beta) + dt*(gamma/(2*beta) - 1)*c]*a_i
        du_i = dp_ef_i / k_ef
        dv_i = (gamma/(beta*dt))*du_i - (gamma/beta)*v_i + dt*(1 - gamma/(2*beta))*a_i
        da_i = du_i/(beta*dt^2) - v_i/(beta*dt) - a_i/(2*beta)

    Parámetros
    ----------
    sistema : SistemaSDOF
    t       : vector de tiempo [s] (puede tener paso variable)
    p       : vector de carga [N], mismo tamaño que t
    u0, v0  : condiciones iniciales de desplazamiento [m] y velocidad [m/s]
    gamma, beta : parámetros del método (por defecto aceleración promedio)
    familia : si se indica ('aceleracion_promedio', 'aceleracion_lineal',
              'diferencia_central', 'fox_goodwin') fija gamma y beta.
    ag      : aceleración del terreno [m/s^2] si la excitación fue sísmica
              (sólo se guarda para calcular la aceleración absoluta)
    """
    if familia is not None:
        if familia not in FAMILIAS_NEWMARK:
            raise ValueError(f"Familia '{familia}' no válida: {list(FAMILIAS_NEWMARK)}")
        gamma, beta = FAMILIAS_NEWMARK[familia]

    t = np.asarray(t, dtype=float).ravel()
    p = np.asarray(p, dtype=float).ravel()
    if t.size != p.size:
        raise ValueError("t y p deben tener el mismo tamaño.")
    if t.size < 2:
        raise ValueError("Se requieren al menos dos instantes de tiempo.")

    m, k, c = sistema.masa, sistema.rigidez, sistema.amortiguamiento
    n = t.size
    u = np.zeros(n)
    v = np.zeros(n)
    a = np.zeros(n)
    u[0], v[0] = u0, v0
    a[0] = (p[0] - c * v0 - k * u0) / m

    dts = np.diff(t)
    paso_uniforme = bool(np.allclose(dts, dts[0], rtol=1e-9, atol=1e-14))

    # Aviso de estabilidad para los esquemas condicionalmente estables
    dt_max = float(np.max(dts))
    # Criterio de estabilidad (Chopra):  dt/Tn <= 1/(pi*sqrt(2)*sqrt(gamma-2*beta))
    if beta < 0.25 and (gamma - 2.0 * beta) > 0:
        limite = sistema.T_n / (math.pi * math.sqrt(2.0) * math.sqrt(gamma - 2.0 * beta))
        if dt_max > limite:
            raise ValueError(
                f"Paso de tiempo dt={dt_max:.5f} s supera el límite de estabilidad "
                f"({limite:.5f} s) para beta={beta}. Reduzca dt o use "
                f"beta=1/4 (aceleración promedio, incondicionalmente estable)."
            )

    if paso_uniforme:
        dt = float(dts[0])
        k_ef = k + gamma / (beta * dt) * c + m / (beta * dt ** 2)
        A = m / (beta * dt) + gamma / beta * c
        B = m / (2.0 * beta) + dt * (gamma / (2.0 * beta) - 1.0) * c
        for i in range(n - 1):
            dp = (p[i + 1] - p[i]) + A * v[i] + B * a[i]
            du = dp / k_ef
            dv = (gamma / (beta * dt)) * du - (gamma / beta) * v[i] \
                + dt * (1.0 - gamma / (2.0 * beta)) * a[i]
            da = du / (beta * dt ** 2) - v[i] / (beta * dt) - a[i] / (2.0 * beta)
            u[i + 1] = u[i] + du
            v[i + 1] = v[i] + dv
            a[i + 1] = a[i] + da
    else:  # paso variable: se recalculan los coeficientes en cada paso
        for i in range(n - 1):
            dt = float(dts[i])
            k_ef = k + gamma / (beta * dt) * c + m / (beta * dt ** 2)
            A = m / (beta * dt) + gamma / beta * c
            B = m / (2.0 * beta) + dt * (gamma / (2.0 * beta) - 1.0) * c
            dp = (p[i + 1] - p[i]) + A * v[i] + B * a[i]
            du = dp / k_ef
            dv = (gamma / (beta * dt)) * du - (gamma / beta) * v[i] \
                + dt * (1.0 - gamma / (2.0 * beta)) * a[i]
            da = du / (beta * dt ** 2) - v[i] / (beta * dt) - a[i] / (2.0 * beta)
            u[i + 1] = u[i] + du
            v[i + 1] = v[i] + dv
            a[i + 1] = a[i] + da

    nombre = next((nm for nm, gb in FAMILIAS_NEWMARK.items()
                   if abs(gb[0] - gamma) < 1e-12 and abs(gb[1] - beta) < 1e-12), None)
    metodo = f"Newmark (γ={gamma:g}, β={beta:g}" + (f", {nombre})" if nombre else ")")
    return Respuesta(t=t, u=u, v=v, a=a, sistema=sistema, p=p, ag=ag,
                     metodo=metodo, etiqueta=etiqueta,
                     metadatos=dict(gamma=gamma, beta=beta, dt=float(dts[0])))


# ===========================================================================
#  2. Interpolación exacta de la excitación (patrón de verificación)
# ===========================================================================
def interpolacion_exacta(sistema: SistemaSDOF, t: np.ndarray, p: np.ndarray,
                         u0: float = 0.0, v0: float = 0.0,
                         ag: np.ndarray | None = None,
                         etiqueta: str = "") -> Respuesta:
    """Solución EXACTA para una excitación interpolada linealmente entre puntos.

    Recurrencia de Chopra (tabla 5.2.1):

        u_{i+1} = A*u_i + B*v_i + C*p_i + D*p_{i+1}
        v_{i+1} = A'*u_i + B'*v_i + C'*p_i + D'*p_{i+1}

    Requiere paso de tiempo uniforme. Como es exacta para carga lineal a
    tramos, se usa como referencia para verificar la precisión de Newmark.
    """
    t = np.asarray(t, dtype=float).ravel()
    p = np.asarray(p, dtype=float).ravel()
    dts = np.diff(t)
    if not np.allclose(dts, dts[0], rtol=1e-9, atol=1e-14):
        raise ValueError("La interpolación exacta requiere paso de tiempo uniforme.")
    dt = float(dts[0])

    z = sistema.zeta
    wn = sistema.omega_n
    wd = sistema.omega_D
    k = sistema.rigidez
    raiz = math.sqrt(1.0 - z ** 2)
    e = math.exp(-z * wn * dt)
    s = math.sin(wd * dt)
    co = math.cos(wd * dt)

    A = e * (z / raiz * s + co)
    B = e * (1.0 / wd * s)
    C = (1.0 / k) * (2.0 * z / (wn * dt)
                     + e * (((1.0 - 2.0 * z ** 2) / (wd * dt) - z / raiz) * s
                            - (1.0 + 2.0 * z / (wn * dt)) * co))
    D = (1.0 / k) * (1.0 - 2.0 * z / (wn * dt)
                     + e * ((2.0 * z ** 2 - 1.0) / (wd * dt) * s
                            + 2.0 * z / (wn * dt) * co))
    Ap = -e * (wn / raiz * s)
    Bp = e * (co - z / raiz * s)
    Cp = (1.0 / k) * (-1.0 / dt
                      + e * ((wn / raiz + z / (dt * raiz)) * s + co / dt))
    Dp = (1.0 / (k * dt)) * (1.0 - e * (z / raiz * s + co))

    n = t.size
    u = np.zeros(n)
    v = np.zeros(n)
    u[0], v[0] = u0, v0
    for i in range(n - 1):
        u[i + 1] = A * u[i] + B * v[i] + C * p[i] + D * p[i + 1]
        v[i + 1] = Ap * u[i] + Bp * v[i] + Cp * p[i] + Dp * p[i + 1]

    a = (p - sistema.amortiguamiento * v - sistema.rigidez * u) / sistema.masa
    return Respuesta(t=t, u=u, v=v, a=a, sistema=sistema, p=p, ag=ag,
                     metodo="Interpolación exacta (carga lineal a tramos)",
                     etiqueta=etiqueta)


# ===========================================================================
#  3. Integral de Duhamel numérica
# ===========================================================================
def duhamel_numerica(sistema: SistemaSDOF, t: np.ndarray, p: np.ndarray,
                     etiqueta: str = "") -> Respuesta:
    """Integral de Duhamel evaluada numéricamente (condiciones iniciales nulas).

        u(t) = (1/(m*wD)) * ∫_0^t p(τ) e^{-z*wn*(t-τ)} sin(wD*(t-τ)) dτ

    Se evalúa expandiendo el seno y acumulando dos integrales con la regla
    trapezoidal, lo que permite obtener toda la historia en O(n).
    Es un método alternativo (menos preciso que la interpolación exacta) que
    sirve para contrastar resultados y para explicar la respuesta como una
    superposición de respuestas a impulsos elementales.
    """
    t = np.asarray(t, dtype=float).ravel()
    p = np.asarray(p, dtype=float).ravel()
    m, wn, wd, z = sistema.masa, sistema.omega_n, sistema.omega_D, sistema.zeta

    f1 = p * np.exp(z * wn * t) * np.cos(wd * t)
    f2 = p * np.exp(z * wn * t) * np.sin(wd * t)
    # integrales acumuladas por regla trapezoidal
    dt = np.diff(t)
    I1 = np.concatenate(([0.0], np.cumsum(0.5 * dt * (f1[1:] + f1[:-1]))))
    I2 = np.concatenate(([0.0], np.cumsum(0.5 * dt * (f2[1:] + f2[:-1]))))

    amort = np.exp(-z * wn * t) / (m * wd)
    u = amort * (np.sin(wd * t) * I1 - np.cos(wd * t) * I2)

    # velocidad y aceleración por diferenciación de la expresión analítica
    du = np.gradient(u, t, edge_order=2)
    a = (p - sistema.amortiguamiento * du - sistema.rigidez * u) / m
    return Respuesta(t=t, u=u, v=du, a=a, sistema=sistema, p=p,
                     metodo="Integral de Duhamel (trapecio)", etiqueta=etiqueta)


# ===========================================================================
#  4. Soluciones analíticas
# ===========================================================================
def vibracion_libre(sistema: SistemaSDOF, t: np.ndarray,
                    u0: float = 0.0, v0: float = 0.0,
                    etiqueta: str = "") -> Respuesta:
    """Vibración libre amortiguada (solución cerrada).

        u(t) = e^{-z wn t} [ u0 cos(wD t) + ((v0 + z wn u0)/wD) sin(wD t) ]
    """
    t = np.asarray(t, dtype=float).ravel()
    z, wn, wd = sistema.zeta, sistema.omega_n, sistema.omega_D
    E = np.exp(-z * wn * t)
    Aa = u0
    Bb = (v0 + z * wn * u0) / wd
    u = E * (Aa * np.cos(wd * t) + Bb * np.sin(wd * t))
    v = E * ((-z * wn) * (Aa * np.cos(wd * t) + Bb * np.sin(wd * t))
             + wd * (-Aa * np.sin(wd * t) + Bb * np.cos(wd * t)))
    a = -(2.0 * z * wn * v + wn ** 2 * u)
    return Respuesta(t=t, u=u, v=v, a=a, sistema=sistema,
                     p=np.zeros_like(t), metodo="Analítica: vibración libre",
                     etiqueta=etiqueta)


def respuesta_permanente_armonica(sistema: SistemaSDOF, carga: CargaArmonica,
                                  t: np.ndarray) -> Respuesta:
    """Sólo la respuesta permanente (steady-state) ante carga armónica.

        u_p(t) = (p0/k) * Rd * sin(w t - phi)
        Rd = 1/sqrt[(1-β²)² + (2 z β)²] ,  phi = atan2(2 z β, 1-β²)
    """
    from .frecuencia import Rd as _Rd, angulo_fase

    t = np.asarray(t, dtype=float).ravel()
    b = sistema.beta(carga.omega)
    rd = _Rd(b, sistema.zeta)
    phi = angulo_fase(b, sistema.zeta)
    ust = carga.p0 / sistema.rigidez
    w = carga.omega
    if carga.tipo == "sin":
        u = ust * rd * np.sin(w * t - phi)
        v = ust * rd * w * np.cos(w * t - phi)
        a = -ust * rd * w ** 2 * np.sin(w * t - phi)
    else:
        u = ust * rd * np.cos(w * t - phi)
        v = -ust * rd * w * np.sin(w * t - phi)
        a = -ust * rd * w ** 2 * np.cos(w * t - phi)
    return Respuesta(t=t, u=u, v=v, a=a, sistema=sistema, p=carga.muestrear(t),
                     metodo="Analítica: respuesta permanente armónica",
                     etiqueta=f"β={b:.3f}, ζ={sistema.zeta:.3f}",
                     metadatos=dict(Rd=rd, fase=phi, beta=b))


def respuesta_armonica(sistema: SistemaSDOF, carga: CargaArmonica,
                       t: np.ndarray, u0: float = 0.0, v0: float = 0.0,
                       etiqueta: str = "") -> Respuesta:
    """Respuesta TOTAL exacta (transitoria + permanente) ante p(t)=p0 sin(w t).

    Se resuelve la solución particular y se ajusta la homogénea para cumplir
    las condiciones iniciales. Incluye el caso límite de resonancia sin
    amortiguamiento (β = 1, ζ = 0), donde la amplitud crece linealmente:

        u(t) = (p0/2k) [ sin(wn t) - wn t cos(wn t) ]
    """
    t = np.asarray(t, dtype=float).ravel()
    k, z, wn, wd = sistema.rigidez, sistema.zeta, sistema.omega_n, sistema.omega_D
    w = carga.omega
    b = w / wn
    ust = carga.p0 / k

    if carga.tipo != "sin":
        raise ValueError("La solución analítica está implementada para p0*sin(w t). "
                         "Para otras formas use el integrador numérico.")

    if z == 0.0 and abs(b - 1.0) < 1e-12:
        # Resonancia no amortiguada (caso límite)
        u = 0.5 * ust * (np.sin(wn * t) - wn * t * np.cos(wn * t))
        v = 0.5 * ust * wn ** 2 * t * np.sin(wn * t)
        a = 0.5 * ust * wn ** 2 * (np.sin(wn * t) + wn * t * np.cos(wn * t))
        # condiciones iniciales adicionales por superposición de vibración libre
        if u0 != 0.0 or v0 != 0.0:
            libre = vibracion_libre(sistema, t, u0, v0)
            u, v, a = u + libre.u, v + libre.v, a + libre.a
        return Respuesta(t=t, u=u, v=v, a=a, sistema=sistema, p=carga.muestrear(t),
                         metodo="Analítica: resonancia no amortiguada",
                         etiqueta=etiqueta or "β=1, ζ=0",
                         metadatos=dict(beta=b))

    D = (1.0 - b ** 2) ** 2 + (2.0 * z * b) ** 2
    C1 = ust * (1.0 - b ** 2) / D      # coeficiente de sin(w t)
    C2 = ust * (-2.0 * z * b) / D      # coeficiente de cos(w t)

    up0 = C2                            # u_p(0)
    vp0 = C1 * w                        # u'_p(0)
    Aa = u0 - up0
    Bb = (v0 + z * wn * Aa - vp0) / wd

    E = np.exp(-z * wn * t)
    coswd, sinwd = np.cos(wd * t), np.sin(wd * t)
    u_h = E * (Aa * coswd + Bb * sinwd)
    v_h = E * (-z * wn * (Aa * coswd + Bb * sinwd)
               + wd * (-Aa * sinwd + Bb * coswd))

    u_p = C1 * np.sin(w * t) + C2 * np.cos(w * t)
    v_p = C1 * w * np.cos(w * t) - C2 * w * np.sin(w * t)

    u = u_h + u_p
    v = v_h + v_p
    p = carga.muestrear(t)
    a = (p - sistema.amortiguamiento * v - k * u) / sistema.masa
    return Respuesta(t=t, u=u, v=v, a=a, sistema=sistema, p=p,
                     metodo="Analítica: armónica (transitoria + permanente)",
                     etiqueta=etiqueta or f"β={b:.3f}, ζ={z:.3f}",
                     metadatos=dict(beta=b, u_permanente=abs(ust) / math.sqrt(D)))


def respuesta_pulso(sistema: SistemaSDOF, carga: Carga, t: np.ndarray,
                    etiqueta: str = "") -> Respuesta:
    """Solución analítica NO amortiguada de pulsos clásicos (ζ = 0).

    Se resuelve la fase forzada (t <= td) con la solución cerrada y la fase
    de vibración libre (t > td) a partir del estado (u(td), u'(td)).

    Pulsos soportados: rectangular, triangular (creciente/decreciente),
    medio seno. Es la referencia analítica para verificar el motor numérico
    en el análisis de cargas impulsivas.
    """
    if sistema.zeta != 0.0:
        raise ValueError("Las soluciones cerradas de pulsos implementadas aquí "
                         "corresponden al sistema NO amortiguado (ζ = 0). "
                         "Para ζ > 0 utilice newmark() o interpolacion_exacta().")

    t = np.asarray(t, dtype=float).ravel()
    wn = sistema.omega_n
    ust = carga.p0 / sistema.rigidez
    td = carga.duracion

    tf = np.clip(t, 0.0, td)   # tiempo dentro de la fase forzada

    if isinstance(carga, PulsoRectangular):
        u_f = ust * (1.0 - np.cos(wn * tf))
        v_f = ust * wn * np.sin(wn * tf)
    elif isinstance(carga, PulsoTriangular) and carga.tipo == "decreciente":
        u_f = ust * (1.0 - np.cos(wn * tf) + np.sin(wn * tf) / (wn * td) - tf / td)
        v_f = ust * (wn * np.sin(wn * tf) + np.cos(wn * tf) / td - 1.0 / td)
    elif isinstance(carga, PulsoTriangular) and carga.tipo == "creciente":
        u_f = ust * (tf / td - np.sin(wn * tf) / (wn * td))
        v_f = ust * (1.0 / td - np.cos(wn * tf) / td)
    elif isinstance(carga, PulsoSemiseno):
        wbar = math.pi / td
        r = wbar / wn
        if abs(r - 1.0) < 1e-10:   # caso especial td = Tn/2
            u_f = 0.5 * ust * (np.sin(wn * tf) - wn * tf * np.cos(wn * tf))
            v_f = 0.5 * ust * wn ** 2 * tf * np.sin(wn * tf)
        else:
            u_f = ust / (1.0 - r ** 2) * (np.sin(wbar * tf) - r * np.sin(wn * tf))
            v_f = ust / (1.0 - r ** 2) * (wbar * np.cos(wbar * tf)
                                          - r * wn * np.cos(wn * tf))
    else:
        raise ValueError(f"No hay solución cerrada implementada para {type(carga).__name__} "
                         f"(use el integrador numérico).")

    # Estado al final del pulso, evaluado con la fórmula cerrada en t = td
    # (más preciso que interpolar sobre la malla) -> vibración libre posterior
    u_td, v_td = _estado_en(carga, sistema, td)

    tau = t - td
    u_l = u_td * np.cos(wn * tau) + (v_td / wn) * np.sin(wn * tau)
    v_l = -u_td * wn * np.sin(wn * tau) + v_td * np.cos(wn * tau)

    dentro = t <= td
    u = np.where(dentro, u_f, u_l)
    v = np.where(dentro, v_f, v_l)
    p = carga.muestrear(t)
    a = (p - sistema.rigidez * u) / sistema.masa
    return Respuesta(t=t, u=u, v=v, a=a, sistema=sistema, p=p,
                     metodo="Analítica: pulso (fase forzada + fase libre)",
                     etiqueta=etiqueta or carga.descripcion(),
                     metadatos=dict(td=td, td_sobre_Tn=td / sistema.T_n))


def _estado_en(carga: Carga, sistema: SistemaSDOF, tt: float) -> tuple[float, float]:
    """(u, u') exactos al final de la fase forzada de un pulso (ζ = 0)."""
    wn = sistema.omega_n
    ust = carga.p0 / sistema.rigidez
    td = carga.duracion
    if isinstance(carga, PulsoRectangular):
        return (ust * (1 - math.cos(wn * tt)), ust * wn * math.sin(wn * tt))
    if isinstance(carga, PulsoTriangular) and carga.tipo == "decreciente":
        u = ust * (1 - math.cos(wn * tt) + math.sin(wn * tt) / (wn * td) - tt / td)
        v = ust * (wn * math.sin(wn * tt) + math.cos(wn * tt) / td - 1.0 / td)
        return u, v
    if isinstance(carga, PulsoTriangular) and carga.tipo == "creciente":
        u = ust * (tt / td - math.sin(wn * tt) / (wn * td))
        v = ust * (1.0 / td - math.cos(wn * tt) / td)
        return u, v
    if isinstance(carga, PulsoSemiseno):
        wbar = math.pi / td
        r = wbar / wn
        if abs(r - 1.0) < 1e-10:
            u = 0.5 * ust * (math.sin(wn * tt) - wn * tt * math.cos(wn * tt))
            v = 0.5 * ust * wn ** 2 * tt * math.sin(wn * tt)
            return u, v
        u = ust / (1 - r ** 2) * (math.sin(wbar * tt) - r * math.sin(wn * tt))
        v = ust / (1 - r ** 2) * (wbar * math.cos(wbar * tt) - r * wn * math.cos(wn * tt))
        return u, v
    raise ValueError("Pulso no soportado")


# ===========================================================================
#  5. Interfaz de alto nivel
# ===========================================================================
def resolver(sistema: SistemaSDOF, carga: Carga,
             t_final: float | None = None, dt: float | None = None,
             u0: float = 0.0, v0: float = 0.0,
             metodo: str = "newmark", **kwargs) -> Respuesta:
    """Resuelve la respuesta del ``sistema`` ante la ``carga`` indicada.

    Es el punto de entrada recomendado: elige automáticamente el vector de
    tiempo (si no se da) y despacha al integrador seleccionado.

    Parámetros
    ----------
    t_final : duración del análisis [s]. Por defecto:
              - carga arbitraria: la duración de la señal + 1 periodo natural
              - pulso: 10*td o 10*Tn (el mayor)
              - armónica: 15 periodos naturales
    dt      : paso de tiempo [s]. Por defecto Tn/100 (y como máximo el dt de
              la señal de entrada si la carga es arbitraria).
    metodo  : 'newmark' | 'exacta' | 'duhamel' | 'analitica'
    """
    if t_final is None:
        if isinstance(carga, CargaArbitraria):
            t_final = float(carga.t_datos[-1]) + sistema.T_n
        elif getattr(carga, "duracion", None):
            t_final = max(10.0 * carga.duracion, 10.0 * sistema.T_n)
        else:
            t_final = 15.0 * sistema.T_n
    if dt is None:
        dt = dt_recomendado(sistema)
        if isinstance(carga, CargaArbitraria):
            dt_senal = float(np.min(np.diff(carga.t_datos)))
            dt = min(dt, dt_senal)

    t = vector_tiempo(t_final, dt)
    p = carga.muestrear(t)

    if metodo == "newmark":
        return newmark(sistema, t, p, u0, v0, etiqueta=carga.descripcion(), **kwargs)
    if metodo in ("exacta", "interpolacion_exacta"):
        return interpolacion_exacta(sistema, t, p, u0, v0,
                                    etiqueta=carga.descripcion())
    if metodo == "duhamel":
        return duhamel_numerica(sistema, t, p, etiqueta=carga.descripcion())
    if metodo == "analitica":
        if isinstance(carga, CargaArmonica):
            return respuesta_armonica(sistema, carga, t, u0, v0)
        return respuesta_pulso(sistema, carga, t)
    raise ValueError(f"Método '{metodo}' no reconocido.")


def resolver_base(sistema: SistemaSDOF, excitacion: ExcitacionBase,
                  dt: float | None = None, u0: float = 0.0, v0: float = 0.0,
                  metodo: str = "newmark", t_extra: float | None = None,
                  **kwargs) -> Respuesta:
    """Respuesta ante excitación sísmica en la base (p_ef = -m*ug'').

    La respuesta u(t) devuelta es RELATIVA a la base; la aceleración absoluta
    se obtiene de ``respuesta.aceleracion_absoluta``.

    Si el paso de la señal es mayor que Tn/20 la señal se remuestrea
    (interpolación lineal) para garantizar precisión en la integración.
    """
    dt_senal = excitacion.dt
    dt_max_admisible = sistema.T_n / 20.0
    if dt is None:
        dt = min(dt_senal, dt_max_admisible)

    t_extra = sistema.T_n * 5.0 if t_extra is None else t_extra
    t_final = excitacion.duracion + t_extra
    t = vector_tiempo(t_final, dt, t_inicial=float(excitacion.t[0]))
    ag = np.interp(t, excitacion.t, excitacion.ag, left=0.0, right=0.0)
    p = -sistema.masa * ag

    if metodo == "newmark":
        r = newmark(sistema, t, p, u0, v0, ag=ag,
                    etiqueta=excitacion.nombre, **kwargs)
    elif metodo in ("exacta", "interpolacion_exacta"):
        r = interpolacion_exacta(sistema, t, p, u0, v0, ag=ag,
                                 etiqueta=excitacion.nombre)
    elif metodo == "duhamel":
        r = duhamel_numerica(sistema, t, p, etiqueta=excitacion.nombre)
        r.ag = ag
    else:
        raise ValueError(f"Método '{metodo}' no válido para excitación en la base.")
    r.metadatos.update(pga=excitacion.pga, excitacion=excitacion.nombre)
    return r
