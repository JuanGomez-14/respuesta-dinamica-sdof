"""
Pruebas de las adiciones al motor: pórtico simbólico, betas de diseño e
identificación desde datos medidos.

Cada prueba se contrasta contra una solución analítica conocida, no contra la
salida del propio código.
"""

import math

import numpy as np
import pytest

from dinamica import (Rd, Rd_maximo, beta_para_Rd, betas_para_transmisibilidad,
                      es_monomio, evaluar_polinomio, identificar,
                      resolver_x_para_rigidez, rigidez_columna_polinomio,
                      rigidez_riostra, rigidez_serie_niveles, sumar_polinomios,
                      transmisibilidad)
from dinamica.portico import formatear_polinomio


# ===========================================================================
#  Pórtico: polinomios de rigidez
# ===========================================================================
class TestRigidezColumna:

    def test_columna_numerica_reproduce_12EI_sobre_H3(self):
        E, I, H = 200e9, 1.0e-4, 3.0
        poli = rigidez_columna_polinomio(E, H, I=I)
        assert es_monomio(poli) and 0 in poli
        assert poli[0] == pytest.approx(12 * E * I / H ** 3)

    def test_voladizo_es_la_cuarta_parte_de_doblemente_empotrada(self):
        args = dict(E=200e9, H=3.0, I=1e-4)
        empotrada = rigidez_columna_polinomio(condicion="empotrada-empotrada", **args)
        voladizo = rigidez_columna_polinomio(condicion="voladizo", **args)
        assert voladizo[0] == pytest.approx(empotrada[0] / 4.0)

    def test_n_columnas_en_paralelo_multiplican_la_rigidez(self):
        una = rigidez_columna_polinomio(200e9, 3.0, I=1e-4, n=1)
        cuatro = rigidez_columna_polinomio(200e9, 3.0, I=1e-4, n=4)
        assert cuatro[0] == pytest.approx(4 * una[0])

    def test_seccion_cuadrada_simbolica_da_grado_4(self):
        # b = h = x  ->  I = x^4/12
        poli = rigidez_columna_polinomio(200e9, 3.0, b=1.0, h=1.0,
                                         b_simbolica=True, h_simbolica=True)
        assert list(poli) == [4]

    def test_solo_h_simbolica_da_grado_3(self):
        poli = rigidez_columna_polinomio(200e9, 3.0, b=0.30, h=1.0,
                                         h_simbolica=True)
        assert list(poli) == [3]

    def test_simbolica_evaluada_coincide_con_la_numerica_equivalente(self):
        """Un polinomio en x evaluado en x=b debe dar lo mismo que la sección fija."""
        E, H, lado = 200e9, 3.0, 0.35
        simbolica = rigidez_columna_polinomio(E, H, b=1.0, h=1.0,
                                              b_simbolica=True, h_simbolica=True)
        numerica = rigidez_columna_polinomio(E, H, I=lado * lado ** 3 / 12)
        assert evaluar_polinomio(simbolica, lado) == pytest.approx(numerica[0])

    def test_rechaza_definir_seccion_por_I_y_por_bh_a_la_vez(self):
        with pytest.raises(ValueError, match="no por ambas"):
            rigidez_columna_polinomio(200e9, 3.0, I=1e-4, b=0.3, h=0.4)

    def test_rechaza_condicion_desconocida(self):
        with pytest.raises(ValueError, match="no válida"):
            rigidez_columna_polinomio(200e9, 3.0, I=1e-4, condicion="rotulada")


class TestRiostra:

    def test_diagonal_3_4_5_calculada_a_mano(self):
        """L_r = 5, cos(theta) = 4/5  ->  k = (A*E/5)*0.64."""
        A, E, L_h, L_v = 20e-4, 200e9, 4.0, 3.0
        k = rigidez_riostra(A, E, L_h, L_v)[0]
        assert k == pytest.approx((A * E / 5.0) * (4.0 / 5.0) ** 2)

    def test_diagonal_mas_horizontal_aporta_mas_rigidez_lateral(self):
        """cos^2(theta) crece al tumbar la diagonal: más componente horizontal."""
        tumbada = rigidez_riostra(20e-4, 200e9, L_h=6.0, L_v=2.0)[0]
        parada = rigidez_riostra(20e-4, 200e9, L_h=2.0, L_v=6.0)[0]
        assert tumbada > parada


