"""
Batería de verificación del motor de cálculo.

Cada prueba contrasta el resultado numérico con una solución analítica, con un
límite teórico conocido o con un principio físico. Se ejecuta con:

    pytest -q                (o bien:  python main.py verificar)
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from dinamica import (G, CargaArmonica, CargaArbitraria, Escalon, ExcitacionBase,
                      PulsoRectangular, PulsoSemiseno, PulsoTriangular, Rd,
                      Rd_maximo, SistemaSDOF, a_si, beta_para_transmisibilidad,
                      beta_resonante, duhamel_numerica, espectro_choque,
                      espectro_respuesta, generar_registro_sintetico,
                      interpolacion_exacta, newmark, resolver, resolver_base,
                      respuesta_armonica, respuesta_permanente_armonica,
                      respuesta_pulso, rigidez_columna, rigidez_paralelo,
                      rigidez_serie, rpm_a_rad_s, sdof_equivalente_voladizo,
                      transmisibilidad, vector_tiempo, vibracion_libre,
                      zeta_por_decremento_logaritmico)
from dinamica.verificacion import balance_energia, comparar, residual_equilibrio


# ===========================================================================
#  1. Propiedades del sistema
# ===========================================================================
class TestSistema:

    def test_propiedades_basicas(self):
        s = SistemaSDOF(masa=1000.0, rigidez=1.0e6, zeta=0.05)
        assert s.omega_n == pytest.approx(math.sqrt(1000.0))
        assert s.T_n == pytest.approx(2 * math.pi / math.sqrt(1000.0))
        assert s.c_critico == pytest.approx(2 * 1000.0 * math.sqrt(1000.0))
        assert s.amortiguamiento == pytest.approx(0.05 * s.c_critico)
        assert s.omega_D == pytest.approx(s.omega_n * math.sqrt(1 - 0.05 ** 2))

    def test_constructores_alternativos(self):
        s = SistemaSDOF.desde_periodo(masa=500.0, T_n=0.5, zeta=0.02)
        assert s.T_n == pytest.approx(0.5)
        s2 = SistemaSDOF.desde_frecuencia(masa=500.0, f_n=2.0)
        assert s2.f_n == pytest.approx(2.0)

    def test_validaciones(self):
        with pytest.raises(ValueError):
            SistemaSDOF(masa=-1, rigidez=1e6)
        with pytest.raises(ValueError):
            SistemaSDOF(masa=1, rigidez=0.0)
        with pytest.raises(ValueError):
            SistemaSDOF(masa=1, rigidez=1e6, zeta=1.2)

    def test_asociacion_de_resortes(self):
        assert rigidez_paralelo(1.0, 2.0, 3.0) == pytest.approx(6.0)
        assert rigidez_serie(2.0, 2.0) == pytest.approx(1.0)
        # en serie el conjunto es MÁS flexible que el elemento más flexible
        assert rigidez_serie(10.0, 1.0) < 1.0

    def test_rigidez_columnas(self):
        k1 = rigidez_columna(200e9, 1e-4, 3.0, "empotrada-empotrada")
        k2 = rigidez_columna(200e9, 1e-4, 3.0, "voladizo")
        assert k1 == pytest.approx(4.0 * k2)          # 12EI/L³ = 4·(3EI/L³)
        assert rigidez_columna(200e9, 1e-4, 3.0, n=4) == pytest.approx(4 * k1)

    def test_sdof_equivalente_voladizo(self):
        s = sdof_equivalente_voladizo(E=25e9, I=0.1, L=10.0, masa_lineal=1000.0,
                                      masa_concentrada=50_000.0)
        assert s.rigidez == pytest.approx(3 * 25e9 * 0.1 / 10.0 ** 3)
        assert s.masa == pytest.approx(50_000.0 + (33 / 140) * 1000.0 * 10.0)

    def test_conversion_unidades(self):
        assert a_si(30, "t") == pytest.approx(30_000.0)
        assert a_si(1, "g") == pytest.approx(G)
        assert a_si(100, "kN") == pytest.approx(1e5)
        assert a_si(1, "cm4") == pytest.approx(1e-8)
        assert rpm_a_rad_s(60) == pytest.approx(2 * math.pi)


# ===========================================================================
#  2. Vibración libre
# ===========================================================================
class TestVibracionLibre:

    def test_analitica_vs_newmark(self):
        s = SistemaSDOF(1000.0, 1.0e6, 0.05)
        t = vector_tiempo(5.0, s.T_n / 500)
        exacta = vibracion_libre(s, t, u0=0.01, v0=0.0)
        num = newmark(s, t, np.zeros_like(t), u0=0.01, v0=0.0)
        assert num.u_max == pytest.approx(exacta.u_max, rel=1e-4)
        assert np.max(np.abs(num.u - exacta.u)) < 1e-4 * exacta.u_max

    def test_decremento_logaritmico(self):
        """El amortiguamiento identificado en la señal debe ser el introducido."""
        zeta = 0.05
        s = SistemaSDOF(1000.0, 1.0e6, zeta)
        t = vector_tiempo(10.0, s.T_n / 2000)
        r = vibracion_libre(s, t, u0=0.01)
        idx = np.where((r.u[1:-1] > r.u[:-2]) & (r.u[1:-1] > r.u[2:]))[0] + 1
        z_id = zeta_por_decremento_logaritmico(r.u[idx[0]], r.u[idx[3]], 3)
        assert z_id == pytest.approx(zeta, rel=1e-3)

    def test_periodo_amortiguado(self):
        s = SistemaSDOF(1000.0, 1.0e6, 0.20)
        t = vector_tiempo(6.0, s.T_n / 2000)
        r = vibracion_libre(s, t, u0=0.01)
        idx = np.where((r.u[1:-1] > r.u[:-2]) & (r.u[1:-1] > r.u[2:]))[0] + 1
        T_medido = float(np.mean(np.diff(t[idx])))
        assert T_medido == pytest.approx(s.T_D, rel=1e-3)

    def test_sistema_no_amortiguado_conserva_energia(self):
        s = SistemaSDOF(1000.0, 1.0e6, 0.0)
        t = vector_tiempo(20.0, s.T_n / 500)
        r = newmark(s, t, np.zeros_like(t), u0=0.01)
        E0 = 0.5 * s.rigidez * 0.01 ** 2
        E = 0.5 * s.masa * r.v ** 2 + 0.5 * s.rigidez * r.u ** 2
        assert np.max(np.abs(E - E0)) / E0 < 1e-6


# ===========================================================================
#  3. Carga armónica
# ===========================================================================
class TestArmonica:

    @pytest.mark.parametrize("beta", [0.2, 0.5, 0.9, 1.0, 1.5, 2.5])
    @pytest.mark.parametrize("zeta", [0.02, 0.05, 0.20])
    def test_newmark_vs_analitica(self, beta, zeta):
        s = SistemaSDOF(2000.0, 5.0e6, zeta)
        c = CargaArmonica(p0=1000.0, omega=beta * s.omega_n)
        t = vector_tiempo(30.0 * s.T_n, s.T_n / 200)
        num = newmark(s, t, c.muestrear(t))
        exacta = respuesta_armonica(s, c, t)
        assert num.u_max == pytest.approx(exacta.u_max, rel=5e-3)

    @pytest.mark.parametrize("beta,zeta", [(0.5, 0.05), (1.0, 0.05), (2.0, 0.10)])
    def test_amplitud_permanente(self, beta, zeta):
        """Tras el transitorio, la amplitud debe ser (p0/k)·Rd."""
        s = SistemaSDOF(2000.0, 5.0e6, zeta)
        c = CargaArmonica(p0=1000.0, omega=beta * s.omega_n)
        t = vector_tiempo(120.0 * s.T_n, s.T_n / 200)
        r = newmark(s, t, c.muestrear(t))
        ventana = r.recortar(100 * s.T_n, 120 * s.T_n)
        esperado = (c.p0 / s.rigidez) * float(Rd(beta, zeta))
        assert ventana.u_max == pytest.approx(esperado, rel=1e-2)

    def test_resonancia_Rd(self):
        """En β = 1, Rd = 1/(2ζ) exactamente."""
        for zeta in (0.01, 0.05, 0.10):
            assert float(Rd(1.0, zeta)) == pytest.approx(1.0 / (2 * zeta))

    def test_Rd_maximo_y_beta_resonante(self):
        zeta = 0.10
        b = beta_resonante(zeta)
        assert float(Rd(b, zeta)) == pytest.approx(Rd_maximo(zeta))
        assert float(Rd(b, zeta)) >= float(Rd(1.0, zeta))

    def test_limite_estatico(self):
        """Con β -> 0 la respuesta tiende al valor estático (Rd -> 1)."""
        s = SistemaSDOF(2000.0, 5.0e6, 0.05)
        c = CargaArmonica(p0=1000.0, omega=0.01 * s.omega_n)
        t = vector_tiempo(3 * c.periodo, s.T_n / 200)
        r = newmark(s, t, c.muestrear(t))
        assert r.u_max == pytest.approx(c.p0 / s.rigidez, rel=2e-2)

    def test_limite_alta_frecuencia(self):
        """Con β >> 1 la masa no alcanza a seguir la carga: Rd -> 0."""
        assert float(Rd(10.0, 0.05)) < 0.011

    def test_resonancia_no_amortiguada_crece_linealmente(self):
        s = SistemaSDOF(1000.0, 1.0e6, 0.0)
        c = CargaArmonica(p0=1000.0, omega=s.omega_n)
        t = vector_tiempo(40 * s.T_n, s.T_n / 400)
        r = respuesta_armonica(s, c, t)
        # la envolvente teórica es (p0/2k)·ωn·t
        env = 0.5 * (c.p0 / s.rigidez) * s.omega_n * t[-1]
        assert r.u_max == pytest.approx(env, rel=0.02)
        num = newmark(s, t, c.muestrear(t))
        assert num.u_max == pytest.approx(r.u_max, rel=0.01)

    def test_fase_en_resonancia(self):
        from dinamica import angulo_fase
        for zeta in (0.02, 0.1, 0.4):
            assert float(angulo_fase(1.0, zeta)) == pytest.approx(math.pi / 2)

    def test_respuesta_permanente_coincide_con_total_al_final(self):
        s = SistemaSDOF(2000.0, 5.0e6, 0.10)
        c = CargaArmonica(p0=1000.0, omega=1.3 * s.omega_n)
        t = vector_tiempo(80 * s.T_n, s.T_n / 400)
        total = respuesta_armonica(s, c, t)
        perm = respuesta_permanente_armonica(s, c, t)
        n = len(t) // 2
        assert np.max(np.abs(total.u[n:] - perm.u[n:])) < 1e-9


# ===========================================================================
#  4. Transmisibilidad
# ===========================================================================
class TestTransmisibilidad:

    def test_valor_unitario_en_raiz_de_dos(self):
        for zeta in (0.0, 0.02, 0.10, 0.5):
            assert float(transmisibilidad(math.sqrt(2), zeta)) == pytest.approx(1.0)

    def test_zona_de_aislamiento(self):
        assert float(transmisibilidad(3.0, 0.05)) < 1.0
        assert float(transmisibilidad(1.2, 0.05)) > 1.0

    def test_beta_objetivo(self):
        b = beta_para_transmisibilidad(0.10, 0.05)
        assert float(transmisibilidad(b, 0.05)) == pytest.approx(0.10, rel=1e-6)
        assert b > math.sqrt(2)

    def test_fuerza_transmitida_coincide_con_TR(self):
        """fT máx / p0 debe coincidir con TR en régimen permanente."""
        s = SistemaSDOF(2000.0, 5.0e6, 0.05)
        beta = 0.7
        c = CargaArmonica(p0=1000.0, omega=beta * s.omega_n)
        t = vector_tiempo(200 * s.T_n, s.T_n / 400)
        r = newmark(s, t, c.muestrear(t))
        ventana = r.recortar(180 * s.T_n, 200 * s.T_n)
        assert ventana.fuerza_transmitida_max / c.p0 == pytest.approx(
            float(transmisibilidad(beta, s.zeta)), rel=2e-2)


# ===========================================================================
#  5. Cargas impulsivas
# ===========================================================================
class TestImpulsivas:

    @pytest.mark.parametrize("carga_cls,kwargs", [
        (PulsoRectangular, dict(p0=1000.0, duracion=0.25)),
        (PulsoTriangular, dict(p0=1000.0, duracion=0.40)),
        (PulsoSemiseno, dict(p0=1000.0, duracion=0.30)),
    ])
    def test_analitica_vs_numerica(self, carga_cls, kwargs):
        s = SistemaSDOF.desde_periodo(1000.0, 0.5, zeta=0.0)
        c = carga_cls(**kwargs)
        t = vector_tiempo(4.0, 0.5 / 2000)
        ana = respuesta_pulso(s, c, t)
        num = newmark(s, t, c.muestrear(t))
        exa = interpolacion_exacta(s, t, c.muestrear(t))
        assert num.u_max == pytest.approx(ana.u_max, rel=1e-3)
        assert exa.u_max == pytest.approx(ana.u_max, rel=1e-3)

    def test_pulso_rectangular_largo_da_Rd_2(self):
        """Un pulso rectangular con td >= Tn/2 produce exactamente Rd = 2."""
        s = SistemaSDOF.desde_periodo(1000.0, 1.0, zeta=0.0)
        c = PulsoRectangular(p0=1000.0, duracion=0.6)
        t = vector_tiempo(3.0, 1.0 / 4000)
        r = interpolacion_exacta(s, t, c.muestrear(t))
        assert r.u_max * s.rigidez / c.p0 == pytest.approx(2.0, rel=1e-3)

    def test_escalon_da_Rd_2(self):
        """La carga súbita mantenida duplica el desplazamiento estático."""
        s = SistemaSDOF.desde_periodo(1000.0, 1.0, zeta=0.0)
        c = Escalon(p0=1000.0)
        t = vector_tiempo(3.0, 1.0 / 4000)
        r = interpolacion_exacta(s, t, c.muestrear(t))
        assert r.u_max == pytest.approx(2.0 * c.p0 / s.rigidez, rel=1e-3)

    def test_aproximacion_impulsiva(self):
        """Para td << Tn, u_max ≈ I/(m·ωn) sin importar la forma del pulso."""
        s = SistemaSDOF.desde_periodo(50_000.0, 1.0, zeta=0.0)
        td = 0.01                       # td/Tn = 0.01
        impulso = 5_000.0               # N·s
        cargas = [PulsoRectangular(impulso / td, td),
                  PulsoTriangular(2 * impulso / td, td),
                  PulsoSemiseno(math.pi * impulso / (2 * td), td)]
        esperado = impulso / (s.masa * s.omega_n)
        for c in cargas:
            t = vector_tiempo(3.0, td / 200)
            r = interpolacion_exacta(s, t, c.muestrear(t))
            assert r.u_max == pytest.approx(esperado, rel=0.02)

    def test_espectro_de_choque_rectangular(self):
        """El espectro de choque del pulso rectangular satura en Rd = 2."""
        razones, Rmax = espectro_choque("rectangular", zeta=0.0,
                                        razones=np.array([0.1, 0.25, 0.5, 1.0, 2.0]))
        assert Rmax[-1] == pytest.approx(2.0, rel=1e-2)
        assert Rmax[2] == pytest.approx(2.0, rel=1e-2)     # td/Tn = 0.5
        assert Rmax[0] < 1.0                               # régimen impulsivo

    def test_maximo_en_fase_libre_para_pulsos_cortos(self):
        s = SistemaSDOF.desde_periodo(1000.0, 1.0, zeta=0.0)
        c = PulsoTriangular(p0=1000.0, duracion=0.05)
        t = vector_tiempo(3.0, 1.0 / 4000)
        r = interpolacion_exacta(s, t, c.muestrear(t))
        assert r.t_u_max > c.duracion      # el pico ocurre después del pulso


# ===========================================================================
#  6. Excitación arbitraria e integradores
# ===========================================================================
class TestIntegradores:

    def test_newmark_vs_interpolacion_exacta(self):
        s = SistemaSDOF(80_000.0, 5.0e6, 0.05)
        exc = generar_registro_sintetico(duracion=10.0, dt=0.01, semilla=1)
        r1 = resolver_base(s, exc, metodo="newmark")
        r2 = resolver_base(s, exc, metodo="exacta")
        assert r1.u_max == pytest.approx(r2.u_max, rel=2e-3)

    def test_duhamel_vs_analitica(self):
        s = SistemaSDOF(2000.0, 5.0e6, 0.05)
        c = CargaArmonica(p0=1000.0, omega=0.8 * s.omega_n)
        t = vector_tiempo(20 * s.T_n, s.T_n / 500)
        d = duhamel_numerica(s, t, c.muestrear(t))
        a = respuesta_armonica(s, c, t)
        assert d.u_max == pytest.approx(a.u_max, rel=1e-3)

    def test_convergencia_de_segundo_orden(self):
        """El error del método de la aceleración promedio debe caer ~4× al
        dividir por 2 el paso de tiempo (convergencia de segundo orden)."""
        s = SistemaSDOF(2000.0, 5.0e6, 0.05)
        c = CargaArmonica(p0=1000.0, omega=1.2 * s.omega_n)
        t_final = 10 * s.T_n
        ref = resolver(s, c, t_final=t_final, dt=s.T_n / 8000, metodo="exacta").u_max
        errores = []
        for div in (20, 40, 80):
            u = resolver(s, c, t_final=t_final, dt=s.T_n / div, metodo="newmark").u_max
            errores.append(abs(u - ref) / ref)
        assert errores[0] > errores[1] > errores[2]
        assert errores[0] / errores[1] > 3.0
        assert errores[1] / errores[2] > 3.0

    def test_estabilidad_condicional(self):
        """Con β = 1/6 y Δt > 0.551·Tn el método es inestable: debe avisar."""
        s = SistemaSDOF(1000.0, 1.0e6, 0.05)
        t = vector_tiempo(10.0, 0.7 * s.T_n)
        with pytest.raises(ValueError, match="estabilidad"):
            newmark(s, t, np.zeros_like(t), familia="aceleracion_lineal")

    def test_aceleracion_promedio_estable_con_paso_grande(self):
        """El método de la aceleración promedio no diverge nunca (β = 1/4)."""
        s = SistemaSDOF(1000.0, 1.0e6, 0.05)
        t = vector_tiempo(50.0, 0.9 * s.T_n)
        r = newmark(s, t, np.zeros_like(t), u0=0.01)
        assert np.all(np.isfinite(r.u))
        assert r.u_max <= 0.0101          # no crece: la energía no aumenta

    def test_paso_variable(self):
        s = SistemaSDOF(1000.0, 1.0e6, 0.05)
        t1 = np.arange(0, 2.0, s.T_n / 200)
        t2 = np.arange(2.0, 5.0, s.T_n / 50)
        t = np.concatenate([t1, t2])
        c = CargaArmonica(p0=1000.0, omega=s.omega_n)
        r = newmark(s, t, c.muestrear(t))
        ref = respuesta_armonica(s, c, t)
        assert r.u_max == pytest.approx(ref.u_max, rel=0.02)

    def test_equilibrio_dinamico(self):
        s = SistemaSDOF(2000.0, 5.0e6, 0.05)
        c = CargaArmonica(p0=1000.0, omega=1.1 * s.omega_n)
        r = resolver(s, c, t_final=20.0, dt=s.T_n / 200)
        assert residual_equilibrio(r)["residual_max_relativo [-]"] < 1e-9

    def test_balance_de_energia(self):
        s = SistemaSDOF(2000.0, 5.0e6, 0.05)
        c = CargaArmonica(p0=1000.0, omega=1.1 * s.omega_n)
        r = resolver(s, c, t_final=20.0, dt=s.T_n / 400)
        assert balance_energia(r)["error_cierre [-]"] < 1e-3


# ===========================================================================
#  7. Excitación en la base y espectros
# ===========================================================================
class TestSismica:

    def test_estructura_rigida_sigue_al_terreno(self):
        """Si Tn << el periodo de la excitación, la masa se mueve solidariamente
        con el terreno: ü_abs ≈ ü_g y el desplazamiento relativo tiende a cero."""
        t = np.arange(0.0, 5.0, 0.001)
        A = 2.0                                   # m/s²
        exc = ExcitacionBase(t, A * np.sin(2 * math.pi * 1.0 * t),
                             nombre="Base armónica de 1 Hz")
        s = SistemaSDOF.desde_periodo(masa=1000.0, T_n=0.02, zeta=0.05)
        r = resolver_base(s, exc, dt=0.0002)
        assert r.a_abs_max == pytest.approx(A, rel=0.02)
        assert r.u_max < 1e-4                     # prácticamente no se deforma

    def test_carga_efectiva_sismica(self):
        exc = generar_registro_sintetico(duracion=5.0, dt=0.01, semilla=4)
        carga = exc.carga_efectiva(masa=1000.0)
        assert isinstance(carga, CargaArbitraria)
        assert carga.p0 == pytest.approx(1000.0 * exc.pga)

    def test_espectro_coincide_con_historia(self):
        """Sd(Tn) del espectro debe ser el |u|máx de la historia en el tiempo."""
        exc = generar_registro_sintetico(duracion=15.0, dt=0.01, semilla=5)
        Tn, zeta = 0.8, 0.05
        esp = espectro_respuesta(exc, zeta=zeta, periodos=np.array([Tn]))
        s = SistemaSDOF.desde_periodo(masa=50_000.0, T_n=Tn, zeta=zeta)
        r = resolver_base(s, exc, metodo="exacta")
        assert esp.Sd[0] == pytest.approx(r.u_max, rel=1e-3)

    def test_relacion_pseudo_espectral(self):
        exc = generar_registro_sintetico(duracion=10.0, dt=0.01, semilla=6)
        esp = espectro_respuesta(exc, zeta=0.05,
                                 periodos=np.array([0.3, 0.8, 2.0]))
        wn = 2 * math.pi / esp.T
        assert np.allclose(esp.PSa, wn ** 2 * esp.Sd)
        assert np.allclose(esp.PSv, wn * esp.Sd)

    def test_escalado_de_registro(self):
        exc = generar_registro_sintetico(duracion=5.0, dt=0.01, semilla=8)
        exc2 = exc.escalar_a_pga(0.4 * G)
        assert exc2.pga == pytest.approx(0.4 * G)

    def test_amortiguamiento_reduce_la_respuesta(self):
        exc = generar_registro_sintetico(duracion=15.0, dt=0.01, semilla=9)
        s = SistemaSDOF.desde_periodo(50_000.0, 0.8, zeta=0.02)
        u2 = resolver_base(s, exc).u_max
        u10 = resolver_base(s.con(zeta=0.10), exc).u_max
        assert u10 < u2


# ===========================================================================
#  8. Cargas: comportamiento de los objetos
# ===========================================================================
class TestCargas:

    def test_carga_arbitraria_interpola_y_se_anula_fuera(self):
        c = CargaArbitraria([0.0, 1.0, 2.0], [0.0, 10.0, 0.0])
        assert c.p(0.5) == pytest.approx(5.0)
        assert c.p(-1.0) == pytest.approx(0.0)
        assert c.p(3.0) == pytest.approx(0.0)

    def test_impulsos_teoricos(self):
        assert PulsoRectangular(100.0, 2.0).impulso == pytest.approx(200.0)
        assert PulsoTriangular(100.0, 2.0).impulso == pytest.approx(100.0)
        assert PulsoSemiseno(100.0, 2.0).impulso == pytest.approx(2 * 100.0 * 2.0 / math.pi)

    def test_suma_de_cargas(self):
        c = CargaArmonica(p0=100.0, omega=1.0) + Escalon(p0=50.0)
        t = np.array([0.0, 1.0])
        assert c.p(t)[0] == pytest.approx(50.0)

    def test_pulso_es_nulo_despues_de_td(self):
        for c in (PulsoRectangular(10.0, 1.0), PulsoTriangular(10.0, 1.0),
                  PulsoSemiseno(10.0, 1.0)):
            assert c.p(1.5) == pytest.approx(0.0)


# ===========================================================================
#  9. Coherencia global de los dos casos de estudio
# ===========================================================================
class TestCasos:

    def test_caso1_resonancia_y_verificacion(self):
        from casos import caso1_maquinaria as c1
        R = c1.ejecutar(generar_figuras=False)
        assert 0.9 < R["beta"] < 1.1                       # opera en resonancia
        assert R["error_pico_newmark"] < 5e-3              # motor verificado
        assert R["Rd"] > 10                                # fuerte amplificación
        assert R["control"]["amortiguar"]["u"] < R["u_permanente"]
        assert R["control"]["rigidizar"]["u"] < R["u_permanente"]

    def test_caso2_sismo_e_impulso(self):
        from casos import caso2_tanque as c2
        R = c2.ejecutar(generar_figuras=False)
        assert R["verificacion_sismo"].aprueba
        assert R["verificacion_impulso"].aprueba
        assert R["error_espectro_vs_historia"] < 5e-3
        assert R["impulso"]["Rd"] < 1.0                    # régimen impulsivo
        assert R["aislamiento"]["reduccion_cortante"] > 0.0
