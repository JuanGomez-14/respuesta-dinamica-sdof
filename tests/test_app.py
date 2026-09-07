"""
Pruebas de la interfaz gráfica.

No se prueba la apariencia, sino lo que puede romperse en silencio: que el
modelo compartido derive bien el sistema, y sobre todo que los valores se
PROPAGUEN cuando un botón los aplica.

Esto último tuvo un fallo real durante el desarrollo: mutar el objeto del
proyecto no basta, porque el valor guardado del widget lo revierte en el
siguiente rerun. Por eso los botones usan ``on_click``, y por eso estas pruebas
comprueban el estado DESPUÉS del rerun y no justo después del clic.
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="La interfaz gráfica es opcional.")

from streamlit.testing.v1 import AppTest  # noqa: E402

from app.estado import Columna, Nivel, Proyecto, proyecto_por_defecto  # noqa: E402
from dinamica import rigidez_serie_niveles  # noqa: E402

TIEMPO_LIMITE = 240
# AppTest resuelve las rutas relativas contra el archivo que la llama (tests/),
# no contra la raíz del proyecto: hay que darle la ruta absoluta.
APP = Path(__file__).resolve().parent.parent / "app_streamlit.py"


def arrancar() -> AppTest:
    """Arranca la app y verifica que no explote en el primer render."""
    prueba = AppTest.from_file(str(APP), default_timeout=TIEMPO_LIMITE)
    prueba.run()
    assert not prueba.exception, [str(e.value) for e in prueba.exception]
    return prueba


# ===========================================================================
#  El modelo compartido (sin Streamlit de por medio)
# ===========================================================================
class TestProyecto:

    def test_el_proyecto_por_defecto_deriva_un_sistema_valido(self):
        proyecto = proyecto_por_defecto()
        assert proyecto.problemas() == []
        assert proyecto.sistema().T_n > 0

    def test_la_rigidez_del_portico_se_recalcula_al_cambiar_una_columna(self):
        """El corazón del rediseño: nada de botones de 'aplicar'."""
        proyecto = proyecto_por_defecto()
        proyecto.rigidez_modo = "portico"
        antes = proyecto.sistema().T_n
        proyecto.niveles[0].columnas[0].H = 5.0     # columna más alta -> más flexible
        despues = proyecto.sistema().T_n
        assert despues > antes

    def test_niveles_en_serie_son_mas_flexibles_que_uno_solo(self):
        proyecto = proyecto_por_defecto()
        proyecto.rigidez_modo = "portico"
        un_nivel = float(proyecto.rigidez())
        proyecto.niveles.append(Nivel(nombre="Nivel 2", columnas=[Columna()]))
        assert float(proyecto.rigidez()) < un_nivel

    def test_la_masa_por_carga_distribuida_usa_el_peso_sobre_g(self):
        proyecto = Proyecto(masa_modo="carga", masa_carga=5.0, masa_area=24.0)
        assert float(proyecto.masa()) == pytest.approx(5.0 * 1e3 * 24.0 / 9.80665)

    def test_una_masa_en_kN_se_interpreta_como_peso(self):
        """kN es una fuerza: hay que dividir por g, no solo cambiar de unidad."""
        proyecto = Proyecto(masa_modo="directa", masa_valor=100.0, masa_unidad="kN")
        assert float(proyecto.masa()) == pytest.approx(100e3 / 9.80665)
        assert "W/g" in proyecto.masa().detalle

    def test_cada_magnitud_reporta_como_se_obtuvo(self):
        proyecto = proyecto_por_defecto()
        assert proyecto.masa().detalle
        assert proyecto.rigidez().detalle

    def test_un_nivel_vacio_se_reporta_con_un_mensaje_entendible(self):
        proyecto = Proyecto(niveles=[Nivel(nombre="Vacío", columnas=[])])
        proyecto.rigidez_modo = "portico"
        assert proyecto.problemas()

    def test_seccion_simbolica_se_detecta(self):
        proyecto = proyecto_por_defecto()
        columna = proyecto.niveles[0].columnas[0]
        assert not proyecto.es_simbolico()
        columna.modo_seccion = "bh"
        columna.b = columna.h = 1.0
        columna.b_simbolica = columna.h_simbolica = True
        assert proyecto.es_simbolico()


# ===========================================================================
#  La app completa
# ===========================================================================
class TestArranque:

    def test_arranca_sin_excepciones_y_con_todas_las_pestanas(self):
        prueba = arrancar()
        assert len(prueba.tabs) == 9
        assert len(prueba.error) == 0


class TestPropagacion:
    """Los botones que aplican un valor deben sobrevivir al rerun."""

    def test_usar_el_K_del_portico_cambia_el_modo_de_rigidez(self):
        prueba = arrancar()
        prueba.button(key="portico_usar_k").click().run()
        assert not prueba.exception
        assert prueba.session_state["proyecto"].rigidez_modo == "portico"

    def test_usar_zeta_del_decremento_actualiza_modelo_y_widget(self):
        prueba = arrancar()
        prueba.button(key="dec_usar").click().run()
        proyecto = prueba.session_state["proyecto"]
        assert proyecto.zeta_procedencia == "decremento logarítmico"
        # El widget debe quedar sincronizado, o al siguiente rerun revertiría.
        assert prueba.session_state["sb_zeta"] == pytest.approx(
            proyecto.zeta_valor * 100)

    def test_identificacion_aplica_periodo_y_amortiguamiento(self):
        """La señal de ejemplo tiene ζ = 4 % y Tₙ = 0.45 s conocidos."""
        prueba = arrancar()
        prueba.radio(key="iden_origen").set_value("ejemplo").run()
        prueba.button(key="iden_usar_T").click().run()
        proyecto = prueba.session_state["proyecto"]
        assert proyecto.rigidez_modo == "periodo"
        assert proyecto.periodo_objetivo == pytest.approx(0.45, abs=0.02)

        prueba.button(key="iden_usar_z").click().run()
        assert prueba.session_state["proyecto"].zeta_valor == pytest.approx(
            0.04, abs=0.008)


class TestDespejeDeX:

    def test_resolver_x_para_un_K_objetivo_y_dejarlo_aplicado(self):
        prueba = arrancar()
        prueba.radio(key="rig_modo").set_value("portico").run()

        modo = [r for r in prueba.radio
                if r.key and r.key.startswith("nivel_") and r.key.endswith("_modo")]
        modo[0].set_value("bh").run()
        [c for c in prueba.checkbox if c.key.endswith("_bs")][0].set_value(True).run()
        [c for c in prueba.checkbox if c.key.endswith("_hs")][0].set_value(True).run()

        proyecto = prueba.session_state["proyecto"]
        assert proyecto.es_simbolico()

        prueba.number_input(key="portico_Kobj").set_value(6000.0).run()
        prueba.selectbox(key="portico_Kobj_u").set_value("kN/m").run()
        prueba.button(key="portico_resolver").click().run()
        assert not prueba.exception

        proyecto = prueba.session_state["proyecto"]
        obtenida = rigidez_serie_niveles(proyecto.polinomios(), proyecto.x_actual)
        assert obtenida == pytest.approx(6.0e6, rel=1e-6)
        assert prueba.session_state["portico_x"] == pytest.approx(proyecto.x_actual)


class TestCalculadoras:

    def test_media_potencia_recupera_el_zeta_supuesto(self):
        prueba = arrancar()
        prueba.number_input(key="rd_zeta").set_value(5.0).run()
        prueba.button(key="rd_media").click().run()
        beta_1, beta_2 = prueba.session_state["rd_betas"]
        assert (beta_2 - beta_1) / 2 == pytest.approx(0.05, rel=0.02)

    def test_diseno_de_aislamiento_no_falla(self):
        prueba = arrancar()
        prueba.number_input(key="iso_tr").set_value(0.25).run()
        assert not prueba.exception


class TestPaginasPesadas:
    """Las páginas que hacen cálculo de verdad, con cada una de sus opciones."""

    @pytest.mark.parametrize("forma", ["rectangular", "triangular",
                                       "semiseno", "exponencial"])
    def test_cada_forma_de_pulso(self, forma):
        prueba = arrancar()
        prueba.radio(key="imp_forma").set_value(forma).run()
        assert not prueba.exception

    @pytest.mark.parametrize("variable", ["masa", "rigidez", "zeta", "omega"])
    def test_cada_barrido_parametrico(self, variable):
        prueba = arrancar()
        prueba.selectbox(key="par_cual").set_value(variable).run()
        assert not prueba.exception

    def test_excitacion_arbitraria_con_el_registro_de_ejemplo(self):
        prueba = arrancar()
        prueba.radio(key="arb_origen").set_value("ejemplo").run()
        assert not prueba.exception


class TestFormatoDeNumeros:
    """Los campos no deben rellenar con ceros y los resultados deben leerse bien."""

    def test_los_campos_no_fuerzan_decimales(self):
        """Escribir 24 debe verse «24», no «24,0000»."""
        from app.formato import FORMATO_ENTRADA
        assert FORMATO_ENTRADA % 24.0 == "24"
        assert FORMATO_ENTRADA % 5.0 == "5"
        assert FORMATO_ENTRADA % 0.34 == "0.34"

    def test_los_campos_no_pasan_a_notacion_cientifica_con_rigideces(self):
        from app.formato import FORMATO_ENTRADA
        assert "e" not in (FORMATO_ENTRADA % 8266635.57)

    def test_los_resultados_llevan_separador_de_miles(self):
        from app.formato import numero
        assert numero(12236.6) == "12.237"
        assert numero(8266635.57) == "8.266.636"

    def test_los_valores_pequenos_conservan_cifras_significativas(self):
        """0,0003829 no debe redondearse a 0,0004."""
        from app.formato import numero
        assert numero(0.0003829) == "0,0003829"

    def test_la_procedencia_de_la_masa_se_lee_bien(self):
        proyecto = Proyecto(masa_modo="carga", masa_carga=5.0, masa_area=24.0)
        detalle = proyecto.masa().detalle
        assert "5 kN/m²" in detalle and "24 m²" in detalle   # sin ceros de relleno
        assert "12.237 kg" in detalle                        # con separador


class TestRenombrarEjes:
    """Cada gráfica se renombra en su sitio, no desde un panel aparte."""

    def test_cada_grafica_ofrece_sus_dos_campos_de_eje(self):
        prueba = arrancar()
        claves = {c.key for c in prueba.text_input if c.key}
        for grafica in ["graf_libre_resp", "graf_arm_carga", "graf_arm_resp",
                        "graf_imp_carga", "graf_imp_resp", "graf_rd", "graf_tr"]:
            assert f"{grafica}_ejex" in claves, f"falta el eje X de {grafica}"
            assert f"{grafica}_ejey" in claves, f"falta el eje Y de {grafica}"

    def test_los_ejes_arrancan_con_su_nombre_por_defecto(self):
        prueba = arrancar()
        assert prueba.session_state["graf_libre_resp_ejex"] == "Tiempo t [s]"
        assert prueba.session_state["graf_libre_resp_ejey"] == "Desplazamiento u [m]"

    def test_renombrar_un_eje_no_afecta_a_las_demas_graficas(self):
        """Cada gráfica es independiente: por eso cada una lleva su clave."""
        prueba = arrancar()
        prueba.text_input(key="graf_libre_resp_ejey").set_value("Flecha δ [mm]").run()
        assert not prueba.exception
        assert prueba.session_state["graf_libre_resp_ejey"] == "Flecha δ [mm]"
        # la de carga armónica sigue intacta
        assert prueba.session_state["graf_arm_resp_ejey"] == "Desplazamiento u [m]"

    def test_el_nombre_editado_llega_a_la_grafica(self):
        """Se comprueba sobre la figura de matplotlib, no solo sobre el estado."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import streamlit as st

        prueba = arrancar()
        prueba.text_input(key="graf_libre_resp_ejey").set_value("Flecha δ [mm]").run()

        ejes_dibujados = []
        original = st.pyplot

        def espiar(fig, *a, **k):
            for ax in fig.axes:
                ejes_dibujados.append(ax.get_ylabel())
            return None

        st.pyplot = espiar
        try:
            prueba.run()
        finally:
            st.pyplot = original
            plt.close("all")

        assert "Flecha δ [mm]" in ejes_dibujados

    def test_restablecer_devuelve_el_nombre_original(self):
        prueba = arrancar()
        prueba.text_input(key="graf_libre_resp_ejex").set_value("t").run()
        assert prueba.session_state["graf_libre_resp_ejex"] == "t"
        prueba.button(key="graf_libre_resp_ejes_reset").click().run()
        assert prueba.session_state["graf_libre_resp_ejex"] == "Tiempo t [s]"


class TestTextoDeProcedencia:
    """El rastro de cada valor se copia al taller: tiene que leerse bien."""

    def test_no_repite_el_mismo_valor_dos_veces(self):
        """«m = 24.000 kg = 24.000 kg» no aporta nada."""
        detalle = Proyecto(masa_valor=24000, masa_unidad="kg").masa().detalle
        assert detalle.count("24.000 kg") == 1

    def test_ofrece_la_equivalencia_corta_cuando_el_numero_es_largo(self):
        assert Proyecto(masa_valor=24000, masa_unidad="kg").masa().detalle == \
            "m = 24.000 kg = 24 t"
        assert Proyecto(rigidez_valor=8266600, rigidez_unidad="N/m").rigidez().detalle == \
            "k = 8.266.600 N/m = 8.267 kN/m"

    def test_no_cambia_de_unidad_si_el_numero_ya_es_comodo(self):
        assert Proyecto(rigidez_valor=500, rigidez_unidad="N/m").rigidez().detalle == \
            "k = 500 N/m"

    def test_el_peso_conserva_la_division_por_g(self):
        detalle = Proyecto(masa_valor=100, masa_unidad="kN").masa().detalle
        assert "W/g" in detalle and "9,80665" in detalle
