# Rediseño de la interfaz: modelo compartido y constructor editable

Fecha: 2026-09-05
Estado: aprobado para implementación

## Problema

La plataforma tiene un motor de cálculo sólido (`dinamica/`) y tres interfaces
que lo exponen mal:

- `main.py` — CLI con argparse; exige memorizar banderas.
- `menu.py` — 1002 líneas de menú de terminal, pregunta por pregunta.
- `app_streamlit.py` — 475 líneas; sidebar con campos fijos y seis pestañas
  organizadas por tipo de análisis.

Un usuario de prueba (compañero de curso) reportó dos problemas distintos:

1. **No logra arrancarla.** Requiere Python, `pip install -r requirements.txt` y
   `streamlit run app_streamlit.py` desde una terminal. En la máquina de
   desarrollo actual, de hecho, `streamlit` no está instalado y no hay entorno
   virtual: la app no arranca sin intervención manual.
2. **No logra usarla una vez abierta.** Los campos son rígidos (un solo modo de
   rigidez a la vez, número fijo de columnas), no se puede armar un pórtico de
   varios niveles, y ningún valor se propaga de una pestaña a otra.

Como referencia, el usuario aportó un HTML monolítico de un tercero con un
constructor dinámico de pórticos y cableado explícito entre pestañas. Ese
archivo define el *nivel de editabilidad* buscado, no la implementación.

## Objetivo

Una sola interfaz gráfica, que arranque con un clic, organizada alrededor de los
problemas que el usuario resuelve (ejercicios del curso), con el nivel de
editabilidad del HTML de referencia y sin sus defectos.

## No objetivos

- Portar el motor a JavaScript. El motor Python es más completo que el del HTML
  (espectros de respuesta y de choque, verificación por balance de energía y
  residual de equilibrio, barridos paramétricos, lectura PEER) y se conserva.
- Publicar la herramienta en la web. Se decidió que siga siendo local.
- Arrastrar y soltar para reordenar. Streamlit no lo soporta de forma nativa;
  se resuelve con botones ↑↓.
- Reescribir `main.py` ni `menu.py`. Quedan intactos en su sitio; simplemente
  dejan de ser el camino recomendado. Así `make casos` y el reporte PDF siguen
  funcionando.

## Arquitectura

### El modelo compartido

Hoy `definir_sistema()` reconstruye un `SistemaSDOF` en cada rerun y lo pasa por
argumento a cada pestaña. No existe un lugar donde persista el estado, y de ahí
viene la incomunicación entre pestañas.

Se introduce un objeto `Proyecto`, guardado en `st.session_state`, como única
fuente de verdad:

```
Proyecto
├── masa      : Magnitud   (valor + procedencia)
├── portico   : list[Nivel]  (cada Nivel: columnas y riostras)
├── rigidez   : Magnitud   (valor + procedencia)
├── zeta      : Magnitud   (valor + procedencia)
└── cargas    : dict       (parámetros de excitación por pestaña)
```

**Regla central: `SistemaSDOF` no se almacena, se deriva.** Es una propiedad
calculada que lee el `Proyecto` y arma el sistema al vuelo. Si la procedencia de
la rigidez es `"portico"`, `k` se recalcula desde los niveles en cada rerun.

Consecuencia de diseño: los botones «enviar este K a la otra pestaña» del HTML
de referencia **no se implementan**. Existen allí porque JavaScript no tiene
estado compartido y hay dos copias del valor que sincronizar. Con un modelo
único no hay nada que sincronizar; cambiar la altura de una columna actualiza
ωₙ, la curva Rd y la respuesta armónica sin ninguna acción del usuario.

### Procedencia

Cada `Magnitud` guarda cómo se obtuvo su valor, con la expresión evaluada:

```python
Magnitud(valor=0.0487, procedencia="decremento logarítmico",
         detalle="δ/√(4π²+δ²) con δ=0.306 promediado sobre 3 pares de picos")
```

No es decorativo: el usuario resuelve ejercicios donde debe **mostrar el
procedimiento**, y el detalle se copia directo al taller. Se muestra bajo cada
valor derivado en el sidebar y en las tarjetas de resultado.

### Unidades

