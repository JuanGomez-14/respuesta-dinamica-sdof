"""
Modelo compartido de la interfaz: el objeto ``Proyecto``.

Es la ÚNICA fuente de verdad de la aplicación. Vive en ``st.session_state`` y
todas las pestañas leen de él y escriben en él.

Regla central
-------------
``SistemaSDOF`` **no se almacena, se deriva**. Es el resultado de
:meth:`Proyecto.sistema`, que recalcula masa, rigidez y amortiguamiento a partir
del estado actual en cada rerun de Streamlit. Por eso cambiar la altura de una
columna en el constructor de pórtico actualiza ωₙ, la curva Rd y la respuesta
armónica sin que el usuario tenga que apretar ningún botón de "aplicar".

Unidades
--------
El motor (``dinamica``) es SI coherente. Aquí se guardan los valores TAL COMO
los escribe el usuario, junto con su unidad; la conversión a SI ocurre al
derivar (``a_si``), nunca a medias. Así el usuario trabaja en cm⁴ y GPa si le
conviene y el motor sigue viendo m⁴ y Pa.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from dinamica import (SistemaSDOF, a_si, formatear_polinomio,
                      rigidez_columna_polinomio, rigidez_riostra,
                      rigidez_serie_niveles, sumar_polinomios)

from .formato import compacto, con_unidad, numero


def _en_si(valor: float, unidad: str) -> str:
    """El valor en la unidad del motor, más su equivalente corto si aporta.

    Evita el texto redundante del tipo «24.000 kg = 24.000 kg»: la segunda
    forma solo aparece cuando de verdad se lee mejor (24 t), y nunca repite el
    dato que el usuario ya está viendo en el campo de entrada.
    """
    exacto = con_unidad(valor, unidad)
    corto = compacto(valor, unidad)
    return exacto if corto == exacto else f"{exacto} = {corto}"

__all__ = ["Magnitud", "Columna", "Riostra", "Nivel", "Proyecto",
           "UNIDADES_E", "UNIDADES_I", "UNIDADES_LONGITUD", "UNIDADES_AREA",
           "UNIDADES_MASA", "UNIDADES_RIGIDEZ", "CONDICIONES_ETIQUETA"]

_contador = itertools.count(1)


def _nuevo_id() -> int:
    """Identificador estable para las claves de los widgets de Streamlit."""
    return next(_contador)


# Unidades ofrecidas en cada tipo de campo (todas existen en dinamica.unidades).
UNIDADES_E = ["GPa", "MPa", "kPa", "Pa"]
UNIDADES_I = ["cm4", "m4", "mm4"]
UNIDADES_LONGITUD = ["m", "cm", "mm"]
UNIDADES_AREA = ["cm2", "m2", "mm2"]
UNIDADES_MASA = ["kg", "t", "kgf", "N", "kN"]
UNIDADES_RIGIDEZ = ["N/m", "kN/m", "kN/mm", "tonf/m"]

CONDICIONES_ETIQUETA = {
    "empotrada-empotrada": "Doblemente empotrada — 12EI/H³",
    "voladizo": "Empotrada-libre (voladizo) — 3EI/H³",
}


# ===========================================================================
#  Magnitud con procedencia
# ===========================================================================
@dataclass(frozen=True)
class Magnitud:
    """Un valor en SI junto con el rastro de cómo se obtuvo.

    El campo ``detalle`` no es decorativo: el usuario resuelve ejercicios en los
    que debe MOSTRAR el procedimiento, y este texto se copia directo al
    desarrollo escrito.

    >>> m = Magnitud(0.05, "decremento logarítmico", "δ=0.314 → ζ=δ/√(4π²+δ²)")
    >>> m.valor
    0.05
    """
    valor: float
    procedencia: str = "directa"
    detalle: str = ""

    def __float__(self) -> float:
        return float(self.valor)


# ===========================================================================
#  Elementos del pórtico
# ===========================================================================
@dataclass
class Columna:
    """Una columna (o un grupo de ``n`` columnas iguales) de un nivel."""
    nombre: str = "Columna"
    n: int = 1
    E: float = 200.0
    E_unidad: str = "GPa"
    H: float = 3.0
    H_unidad: str = "m"
    condicion: str = "empotrada-empotrada"
    modo_seccion: str = "I"          # "I" (inercia directa) | "bh" (rectangular)
    I: float = 3692.0
    I_unidad: str = "cm4"
    b: float = 30.0
    b_simbolica: bool = False
    h: float = 40.0
    h_simbolica: bool = False
    bh_unidad: str = "cm"
    id: int = field(default_factory=_nuevo_id)

    def polinomio(self) -> dict[int, float]:
        """Rigidez lateral como polinomio en x, ya en SI.

        Cuando ``b`` o ``h`` son simbólicas, el valor escrito actúa como
        coeficiente de x y la unidad elegida escala ese coeficiente, de modo que
        x siempre se interpreta en metros.
        """
        E_Pa = a_si(self.E, self.E_unidad)
        H_m = a_si(self.H, self.H_unidad)
        if self.modo_seccion == "I":
            return rigidez_columna_polinomio(
                E_Pa, H_m, self.condicion, I=a_si(self.I, self.I_unidad), n=self.n)

        factor = a_si(1.0, self.bh_unidad)
        return rigidez_columna_polinomio(
            E_Pa, H_m, self.condicion,
            b=self.b * factor, h=self.h * factor,
            b_simbolica=self.b_simbolica, h_simbolica=self.h_simbolica,
            n=self.n)

    def descripcion(self) -> str:
        """Resumen de una línea para la lista de elementos."""
        coef = 12 if self.condicion == "empotrada-empotrada" else 3
        if self.modo_seccion == "I":
            sec = f"I = {self.I:g} {self.I_unidad}"
        else:
            b = f"{self.b:g}x" if self.b_simbolica else f"{self.b:g}"
            h = f"{self.h:g}x" if self.h_simbolica else f"{self.h:g}"
            sec = f"b×h = {b} × {h} {self.bh_unidad}"
        plural = f"{self.n}× " if self.n > 1 else ""
        return (f"{plural}{coef}EI/H³ · E = {self.E:g} {self.E_unidad} · "
                f"H = {self.H:g} {self.H_unidad} · {sec}")


@dataclass
class Riostra:
    """Una riostra diagonal; aporta solo la componente horizontal de su rigidez axial."""
    nombre: str = "Riostra"
    n: int = 1
    A: float = 20.0
    A_unidad: str = "cm2"
    E: float = 200.0
    E_unidad: str = "GPa"
    L_h: float = 4.0
    L_v: float = 3.0
    L_unidad: str = "m"
    id: int = field(default_factory=_nuevo_id)

    def polinomio(self) -> dict[int, float]:
        """Rigidez lateral aportada, en SI. Siempre de grado 0 (no simbólica)."""
        poli = rigidez_riostra(
            A=a_si(self.A, self.A_unidad),
            E=a_si(self.E, self.E_unidad),
            L_h=a_si(self.L_h, self.L_unidad),
            L_v=a_si(self.L_v, self.L_unidad))
        return {0: poli[0] * self.n}

    def descripcion(self) -> str:
        L_r = math.hypot(self.L_h, self.L_v)
        plural = f"{self.n}× " if self.n > 1 else ""
        return (f"{plural}A = {self.A:g} {self.A_unidad} · E = {self.E:g} "
                f"{self.E_unidad} · L_h = {self.L_h:g}, L_v = {self.L_v:g} "
                f"{self.L_unidad} (L_r = {L_r:.3f})")


@dataclass
class Nivel:
    """Un nivel del pórtico: sus columnas y riostras trabajan en PARALELO."""
    nombre: str = "Nivel"
    columnas: list[Columna] = field(default_factory=lambda: [Columna()])
    riostras: list[Riostra] = field(default_factory=list)
    id: int = field(default_factory=_nuevo_id)

    def polinomio(self) -> dict[int, float]:
        """Rigidez de piso: suma de los aportes de todos sus elementos."""
        elementos = [*self.columnas, *self.riostras]
        if not elementos:
            raise ValueError(
                f"«{self.nombre}» no tiene ningún elemento: agregue al menos una "
                "columna o una riostra.")
        return sumar_polinomios(e.polinomio() for e in elementos)

    def expresion(self) -> str:
        """Rigidez de piso escrita como polinomio, para mostrarla al usuario."""
        return formatear_polinomio(self.polinomio())


# ===========================================================================
#  El proyecto
# ===========================================================================
@dataclass
class Proyecto:
    """Estado completo de la sesión de trabajo."""

    nombre: str = "Sistema analizado"

    # --- masa ---------------------------------------------------------
    masa_modo: str = "directa"           # "directa" | "carga"
    masa_valor: float = 24_000.0
    masa_unidad: str = "kg"
    masa_carga: float = 5.0              # carga distribuida
    masa_carga_unidad: str = "kN/m2"     # informativo; se opera en kN/m²
    masa_area: float = 24.0              # área tributaria [m²]

    # --- rigidez ------------------------------------------------------
    rigidez_modo: str = "directa"        # "directa" | "portico" | "periodo"
    rigidez_valor: float = 8.2666e6
    rigidez_unidad: str = "N/m"
    periodo_objetivo: float = 0.34
    niveles: list[Nivel] = field(default_factory=lambda: [Nivel(nombre="Nivel 1")])
    x_actual: float = 0.30               # valor de la incógnita x [m]

    # --- amortiguamiento ---------------------------------------------
    zeta_valor: float = 0.05
    zeta_procedencia: str = "directa"
    zeta_detalle: str = ""

    # --- parámetros de excitación por pestaña -------------------------
    cargas: dict = field(default_factory=dict)

    # --- nombres personalizados de las variables ----------------------
    # {etiqueta_por_defecto: nombre_del_usuario}; ver app.etiquetas
    etiquetas: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    #  Masa
    # ------------------------------------------------------------------
    def masa(self) -> Magnitud:
        """Masa en kg, con su procedencia."""
        if self.masa_modo == "carga":
            # q [kN/m²] × área [m²] = peso [kN] -> N -> masa = W/g
            peso_N = self.masa_carga * 1e3 * self.masa_area
            m = peso_N / 9.80665
            return Magnitud(m, "desde carga distribuida",
                            f"W = q·A = {numero(self.masa_carga)} kN/m² × "
                            f"{numero(self.masa_area)} m² = "
                            f"{numero(peso_N / 1e3)} kN  →  "
                            f"m = W/g = {_en_si(m, 'kg')}")
        m = a_si(self.masa_valor, self.masa_unidad)
        if self.masa_unidad in ("N", "kN", "kgf"):
            # El usuario escribió un PESO; se convierte a masa dividiendo por g.
            m = m / 9.80665
            return Magnitud(m, "desde peso",
                            f"m = W/g = {numero(self.masa_valor)} "
                            f"{self.masa_unidad} / 9,80665 = {_en_si(m, 'kg')}")
        return Magnitud(m, "directa", f"m = {_en_si(m, 'kg')}")

    # ------------------------------------------------------------------
    #  Pórtico
    # ------------------------------------------------------------------
    def polinomios(self) -> list[dict[int, float]]:
        """Rigidez de piso de cada nivel, como polinomios en x."""
        if not self.niveles:
            raise ValueError("El pórtico no tiene niveles.")
        return [n.polinomio() for n in self.niveles]

    def es_simbolico(self) -> bool:
        """¿Alguna sección quedó en función de la incógnita x?"""
        try:
            return any(max(p) > 0 for p in self.polinomios())
        except ValueError:
            return False

    def rigidez_portico(self) -> float:
        """Rigidez lateral equivalente del pórtico [N/m], evaluada en ``x_actual``."""
        return rigidez_serie_niveles(self.polinomios(), self.x_actual)

    # ------------------------------------------------------------------
    #  Rigidez
    # ------------------------------------------------------------------
    def rigidez(self) -> Magnitud:
        """Rigidez lateral en N/m, con su procedencia."""
        if self.rigidez_modo == "portico":
            k = self.rigidez_portico()
            n = len(self.niveles)
            serie = (" en serie" if n > 1 else "")
            detalle = (f"{n} nivel(es){serie}, columnas y riostras de cada nivel "
                       f"en paralelo")
            if self.es_simbolico():
                detalle += f", evaluado en x = {numero(self.x_actual)} m"
            return Magnitud(k, "desde el pórtico",
                            detalle + f"  →  k = {_en_si(k, 'N/m')}")

        if self.rigidez_modo == "periodo":
            m = float(self.masa())
            k = m * (2 * math.pi / self.periodo_objetivo) ** 2
            return Magnitud(k, "desde el periodo",
                            f"k = m·(2π/Tₙ)² = {numero(m)}·"
                            f"(2π/{numero(self.periodo_objetivo)})² "
                            f"= {_en_si(k, 'N/m')}")

        k = a_si(self.rigidez_valor, self.rigidez_unidad)
        return Magnitud(k, "directa", f"k = {_en_si(k, 'N/m')}")

    # ------------------------------------------------------------------
    #  Amortiguamiento
    # ------------------------------------------------------------------
    def zeta(self) -> Magnitud:
        """Fracción de amortiguamiento crítico, con su procedencia."""
        return Magnitud(self.zeta_valor, self.zeta_procedencia,
                        self.zeta_detalle or
                        f"ζ = {numero(self.zeta_valor)} "
                        f"({numero(self.zeta_valor * 100)} %)")

    def fijar_zeta(self, valor: float, procedencia: str, detalle: str = "") -> None:
        """Registra un ζ obtenido por un procedimiento (decremento, ancho de banda)."""
        self.zeta_valor = valor
        self.zeta_procedencia = procedencia
        self.zeta_detalle = detalle

    # ------------------------------------------------------------------
    #  Derivación del sistema
    # ------------------------------------------------------------------
    def sistema(self) -> SistemaSDOF:
        """Construye el ``SistemaSDOF`` a partir del estado actual.

        Se recalcula en cada llamada: es la razón por la que los cambios se
        propagan solos entre pestañas.
        """
        return SistemaSDOF(masa=float(self.masa()),
                           rigidez=float(self.rigidez()),
                           zeta=self.zeta_valor,
                           nombre=self.nombre)

    def problemas(self) -> list[str]:
        """Lista de razones por las que el sistema no se puede derivar todavía.

        Vacía cuando todo está bien. Permite que la interfaz avise con un
        mensaje entendible en vez de dejar escapar una excepción.
        """
        fallas: list[str] = []
        try:
            m = float(self.masa())
            if m <= 0:
                fallas.append("La masa debe ser positiva.")
        except Exception as exc:
            fallas.append(f"Masa: {exc}")
        try:
            k = float(self.rigidez())
            if k <= 0:
                fallas.append("La rigidez debe ser positiva.")
        except Exception as exc:
            fallas.append(f"Rigidez: {exc}")
        if not 0 <= self.zeta_valor < 1:
            fallas.append("El amortiguamiento debe cumplir 0 ≤ ζ < 1.")
        return fallas


def proyecto_por_defecto() -> Proyecto:
    """Proyecto inicial: un pórtico de un nivel con cuatro columnas de acero."""
    columna = Columna(nombre="Columnas del nivel", n=4, E=200.0, E_unidad="GPa",
                      H=3.5, condicion="empotrada-empotrada",
                      modo_seccion="I", I=3692.0, I_unidad="cm4")
    return Proyecto(niveles=[Nivel(nombre="Nivel 1", columnas=[columna])])
