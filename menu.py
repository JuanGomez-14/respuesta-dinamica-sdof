#!/usr/bin/env python3
"""
================================================================================
 MENÚ INTERACTIVO POR CONSOLA
 Laboratorio Computacional de Respuesta Dinámica · Universidad de Medellín
================================================================================

Permite usar todo el motor de cálculo **sin escribir código ni recordar
comandos**: se ejecuta, aparece un menú y los datos se ingresan uno por uno,
con valores por defecto y con las unidades indicadas en cada pregunta.

Ejecución:
    python menu.py
    python main.py menu
    python main.py            (sin argumentos también abre el menú)

Facilidades de entrada
----------------------
* Se puede escribir el valor con su unidad y el programa lo convierte a SI:
      Masa m [kg]: 30 t          ->  30 000 kg
      Rigidez k [N/m]: 8500 kN/m ->  8.5e6 N/m
      Inercia I [m^4]: 3692 cm4  ->  3.692e-5 m^4
* Se acepta la coma decimal (3,5 = 3.5).
* ENTER en blanco toma el valor por defecto que aparece entre corchetes.
* En cualquier pregunta se puede escribir 'x' para cancelar y volver al menú.
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import numpy as np

from dinamica import (G, CargaArbitraria, CargaArmonica, CargaChirp,
                      ExcitacionBase, PulsoExponencial, PulsoRectangular,
                      PulsoSemiseno, PulsoTriangular, Rd, Rd_maximo, SistemaSDOF,
                      TABLA_UNIDADES, a_si, angulo_fase, barrido_carga,
                      barrido_parametro, derivar_aceleracion, espectro_respuesta,
                      generar_registro_sintetico, graficos, leer_csv,
                      leer_peer_at2, periodos_logaritmicos, resolver,
                      resolver_base, rigidez_columna, rigidez_paralelo,
                      rigidez_serie, sdof_equivalente_voladizo, transmisibilidad,
                      vector_tiempo, vibracion_libre)
from dinamica.graficos import (graficar_Rd, graficar_TR, graficar_acelerograma,
                               graficar_barrido, graficar_comparacion,
                               graficar_espectro, graficar_fase,
                               graficar_historia, graficar_pulso_fases,
                               graficar_respuesta_sismica)
from dinamica.unidades import FACTORES_A_SI
from dinamica.verificacion import verificar_todo

SALIDAS = Path("salidas/menu")


# ===========================================================================
#  Utilidades de presentación
# ===========================================================================
ANCHO = 74


class Cancelado(Exception):
    """El usuario escribió 'x' para volver al menú anterior."""


def titulo(texto: str) -> None:
    print()
    print("=" * ANCHO)
    print(f" {texto}")
    print("=" * ANCHO)


def subtitulo(texto: str) -> None:
    print()
    print(f"--- {texto} " + "-" * max(0, ANCHO - len(texto) - 6))


def aviso(texto: str, tipo: str = "info") -> None:
    marca = {"info": "[i]", "ok": "[✓]", "alerta": "[!]", "error": "[X]"}[tipo]
    print()
    for i, linea in enumerate(_envolver(texto, ANCHO - 6)):
        print(f" {marca if i == 0 else '   '} {linea}")


def _envolver(texto: str, ancho: int) -> list[str]:
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        if len(actual) + len(p) + 1 > ancho:
            lineas.append(actual)
            actual = p
        else:
            actual = f"{actual} {p}".strip()
    if actual:
        lineas.append(actual)
    return lineas or [""]


def abrir_archivo(ruta) -> bool:
    """Abre un archivo (figura, CSV o PDF) con el programa por defecto del
    sistema operativo. Devuelve True si se pudo lanzar."""
    import os
    import platform
    ruta = str(ruta)
    try:
        if platform.system() == "Darwin":            # macOS
            subprocess.Popen(["open", ruta])
        elif os.name == "nt":                        # Windows
            os.startfile(ruta)                       # type: ignore[attr-defined]
        else:                                        # Linux
            subprocess.Popen(["xdg-open", ruta],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def pausa() -> None:
    try:
        input("\n   Presione ENTER para volver al menú... ")
    except EOFError:
        pass


# ===========================================================================
#  Utilidades de entrada de datos
# ===========================================================================
def _leer(mensaje: str) -> str:
    try:
        texto = input(mensaje).strip()
    except EOFError:
        raise SystemExit("\n\nEntrada terminada. Hasta luego.")
    except KeyboardInterrupt:
        raise SystemExit("\n\nInterrumpido por el usuario. Hasta luego.")
    if texto.lower() in ("x", "salir", "cancelar"):
        raise Cancelado
    return texto


def pedir_numero(mensaje: str, defecto: float | None = None,
                 minimo: float | None = None, maximo: float | None = None,
                 unidad_si: str | None = None) -> float:
    """Pide un número, admitiendo unidades ('30 t'), coma decimal y un defecto.

    ``unidad_si`` es sólo informativo (la unidad en que se interpreta el valor
    si el usuario no escribe ninguna).
    """
    sufijo = f" [{_formato(defecto)}]" if defecto is not None else ""
    while True:
        texto = _leer(f"   {mensaje}{sufijo}: ")
        if not texto:
            if defecto is not None:
                return float(defecto)
            print("      · Debe ingresar un valor.")
            continue
        texto = texto.replace(",", ".")
        partes = texto.split()
        try:
            valor = float(partes[0])
            if len(partes) > 1:                      # trae unidad
                unidad = " ".join(partes[1:])
                if unidad not in FACTORES_A_SI:
                    print(f"      · Unidad '{unidad}' no reconocida. "
                          f"Válidas: {', '.join(sorted(FACTORES_A_SI))}")
                    continue
                convertido = a_si(valor, unidad)
                print(f"      · {valor:g} {unidad} = {_formato(convertido)}"
                      f"{' ' + unidad_si if unidad_si else ''}")
                valor = convertido
        except ValueError:
            print("      · No es un número válido. Ejemplos: 24000 · 3,5 · 30 t")
            continue
        if minimo is not None and valor < minimo:
            print(f"      · El valor debe ser mayor o igual que {minimo}.")
            continue
        if maximo is not None and valor > maximo:
            print(f"      · El valor debe ser menor o igual que {maximo}.")
            continue
        return valor


def pedir_entero(mensaje: str, defecto: int | None = None,
                 minimo: int = 1) -> int:
    return int(pedir_numero(mensaje, defecto, minimo=minimo))


def pedir_texto(mensaje: str, defecto: str = "") -> str:
    sufijo = f" [{defecto}]" if defecto else ""
    texto = _leer(f"   {mensaje}{sufijo}: ")
    return texto or defecto


def pedir_si_no(mensaje: str, defecto: bool = True) -> bool:
    sufijo = " [S/n]" if defecto else " [s/N]"
    while True:
        texto = _leer(f"   {mensaje}{sufijo}: ").lower()
        if not texto:
            return defecto
        if texto in ("s", "si", "sí", "y", "yes"):
            return True
        if texto in ("n", "no"):
            return False
        print("      · Responda 's' o 'n'.")


def pedir_opcion(titulo_menu: str, opciones: list[str],
                 defecto: int | None = None) -> int:
    """Muestra una lista numerada y devuelve el índice (base 0) elegido."""
    print()
    print(f"   {titulo_menu}")
    for i, op in enumerate(opciones, start=1):
        print(f"      {i}. {op}")
    sufijo = f" [{defecto}]" if defecto else ""
    while True:
        texto = _leer(f"   Opción{sufijo}: ")
        if not texto and defecto:
            return defecto - 1
        if texto.isdigit() and 1 <= int(texto) <= len(opciones):
            return int(texto) - 1
        print(f"      · Escriba un número entre 1 y {len(opciones)}.")


def _formato(x: float) -> str:
    if x is None:
        return ""
    a = abs(x)
    if a != 0 and (a >= 1e5 or a < 1e-3):
        return f"{x:.4g}"
    return f"{x:g}"


# ===========================================================================
#  Aplicación
# ===========================================================================
class Aplicacion:
    """Estado y flujo del menú interactivo."""

    def __init__(self) -> None:
        self.sistema: SistemaSDOF | None = None
        self.ultima_carga = None
        self.ultima_respuesta = None
        self.ultima_excitacion: ExcitacionBase | None = None
        graficos.usar_carpeta(SALIDAS)

    # ---------------------------------------------------------------- menú
    def ejecutar(self) -> None:
        self._bienvenida()
        opciones = [
            ("Definir o modificar el sistema (m, k, ζ)", self.definir_sistema),
            ("Carga ARMÓNICA (máquina, viento periódico...)", self.analisis_armonico),
            ("Carga IMPULSIVA (impacto, explosión, frenado)", self.analisis_impulsivo),
            ("Excitación ARBITRARIA (sismo o señal de archivo)", self.analisis_arbitrario),
            ("Vibración LIBRE (prueba de pull-back)", self.analisis_libre),
            ("Curvas de amplificación Rd, transmisibilidad TR y fase", self.curvas),
            ("Espectro de respuesta de un acelerograma", self.espectro),
            ("Análisis PARAMÉTRICO (barrer una variable)", self.parametrico),
            ("Verificar el motor de cálculo (pruebas automáticas)", self.verificar),
            ("Resolver los DOS CASOS DE ESTUDIO", self.casos),
            ("Generar el REPORTE TÉCNICO en PDF", self.reporte),
            ("Ver / abrir los resultados generados (figuras y CSV)", self.ver_resultados),
            ("Ayuda: unidades y convenciones", self.ayuda),
        ]
        while True:
            self._encabezado()
            for i, (texto, _) in enumerate(opciones, start=1):
                print(f"   {i:2d}. {texto}")
            print("    0. Salir")
            try:
                eleccion = _leer("\n   Elija una opción: ")
            except Cancelado:
                continue
            if eleccion == "0":
                print("\n   Hasta luego. Los resultados quedaron en "
                      f"'{SALIDAS}'.\n")
                return
            if not eleccion.isdigit() or not (1 <= int(eleccion) <= len(opciones)):
                aviso("Opción no válida. Escriba un número del menú.", "error")
                pausa()
                continue
            try:
                opciones[int(eleccion) - 1][1]()
            except Cancelado:
                aviso("Operación cancelada; se vuelve al menú principal.", "info")
                pausa()
            except Exception as exc:                      # error controlado
                aviso(f"Ocurrió un error: {exc}", "error")
                pausa()

    def _bienvenida(self) -> None:
        print()
        print("╔" + "═" * (ANCHO - 2) + "╗")
        for linea in ["LABORATORIO COMPUTACIONAL DE RESPUESTA DINÁMICA",
                      "Sistemas de un grado de libertad (SDOF)",
                      "Universidad de Medellín · Dinámica de Estructuras"]:
            print("║" + linea.center(ANCHO - 2) + "║")
        print("╚" + "═" * (ANCHO - 2) + "╝")
        print("\n   Todos los datos se ingresan en unidades SI (kg, N/m, N, s),")
        print("   pero puede escribir la unidad y se convierte sola: '30 t', '8500 kN/m'.")
        print("   Escriba 'x' en cualquier pregunta para cancelar y volver al menú.")

    def _encabezado(self) -> None:
        print()
        print("-" * ANCHO)
        if self.sistema is None:
            print(" SISTEMA ACTUAL: (sin definir — use la opción 1)")
        else:
            s = self.sistema
            print(f" SISTEMA ACTUAL: m = {s.masa:,.1f} kg | k = {s.rigidez:,.1f} N/m "
                  f"| ζ = {s.zeta:.3f}")
            print(f"                 ωn = {s.omega_n:.4f} rad/s | fn = {s.f_n:.4f} Hz "
                  f"| Tn = {s.T_n:.4f} s")
        if self.ultima_carga is not None:
            print(f" ÚLTIMA CARGA:   {self.ultima_carga.descripcion()[:ANCHO-18]}")
        print("-" * ANCHO)
        print(" MENÚ PRINCIPAL")

    # ------------------------------------------------------ 1. el sistema
    def definir_sistema(self) -> None:
        titulo("DEFINICIÓN DEL SISTEMA DE UN GRADO DE LIBERTAD")
        print("\n   La estructura real se reduce a tres números: masa (m),")
        print("   rigidez (k) y fracción de amortiguamiento crítico (ζ).")

        modo = pedir_opcion("¿Cómo desea definir la RIGIDEZ?", [
            "Directamente, ingresando k [N/m]",
            "Por geometría: columnas con E, I, L (12EI/L³ o 3EI/L³)",
            "Por el periodo natural Tn [s] (si lo midió o lo conoce)",
            "Por la frecuencia natural fn [Hz]",
            "Voladizo con masa distribuida (método de Rayleigh)",
            "Varios resortes en serie o en paralelo",
        ], defecto=1)

        if modo == 4:                       # voladizo con masa distribuida
            self._sistema_voladizo()
            return

        masa = pedir_numero("Masa m [kg]", minimo=1e-9, unidad_si="kg")

        if modo == 0:
            k = pedir_numero("Rigidez k [N/m]", minimo=1e-9, unidad_si="N/m")
        elif modo == 1:
            k = self._rigidez_por_geometria()
        elif modo == 2:
            Tn = pedir_numero("Periodo natural Tn [s]", minimo=1e-9)
            k = masa * (2 * math.pi / Tn) ** 2
            print(f"      · k = m·(2π/Tn)² = {k:,.1f} N/m")
        elif modo == 3:
            fn = pedir_numero("Frecuencia natural fn [Hz]", minimo=1e-9)
            k = masa * (2 * math.pi * fn) ** 2
            print(f"      · k = m·(2π·fn)² = {k:,.1f} N/m")
        else:
            k = self._rigidez_asociada()

        zeta = pedir_numero("Fracción de amortiguamiento ζ (0.02 acero, 0.05 concreto)",
                            defecto=0.05, minimo=0.0, maximo=0.99)
        nombre = pedir_texto("Nombre del sistema", "Sistema analizado")
        self.sistema = SistemaSDOF(masa=masa, rigidez=k, zeta=zeta, nombre=nombre)
        self._mostrar_sistema()
        pausa()

    def _rigidez_por_geometria(self) -> float:
        print("\n   Rigidez lateral de columnas iguales trabajando en paralelo:")
        E = pedir_numero("Módulo de elasticidad E [Pa] (acero 200e9, concreto 25e9)",
                         defecto=200e9, minimo=1.0, unidad_si="Pa")
        I = pedir_numero("Inercia de la sección I [m^4] (admite 'cm4')",
                         minimo=1e-15, unidad_si="m^4")
        L = pedir_numero("Altura libre L [m]", minimo=1e-6, unidad_si="m")
        n = pedir_entero("Número de columnas iguales", defecto=1)
        cond = ["empotrada-empotrada", "voladizo"][pedir_opcion(
            "Condición de apoyo de las columnas:", [
                "Empotrada-empotrada (viga o losa muy rígida)  →  k = 12·E·I/L³",
                "En voladizo / cabeza libre de girar           →  k = 3·E·I/L³",
            ], defecto=1)]
        k = rigidez_columna(E, I, L, condicion=cond, n=n)
        coef = 12 if cond == "empotrada-empotrada" else 3
        print(f"      · k = {n} × {coef}·E·I/L³ = {k:,.1f} N/m")
        return k

    def _rigidez_asociada(self) -> float:
        disposicion = pedir_opcion("¿Cómo trabajan los elementos?", [
            "En PARALELO (mismo desplazamiento; se suman las rigideces)",
            "En SERIE (misma fuerza; se suman las flexibilidades)",
        ], defecto=1)
        n = pedir_entero("¿Cuántos elementos?", defecto=2, minimo=2)
        ks = [pedir_numero(f"Rigidez del elemento {i+1} [N/m]", minimo=1e-9)
              for i in range(n)]
        k = rigidez_paralelo(ks) if disposicion == 0 else rigidez_serie(ks)
        print(f"      · k equivalente = {k:,.1f} N/m")
        return k

    def _sistema_voladizo(self) -> None:
        print("\n   Sistema equivalente de 1 GDL para un voladizo (torre, poste,")
        print("   tanque elevado) con masa distribuida y masa concentrada arriba.")
        E = pedir_numero("Módulo de elasticidad E [Pa]", defecto=25e9, minimo=1.0)
        I = pedir_numero("Inercia de la sección I [m^4] (admite 'cm4')", minimo=1e-15)
        L = pedir_numero("Altura H [m]", minimo=1e-6)
        masa_lineal = pedir_numero("Masa por unidad de longitud [kg/m]",
                                   defecto=0.0, minimo=0.0)
        masa_conc = pedir_numero("Masa concentrada en la punta [kg]",
                                 defecto=0.0, minimo=0.0)
        zeta = pedir_numero("Fracción de amortiguamiento ζ", defecto=0.05,
                            minimo=0.0, maximo=0.99)
        nombre = pedir_texto("Nombre del sistema", "Voladizo equivalente")
        self.sistema = sdof_equivalente_voladizo(
            E=E, I=I, L=L, masa_lineal=masa_lineal, masa_concentrada=masa_conc,
            zeta=zeta, nombre=nombre)
        print(f"\n      · k = 3·E·I/H³ = {self.sistema.rigidez:,.1f} N/m")
        print(f"      · m* = (33/140)·m_distribuida + m_concentrada = "
              f"{self.sistema.masa:,.1f} kg")
        self._mostrar_sistema()
        pausa()

    def _mostrar_sistema(self) -> None:
        s = self.sistema
        subtitulo("PROPIEDADES DINÁMICAS DEL SISTEMA")
        print(s.resumen())
        aviso(f"Periodo natural Tn = {s.T_n:.4f} s. Toda la respuesta dependerá de "
              f"comparar este 'reloj' de la estructura con el de la excitación.", "ok")

    def _exigir_sistema(self) -> SistemaSDOF:
        if self.sistema is None:
            aviso("Primero debe definir el sistema. Se abre la opción 1.", "alerta")
            self.definir_sistema()
        if self.sistema is None:
            raise Cancelado
        return self.sistema

    # -------------------------------------------------- 2. carga armónica
    def analisis_armonico(self) -> None:
        s = self._exigir_sistema()
        titulo("RESPUESTA ANTE CARGA ARMÓNICA   p(t) = p₀·sen(ω·t)")
        p0 = pedir_numero("Amplitud de la fuerza p₀ [N] (admite 'kN')", minimo=0.0,
                          unidad_si="N")

        modo = pedir_opcion("¿Cómo conoce la frecuencia de la excitación?", [
            "Frecuencia en Hz (ciclos por segundo)",
            "Velocidad de una máquina en rpm",
            "Frecuencia circular ω en rad/s",
            "Relación de frecuencias β = ω/ωn (para estudiar un escenario)",
        ], defecto=1)
        if modo == 0:
            w = 2 * math.pi * pedir_numero("Frecuencia f [Hz]", minimo=1e-9)
        elif modo == 1:
            w = 2 * math.pi * pedir_numero("Velocidad [rpm]", minimo=1e-9) / 60.0
        elif modo == 2:
            w = pedir_numero("Frecuencia circular ω [rad/s]", minimo=1e-9)
        else:
            w = pedir_numero("Relación β = ω/ωn", minimo=1e-9) * s.omega_n

        t_final = pedir_numero("Duración del análisis [s]",
                               defecto=round(20 * s.T_n, 3), minimo=1e-6)
        u0 = pedir_numero("Desplazamiento inicial u₀ [m]", defecto=0.0)
        v0 = pedir_numero("Velocidad inicial v₀ [m/s]", defecto=0.0)

        carga = CargaArmonica(p0=p0, omega=w)
        dt = s.T_n / 200.0
        r = resolver(s, carga, t_final=t_final, dt=dt, u0=u0, v0=v0)
        self.ultima_carga, self.ultima_respuesta = carga, r

        beta = s.beta(w)
        rd = float(Rd(beta, s.zeta))
        tr = float(transmisibilidad(beta, s.zeta))
        u_est = p0 / s.rigidez

        subtitulo("RESULTADOS")
        print(f"   Frecuencia de excitación        f = {w/(2*math.pi):.4f} Hz "
              f"(ω = {w:.4f} rad/s)")
        print(f"   Relación de frecuencias         β = {beta:.4f}")
        print(f"   Factor de amplificación        Rd = {rd:.4f}   "
              f"(máximo posible con ζ={s.zeta:.3f}: {Rd_maximo(s.zeta):.3f})")
        print(f"   Ángulo de fase                  φ = "
              f"{math.degrees(float(angulo_fase(beta, s.zeta))):.2f}°")
        print(f"   Desplazamiento estático  u_st = p₀/k = {u_est*1e3:.4f} mm")
        print(f"   Amplitud permanente      u₀ = u_st·Rd = {u_est*rd*1e3:.4f} mm")
        print(f"   Pico total (transitorio + permanente) = {r.u_max*1e3:.4f} mm "
              f"en t = {r.t_u_max:.3f} s")
        print(f"   Velocidad máxima                      = {r.v_max*1e3:.2f} mm/s")
        print(f"   Aceleración máxima                    = {r.a_max:.4f} m/s² "
              f"({r.a_max/G:.4f} g)")
        print(f"   Cortante basal máximo  V = k·u        = {r.cortante_max/1e3:.3f} kN")
        print(f"   Transmisibilidad               TR = {tr:.4f}")
        print(f"   Fuerza transmitida al apoyo  fT = p₀·TR = {p0*tr/1e3:.3f} kN")

        self._interpretar_armonica(beta, s.zeta, tr)
        self._guardar(r, "armonica", tipo="historia")
        if pedir_si_no("¿Comparar con la solución analítica exacta (verificación)?", False):
            from dinamica import respuesta_armonica
            exacta = respuesta_armonica(s, carga, r.t, u0, v0)
            err = abs(r.u_max - exacta.u_max) / exacta.u_max * 100
            print(f"\n   Analítica exacta |u|máx = {exacta.u_max*1e3:.6f} mm")
            print(f"   Newmark          |u|máx = {r.u_max*1e3:.6f} mm  → error = {err:.5f} %")
            ruta = graficar_comparacion(
                [exacta.recortar(0, min(t_final, 6 * s.T_n)),
                 r.recortar(0, min(t_final, 6 * s.T_n))],
                ["Analítica exacta", "Newmark"],
                titulo="Verificación: analítica vs. Newmark",
                nombre_archivo=self._nombre_unico("armonica_verificacion"))
            print(f"   Figura de comparación: {ruta}")
            self._ofrecer_abrir(ruta)
        pausa()

    @staticmethod
    def _interpretar_armonica(beta: float, zeta: float, tr: float) -> None:
        if abs(beta - 1.0) < 0.15:
            aviso("¡RESONANCIA! β está muy cerca de 1: la frecuencia de la carga casi "
                  f"coincide con la natural. Aquí Rd ≈ 1/(2ζ) = {1/(2*zeta) if zeta else float('inf'):.1f} "
                  "y el amortiguamiento es lo ÚNICO que limita la respuesta. "
                  "Soluciones: desintonizar (cambiar k o m), amortiguar o cambiar la "
                  "velocidad de operación.", "alerta")
        elif beta < 0.4:
            aviso("β << 1: zona CUASI-ESTÁTICA. La carga es lenta comparada con la "
                  "estructura, que la sigue casi sin amplificar. Manda la RIGIDEZ.", "info")
        elif beta > math.sqrt(2):
            aviso(f"β > √2 = 1.414: zona de AISLAMIENTO (TR = {tr:.3f}). Sólo llega al "
                  f"apoyo el {tr*100:.1f} % de la fuerza. Manda la MASA (inercia). "
                  "Ojo: aquí más amortiguamiento EMPEORA la transmisión de fuerza.", "ok")
        else:
            aviso(f"1.15 < β < 1.41 aproximadamente: todavía en zona de AMPLIFICACIÓN "
                  f"(TR = {tr:.3f} > 1). Para aislar hay que superar β = √2.", "info")

    # ------------------------------------------------ 3. carga impulsiva
    def analisis_impulsivo(self) -> None:
        s = self._exigir_sistema()
        titulo("RESPUESTA ANTE CARGA IMPULSIVA")
        tipos = [
            ("Triangular decreciente (explosión idealizada)",
             lambda p, t: PulsoTriangular(p, t, "decreciente")),
            ("Rectangular (carga súbita de duración finita)",
             lambda p, t: PulsoRectangular(p, t)),
            ("Medio seno (impacto suave)", lambda p, t: PulsoSemiseno(p, t)),
            ("Triangular creciente", lambda p, t: PulsoTriangular(p, t, "creciente")),
            ("Triangular simétrico", lambda p, t: PulsoTriangular(p, t, "simetrico")),
            ("Exponencial de Friedlander (onda de choque)",
             lambda p, t: PulsoExponencial(p, t)),
        ]
        i = pedir_opcion("Forma del pulso:", [t[0] for t in tipos], defecto=1)
        p0 = pedir_numero("Fuerza pico p₀ [N] (admite 'kN')", minimo=0.0, unidad_si="N")
        td = pedir_numero("Duración del pulso td [s]", minimo=1e-9)
        t_final = pedir_numero("Duración del análisis [s]",
                               defecto=round(max(8 * s.T_n, 10 * td), 3), minimo=td)

        carga = tipos[i][1](p0, td)
        dt = min(td, s.T_n) / 300.0
        r = resolver(s, carga, t_final=t_final, dt=dt)
        self.ultima_carga, self.ultima_respuesta = carga, r

        razon = td / s.T_n
        rd = r.u_max * s.rigidez / p0 if p0 else float("nan")
        impulso = getattr(carga, "impulso", 0.5 * p0 * td)

        subtitulo("RESULTADOS")
        print(f"   Relación duración/periodo   td/Tn = {razon:.4f}")
        print(f"   Impulso total          I = ∫p·dt = {impulso:,.2f} N·s")
        print(f"   Desplazamiento estático  p₀/k    = {p0/s.rigidez*1e3:.4f} mm")
        print(f"   Desplazamiento máximo    |u|máx  = {r.u_max*1e3:.4f} mm "
              f"en t = {r.t_u_max:.4f} s "
              f"({'FASE LIBRE' if r.t_u_max > td else 'fase forzada'})")
        print(f"   Factor de amplificación  Rd      = {rd:.4f}")
        print(f"   Cortante basal máximo            = {r.cortante_max/1e3:.3f} kN")
        print(f"   Aproximación impulsiva I/(m·ωn)  = "
              f"{impulso/(s.masa*s.omega_n)*1e3:.4f} mm")

        if razon < 0.25:
            aviso("RÉGIMEN IMPULSIVO (td/Tn < 0.25): la carga desaparece antes de que "
                  "la estructura alcance a responder. Lo que gobierna es el IMPULSO "
                  "total, no la fuerza pico ni la forma del pulso, y el máximo ocurre "
                  "después del pulso, en vibración libre.", "info")
        elif razon > 3:
            aviso("RÉGIMEN CUASI-ESTÁTICO (td/Tn >> 1): la carga es tan lenta que la "
                  "estructura la sigue; Rd tiende al valor estático (2 para el pulso "
                  "rectangular, por la aplicación súbita).", "info")
        else:
            aviso("ZONA DE AMPLIFICACIÓN DINÁMICA (0.25 < td/Tn < 3): es el rango más "
                  "desfavorable; aquí Rd alcanza sus valores máximos (hasta 2).", "alerta")

        base = self._nombre_unico("impulsiva")
        ruta = graficar_pulso_fases(r, td, titulo=f"Respuesta ante {carga.nombre.lower()}",
                                    nombre_archivo=base)
        csv = r.a_csv(SALIDAS / f"{base}.csv")
        print(f"\n   Figura : {ruta}")
        print(f"   CSV    : {csv}")
        self._ofrecer_abrir(ruta)
        pausa()

    # ---------------------------------------------- 4. carga arbitraria
    def analisis_arbitrario(self) -> None:
        s = self._exigir_sistema()
        titulo("RESPUESTA ANTE EXCITACIÓN ARBITRARIA (MÉTODO DE NEWMARK)")
        origen = pedir_opcion("Origen de la señal:", [
            "Archivo CSV/TXT de dos columnas (tiempo, valor)",
            "Archivo PEER NGA (.AT2) de un sismo real",
            "Registro sísmico sintético generado por el programa",
        ], defecto=3)

        if origen == 2:
            pga = pedir_numero("Aceleración pico del terreno objetivo [g]",
                               defecto=0.20, minimo=0.001)
            dur = pedir_numero("Duración del registro [s]", defecto=30.0, minimo=1.0)
            semilla = pedir_entero("Semilla (para poder repetir el mismo registro)",
                                   defecto=2026)
            exc = generar_registro_sintetico(duracion=dur, dt=0.005,
                                             pga_objetivo=pga * G, semilla=semilla)
            t, valores, es_fuerza = exc.t, exc.ag, False
        else:
            ruta = pedir_texto("Ruta del archivo",
                               "casos/datos/registro_sintetico.csv")
            if not Path(ruta).exists():
                aviso(f"No se encontró el archivo '{ruta}'.", "error")
                pausa()
                return
            if origen == 1:
                t, valores = leer_peer_at2(ruta)
                es_fuerza = False
                print("      · Formato PEER leído; valores convertidos de g a m/s².")
            else:
                contenido = pedir_opcion("¿Qué contiene la segunda columna?", [
                    "Aceleración del terreno (sismo)",
                    "Desplazamiento del terreno (se derivará dos veces)",
                    "Fuerza p(t) aplicada a la masa",
                ], defecto=1)
                unidades = {0: ["g", "m/s2", "cm/s2", "gal"],
                            1: ["m", "cm", "mm"],
                            2: ["N", "kN", "tonf"]}[contenido]
                u = unidades[pedir_opcion("Unidad de esa columna:", unidades, defecto=1)]
                t, valores = leer_csv(ruta, unidad_valor=u)
                es_fuerza = contenido == 2
                if contenido == 1:
                    valores = derivar_aceleracion(t, valores)
                    print("      · Señal derivada dos veces para obtener la aceleración.")
            exc = None

        subtitulo("RESULTADOS")
        if es_fuerza:
            carga = CargaArbitraria(t, valores, nombre=Path(ruta).name)
            r = resolver(s, carga, dt=min(float(np.min(np.diff(t))), s.T_n / 100))
            self.ultima_carga = carga
            print(f"   {carga.descripcion()}")
        else:
            exc = exc or ExcitacionBase(t, valores, nombre="Señal cargada")
            self.ultima_excitacion = exc
            print(f"   {exc.descripcion()}")
            r = resolver_base(s, exc)
            print(f"   Aceleración absoluta máxima  = {r.a_abs_max:.4f} m/s² "
                  f"({r.a_abs_max/G:.4f} g)  → amplificación {r.a_abs_max/exc.pga:.2f}× "
                  f"respecto a la PGA")
            print(f"   Coeficiente sísmico V/W      = "
                  f"{r.cortante_max/(s.masa*G):.4f}")
        self.ultima_respuesta = r
        print(f"   Desplazamiento relativo máximo = {r.u_max*1e3:.3f} mm "
              f"en t = {r.t_u_max:.3f} s")
        print(f"   Velocidad máxima               = {r.v_max:.4f} m/s")
        print(f"   Cortante basal máximo  V = k·u = {r.cortante_max/1e3:.2f} kN")

        if pedir_si_no("¿Mostrar la verificación numérica de esta solución?", True):
            print()
            print(verificar_todo(r).texto())

        self._guardar(r, "arbitraria", tipo="sismica" if not es_fuerza else "historia")
        if not es_fuerza and pedir_si_no("¿Graficar también el acelerograma?", False):
            ruta_ag = graficar_acelerograma(
                exc, nombre_archivo=self._nombre_unico("acelerograma"))
            print(f"   Figura: {ruta_ag}")
            self._ofrecer_abrir(ruta_ag)
        pausa()

    # ------------------------------------------------- 5. vibración libre
    def analisis_libre(self) -> None:
        s = self._exigir_sistema()
        titulo("VIBRACIÓN LIBRE (prueba de pull-back)")
        u0 = pedir_numero("Desplazamiento inicial u₀ [m] (admite 'mm')",
                          defecto=0.02, unidad_si="m")
        v0 = pedir_numero("Velocidad inicial v₀ [m/s]", defecto=0.0)
        nciclos = pedir_entero("Número de ciclos a analizar", defecto=10)

        t = vector_tiempo(nciclos * s.T_n, s.T_n / 400)
        r = vibracion_libre(s, t, u0=u0, v0=v0)
        self.ultima_respuesta = r

        delta = (2 * math.pi * s.zeta / math.sqrt(1 - s.zeta ** 2)) if s.zeta else 0.0
        subtitulo("RESULTADOS")
        print(f"   Periodo natural              Tn = {s.T_n:.5f} s")
        print(f"   Periodo amortiguado          TD = {s.T_D:.5f} s")
        print(f"   Decremento logarítmico        δ = {delta:.5f}")
        print(f"   Reducción de amplitud por ciclo = "
              f"{(1-math.exp(-delta))*100:.2f} %")
        print(f"   Ciclos hasta reducir al 10 %    ≈ "
              f"{math.log(10)/delta:.1f}" if delta > 0 else
              "   Sin amortiguamiento: la amplitud no decae")
        print(f"   |u|máx = {r.u_max*1e3:.4f} mm | |v|máx = {r.v_max:.4f} m/s")
        aviso("En vibración libre el sistema sólo muestra sus propiedades: periodo y "
              "amortiguamiento. Es la prueba que se usa en campo para identificar ζ "
              "midiendo cuánto decae la amplitud entre picos sucesivos.", "info")
        self._guardar(r, "vibracion_libre", tipo="historia", paneles=("u", "v"))
        pausa()

    # ---------------------------------------------------- 6. curvas Rd/TR
    def curvas(self) -> None:
        titulo("CURVAS DE RESPUESTA EN FRECUENCIA (Rd, TR y ángulo de fase)")
        texto = pedir_texto("Amortiguamientos a graficar, separados por comas",
                            "0.02,0.05,0.10,0.20,0.50")
        zetas = [float(z.strip().replace(",", ".")) for z in texto.split(",") if z.strip()]
        marcar = None
        if pedir_si_no("¿Señalar un punto de operación en las curvas?", True):
            b = pedir_numero("Relación de frecuencias β del punto", defecto=1.0, minimo=0.0)
            z = pedir_numero("Amortiguamiento ζ del punto", defecto=zetas[0],
                             minimo=0.0, maximo=0.99)
            marcar = dict(beta=b, zeta=z)
            print(f"\n      · Rd = {float(Rd(b, z)):.4f}")
            print(f"      · TR = {float(transmisibilidad(b, z)):.4f}")
            print(f"      · φ  = {math.degrees(float(angulo_fase(b, z))):.2f}°")
        r1 = graficar_Rd(zetas, marcar=marcar, nombre_archivo=self._nombre_unico("curvas_Rd"))
        r2 = graficar_TR(zetas, marcar=marcar, nombre_archivo=self._nombre_unico("curvas_TR"))
        r3 = graficar_fase(zetas, nombre_archivo=self._nombre_unico("curvas_fase"))
        subtitulo("FIGURAS GENERADAS")
        for r in (r1, r2, r3):
            print(f"   {r}")
        self._ofrecer_abrir(r1, r2, r3)
        aviso("Recuerde: TR = 1 exactamente en β = √2 para cualquier amortiguamiento; "
              "sólo por encima de ese valor hay aislamiento.", "info")
        pausa()

    # ------------------------------------------------------- 7. espectros
    def espectro(self) -> None:
        titulo("ESPECTRO DE RESPUESTA DE UN ACELEROGRAMA")
        if self.ultima_excitacion is not None and pedir_si_no(
                f"¿Usar la última señal cargada ({self.ultima_excitacion.nombre})?", True):
            exc = self.ultima_excitacion
        else:
            origen = pedir_opcion("Origen de la señal:", [
                "Archivo CSV (tiempo, aceleración)",
                "Archivo PEER (.AT2)",
                "Registro sintético generado por el programa",
            ], defecto=3)
            if origen == 2:
                pga = pedir_numero("PGA objetivo [g]", defecto=0.20, minimo=0.001)
                exc = generar_registro_sintetico(duracion=30.0, dt=0.005,
                                                 pga_objetivo=pga * G)
            else:
                ruta = pedir_texto("Ruta del archivo", "casos/datos/registro_sintetico.csv")
                if origen == 1:
                    t, ag = leer_peer_at2(ruta)
                else:
                    unidades = ["g", "m/s2", "cm/s2", "gal"]
                    u = unidades[pedir_opcion("Unidad de la aceleración:", unidades,
                                              defecto=1)]
                    t, ag = leer_csv(ruta, unidad_valor=u)
                exc = ExcitacionBase(t, ag, nombre=Path(ruta).stem)
            self.ultima_excitacion = exc

        print(f"\n   {exc.descripcion()}")
        texto = pedir_texto("Amortiguamientos del espectro", "0.02,0.05,0.10")
        zetas = [float(z.strip().replace(",", ".")) for z in texto.split(",") if z.strip()]
        T_min = pedir_numero("Periodo mínimo [s]", defecto=0.05, minimo=0.005)
        T_max = pedir_numero("Periodo máximo [s]", defecto=4.0, minimo=0.1)
        n = pedir_entero("Número de periodos (más = más lento)", defecto=60)

        print("\n   Calculando el espectro (resolviendo un sistema por cada periodo)...")
        periodos = periodos_logaritmicos(T_min, T_max, n)
        if self.sistema is not None:
            periodos = np.unique(np.append(periodos, self.sistema.T_n))
        espectros = [espectro_respuesta(exc, zeta=z, periodos=periodos) for z in zetas]

        subtitulo("RESULTADOS")
        for esp in espectros:
            Tp, PSap = esp.PSa_maxima
            print(f"   ζ = {esp.zeta*100:5.1f} %  →  PSa máxima = {PSap/G:.4f} g "
                  f"en T = {Tp:.3f} s | Sd máximo = {np.max(esp.Sd)*1e3:.2f} mm")
        if self.sistema is not None:
            print(f"\n   Valores espectrales en el periodo del sistema actual "
                  f"(Tn = {self.sistema.T_n:.4f} s):")
            for esp in espectros:
                v = esp.en_periodo(self.sistema.T_n)
                print(f"      ζ = {esp.zeta*100:4.1f} %  →  Sd = {v['Sd [m]']*1e3:8.3f} mm | "
                      f"PSa = {v['PSa [g]']:.4f} g | "
                      f"fuerza equivalente m·PSa = "
                      f"{self.sistema.masa*v['PSa [m/s2]']/1e3:8.2f} kN")
        ruta = graficar_espectro(espectros,
                                 marcar_T=self.sistema.T_n if self.sistema else None,
                                 nombre_archivo=self._nombre_unico("espectro"))
        print(f"\n   Figura: {ruta}")
        self._ofrecer_abrir(ruta)
        aviso("El espectro entrega directamente la respuesta pico de CUALQUIER sistema "
              "de 1 GDL ante ese registro: entrando con Tn se lee Sd (desplazamiento) "
              "y PSa (con la que se calcula la fuerza de diseño fs = m·PSa).", "info")
        pausa()

    # --------------------------------------------------- 8. paramétrico
    def parametrico(self) -> None:
        s = self._exigir_sistema()
        titulo("ANÁLISIS PARAMÉTRICO")
        print("\n   Se repite el cálculo variando una sola variable para ver la")
        print("   tendencia de la respuesta y explicar físicamente el cambio.")

        if self.ultima_carga is not None and pedir_si_no(
                f"¿Usar la última carga definida ({self.ultima_carga.nombre})?", True):
            carga = self.ultima_carga
        else:
            p0 = pedir_numero("Amplitud de la carga armónica p₀ [N]", defecto=1000.0)
            f = pedir_numero("Frecuencia de la carga [Hz]",
                             defecto=round(s.f_n, 3), minimo=1e-9)
            carga = CargaArmonica(p0=p0, omega=2 * math.pi * f)
            self.ultima_carga = carga

        variables = [
            ("Masa m [kg]", "masa"),
            ("Rigidez k [N/m]", "rigidez"),
            ("Amortiguamiento ζ", "zeta"),
            ("Relación de frecuencias β = ω/ωn (sólo carga armónica)", "beta"),
        ]
        i = pedir_opcion("Variable a barrer:", [v[0] for v in variables], defecto=3)
        clave = variables[i][1]

        if clave == "beta":
            v_min = pedir_numero("β inicial", defecto=0.1, minimo=0.01)
            v_max = pedir_numero("β final", defecto=3.0, minimo=0.02)
            n = pedir_entero("Número de puntos", defecto=40)
            p0 = getattr(carga, "p0", 1000.0)
            valores = np.linspace(v_min, v_max, n)
            print("\n   Calculando...")
            res = barrido_carga(s, lambda b: CargaArmonica(p0=p0, omega=b * s.omega_n),
                                valores, "beta", guardar_respuestas=False,
                                t_final=60 * s.T_n, dt=s.T_n / 100)
            etiqueta_x = "Relación de frecuencias β = ω/ωn"
        else:
            actual = {"masa": s.masa, "rigidez": s.rigidez, "zeta": s.zeta}[clave]
            print(f"\n   Valor actual: {actual:g}")
            v_min = pedir_numero("Valor inicial", defecto=round(actual * 0.5, 6),
                                 minimo=1e-12)
            v_max = pedir_numero("Valor final", defecto=round(actual * 2.0, 6),
                                 minimo=1e-12)
            n = pedir_entero("Número de puntos", defecto=15)
            valores = np.linspace(v_min, v_max, n)
            print("\n   Calculando...")
            res = barrido_parametro(s, carga, clave, valores, guardar_respuestas=False,
                                    t_final=60 * s.T_n, dt=s.T_n / 100)
            etiqueta_x = variables[i][0]

        subtitulo("TABLA DE RESULTADOS")
        print(res.tabla_texto(["u_max [mm]", "V_max [kN]", "Rd [-]", "Tn [s]"]))
        v = res.variacion("u_max [mm]")
        print()
        print(f"   El desplazamiento máximo varía entre {v['minimo']:.4f} y "
              f"{v['maximo']:.4f} mm ({v['razon_max_min']:.1f}× de diferencia).")
        print(f"   El máximo se produce con {res.parametro} = "
              f"{v['valor_parametro_maximo']:g}.")

        base = self._nombre_unico("parametrico")
        ruta = graficar_barrido(res, "u_max [mm]", etiqueta_x=etiqueta_x,
                                titulo=f"Análisis paramétrico: efecto de {etiqueta_x}",
                                nombre_archivo=base)
        csv = res.a_csv(SALIDAS / f"{base}.csv")
        print(f"\n   Figura : {ruta}")
        print(f"   Tabla  : {csv}")
        self._ofrecer_abrir(ruta)
        pausa()

    # ------------------------------------------ 9-11. utilidades globales
    def verificar(self) -> None:
        titulo("VERIFICACIÓN DEL MOTOR DE CÁLCULO")
        print("\n   Se ejecutan las pruebas automáticas: cada una compara el resultado")
        print("   numérico con una solución analítica o un límite teórico conocido.\n")
        subprocess.call([sys.executable, "-m", "pytest"])
        pausa()

    def casos(self) -> None:
        titulo("CASOS DE ESTUDIO")
        cual = pedir_opcion("¿Cuál desea resolver?", [
            "Caso 1 — Entrepiso industrial con máquina rotativa (carga armónica)",
            "Caso 2 — Tanque elevado bajo sismo e impacto",
            "Los dos",
        ], defecto=3)
        print("\n   Calculando (puede tardar hasta un minuto)...\n")
        if cual in (0, 2):
            from casos import caso1_maquinaria as c1
            print(c1.imprimir_informe(c1.ejecutar()))
        if cual in (1, 2):
            from casos import caso2_tanque as c2
            print(c2.imprimir_informe(c2.ejecutar()))
        graficos.usar_carpeta(SALIDAS)      # se restaura la carpeta del menú
        pausa()

    def reporte(self) -> None:
        titulo("GENERACIÓN DEL REPORTE TÉCNICO EN PDF")
        print("\n   Se resolverán los dos casos de estudio y se compondrá el documento.")
        print("   Esto tarda alrededor de un minuto...\n")
        from reporte.generar_reporte import generar
        ruta = generar()
        graficos.usar_carpeta(SALIDAS)
        aviso(f"Reporte generado: {ruta.resolve()}", "ok")
        if pedir_si_no("¿Abrir el reporte PDF ahora?", True):
            abrir_archivo(ruta)
        pausa()

    def ver_resultados(self) -> None:
        titulo("RESULTADOS GENERADOS EN ESTA SESIÓN")
        SALIDAS.mkdir(parents=True, exist_ok=True)
        archivos = sorted(SALIDAS.iterdir(), key=lambda p: p.stat().st_mtime)
        if not archivos:
            aviso("Todavía no ha generado ningún resultado. Ejecute cualquier "
                  "análisis (opciones 2 a 8) y las figuras aparecerán aquí.", "info")
            pausa()
            return
        print(f"\n   Carpeta: {SALIDAS.resolve()}\n")
        figuras = [a for a in archivos if a.suffix == ".png"]
        for i, a in enumerate(archivos, start=1):
            tipo = {"png": "figura", "csv": "datos ", "pdf": "reporte"}.get(
                a.suffix.lstrip("."), "      ")
            print(f"   {i:2d}. [{tipo}] {a.name}   ({a.stat().st_size/1024:,.0f} kB)")
        print()
        que = pedir_opcion("¿Qué desea hacer?", [
            "Abrir TODAS las figuras",
            "Abrir un archivo por su número",
            "Abrir la carpeta en el explorador de archivos",
            "Volver al menú",
        ], defecto=4)
        if que == 0:
            for f in figuras:
                abrir_archivo(f)
            aviso(f"Se abrieron {len(figuras)} figuras.", "ok")
        elif que == 1:
            n = pedir_entero(f"Número del archivo (1 a {len(archivos)})", minimo=1)
            if 1 <= n <= len(archivos):
                abrir_archivo(archivos[n - 1])
            else:
                aviso("Ese número no está en la lista.", "error")
        elif que == 2:
            abrir_archivo(SALIDAS.resolve())
        pausa()

    def ayuda(self) -> None:
        titulo("AYUDA: UNIDADES Y CONVENCIONES")
        print()
        print(TABLA_UNIDADES)
        print("   CONVERSIÓN AUTOMÁTICA: escriba el valor seguido de la unidad y el")
        print("   programa lo pasa a SI. Unidades reconocidas:")
        print("      " + ", ".join(sorted(FACTORES_A_SI)))
        print()
        print("   CONVENCIONES DE CÁLCULO")
        print("      · Ecuación resuelta:  m·u'' + c·u' + k·u = p(t)")
        print("      · Sismo: p_ef(t) = -m·üg(t); u(t) es el desplazamiento RELATIVO")
        print("        a la base y la aceleración absoluta es ü + üg.")
        print("      · Integración: Newmark de aceleración promedio (γ=1/2, β=1/4),")
        print("        incondicionalmente estable, con Δt = Tn/200 por defecto.")
        print("      · Resultados mostrados en mm, kN, m/s² y g.")
        print()
        print(f"   Las figuras y archivos de este menú se guardan en: {SALIDAS}/")
        print("   Al terminar cada análisis el programa ofrece ABRIR la figura, y la")
        print("   opción 13 del menú lista todo lo generado y permite abrirlo.")
        print("   Los archivos se numeran (armonica_1.png, armonica_2.png...), así que")
        print("   ningún análisis anterior se sobrescribe.")
        pausa()

    # ------------------------------------------------------- utilidades
    def _nombre_unico(self, base: str) -> str:
        """Devuelve 'base_1', 'base_2'... para no sobrescribir análisis previos."""
        SALIDAS.mkdir(parents=True, exist_ok=True)
        i = 1
        while (SALIDAS / f"{base}_{i}.png").exists() or (SALIDAS / f"{base}_{i}.csv").exists():
            i += 1
        return f"{base}_{i}"

    def _ofrecer_abrir(self, *rutas) -> None:
        """Pregunta si desea abrir las figuras generadas con el visor del sistema."""
        rutas = [r for r in rutas if r]
        if not rutas:
            return
        etiqueta = "la figura" if len(rutas) == 1 else f"las {len(rutas)} figuras"
        try:
            if pedir_si_no(f"¿Abrir {etiqueta} ahora?", True):
                fallos = [r for r in rutas if not abrir_archivo(r)]
                if fallos:
                    aviso("No se pudo abrir automáticamente. Ábrala desde el "
                          f"explorador de archivos en: {SALIDAS.resolve()}", "alerta")
        except Cancelado:
            pass

    def _guardar(self, r, nombre: str, tipo: str = "historia",
                 paneles=("p", "u", "v", "a")) -> None:
        SALIDAS.mkdir(parents=True, exist_ok=True)
        graficos.usar_carpeta(SALIDAS)
        base = self._nombre_unico(nombre)
        if tipo == "sismica":
            ruta = graficar_respuesta_sismica(r, nombre_archivo=base)
        else:
            ruta = graficar_historia(r, mostrar=paneles, nombre_archivo=base)
        csv = r.a_csv(SALIDAS / f"{base}.csv")
        print(f"\n   Figura : {ruta}")
        print(f"   CSV    : {csv}")
        self._ofrecer_abrir(ruta)


def main() -> None:
    try:
        Aplicacion().ejecutar()
    except SystemExit as exc:
        print(exc)
    except KeyboardInterrupt:
        print("\n\n   Interrumpido por el usuario. Hasta luego.\n")


if __name__ == "__main__":
    main()