El motor es SI coherente (kg, N/m, N, m, s) y así se queda. **Toda conversión
ocurre en el borde**, dentro del widget de entrada; hacia adentro solo circula
SI. Esto evita el defecto del HTML de referencia, que rotula `k` como kN/m en el
sidebar pero la consume como N/m en `getSystem()`, y propaga ese factor 1000 a
`computeRdDesignK` (donde `K = ωₙ²·m` con m en kg da N/m, no kN/m).

### Disposición de archivos

```
app/
├── __init__.py
├── estado.py       Proyecto, Nivel, Columna, Riostra, Magnitud; derivación del sistema
├── widgets.py      campo-con-unidad, lista editable, tarjeta de resultado, procedencia
└── paginas/
    ├── __init__.py
    ├── inicio.py         portada «¿qué necesitás hallar?»
    ├── portico.py        constructor de niveles → K
    ├── libre.py          vibración libre + identificación de Tn y ζ
    ├── armonica.py       carga armónica
    ├── impulsiva.py      carga impulsiva
    ├── arbitraria.py     excitación arbitraria + espectro
    ├── amplificacion.py  curvas Rd + β objetivo + sección mínima de columna
    └── transmisibilidad.py  curvas TR + β objetivo + diseño de aislamiento
app_streamlit.py    punto de entrada delgado: arma sidebar y despacha pestañas
```

`dinamica/` solo recibe adiciones (abajo); su código actual no se modifica.

## Adiciones al motor

Todas son funciones puras, en el estilo vigente del paquete: unidades SI,
docstring con la fórmula y doctest.

### `dinamica/portico.py` (nuevo)

Rigidez lateral como polinomio en una dimensión simbólica `x`, representado como
`dict[int, float]` de `{potencia: coeficiente}`.

- `rigidez_columna_polinomio(E, H, condicion, ...)` — sección por inercia directa
  (grado 0) o por `b×h` con `b` y/o `h` marcadas como simbólicas. Si ambas son
  simbólicas, `I = b·h³/12` da grado 4.
- `rigidez_riostra(A, E, L_h, L_v)` — `k = (A·E/L_r)·cos²θ`, con
  `L_r = √(L_h² + L_v²)` y `cos θ = L_h/L_r`. No existe hoy en el motor.
- `sumar_polinomios(...)` — combinación en paralelo dentro de un nivel.
- `evaluar_polinomio(poli, x)` y `rigidez_serie_niveles(niveles, x)` — combinación
  en serie entre niveles, reusando `rigidez_serie`.
- `resolver_x_para_rigidez(niveles, K_objetivo)` — forma cerrada cuando el
  resultado es un monomio puro; bisección en caso general. `K_s(x)` es monótona
  creciente en `x`, lo que garantiza la convergencia.

### `dinamica/frecuencia.py` (adiciones)

- `beta_para_Rd(Rd_objetivo, zeta)` — raíces de `(1−β²)² + (2ζβ)² = 1/Rd²`,
  cuadrática en `x = β²`. Devuelve ambas raíces cuando `Rd > 1` (necesarias para
  el método de ancho de banda de media potencia, donde `(β₂−β₁)/2 ≈ ζ`), y solo
  la rama física cuando `Rd < 1`.
- `betas_para_transmisibilidad(TR_objetivo, zeta)` — variante de dos raíces del
  existente `beta_para_transmisibilidad`, que hoy solo devuelve la rama de
  aislamiento y lanza `ValueError` si `TR ≥ 1`. La función actual no se modifica.

### `dinamica/identificacion.py` (nuevo)

De una tabla medida `(t, u)` a las propiedades del sistema:

- `detectar_picos(t, u, prominencia=None)` — con `scipy.signal.find_peaks`
  (scipy ya es dependencia). El HTML de referencia usa una comparación de tres
  puntos vecinos, que cuenta ruido como picos.
- `identificar_periodo(picos)` — promedio de separaciones entre picos sucesivos.
- `identificar_zeta(picos)` — decremento logarítmico promediado, reusando
  `zeta_por_decremento_logaritmico`.
- `identificar(t, u)` — devuelve `Tn`, `ζ`, los picos y el texto del
  procedimiento para la `Magnitud`.

### `dinamica/io_senales.py` (adición)