class TestCombinacion:

    def test_paralelo_suma_coeficientes_de_la_misma_potencia(self):
        assert sumar_polinomios([{0: 100.0}, {0: 50.0}]) == {0: 150.0}

    def test_paralelo_conserva_potencias_distintas(self):
        assert sumar_polinomios([{0: 100.0}, {4: 7.0}]) == {0: 100.0, 4: 7.0}

    def test_dos_niveles_identicos_en_serie_dan_la_mitad(self):
        assert rigidez_serie_niveles([{0: 1000.0}, {0: 1000.0}], x=0.0) == \
            pytest.approx(500.0)

    def test_serie_es_menor_que_el_nivel_mas_flexible(self):
        K = rigidez_serie_niveles([{0: 1000.0}, {0: 4000.0}], x=0.0)
        assert K < 1000.0

    def test_nivel_no_positivo_es_rechazado(self):
        with pytest.raises(ValueError, match="rigidez de piso"):
            rigidez_serie_niveles([{1: 5.0}], x=0.0)


class TestResolverX:

    def test_forma_cerrada_un_nivel_monomio(self):
        poli = rigidez_columna_polinomio(200e9, 3.0, b=1.0, h=1.0,
                                         b_simbolica=True, h_simbolica=True, n=4)
        K = evaluar_polinomio(poli, 0.35)
        x, como = resolver_x_para_rigidez([poli], K)
        assert x == pytest.approx(0.35, rel=1e-9)
        assert como.startswith("forma cerrada")

    def test_forma_cerrada_varios_niveles_de_igual_potencia(self):
        """1/(C1 x^n) + 1/(C2 x^n) se reduce a un monomio de la misma potencia."""
        a = rigidez_columna_polinomio(200e9, 3.0, b=1.0, h=1.0,
                                      b_simbolica=True, h_simbolica=True)
        b = rigidez_columna_polinomio(200e9, 3.0, b=1.0, h=1.0,
                                      b_simbolica=True, h_simbolica=True, n=2)
        K = rigidez_serie_niveles([a, b], 0.4)
        x, como = resolver_x_para_rigidez([a, b], K)
        assert x == pytest.approx(0.4, rel=1e-9)
        assert como.startswith("forma cerrada")

    def test_biseccion_cuando_las_potencias_diferen(self):
        """Alturas distintas -> misma potencia; mezclar grados fuerza bisección."""
        cuadrada = rigidez_columna_polinomio(200e9, 3.0, b=1.0, h=1.0,
                                             b_simbolica=True, h_simbolica=True)
        solo_h = rigidez_columna_polinomio(200e9, 3.0, b=0.30, h=1.0,
                                           h_simbolica=True)
        niveles = [cuadrada, solo_h]
        K = rigidez_serie_niveles(niveles, 0.42)
        x, como = resolver_x_para_rigidez(niveles, K)
        assert x == pytest.approx(0.42, rel=1e-6)
        assert como.startswith("bisección")

    def test_nivel_con_terminos_mezclados_usa_biseccion(self):
        """Columna simbólica + riostra numérica en el mismo nivel."""
        nivel = sumar_polinomios([
            rigidez_columna_polinomio(200e9, 3.0, b=1.0, h=1.0,
                                      b_simbolica=True, h_simbolica=True),
            rigidez_riostra(20e-4, 200e9, 4.0, 3.0),
        ])
        assert not es_monomio(nivel)
        K = rigidez_serie_niveles([nivel], 0.28)
        x, _ = resolver_x_para_rigidez([nivel], K)
        assert x == pytest.approx(0.28, rel=1e-6)

    def test_rigidez_inalcanzable_avisa(self):
        poli = rigidez_columna_polinomio(200e9, 3.0, b=1.0, h=1.0,
                                         b_simbolica=True, h_simbolica=True)
        with pytest.raises(ValueError, match="excede el límite|no se alcanza"):
            resolver_x_para_rigidez([poli], 1e30, x_max=1.0)

    def test_sin_incognita_avisa_en_vez_de_iterar(self):
        with pytest.raises(ValueError, match="Ningún nivel depende de x"):
            resolver_x_para_rigidez([{0: 1000.0}], 500.0)

    def test_formateo_legible_del_polinomio(self):
        assert formatear_polinomio({0: 1500.0, 4: 2.5}) == "1500 + 2.5·x⁴"


