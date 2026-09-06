#!/usr/bin/env python3
"""
================================================================================
 PLATAFORMA DE CÁLCULO DE RESPUESTA DINÁMICA — INTERFAZ DE LÍNEA DE COMANDOS
 Universidad de Medellín · Dinámica de Estructuras · Proyecto de aula
================================================================================

Permite analizar CUALQUIER sistema de un grado de libertad sin escribir código.

MODO MÁS SENCILLO: menú interactivo (pide los datos uno por uno)
    python main.py            (sin argumentos)
    python main.py menu
    python menu.py

Ejemplos rápidos
----------------
  # 1) Carga armónica sobre un sistema definido por masa y rigidez
  python main.py armonica --masa 24000 --rigidez 8.27e6 --zeta 0.02 \
                          --p0 1600 --frecuencia 3.0 --tfinal 25

  # 2) La rigidez se calcula a partir de la geometría (4 columnas empotradas)
  python main.py armonica --masa 24000 --E 200e9 --I 3.692e-5 --L 3.5 --n 4 \
                          --zeta 0.02 --p0 1600 --rpm 180

  # 3) Carga impulsiva (pulso triangular de 150 kN y 0.05 s)
  python main.py pulso --masa 80545 --rigidez 5.34e6 --zeta 0.05 \
                       --tipo triangular --p0 150e3 --td 0.05

  # 4) Excitación arbitraria leída de un archivo CSV de aceleraciones en g
  python main.py arbitraria --masa 80545 --periodo 0.77 --zeta 0.05 \
                            --archivo casos/datos/registro_sintetico.csv --unidad g

  # 5) Vibración libre (prueba de "pull-back")
  python main.py libre --masa 80545 --rigidez 5.34e6 --zeta 0.05 --u0 0.02

  # 6) Espectro de respuesta de un registro
  python main.py espectro --archivo casos/datos/registro_sintetico.csv --unidad g

  # 7) Curvas de amplificación dinámica y transmisibilidad
  python main.py curvas

  # 8) Resolver los dos casos de estudio y generar el reporte PDF completo
  python main.py casos
  python main.py reporte

UNIDADES DE ENTRADA: SI (kg, N/m, N, s, m, m/s²).  Use --unidad para las
señales de archivo (g, gal, cm/s2, mm, m). Las salidas se imprimen en mm, kN y g.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from dinamica import (G, CargaArbitraria, CargaArmonica, ExcitacionBase,
                      PulsoExponencial, PulsoRectangular, PulsoSemiseno,
                      PulsoTriangular, Rd, SistemaSDOF, TABLA_UNIDADES,
                      derivar_aceleracion, espectro_respuesta, graficos, hz_a_rad_s,
                      leer_csv, leer_peer_at2, periodos_logaritmicos, resolver,
                      resolver_base, rigidez_columna, rpm_a_rad_s,
                      transmisibilidad, vector_tiempo, vibracion_libre)
from dinamica.graficos import (graficar_Rd, graficar_TR, graficar_espectro,
                               graficar_fase, graficar_historia,
                               graficar_pulso_fases, graficar_respuesta_sismica)
from dinamica.verificacion import verificar_todo

SALIDAS = Path("salidas")


# ===========================================================================
#  Construcción del sistema a partir de los argumentos
# ===========================================================================
def _agregar_argumentos_sistema(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("Definición del sistema de 1 GDL")
    g.add_argument("--masa", type=float, help="masa m [kg]")
    g.add_argument("--peso", type=float, help="peso W [N] (alternativa a --masa)")
    g.add_argument("--rigidez", type=float, help="rigidez k [N/m]")
    g.add_argument("--periodo", type=float, help="periodo natural Tn [s] (alternativa a --rigidez)")
    g.add_argument("--frecuencia-natural", type=float, dest="fn",
                   help="frecuencia natural fn [Hz] (alternativa a --rigidez)")
    g.add_argument("--zeta", type=float, default=0.05,
                   help="fracción de amortiguamiento crítico (por defecto 0.05)")
    g.add_argument("--E", type=float, help="módulo de elasticidad [Pa] (para calcular k)")
    g.add_argument("--I", type=float, help="inercia de la sección [m^4] (para calcular k)")
    g.add_argument("--L", type=float, help="altura del elemento [m] (para calcular k)")
    g.add_argument("--n", type=int, default=1, help="número de columnas iguales")
    g.add_argument("--condicion", default="empotrada-empotrada",
                   choices=["empotrada-empotrada", "empotrada-articulada", "voladizo"],
                   help="condición de apoyo de las columnas")
    g.add_argument("--nombre", default="Sistema analizado")


def construir_sistema(a: argparse.Namespace) -> SistemaSDOF:
    if a.masa is None and a.peso is None:
        raise SystemExit("ERROR: indique --masa [kg] o --peso [N].")
    masa = a.masa if a.masa is not None else a.peso / G

    if a.rigidez is not None:
        k = a.rigidez
    elif a.E and a.I and a.L:
        k = rigidez_columna(a.E, a.I, a.L, condicion=a.condicion, n=a.n)
    elif a.periodo is not None:
        return SistemaSDOF.desde_periodo(masa, a.periodo, a.zeta, a.nombre)
    elif a.fn is not None:
        return SistemaSDOF.desde_frecuencia(masa, a.fn, a.zeta, a.nombre)
    else:
        raise SystemExit("ERROR: defina la rigidez con --rigidez, con --E/--I/--L "
                         "o con --periodo / --frecuencia-natural.")
    return SistemaSDOF(masa=masa, rigidez=k, zeta=a.zeta, nombre=a.nombre)


def _guardar(resp, nombre: str, args) -> None:
    SALIDAS.mkdir(parents=True, exist_ok=True)
    ruta_csv = SALIDAS / f"{nombre}.csv"
    resp.a_csv(ruta_csv)
    graficos.usar_carpeta(SALIDAS / "figuras")
    if resp.ag is not None:
        ruta_fig = graficar_respuesta_sismica(resp, titulo=f"Respuesta — {nombre}",
                                              nombre_archivo=nombre)
    else:
        ruta_fig = graficar_historia(resp, titulo=f"Respuesta — {nombre}",
                                     nombre_archivo=nombre)
    print(f"\n  Historia completa  : {ruta_csv}")
    print(f"  Figura             : {ruta_fig}")


def _leer_senal(args) -> tuple[np.ndarray, np.ndarray]:
    ruta = Path(args.archivo)
    if ruta.suffix.lower() == ".at2":
        return leer_peer_at2(ruta)
    return leer_csv(ruta, columna_tiempo=args.col_tiempo, columna_valor=args.col_valor,
                    unidad_valor=args.unidad, separador=args.separador)


# ===========================================================================
#  Subcomandos
# ===========================================================================
def cmd_armonica(a) -> None:
    s = construir_sistema(a)
    if a.rpm is not None:
        w = rpm_a_rad_s(a.rpm)
    elif a.frecuencia is not None:
        w = hz_a_rad_s(a.frecuencia)
    elif a.omega is not None:
        w = a.omega
    elif a.beta is not None:
        w = a.beta * s.omega_n
    else:
        raise SystemExit("ERROR: indique la frecuencia de excitación con "
                         "--frecuencia [Hz], --omega [rad/s], --rpm o --beta.")
    carga = CargaArmonica(p0=a.p0, omega=w, tipo=a.tipo)
    t_final = a.tfinal or 20.0 * s.T_n
    dt = a.dt or s.T_n / 200.0
    resp = resolver(s, carga, t_final=t_final, dt=dt, u0=a.u0, v0=a.v0,
                    metodo=a.metodo)

    beta = s.beta(w)
    print(s.resumen())
    print(f"\nEXCITACIÓN: {carga.descripcion()}")
    print(f"  β = ω/ωn = {beta:.4f}")
    print(f"  Rd  = {float(Rd(beta, s.zeta)):.4f}   TR = {float(transmisibilidad(beta, s.zeta)):.4f}")
    print(f"  u_estático = p0/k = {carga.p0/s.rigidez*1e3:.4f} mm")
    print(f"  Amplitud permanente = {carga.p0/s.rigidez*float(Rd(beta, s.zeta))*1e3:.4f} mm")
    print("\n" + resp.resumen())
    _guardar(resp, a.salida or "armonica", a)


def cmd_pulso(a) -> None:
    s = construir_sistema(a)
    fabricas = {
        "rectangular": lambda: PulsoRectangular(a.p0, a.td),
        "triangular": lambda: PulsoTriangular(a.p0, a.td, tipo="decreciente"),
        "triangular-creciente": lambda: PulsoTriangular(a.p0, a.td, tipo="creciente"),
        "triangular-simetrico": lambda: PulsoTriangular(a.p0, a.td, tipo="simetrico"),
        "semiseno": lambda: PulsoSemiseno(a.p0, a.td),
        "exponencial": lambda: PulsoExponencial(a.p0, a.td),
    }
    carga = fabricas[a.tipo]()
    t_final = a.tfinal or max(8.0 * s.T_n, 10.0 * a.td)
    dt = a.dt or min(s.T_n, a.td) / 200.0
    resp = resolver(s, carga, t_final=t_final, dt=dt, metodo=a.metodo)

    print(s.resumen())
    print(f"\nEXCITACIÓN: {carga.descripcion()}")
    print(f"  td/Tn = {a.td/s.T_n:.4f}")
    print(f"  u_estático = p0/k = {carga.p0/s.rigidez*1e3:.4f} mm")
    print(f"  Rd = |u|max·k/p0 = {resp.u_max*s.rigidez/carga.p0:.4f}")
    print("\n" + resp.resumen())
    graficos.usar_carpeta(SALIDAS / "figuras")
    ruta = graficar_pulso_fases(resp, a.td, nombre_archivo=a.salida or "pulso")
    resp.a_csv(SALIDAS / f"{a.salida or 'pulso'}.csv")
    print(f"\n  Figura: {ruta}")


def cmd_arbitraria(a) -> None:
    s = construir_sistema(a)
    t, v = _leer_senal(a)
    if a.tipo_senal == "desplazamiento":
        ag = derivar_aceleracion(t, v)
        print("  (la señal de desplazamientos del terreno se derivó dos veces "
              "para obtener la aceleración)")
    else:
        ag = v

    if a.como_fuerza:
        carga = CargaArbitraria(t, ag, nombre=Path(a.archivo).name)
        resp = resolver(s, carga, dt=a.dt, metodo=a.metodo)
    else:
        exc = ExcitacionBase(t, ag, nombre=Path(a.archivo).name)
        print(exc.descripcion())
        resp = resolver_base(s, exc, dt=a.dt, metodo=a.metodo)

    print(s.resumen())
    print("\n" + resp.resumen())
    if not a.como_fuerza:
        print(f"  Cortante basal máximo = {resp.cortante_max/1e3:.3f} kN")
        print(f"  Coeficiente sísmico V/W = {resp.cortante_max/(s.masa*G):.4f}")
    print("\n" + verificar_todo(resp).texto())
    _guardar(resp, a.salida or "arbitraria", a)


def cmd_libre(a) -> None:
    s = construir_sistema(a)
    t_final = a.tfinal or 10.0 * s.T_n
    t = vector_tiempo(t_final, s.T_n / 200.0)
    resp = vibracion_libre(s, t, u0=a.u0, v0=a.v0)
    print(s.resumen())
    print(f"\n  Periodo amortiguado TD = {s.T_D:.5f} s")
    print(f"  Decremento logarítmico δ = 2πζ/√(1-ζ²) = "
          f"{2*np.pi*s.zeta/np.sqrt(1-s.zeta**2):.5f}")
    print(f"  Reducción de amplitud por ciclo = "
          f"{(1-np.exp(-2*np.pi*s.zeta/np.sqrt(1-s.zeta**2)))*100:.2f} %")
    print("\n" + resp.resumen())
    _guardar(resp, a.salida or "vibracion_libre", a)


def cmd_espectro(a) -> None:
    t, ag = _leer_senal(a)
    exc = ExcitacionBase(t, ag, nombre=Path(a.archivo).stem)
    print(exc.descripcion())
    periodos = periodos_logaritmicos(a.tmin, a.tmax, a.npuntos)
    zetas = [float(z) for z in a.zetas.split(",")]
    espectros = [espectro_respuesta(exc, zeta=z, periodos=periodos) for z in zetas]
    graficos.usar_carpeta(SALIDAS / "figuras")
    ruta = graficar_espectro(espectros, nombre_archivo=a.salida or "espectro")
    for esp in espectros:
        Tp, PSap = esp.PSa_maxima
        print(f"  ζ = {esp.zeta*100:5.1f} % → PSa máxima = {PSap/G:.4f} g en T = {Tp:.3f} s ; "
              f"Sd máximo = {np.max(esp.Sd)*1e3:.2f} mm")
    if a.periodo:
        print("\n  Valores espectrales para Tn = %.4f s:" % a.periodo)
        for esp in espectros:
            v = esp.en_periodo(a.periodo)
            print(f"    ζ={esp.zeta*100:4.1f} % → Sd = {v['Sd [m]']*1e3:8.3f} mm ; "
                  f"PSa = {v['PSa [g]']:.4f} g")
    print(f"\n  Figura: {ruta}")


def cmd_curvas(a) -> None:
    graficos.usar_carpeta(SALIDAS / "figuras")
    zetas = [float(z) for z in a.zetas.split(",")]
    marcar = dict(beta=a.beta, zeta=a.zeta) if a.beta else None
    r1 = graficar_Rd(zetas, marcar=marcar, nombre_archivo="curvas_Rd")
    r2 = graficar_TR(zetas, marcar=marcar, nombre_archivo="curvas_TR")
    r3 = graficar_fase(zetas, nombre_archivo="curvas_fase")
    print("Curvas generadas:")
    for r in (r1, r2, r3):
        print(f"   {r}")
    if a.beta:
        print(f"\n  En β = {a.beta:.3f} y ζ = {a.zeta:.3f}: "
              f"Rd = {float(Rd(a.beta, a.zeta)):.4f} ; "
              f"TR = {float(transmisibilidad(a.beta, a.zeta)):.4f}")


def cmd_casos(a) -> None:
    from casos import caso1_maquinaria, caso2_tanque
    print(caso1_maquinaria.imprimir_informe(caso1_maquinaria.ejecutar()))
    print()
    print(caso2_tanque.imprimir_informe(caso2_tanque.ejecutar()))


def cmd_reporte(a) -> None:
    from reporte.generar_reporte import generar
    ruta = generar()
    print(f"\nReporte técnico generado: {ruta}")


def cmd_verificar(a) -> None:
    import subprocess
    print("Ejecutando la batería de pruebas (pytest)...\n")
    codigo = subprocess.call([sys.executable, "-m", "pytest"])
    sys.exit(codigo)


def cmd_unidades(a) -> None:
    print(TABLA_UNIDADES)


def cmd_menu(a) -> None:
    """Abre el menú interactivo por consola."""
    from menu import Aplicacion
    Aplicacion().ejecutar()


# ===========================================================================
def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=False)

    # --- armónica ---
    a1 = sub.add_parser("armonica", help="respuesta ante carga armónica")
    _agregar_argumentos_sistema(a1)
    g = a1.add_argument_group("Excitación armónica")
    g.add_argument("--p0", type=float, required=True, help="amplitud de la fuerza [N]")
    g.add_argument("--frecuencia", type=float, help="frecuencia de excitación [Hz]")
    g.add_argument("--omega", type=float, help="frecuencia de excitación [rad/s]")
    g.add_argument("--rpm", type=float, help="velocidad de la máquina [rpm]")
    g.add_argument("--beta", type=float, help="relación de frecuencias ω/ωn")
    g.add_argument("--tipo", default="sin", choices=["sin", "cos"])
    _agregar_argumentos_analisis(a1)
    a1.set_defaults(func=cmd_armonica)

    # --- pulso ---
    a2 = sub.add_parser("pulso", help="respuesta ante carga impulsiva")
    _agregar_argumentos_sistema(a2)
    g = a2.add_argument_group("Pulso")
    g.add_argument("--tipo", default="triangular",
                   choices=["rectangular", "triangular", "triangular-creciente",
                            "triangular-simetrico", "semiseno", "exponencial"])
    g.add_argument("--p0", type=float, required=True, help="fuerza pico [N]")
    g.add_argument("--td", type=float, required=True, help="duración del pulso [s]")
    _agregar_argumentos_analisis(a2)
    a2.set_defaults(func=cmd_pulso)

    # --- arbitraria ---
    a3 = sub.add_parser("arbitraria", help="respuesta ante una señal arbitraria de archivo")
    _agregar_argumentos_sistema(a3)
    _agregar_argumentos_senal(a3)
    a3.add_argument("--tipo-senal", default="aceleracion",
                    choices=["aceleracion", "desplazamiento"],
                    help="qué contiene la segunda columna del archivo")
    a3.add_argument("--como-fuerza", action="store_true",
                    help="interpretar la señal como fuerza p(t) [N] y no como "
                         "aceleración del terreno")
    _agregar_argumentos_analisis(a3)
    a3.set_defaults(func=cmd_arbitraria)

    # --- vibración libre ---
    a4 = sub.add_parser("libre", help="vibración libre con condiciones iniciales")
    _agregar_argumentos_sistema(a4)
    _agregar_argumentos_analisis(a4)
    a4.set_defaults(func=cmd_libre)

    # --- espectro ---
    a5 = sub.add_parser("espectro", help="espectro de respuesta de un acelerograma")
    _agregar_argumentos_senal(a5)
    a5.add_argument("--zetas", default="0.02,0.05,0.10")
    a5.add_argument("--tmin", type=float, default=0.05)
    a5.add_argument("--tmax", type=float, default=4.0)
    a5.add_argument("--npuntos", type=int, default=100)
    a5.add_argument("--periodo", type=float, help="periodo a consultar [s]")
    a5.add_argument("--salida")
    a5.set_defaults(func=cmd_espectro)

    # --- curvas ---
    a6 = sub.add_parser("curvas", help="curvas Rd, TR y ángulo de fase")
    a6.add_argument("--zetas", default="0.02,0.05,0.10,0.20,0.50")
    a6.add_argument("--beta", type=float, help="punto de operación a señalar")
    a6.add_argument("--zeta", type=float, default=0.05)
    a6.set_defaults(func=cmd_curvas)

    # --- casos, reporte, verificación, unidades ---
    sub.add_parser("casos", help="resuelve los dos casos de estudio").set_defaults(func=cmd_casos)
    sub.add_parser("reporte", help="genera el reporte técnico PDF").set_defaults(func=cmd_reporte)
    sub.add_parser("verificar", help="ejecuta las pruebas de verificación").set_defaults(func=cmd_verificar)
    sub.add_parser("unidades", help="muestra la tabla de unidades").set_defaults(func=cmd_unidades)
    sub.add_parser("menu", help="menú interactivo por consola (ingreso manual de datos)"
                   ).set_defaults(func=cmd_menu)
    return p


def _agregar_argumentos_analisis(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("Parámetros del análisis")
    g.add_argument("--tfinal", type=float, help="duración del análisis [s]")
    g.add_argument("--dt", type=float, help="paso de tiempo [s] (por defecto Tn/200)")
    g.add_argument("--u0", type=float, default=0.0, help="desplazamiento inicial [m]")
    g.add_argument("--v0", type=float, default=0.0, help="velocidad inicial [m/s]")
    g.add_argument("--metodo", default="newmark",
                   choices=["newmark", "exacta", "duhamel", "analitica"])
    g.add_argument("--salida", help="nombre base de los archivos de salida")


def _agregar_argumentos_senal(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("Archivo de la señal")
    g.add_argument("--archivo", required=True, help="ruta del CSV/TXT/AT2")
    g.add_argument("--unidad", default="m/s2",
                   help="unidad de la segunda columna: g, gal, cm/s2, m/s2, mm, m, N, kN")
    g.add_argument("--col-tiempo", type=int, default=0)
    g.add_argument("--col-valor", type=int, default=1)
    g.add_argument("--separador", default=",")


def main(argv=None) -> None:
    args = construir_parser().parse_args(argv)
    if getattr(args, "func", None) is None:
        # Sin subcomando se abre el menú interactivo (modo más cómodo para
        # ingresar los datos a mano).
        cmd_menu(args)
        return
    args.func(args)


if __name__ == "__main__":
    main()
