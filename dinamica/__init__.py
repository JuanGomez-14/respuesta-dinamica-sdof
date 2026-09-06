"""
================================================================================
 dinamica — Laboratorio Computacional de Respuesta Dinámica (sistemas de 1 GDL)
 Universidad de Medellín · Facultad de Ingeniería · Ingeniería Civil
 Asignatura: Dinámica de Estructuras · Proyecto de aula 2026
================================================================================

Motor de cálculo general para analizar la respuesta dinámica de sistemas
estructurales de un grado de libertad (o idealizables como tales) sometidos a:

    * cargas armónicas
    * cargas impulsivas
    * excitaciones dinámicas arbitrarias (series temporales de aceleración,
      desplazamiento o fuerza)

Uso mínimo
----------
>>> from dinamica import SistemaSDOF, CargaArmonica, resolver
>>> sistema = SistemaSDOF(masa=30_000, rigidez=12.0e6, zeta=0.05,
...                       nombre="Entrepiso industrial")
>>> carga = CargaArmonica(p0=8_000.0, omega=18.0)
>>> r = resolver(sistema, carga, t_final=20.0)
>>> round(r.u_max * 1000, 2)  # desplazamiento máximo en mm
3.83

UNIDADES: todo el motor trabaja en SI coherente
    m [kg] · k [N/m] · c [N·s/m] · p [N] · u [m] · t [s] · ω [rad/s]
(ver ``dinamica.unidades`` para convertir desde t, kN, mm, GPa, g, rpm...).
"""

from .unidades import (G, a_si, desde_si, rpm_a_rad_s, rpm_a_hz, hz_a_rad_s,
                       rad_s_a_hz, TABLA_UNIDADES)
from .sistema import (SistemaSDOF, rigidez_serie, rigidez_paralelo,
                      rigidez_columna, rigidez_portico_columnas, masa_desde_peso,
                      sdof_equivalente_voladizo, sdof_equivalente_viga_simple,
                      zeta_por_decremento_logaritmico, zeta_por_ancho_de_banda)
from .cargas import (Carga, CargaArmonica, CargaChirp, PulsoRectangular,
                     PulsoTriangular, PulsoSemiseno, PulsoExponencial, Escalon,
                     Rampa, CargaArbitraria, CargaNula, ExcitacionBase,
                     suma_de_cargas)
from .solucionadores import (Respuesta, newmark, interpolacion_exacta,
                             duhamel_numerica, vibracion_libre,
                             respuesta_armonica, respuesta_permanente_armonica,
                             respuesta_pulso, resolver, resolver_base,
                             vector_tiempo, dt_recomendado, FAMILIAS_NEWMARK)
from .frecuencia import (Rd, Rv, Ra, angulo_fase, transmisibilidad,
                         beta_resonante, Rd_maximo, transmisibilidad_maxima,
                         beta_para_transmisibilidad, betas_para_transmisibilidad,
                         beta_para_Rd, eficiencia_aislamiento,
                         rigidez_para_beta, curva_Rd, curva_TR, curva_fase,
                         amplitud_permanente, fuerza_transmitida_maxima,
                         fuerza_desbalance, energia_disipada_por_ciclo)
from .espectros import (EspectroRespuesta, espectro_respuesta, espectro_choque,
                        periodos_logaritmicos)
from .parametrico import (ResultadoBarrido, barrido_parametro, barrido_carga,
                          barrido_sismico, metricas, sensibilidad)
from .verificacion import (residual_equilibrio, balance_energia, comparar,
                           convergencia, verificar_todo, InformeVerificacion)
from .portico import (CONDICIONES, rigidez_columna_polinomio, rigidez_riostra,
                      sumar_polinomios, evaluar_polinomio, formatear_polinomio,
                      es_monomio, rigidez_serie_niveles, resolver_x_para_rigidez)
from .identificacion import Pico, Identificacion, detectar_picos, identificar
from .io_senales import (leer_csv, leer_peer_at2, escribir_csv, leer_excel,
                         excitacion_desde_csv, carga_desde_csv,
                         corregir_linea_base, filtrar_paso_alto, remuestrear,
                         derivar_aceleracion, generar_registro_sintetico)

__version__ = "1.0.0"
__autores__ = "Proyecto de aula — Dinámica de Estructuras, Universidad de Medellín"

__all__ = [n for n in dir() if not n.startswith("_")]