- `leer_excel(ruta, hoja=0)` — lectura de `.xlsx`/`.xls` vía pandas, saltando
  filas de encabezado no numéricas. Añade `openpyxl` a `requirements.txt`.

## Interfaz

Sidebar permanente con el sistema (masa, rigidez, ζ), sus propiedades derivadas
(ωₙ, fₙ, Tₙ, ω_D, c, c_cr) y la procedencia de cada valor. Alimenta todas las
pestañas.

| Pestaña | Resuelve |
|---|---|
| Inicio | «¿Qué te dan y qué necesitás hallar?» → enlaza a la pestaña pertinente |
| Pórtico → K | constructor de niveles, columnas y riostras; numérico o simbólico en x |
| Vibración libre | respuesta libre e identificación de Tₙ y ζ desde datos medidos |
| Carga armónica | respuesta total y permanente, Rd, ángulo de fase |
| Carga impulsiva | pulsos rectangular/triangular/semiseno/exponencial, contrastados con impulso–cantidad de movimiento |
| Excitación arbitraria | señal pegada o archivo, respuesta y espectro |
| Amplificación Rd | curvas, β para un Rd objetivo, sección mínima de columna |
| Transmisibilidad | curvas, β para un TR objetivo, diseño de aislamiento |

Las pestañas se navegan libremente; la portada orienta pero no encierra.

### Constructor editable

Un mismo widget de «lista editable» (`app/widgets.py`) sirve para niveles,
columnas y riostras. Por elemento: renombrar, reordenar (↑↓), duplicar,
eliminar.

Por columna: `E` con unidad, altura `H`, condición de apoyo (`12EI/H³`
doblemente empotrada o `3EI/H³` en voladizo), y sección definida por inercia
directa o por `b×h`, con casillas para marcar `b` y/o `h` como coeficiente de la
incógnita `x`. Por riostra: `A`, `E`, `L_h`, `L_v` con sus unidades.

## Lanzador

`Abrir herramienta.command` (macOS) y `Abrir herramienta.bat` (Windows):

1. Detecta un Python 3.10+; si no hay, muestra el enlace de descarga y termina
   con un mensaje legible, no un traceback.
2. Crea `.venv` si no existe e instala `requirements.txt` (solo la primera vez).
3. Levanta `streamlit run app_streamlit.py`, que abre el navegador.

## Pruebas

`tests/test_motor.py` cubre el motor existente y no se toca. Se agregan pruebas
de las adiciones, verificadas contra soluciones analíticas:

- `tests/test_portico.py` — el polinomio de una columna numérica reproduce
  `12EI/H³`; dos niveles iguales en serie dan `K/2`; `resolver_x_para_rigidez`
  cierra el viaje de ida y vuelta (dado `x`, calcular `K`, recuperar `x`);
  la riostra reproduce `(A·E/L_r)·cos²θ` en un caso calculado a mano.
- `tests/test_frecuencia_beta.py` — `beta_para_Rd` con `Rd = Rd_max/√2` satisface
  `(β₂−β₁)/2 ≈ ζ` dentro de la tolerancia de la aproximación; las raíces
  devueltas evaluadas en `Rd(β,ζ)` reproducen el objetivo.
- `tests/test_identificacion.py` — sobre una señal sintética de vibración libre
  con `ζ` y `Tn` conocidos, los valores identificados se recuperan dentro del 2 %.
- `tests/test_app_importa.py` — prueba de humo: los módulos de `app/` importan y
  un `Proyecto` por defecto deriva un `SistemaSDOF` válido.

La interfaz no se prueba unitariamente.

## Riesgos

- **Streamlit no está instalado en la máquina de desarrollo.** El lanzador debe
  probarse desde cero, con el `.venv` borrado, o no se habrá verificado lo que
  precisamente falla hoy.
- **Rendimiento del rerun.** Si toda la app recalcula en cada tecla, la
  experiencia empeora. Mitigación: `st.cache_data` en las funciones puras caras
  (curvas, espectros) y `st.form` en los bloques de entrada densos.
- **Ambos `b` y `h` simbólicos dan grado 4**, no 2. Es correcto pero
  contraintuitivo; el UI debe mostrar el polinomio resultante para que el usuario
  lo verifique.