# ===========================================================================
#  Betas asociados a un objetivo
# ===========================================================================
class TestBetaParaRd:

    @pytest.mark.parametrize("zeta", [0.02, 0.05, 0.10])
    def test_las_raices_reproducen_el_Rd_objetivo(self, zeta):
        objetivo = 3.0
        for beta in beta_para_Rd(objetivo, zeta):
            assert float(Rd(beta, zeta)) == pytest.approx(objetivo, rel=1e-9)

    @pytest.mark.parametrize("zeta", [0.01, 0.02, 0.05])
    def test_identidad_de_media_potencia(self, zeta):
        """Con Rd = Rd_max/sqrt(2) se cumple (b2-b1)/2 ~= zeta."""
        b1, b2 = beta_para_Rd(Rd_maximo(zeta) / math.sqrt(2), zeta)
        assert (b2 - b1) / 2 == pytest.approx(zeta, rel=0.02)

    def test_dos_raices_rodean_la_resonancia_si_Rd_mayor_que_1(self):
        b1, b2 = beta_para_Rd(3.0, 0.05)
        assert b1 < 1.0 < b2

    def test_Rd_menor_que_1_deja_solo_la_rama_de_aislamiento(self):
        raices = beta_para_Rd(0.5, 0.05)
        assert len(raices) == 1 and raices[0] > math.sqrt(2)

    def test_Rd_inalcanzable_avisa_con_el_maximo(self):
        with pytest.raises(ValueError, match="inalcanzable"):
            beta_para_Rd(Rd_maximo(0.20) * 1.5, 0.20)


class TestBetasParaTransmisibilidad:

    @pytest.mark.parametrize("objetivo", [0.2, 0.3, 0.7])
    def test_las_raices_reproducen_la_TR_objetivo(self, objetivo):
        for beta in betas_para_transmisibilidad(objetivo, 0.05):
            assert float(transmisibilidad(beta, 0.05)) == pytest.approx(objetivo,
                                                                        rel=1e-9)

    def test_aislar_exige_beta_mayor_que_raiz_de_2(self):
        raices = betas_para_transmisibilidad(0.3, 0.05)
        assert len(raices) == 1 and raices[0] > math.sqrt(2)

    def test_TR_mayor_que_1_da_dos_ramas(self):
        b1, b2 = betas_para_transmisibilidad(1.5, 0.10)
        assert b1 < 1.0 < b2


# ===========================================================================
#  Identificación desde datos medidos
# ===========================================================================
def _senal_libre(zeta: float, Tn: float, t_final: float = 6.0, n: int = 6001):
    """Vibración libre amortiguada analítica, con u(0)=1 y v(0)=0."""
    wn = 2 * math.pi / Tn
    wd = wn * math.sqrt(1 - zeta ** 2)
    t = np.linspace(0.0, t_final, n)
    u = np.exp(-zeta * wn * t) * (np.cos(wd * t) + (zeta * wn / wd) * np.sin(wd * t))
    return t, u


class TestIdentificacion:

    @pytest.mark.parametrize("zeta,Tn", [(0.02, 0.5), (0.05, 0.8), (0.10, 0.35)])
    def test_recupera_zeta_y_periodo_conocidos(self, zeta, Tn):
        t, u = _senal_libre(zeta, Tn)
        r = identificar(t, u)
        assert r.zeta == pytest.approx(zeta, rel=0.02)
        assert r.T_n == pytest.approx(Tn, rel=0.02)

    def test_reporta_el_procedimiento(self):
        t, u = _senal_libre(0.05, 0.5)
        r = identificar(t, u)
        assert "δ" in r.detalle and "ζ" in r.detalle
        assert r.n_parejas >= 2

    def test_periodo_natural_es_menor_que_el_amortiguado(self):
        """T_n = T_D*sqrt(1-zeta^2) < T_D."""
        t, u = _senal_libre(0.20, 0.5)
        r = identificar(t, u)
        assert r.T_n < r.T_D

    def test_frecuencias_derivadas_son_coherentes(self):
        t, u = _senal_libre(0.05, 0.5)
        r = identificar(t, u)
        assert r.omega_n == pytest.approx(2 * math.pi / r.T_n)
        assert r.f_n == pytest.approx(1.0 / r.T_n)

    def test_senal_estacionaria_no_estima_zeta_pero_lo_explica(self):
        t = np.linspace(0, 5, 5001)
        u = np.sin(2 * math.pi * 2.0 * t)  # sin decaimiento
        r = identificar(t, u)
        assert r.zeta is None
        assert "estacionario" in r.detalle

    def test_datos_insuficientes_no_revientan(self):
        t = np.linspace(0, 0.1, 20)
        r = identificar(t, np.zeros_like(t))
        assert r.zeta is None and r.T_n is None
        assert "se requieren al menos 2" in r.detalle

    def test_ruido_no_genera_picos_espurios(self):
        """La prominencia debe filtrar el ruido de medición."""
        t, u = _senal_libre(0.05, 0.5)
        generador = np.random.default_rng(42)
        con_ruido = u + generador.normal(0, 0.002, u.size)
        r = identificar(t, con_ruido)
        assert r.zeta == pytest.approx(0.05, rel=0.15)
