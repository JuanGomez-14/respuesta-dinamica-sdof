"""
Verificación de la coherencia física y numérica de los resultados.

El enunciado del laboratorio exige "verificar la coherencia física y numérica
de la solución". Este módulo agrupa las comprobaciones automáticas:

1. ``residual_equilibrio``  : ¿se cumple m·u'' + c·u' + k·u = p(t) en cada
                              instante? (control del integrador)
2. ``balance_energia``      : ¿la energía introducida por la carga se reparte
                              entre energía cinética, de deformación y
                              disipada? (control físico global)
3. ``comparar``             : error entre dos soluciones (numérica vs analítica)
4. ``convergencia``         : error del pico en función del paso de tiempo
5. ``verificar_todo``       : ejecuta la batería completa y devuelve un informe
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .sistema import SistemaSDOF
from .solucionadores import Respuesta

__all__ = ["residual_equilibrio", "balance_energia", "comparar",
           "convergencia", "verificar_todo", "InformeVerificacion"]


def residual_equilibrio(resp: Respuesta) -> dict:
    """Residual de la ecuación de movimiento en cada instante.

        r(t) = m·u''(t) + c·u'(t) + k·u(t) - p(t)

    Se normaliza con el máximo de la carga (o con la fuerza de inercia máxima
    si la carga es nula, como en vibración libre).
    """
    s = resp.sistema
    p = resp.p if resp.p is not None else np.zeros_like(resp.t)
    r = s.masa * resp.a + s.amortiguamiento * resp.v + s.rigidez * resp.u - p
    escala = max(float(np.max(np.abs(p))), float(np.max(np.abs(s.masa * resp.a))), 1e-30)
    return {
        "residual_max [N]": float(np.max(np.abs(r))),
        "residual_max_relativo [-]": float(np.max(np.abs(r))) / escala,
        "residual_rms_relativo [-]": float(np.sqrt(np.mean(r ** 2))) / escala,
    }


def balance_energia(resp: Respuesta) -> dict:
    """Balance energético acumulado hasta el final del análisis.

        E_entrada  = ∫ p·u'  dt            (trabajo de la carga externa)
        E_cinetica = ½·m·u'²               (energía cinética instantánea)
        E_elastica = ½·k·u²                (energía de deformación instantánea)
        E_disipada = ∫ c·u'² dt            (energía disipada por amortiguamiento)

    Debe cumplirse  E_entrada ≈ E_cinetica + E_elastica + E_disipada.
    El error de cierre es un indicador global de la calidad de la integración.
    """
    s = resp.sistema
    p = resp.p if resp.p is not None else np.zeros_like(resp.t)
    t, v = resp.t, resp.v

    E_entrada = float(np.trapezoid(p * v, t)) if hasattr(np, "trapezoid") \
        else float(np.trapz(p * v, t))
    E_disipada = float(np.trapezoid(s.amortiguamiento * v ** 2, t)) if hasattr(np, "trapezoid") \
        else float(np.trapz(s.amortiguamiento * v ** 2, t))
    E_cinetica = 0.5 * s.masa * v[-1] ** 2
    E_elastica = 0.5 * s.rigidez * resp.u[-1] ** 2
    E_inicial = 0.5 * s.masa * v[0] ** 2 + 0.5 * s.rigidez * resp.u[0] ** 2

    total_final = E_cinetica + E_elastica + E_disipada
    referencia = max(abs(E_entrada + E_inicial), 1e-30)
    return {
        "E_entrada [J]": E_entrada,
        "E_inicial [J]": E_inicial,
        "E_cinetica_final [J]": E_cinetica,
        "E_elastica_final [J]": E_elastica,
        "E_disipada [J]": E_disipada,
        "error_cierre [-]": abs(E_entrada + E_inicial - total_final) / referencia,
    }


def comparar(resp: Respuesta, referencia: Respuesta,
             nombre: str = "solución numérica") -> dict:
    """Error de una solución respecto a otra tomada como referencia."""
    u_ref = np.interp(resp.t, referencia.t, referencia.u)
    denom = float(np.max(np.abs(u_ref)))
    return {
        "nombre": nombre,
        "u_max [m]": resp.u_max,
        "u_max_referencia [m]": referencia.u_max,
        "error_pico [-]": abs(resp.u_max - referencia.u_max) / referencia.u_max,
        "error_max_absoluto [m]": float(np.max(np.abs(resp.u - u_ref))),
        "error_max_relativo [-]": float(np.max(np.abs(resp.u - u_ref))) / denom,
        "error_rms_relativo [-]": float(np.sqrt(np.mean((resp.u - u_ref) ** 2))) / denom,
    }


def convergencia(sistema: SistemaSDOF, carga, razones_dt=None,
                 t_final: float | None = None, familias=("aceleracion_promedio",
                                                         "aceleracion_lineal"),
                 referencia_dt: float | None = None) -> dict:
    """Error del pico de desplazamiento en función de Δt/Tn.

    La solución de referencia se calcula con el integrador de interpolación
    exacta y un paso muy fino.
    """
    from .solucionadores import resolver

    if razones_dt is None:
        razones_dt = np.array([1/5, 1/10, 1/20, 1/50, 1/100, 1/200])
    razones_dt = np.asarray(razones_dt, dtype=float)
    if t_final is None:
        t_final = 20.0 * sistema.T_n
    dt_ref = referencia_dt or sistema.T_n / 2000.0
    u_ref = resolver(sistema, carga, t_final=t_final, dt=dt_ref, metodo="exacta").u_max

    salida = {"razones_dt": razones_dt, "u_referencia": u_ref}
    for fam in familias:
        errores = []
        for rz in razones_dt:
            u = resolver(sistema, carga, t_final=t_final, dt=sistema.T_n * rz,
                         metodo="newmark", familia=fam).u_max
            errores.append((u - u_ref) / u_ref)
        salida[fam] = np.array(errores)
    return salida


@dataclass
class InformeVerificacion:
    """Resultado de la batería de verificaciones."""

    equilibrio: dict
    energia: dict
    comparaciones: list

    @property
    def aprueba(self) -> bool:
        """Criterios de aceptación usados en este laboratorio."""
        ok = self.equilibrio["residual_max_relativo [-]"] < 1e-6
        ok &= self.energia["error_cierre [-]"] < 1e-2
        for c in self.comparaciones:
            ok &= c["error_pico [-]"] < 1e-2
        return bool(ok)

    def texto(self) -> str:
        L = ["VERIFICACIÓN DE LA SOLUCIÓN", "-" * 60]
        L.append(f"  Residual máximo de la ecuación de movimiento : "
                 f"{self.equilibrio['residual_max_relativo [-]']:.3e}  (adimensional)")
        L.append(f"  Residual RMS                                 : "
                 f"{self.equilibrio['residual_rms_relativo [-]']:.3e}")
        L.append(f"  Error de cierre del balance de energía       : "
                 f"{self.energia['error_cierre [-]']*100:.4f} %")
        L.append(f"    E_entrada = {self.energia['E_entrada [J]']:.4f} J   "
                 f"E_disipada = {self.energia['E_disipada [J]']:.4f} J")
        for c in self.comparaciones:
            L.append(f"  {c['nombre']:<42s}: error pico = {c['error_pico [-]']*100:.5f} % ; "
                     f"RMS = {c['error_rms_relativo [-]']*100:.5f} %")
        L.append("-" * 60)
        L.append(f"  RESULTADO: {'APROBADA' if self.aprueba else 'REVISAR'}")
        return "\n".join(L)


def verificar_todo(resp: Respuesta, referencias: dict | None = None) -> InformeVerificacion:
    """Ejecuta la batería completa de verificaciones sobre una respuesta.

    ``referencias`` es un diccionario {nombre: Respuesta} con las soluciones
    contra las cuales contrastar (analítica exacta, interpolación exacta...).
    """
    comparaciones = []
    for nombre, ref in (referencias or {}).items():
        comparaciones.append(comparar(resp, ref, nombre=f"vs. {nombre}"))
    return InformeVerificacion(equilibrio=residual_equilibrio(resp),
                               energia=balance_energia(resp),
                               comparaciones=comparaciones)
