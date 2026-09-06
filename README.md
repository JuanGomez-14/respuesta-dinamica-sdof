# Laboratorio Computacional de Respuesta Dinámica 📈

**Guía completa: qué es, cómo se instala, cómo se prueba y cómo funciona.**

> Universidad de Medellín · Facultad de Ingeniería · Ingeniería Civil
> Asignatura: **Dinámica de Estructuras** · Proyecto de aula 2026
> Entregables: **plataforma de cálculo** + **reporte técnico en PDF**

Hola 👋. Este documento está escrito para que puedas entender, instalar, probar y
defender este trabajo **aunque nunca hayas programado en Python**. Está en orden:
primero lo instalas, luego lo pruebas, y al final entiendes cómo funciona por dentro.

---

## 0. Empezar en 30 segundos ⚡

**No hace falta abrir la terminal ni escribir nada.**

| Sistema | Qué hacer |
|---|---|
| **macOS** | doble clic en **`Abrir herramienta.command`** |
| **Windows** | doble clic en **`Abrir herramienta.bat`** |

La primera vez tarda uno o dos minutos: crea su propio entorno e instala lo que
necesita. Después abre sola en el navegador. Si no tienes Python instalado, el
lanzador te lo dice con el enlace de descarga en vez de mostrarte un error.

Para cerrarla: vuelve a la ventana negra que quedó abierta y presiona `Ctrl+C`.

### Cómo está organizada la herramienta

La **barra lateral** define el sistema (masa, rigidez, amortiguamiento) y alimenta
**todas** las pestañas a la vez. No hay que copiar valores de una pestaña a otra:
si cambias la altura de una columna en *Pórtico → K*, el periodo, las curvas y las
respuestas se actualizan solos.

| Pestaña | Para cuando el ejercicio... |
|---|---|
| 🧭 Inicio | ...no sabes por dónde empezar: es un índice por objetivo |
| 🏛 Pórtico → K | ...te da la geometría y pide la rigidez (o pide la sección mínima) |
| 🔔 Vibración libre | ...te da una tabla (t, u) y pide Tₙ y ζ |
| 🔁 Carga armónica | ...tiene una máquina o carga que oscila |
| 💥 Carga impulsiva | ...tiene un golpe, impacto o explosión |
| 📈 Excitación arbitraria | ...te da un registro sísmico o una señal cualquiera |
| 📊 Amplificación R_d | ...pide que el desplazamiento no supere N veces el estático |
| 🛡 Transmisibilidad | ...pide aislar: transmitir solo un % de la fuerza |
| 🎛 Paramétrico | ...pregunta "¿y si la masa fuera un 20 % mayor?" |

Cada valor derivado muestra debajo **cómo se obtuvo**, con la expresión evaluada,
para que puedas copiarlo al desarrollo escrito del taller.

Las unidades se eligen campo por campo (GPa, cm⁴, kN/m…). Por dentro todo se
convierte a SI coherente (kg, N/m, N, m, s): no hay factores de 1000 escondidos.

> Las otras dos interfaces (`main.py` por línea de comandos y `menu.py` por menú de
> terminal) **siguen funcionando** y se documentan más abajo, pero ya no son el
> camino recomendado. La app gráfica es la herramienta principal.

---

## Índice

0. [Empezar en 30 segundos](#0-empezar-en-30-segundos-)
1. [¿Qué es esto en dos minutos?](#1-qué-es-esto-en-dos-minutos)
2. [Qué pedía el enunciado y dónde está resuelto](#2-qué-pedía-el-enunciado-y-dónde-está-resuelto)
3. [Instalación paso a paso](#3-instalación-paso-a-paso)
4. [Cómo probar que funciona (10 minutos)](#4-cómo-probar-que-funciona-10-minutos)
5. [Cómo se usa: las cuatro formas](#5-cómo-se-usa-las-cuatro-formas)
6. [Cómo funciona por dentro (la teoría, sin dolor)](#6-cómo-funciona-por-dentro-la-teoría-sin-dolor)
7. [Los dos casos de estudio, explicados](#7-los-dos-casos-de-estudio-explicados)
8. [Cómo cambiar los datos y meter TU propio caso](#8-cómo-cambiar-los-datos-y-meter-tu-propio-caso)
9. [Mapa de archivos](#9-mapa-de-archivos)
10. [Cómo se verificó que los resultados son correctos](#10-cómo-se-verificó-que-los-resultados-son-correctos)
11. [Preguntas típicas de la sustentación (con respuesta)](#11-preguntas-típicas-de-la-sustentación-con-respuesta)
12. [Problemas frecuentes y soluciones](#12-problemas-frecuentes-y-soluciones)
13. [Glosario rápido](#13-glosario-rápido)
14. [Checklist de entrega](#14-checklist-de-entrega)

---

## 1. ¿Qué es esto en dos minutos?

Es un **motor de cálculo** (un programa) que resuelve la ecuación de movimiento de
un sistema estructural de **un grado de libertad**:

```
m · u''(t)  +  c · u'(t)  +  k · u(t)  =  p(t)
│              │              │           │
masa           amortiguador   resorte     carga que varía con el tiempo
```

Traducido: le dices **cuánto pesa** la estructura (m), **qué tan rígida** es (k),
**cuánta energía disipa** (ζ) y **qué carga** la sacude (p(t)), y el programa te
devuelve cómo se mueve en el tiempo: desplazamiento `u(t)`, velocidad `u'(t)`,
aceleración `u''(t)`, fuerzas, cortante basal, gráficas y conclusiones.

Resuelve los **tres tipos de excitación** que pide el laboratorio:

| Tipo de carga | Ejemplo real | Cómo la resuelve |
|---|---|---|
| **Armónica** | un motor o ventilador desbalanceado | solución analítica exacta + Newmark |
| **Impulsiva** | un impacto, una explosión, un frenado | solución cerrada por fases + Newmark |
| **Arbitraria** | un sismo (acelerograma), una señal medida | **método de Newmark directo** |

Y además calcula lo que el enunciado pide explícitamente: **factor de amplificación
dinámica (Rd)**, **transmisibilidad (TR)**, **análisis paramétrico**, **espectros de
respuesta**, y genera todas las **gráficas** y el **reporte técnico en PDF**.

---

## 2. Qué pedía el enunciado y dónde está resuelto

| Requisito de la guía | Dónde está | Estado |
|---|---|---|
| 3.1 Motor de cálculo general y modificable | `dinamica/` (10 módulos) | ✅ |
| 3.2 Respuesta ante carga armónica | `dinamica/solucionadores.py` → `respuesta_armonica` | ✅ |
| 3.2 Respuesta ante carga impulsiva | `respuesta_pulso` + pulsos en `cargas.py` | ✅ |
| 3.2 Excitaciones arbitrarias con **Newmark directo** | `newmark()` | ✅ |
| 3.2 Entrada por vector de tiempo + aceleraciones **o desplazamientos** | `io_senales.py` (`leer_csv`, `derivar_aceleracion`) | ✅ |
| 3.2 Declaración explícita de unidades | `dinamica/unidades.py` y sección 6.6 de esta guía | ✅ |
| 3.2 Contraste con soluciones analíticas | `dinamica/verificacion.py` + `tests/` | ✅ |
| 3.3 Gráficas con título, ejes y unidades | `dinamica/graficos.py` (15 tipos de figura) | ✅ |
| 3.4 Análisis paramétrico (m, k, ζ, β, amplitud, duración, cond. iniciales) | `dinamica/parametrico.py` | ✅ |
| 3.5 Factor de amplificación dinámica | `dinamica/frecuencia.py` → `Rd`, `Rd_maximo` | ✅ |
| 3.6 Transmisibilidad y zonas de aislamiento | `frecuencia.py` → `transmisibilidad`, `beta_para_transmisibilidad` | ✅ |
| 3.7 Aplicación a dos casos de estudio | `casos/caso1_maquinaria.py`, `casos/caso2_tanque.py` | ✅ |
| 5.1 Plataforma funcional y documentada | todo el repositorio; 4 formas de uso (menú, CLI, GUI, API) | ✅ |
| 5.2 Reporte técnico en PDF | `salidas/Reporte-Tecnico-Respuesta-Dinamica.pdf` (26 páginas) | ✅ |

---

## 3. Instalación paso a paso

### 3.1 Qué necesitas

- **Python 3.10 o superior** (probado en 3.11).
- Nada más. Las librerías se instalan solas con un comando.

Comprueba si ya lo tienes:

```bash
python3 --version        # macOS / Linux
python --version         # Windows
```

Si no lo tienes, descárgalo de <https://www.python.org/downloads/>
👉 **En Windows marca la casilla “Add Python to PATH”** durante la instalación.

### 3.2 Instalación (copiar y pegar)

Abre una terminal **dentro de la carpeta del proyecto** (la que contiene este
`README.md`) y ejecuta:

**macOS / Linux**

```bash
cd ruta/a/la/carpeta/del/proyecto
python3 -m venv .venv                 # crea un "entorno virtual" aislado
source .venv/bin/activate             # lo activa (verás (.venv) en el prompt)
pip install -r requirements.txt       # instala todo lo necesario
```

**Windows (PowerShell)**

```powershell
cd ruta\a\la\carpeta\del\proyecto
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Si PowerShell bloquea el script de activación, ejecuta una sola vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**¿Qué es el entorno virtual?** Una carpeta (`.venv`) donde se instalan las
librerías **sólo para este proyecto**, sin tocar el resto de tu computador. Cada
vez que abras una terminal nueva para trabajar, actívalo otra vez con
`source .venv/bin/activate` (o `.venv\Scripts\Activate.ps1` en Windows).

### 3.3 Comprobar que quedó bien instalado

```bash
python -c "import dinamica; print('OK, versión', dinamica.__version__)"
```

Debe imprimir `OK, versión 1.0.0`.

---

## 4. Cómo probar que funciona (10 minutos)

### Prueba 1 — La batería de verificación automática

```bash
pytest
```

Salida esperada (tarda ~20 s):

```
.......................................................................  [100%]
85 passed
```

Son **85 comprobaciones**: 71 pruebas del motor y 14 ejemplos incluidos en la
documentación. Cada una compara el resultado numérico contra una **solución
analítica** o un **límite teórico conocido** (por ejemplo: que en resonancia
Rd = 1/(2ζ), que TR = 1 exactamente en β = √2, o que una carga súbita mantenida
duplica el desplazamiento estático). Si las 85 pasan, el motor está bien.

También puedes correrlas con `python main.py verificar`.

### Prueba 2 — El menú interactivo (la forma más fácil)

```bash
python main.py            # o bien:  python menu.py
```

Aparece un menú y **el programa va pidiendo los datos uno por uno**, con el valor
por defecto entre corchetes (ENTER lo acepta):

```
╔════════════════════════════════════════════════════════════════════════╗
║            LABORATORIO COMPUTACIONAL DE RESPUESTA DINÁMICA             ║
║                Sistemas de un grado de libertad (SDOF)                 ║
║           Universidad de Medellín · Dinámica de Estructuras            ║
╚════════════════════════════════════════════════════════════════════════╝

--------------------------------------------------------------------------
 SISTEMA ACTUAL: m = 24,000.0 kg | k = 8,266,600.0 N/m | ζ = 0.020
                 ωn = 18.5591 rad/s | fn = 2.9538 Hz | Tn = 0.3385 s
--------------------------------------------------------------------------
 MENÚ PRINCIPAL
    1. Definir o modificar el sistema (m, k, ζ)
    2. Carga ARMÓNICA (máquina, viento periódico...)
    3. Carga IMPULSIVA (impacto, explosión, frenado)
    4. Excitación ARBITRARIA (sismo o señal de archivo)
    5. Vibración LIBRE (prueba de pull-back)
    6. Curvas de amplificación Rd, transmisibilidad TR y fase
    7. Espectro de respuesta de un acelerograma
    8. Análisis PARAMÉTRICO (barrer una variable)
    9. Verificar el motor de cálculo (pruebas automáticas)
   10. Resolver los DOS CASOS DE ESTUDIO
   11. Generar el REPORTE TÉCNICO en PDF
   12. Ayuda: unidades y convenciones
    0. Salir
```

Ver la sección **5, Forma A** para el detalle de cómo se ingresan los datos.

### Prueba 3 — Un cálculo suelto desde la terminal

```bash
python main.py armonica --masa 24000 --rigidez 8.2666e6 --zeta 0.02 \
                        --p0 1600 --rpm 180 --tfinal 25
```

Salida esperada (exactamente esto):

```
--- Sistema analizado ---
  m [kg]         = 24,000.0000
  k [N/m]        = 8.2666e+06
  c [N*s/m]      = 17,816.7741
  c_cr [N*s/m]   = 8.9084e+05
  zeta [-]       = 0.0200
  wn [rad/s]     = 18.5591
  fn [Hz]        = 2.9538
  Tn [s]         = 0.3385

EXCITACIÓN: p(t) = 1,600.0 N · sin(18.850·t) ; f = 3.000 Hz ; T = 0.333 s
  β = ω/ωn = 1.0156
  Rd  = 19.4429   TR = 19.4590
  u_estático = p0/k = 0.1935 mm
  Amplitud permanente = 3.7632 mm

Respuesta [Newmark (γ=0.5, β=0.25, aceleracion_promedio)]
  |u|max          = 3.9055 mm  (t = 7.3651 s)
  |u'|max         = 0.0735 m/s
  |u''|max        = 1.3836 m/s²
  |V|max = k|u|max= 32.2849 kN
  |fT|max         = 32.3135 kN

  Historia completa  : salidas/armonica.csv
  Figura             : salidas/figuras/armonica.png
```

Y aparecen dos archivos nuevos: el **CSV** con toda la historia
(t, u, v, a, p, k·u) y el **PNG** con la gráfica de cuatro paneles.

### Prueba 4 — Los dos casos de estudio completos

```bash
python main.py casos
```

Tarda ~40 s. Imprime los dos informes numerados en pantalla; el del caso 1
empieza así:

```
==============================================================================
CASO 1 — ENTREPISO INDUSTRIAL CON MÁQUINA ROTATIVA (CARGA ARMÓNICA)
==============================================================================

1) IDEALIZACIÓN Y PROPIEDADES DEL SISTEMA EQUIVALENTE DE 1 GDL
   Rigidez por columna              k1 = 2,066,659 N/m = 12·E·I/L³
   Rigidez lateral total (paralelo) k  = 8,266,636 N/m = 4 × k1
   Frecuencia natural               ωn = 18.5592 rad/s ; fn = 2.9538 Hz ; Tn = 0.3385 s

2) EXCITACIÓN
   p0 = m_e·e·ω² = 30 kg × 0.150 m × (18.850 rad/s)² = 1,598.9 N
   Relación de frecuencias β = ω/ωn = 1.0156   (RESONANCIA)

3) RESPUESTA
   Factor de amplificación  Rd  = 19.444 (máximo posible con ζ=0.02: 25.005)
   Amplitud permanente      u0  = 3.7607 mm
   Fuerza transmitida a la cimentación = 31.11 kN (la carga aplicada es sólo 1.60 kN)

4) VERIFICACIÓN DEL MOTOR DE CÁLCULO
   |u|máx analítica exacta   = 3.909042 mm
   |u|máx Newmark (Δt=Tn/200)= 3.902848 mm  → error = 0.15846 %
```

…y continúa con los criterios de servicio, el análisis paramétrico, las
estrategias de control y el arranque de la máquina. Después hace lo mismo con el
caso 2 (sismo + impacto), incluyendo un bloque de verificación que termina en
`RESULTADO: APROBADA`.

Al finalizar quedan **26 figuras** en `salidas/figuras/caso1/` y
`salidas/figuras/caso2/`.

### Prueba 5 — Generar el reporte técnico en PDF

```bash
python main.py reporte
```

```
Resolviendo el caso 1 (carga armónica)...
Resolviendo el caso 2 (sismo e impulso)...
Componiendo el reporte PDF...

Reporte generado: .../salidas/Reporte-Tecnico-Respuesta-Dinamica.pdf
```

Al abrirlo: 26 páginas con portada, tablas, las 21 figuras, las verificaciones y
las conclusiones. **Éste es el segundo entregable del proyecto.**

### Prueba 6 — La interfaz gráfica interactiva

```bash
streamlit run app_streamlit.py
```

Se abre solo el navegador en `localhost:8501`. Lo que verás:

- **Barra lateral**: masa, rigidez (directa, por geometría E·I·L, o por periodo)
  y un deslizador de ζ. Debajo se actualizan en vivo ωn, fn, Tn, c y c_cr.
- **Seis pestañas**: carga armónica · carga impulsiva · excitación arbitraria ·
  curvas Rd y TR · análisis paramétrico · vibración libre.
- En cada una, una fila de **indicadores** (β, Rd, u estático, amplitud
  permanente, TR…) y un **aviso automático** según el caso: rojo
  *“⚠ El sistema opera prácticamente en RESONANCIA”*, verde
  *“β > √2: zona de AISLAMIENTO”* o azul informativo.
- Las gráficas **se redibujan al instante** al mover cualquier valor.

Es lo más útil para la sustentación individual: te preguntan “¿qué pasa si
duplico el amortiguamiento?”, lo mueves y lo muestras.

Para cerrarla: `Ctrl + C` en la terminal.

---

## 5. Cómo se usa: las cuatro formas

> Las cuatro usan **exactamente el mismo motor de cálculo**; cambia solo la
> manera de introducir los datos. Elige la que te resulte más cómoda.

### Forma A — Menú interactivo por consola (la más fácil) ⭐

```bash
python main.py          # sin argumentos abre el menú
python main.py menu     # equivalente
python menu.py          # equivalente
```

No hay que recordar ningún comando: se elige una opción del menú y el programa
**pregunta los datos uno por uno**, indicando en cada pregunta la unidad
esperada y un valor por defecto entre corchetes.

**Ayudas al ingresar datos:**

| Puedes escribir | Y el programa… |
|---|---|
| `30 t`, `8500 kN/m`, `3692 cm4`, `150 kN`, `0.25 g` | convierte solo a unidades SI y te muestra la conversión |
| `3,5` | acepta la coma decimal |
| *(ENTER en blanco)* | toma el valor por defecto que aparece entre corchetes |
| `x` | cancela la pregunta y vuelve al menú |

**Ejemplo real de una sesión** (opción 1 y luego opción 2):

```
   Masa m [kg]: 24 t
      · 24 t = 24000 kg
   Rigidez k [N/m]: 8.2666e6
   Fracción de amortiguamiento ζ (0.02 acero, 0.05 concreto) [0.05]: 0.02

--- PROPIEDADES DINÁMICAS DEL SISTEMA -----------------------------------
  wn [rad/s]     = 18.5591
  fn [Hz]        = 2.9538
  Tn [s]         = 0.3385
  ...
```

y al analizar la carga armónica (opción 2, con p₀ = 1600 N a 180 rpm):

```
--- RESULTADOS ----------------------------------------------------------
   Relación de frecuencias         β = 1.0156
   Factor de amplificación        Rd = 19.4429   (máximo posible con ζ=0.020: 25.005)
   Ángulo de fase                  φ = 127.83°
   Desplazamiento estático  u_st = p₀/k = 0.1935 mm
   Amplitud permanente      u₀ = u_st·Rd = 3.7632 mm
   Cortante basal máximo  V = k·u        = 32.223 kN
   Transmisibilidad               TR = 19.4590
   Fuerza transmitida al apoyo  fT = p₀·TR = 31.134 kN

 [!] ¡RESONANCIA! β está muy cerca de 1: la frecuencia de la carga casi
     coincide con la natural. Aquí Rd ≈ 1/(2ζ) = 25.0 y el
     amortiguamiento es lo ÚNICO que limita la respuesta. Soluciones:
     desintonizar (cambiar k o m), amortiguar o cambiar la velocidad de
     operación.

   Figura : salidas/menu/armonica.png
   CSV    : salidas/menu/armonica.csv
```

Además del resultado numérico, **el menú interpreta el caso automáticamente**:
avisa si estás en resonancia, en zona cuasi-estática, en zona de aislamiento
(β > √2), o si el pulso está en régimen impulsivo, de amplificación o
cuasi-estático. El sistema definido **se conserva** entre análisis, así que
puedes encadenar: definir la estructura una vez y luego probar carga armónica,
impulsiva, sismo y análisis paramétrico sin volver a escribir los datos.

Todo lo que genera el menú queda en `salidas/menu/` (figuras PNG y CSV).

### Forma B — Línea de comandos (para repetir un cálculo con un solo comando)

```bash
# Ver todas las opciones
python main.py --help
python main.py armonica --help

# 1) Carga armónica, sistema dado por masa y rigidez
python main.py armonica --masa 24000 --rigidez 8.27e6 --zeta 0.02 --p0 1600 --frecuencia 3.0

# 2) La rigidez se calcula sola a partir de la geometría (4 columnas empotradas)
python main.py armonica --masa 24000 --E 200e9 --I 3.692e-5 --L 3.5 --n 4 \
                        --zeta 0.02 --p0 1600 --rpm 180

# 3) Carga impulsiva (pulso triangular de 150 kN durante 0.05 s)
python main.py pulso --masa 80545 --rigidez 5.34e6 --zeta 0.05 \
                     --tipo triangular --p0 150e3 --td 0.05

# 4) Sismo leído de un archivo CSV con la aceleración en g
python main.py arbitraria --masa 80545 --periodo 0.77 --zeta 0.05 \
                          --archivo casos/datos/registro_sintetico.csv --unidad g

# 5) Una fuerza medida (no un sismo): se usa --como-fuerza
python main.py arbitraria --masa 80545 --periodo 0.77 --zeta 0.05 \
                          --archivo casos/datos/fuerza_impactos.csv --unidad N --como-fuerza

# 6) Vibración libre (prueba de "pull-back": halas la estructura y la sueltas)
python main.py libre --masa 80545 --rigidez 5.34e6 --zeta 0.05 --u0 0.02

# 7) Espectro de respuesta de un acelerograma
python main.py espectro --archivo casos/datos/registro_sintetico.csv --unidad g --periodo 0.77

# 8) Curvas Rd, TR y ángulo de fase, señalando un punto de operación
python main.py curvas --beta 1.016 --zeta 0.02

# 9) Ver la tabla de unidades de entrada y salida
python main.py unidades
```

Cada comando guarda automáticamente la **figura** y el **CSV** con la historia
completa en `salidas/`.

### Forma C — Interfaz gráfica

```bash
streamlit run app_streamlit.py
```

Seis pestañas: carga armónica · carga impulsiva · excitación arbitraria (permite
**subir tu propio CSV**) · curvas Rd y TR · análisis paramétrico · vibración libre.

### Forma D — Escribiendo un script de Python (lo más flexible)

```python
from dinamica import SistemaSDOF, CargaArmonica, resolver, Rd

# 1) Defino el sistema (SI: kg, N/m)
sistema = SistemaSDOF(masa=24_000, rigidez=8.2666e6, zeta=0.02,
                      nombre="Entrepiso industrial")
print(sistema.resumen())          # Tn, fn, wn, c, c_cr...

# 2) Defino la carga
carga = CargaArmonica(p0=1600.0, omega=18.85)     # 1.6 kN a 3 Hz

# 3) Resuelvo
r = resolver(sistema, carga, t_final=25.0)

# 4) Leo resultados
print("u máximo   =", r.u_max * 1000, "mm")
print("cortante   =", r.cortante_max / 1000, "kN")
print("β          =", sistema.beta(carga.omega))
print("Rd teórico =", float(Rd(sistema.beta(carga.omega), sistema.zeta)))

# 5) Grafico y exporto
from dinamica.graficos import graficar_historia
graficar_historia(r, nombre_archivo="mi_analisis")
r.a_csv("mi_analisis.csv")
```

---

## 6. Cómo funciona por dentro (la teoría, sin dolor)

### 6.1 La idea central

Toda estructura que vibra hace lo mismo: **intercambia energía** entre su
elasticidad (el resorte, `k`) y su inercia (la masa, `m`), y va perdiendo un poco
en cada ciclo (el amortiguador, `c`). De ahí sale su **frecuencia natural**:

```
ωn = √(k/m)   [rad/s]        fn = ωn/2π   [Hz]        Tn = 2π/ωn   [s]
```

**Todo el comportamiento dinámico depende de comparar el "reloj" de la estructura
(Tn) con el "reloj" de la carga.** Esa comparación tiene un nombre distinto según
el tipo de carga:

- Carga armónica → **β = ω/ωn** (relación de frecuencias)
- Carga impulsiva → **td/Tn** (duración del pulso sobre el periodo)
- Sismo → dónde cae Tn dentro del **espectro** del registro

### 6.2 Carga armónica: resonancia, Rd y TR

Si `p(t) = p₀·sen(ωt)`, después del transitorio la estructura oscila con amplitud:

```
u₀ = (p₀/k) · Rd            donde     Rd = 1 / √[(1 − β²)² + (2ζβ)²]
     └──┬──┘  └┬┘
 lo que se movería      cuánto lo amplifica
 si la carga fuera      el hecho de que sea
 estática               dinámica
```

Tres zonas, y conviene tenerlas clarísimas para la sustentación:

| Zona | β | Qué manda | Rd |
|---|---|---|---|
| **Cuasi-estática** | β ≪ 1 | la **rigidez** | Rd → 1 |
| **Resonancia** | β ≈ 1 | el **amortiguamiento** | Rd = 1/(2ζ) |
| **Inercial / aislamiento** | β ≫ 1 | la **masa** | Rd → 0 |

Y la **transmisibilidad**, que dice qué fracción de la fuerza llega a la cimentación:

```
TR = √[1 + (2ζβ)²] / √[(1 − β²)² + (2ζβ)²]
```

Dos hechos que siempre preguntan:
- **TR = 1 exactamente en β = √2 ≈ 1.414**, sin importar el amortiguamiento.
- Sólo hay **aislamiento** si β > √2, es decir, si la estructura es **más flexible**
  que la excitación. Aislar **no** es rigidizar: es desintonizar hacia abajo.
- En la zona de aislamiento, **más amortiguamiento empeora** la transmisión de fuerza.

### 6.3 Carga impulsiva: manda el impulso, no la fuerza

Si la carga dura mucho menos que el periodo (`td/Tn < 0.25`), la estructura “no
alcanza a reaccionar” mientras la carga actúa. Lo único que importa es el
**impulso total** `I = ∫p·dt`, y el máximo ocurre **después**, en vibración libre:

```
u_máx ≈ I / (m · ωn)
```

En el caso 2 de este trabajo eso se comprueba: tres pulsos de formas distintas
(rectangular, triangular, medio seno) con **el mismo impulso** pero con fuerzas
pico que varían al doble producen prácticamente **el mismo desplazamiento**
(5.276, 5.275 y 5.279 mm).

El **espectro de choque** resume todo esto: grafica el Rd máximo frente a td/Tn.
La carga súbita mantenida (escalón) da exactamente **Rd = 2**: ése es el famoso
“factor 2” de las cargas dinámicas.

### 6.4 Excitación arbitraria: el método de Newmark

Un sismo no tiene fórmula. Se integra **paso a paso**: conocido el estado en el
instante `i`, se calcula el del instante `i+1`. Newmark supone una ley de
variación de la aceleración dentro del paso y resuelve el equilibrio incremental:

```
k_ef  = k + (γ/(β·Δt))·c + m/(β·Δt²)               ← rigidez efectiva
Δp_ef = Δp + [m/(β·Δt) + (γ/β)·c]·v + [m/(2β) + Δt·(γ/(2β) − 1)·c]·a
Δu    = Δp_ef / k_ef                                ← se despeja el incremento
```

- Con **γ = 1/2 y β = 1/4** (aceleración promedio, el que usamos por defecto) el
  método es **incondicionalmente estable**: nunca “explota”, aunque el paso sea grande.
- Con **β = 1/6** (aceleración lineal) es más preciso pero sólo estable si
  Δt ≤ 0.551·Tn. El programa **verifica el límite y avisa** si te pasas.

Para excitación sísmica en la base, la carga efectiva es `p_ef(t) = −m·üg(t)` y la
respuesta `u(t)` que se obtiene es el desplazamiento **relativo** a la base
(que es el que produce esfuerzos). La aceleración **absoluta** se recupera como
`ü_total = ü + üg` (es la que “sienten” las personas y los equipos).

### 6.5 Idealización: de muchos grados de libertad a uno solo

Esta parte es la que más pesa en la sustentación. Dos herramientas:

**a) Resortes en serie y en paralelo**

```
En PARALELO (mismo desplazamiento):   k_eq = k₁ + k₂ + ...    → columnas de un pórtico con losa rígida
En SERIE    (misma fuerza):         1/k_eq = 1/k₁ + 1/k₂ + ... → estructura + aislador + suelo
```

**b) Masa distribuida → masa equivalente (Rayleigh)**

Se supone una forma de vibración ψ(x) y se calculan propiedades “generalizadas”
referidas a un punto. Para un voladizo con masa uniforme:

```
k* = 3·E·I/H³            m* = (33/140)·m_fuste + m_concentrada     [33/140 = 0.2357]
```

Ambas están implementadas: `rigidez_paralelo`, `rigidez_serie`,
`rigidez_columna`, `sdof_equivalente_voladizo`, `sdof_equivalente_viga_simple`.

### 6.6 Unidades (⚠️ el error más común)

**Todo el motor trabaja en SI coherente.** Si respetas esta tabla, no fallas:

| Entras | En | | Sale | En |
|---|---|---|---|---|
| masa m | **kg** | | desplazamiento u | **m** (se muestra en mm) |
| rigidez k | **N/m** | | velocidad u' | **m/s** |
| ζ | adimensional (0.05 = 5 %) | | aceleración u'' | **m/s²** (se muestra en g) |
| carga p | **N** | | fuerza elástica k·u | **N** (se muestra en kN) |
| aceleración del suelo | **m/s²** | | cortante basal V | **N** (se muestra en kN) |
| tiempo | **s** | | Rd, TR | adimensionales |
| E | **Pa** | I | **m⁴** | |

Y si tus datos están en otras unidades, conviértelos explícitamente:

```python
from dinamica import a_si
masa = a_si(30, "t")        # 30 toneladas  → 30 000 kg
k    = a_si(8500, "kN/m")   # 8500 kN/m     → 8.5e6 N/m
I    = a_si(3692, "cm4")    # 3692 cm⁴      → 3.692e-5 m⁴
pga  = a_si(0.25, "g")      # 0.25 g        → 2.452 m/s²
```

En la línea de comandos, para las señales de archivo se usa `--unidad g`,
`--unidad gal`, `--unidad mm`, etc.

---

## 7. Los dos casos de estudio, explicados

> Los dos casos se resuelven completos, con idealización, hipótesis, resultados,
> análisis paramétrico, verificación, interpretación y conclusiones, tanto en el
> PDF como al ejecutar `python main.py casos`.

### 🏭 Caso 1 — Entrepiso industrial con máquina rotativa (CARGA ARMÓNICA)

**El problema.** Una plataforma de acero (4 columnas + losa rígida, 24 t) sostiene
un ventilador que gira a 180 rpm (3 Hz) con un desbalance de 30 kg a 15 cm.

**La idealización.** Diafragma rígido ⇒ un solo grado de libertad; las 4 columnas
empotradas-empotradas trabajan **en paralelo**: k = 4 · 12EI/L³ = 8.27 MN/m.

**Los números que salen:**

| Resultado | Valor | Lectura |
|---|---|---|
| Tn = 0.3385 s, fn = 2.954 Hz | | la máquina gira a 3.00 Hz |
| **β = 1.016** | | ⚠️ **está en resonancia** |
| Fuerza del desbalance p₀ = m·e·ω² | 1.60 kN | apenas el 0.7 % del peso |
| Desplazamiento estático p₀/k | 0.193 mm | insignificante |
| **Rd = 19.4** | | la dinámica lo multiplica por 19 |
| **Amplitud real = 3.76 mm** | | ❌ supera el límite de servicio (1 mm) |
| Aceleración = 0.136 g | | ❌ supera el límite de confort (0.05 g) |
| **Fuerza transmitida = 31.1 kN** | | ¡19 veces la fuerza aplicada! |

**La moraleja:** el problema **no es de resistencia** (la fuerza es ridícula), es
de **sintonía de frecuencias**. Y las soluciones que evalúa el programa:

| Estrategia | Resultado | Comentario |
|---|---|---|
| Rigidizar hasta β = 0.5 (k × 4.13) | 0.062 mm (−98 %) | la mejor opción |
| Amortiguadores hasta ζ = 10 % | 0.941 mm (−75 %) | funciona **porque** está en resonancia |
| Aislar la máquina (TR = 0.20) | fuerza transmitida 0.32 kN | pero exige 170 mm de deflexión estática |
| Balancear el rotor / cambiar rpm | p₀ ∝ ω² | normalmente lo más barato |

Extra: se simula el **arranque** de la máquina (barrido de frecuencias que
atraviesa la resonancia) y se comprueba que el pico es sólo el 81 % de la
amplitud permanente: **pasar rápido por la resonancia no es lo peligroso;
lo peligroso es quedarse ahí.**

### 💧 Caso 2 — Tanque elevado (SISMO + IMPACTO)

**El problema.** Un tanque de 60 m³ sobre una torre de concreto de 12 m (fuste
anular hueco). Se analiza ante (A) un **acelerograma** y (B) un **impacto**.

**La idealización.** Voladizo con masa concentrada arriba + masa distribuida del
fuste por Rayleigh: k = 3EI_ef/H³ = 5.34 MN/m, m* = 80 545 kg ⇒ **Tn = 0.772 s**.
Se verifica con una prueba numérica de vibración libre: el periodo y el
amortiguamiento identificados a partir de la señal coinciden con los teóricos con
errores del 0.04 % y 0.003 %.

**(A) Respuesta sísmica** (registro sintético, PGA = 0.20 g, integrado con Newmark):

| Resultado | Valor |
|---|---|
| Desplazamiento relativo máximo | 55.3 mm |
| Deriva de la torre u/H | 0.46 % |
| Aceleración absoluta máxima | 0.376 g (**1.9 veces la PGA**) |
| Cortante basal | 295 kN |
| Momento en la base | 3 542 kN·m |
| Coeficiente sísmico V/W | 0.374 (demanda **elástica**) |

Se calcula además el **espectro de respuesta** del registro para ζ = 2, 5 y 10 %,
y se comprueba que `Sd(Tn)` del espectro coincide con el pico de la historia en el
tiempo con un error del **0.05 %** (dos cálculos totalmente independientes).

**(B) Carga impulsiva** (pulso triangular de 150 kN y 50 ms):

| Resultado | Valor | Lectura |
|---|---|---|
| td/Tn = 0.065 | | régimen **impulsivo** |
| Desplazamiento estático p₀/k | 28.1 mm | lo que daría un cálculo estático |
| Desplazamiento real | 5.28 mm | **¡5 veces menor!** |
| Rd = 0.19 | | la estructura no alcanza a responder |

**La moraleja del caso 2:** una carga enorme (150 kN) produce menos que una
pequeña (1.6 kN en el caso 1), porque **lo que manda no es la magnitud sino la
relación entre el tiempo de la carga y el periodo de la estructura.**

Y algo que sorprende y luce mucho en la sustentación: **rigidizar tiene efectos
opuestos según la excitación.** Ante sismo reduce desplazamientos pero puede
aumentar las fuerzas (te mueve dentro del espectro); ante el impulso **empeora**
la respuesta porque acerca td/Tn a la zona de amplificación.

---

## 8. Cómo cambiar los datos y meter TU propio caso

### 8.1 Cambiar los datos de los casos existentes

Cada caso tiene **un solo bloque de datos al principio del archivo**. Abre
`casos/caso1_maquinaria.py` y edita:

```python
DATOS = dict(
    masa_losa=18_000.0,          # kg
    masa_equipo=6_000.0,         # kg
    E_acero=200e9,               # Pa
    I_columna=3.692e-5,          # m^4
    L_columna=3.50,              # m
    n_columnas=4,
    zeta=0.02,
    velocidad_rpm=180.0,         # rpm
    masa_excentrica=30.0,        # kg
    excentricidad=0.15,          # m
    ...
)
```

Guarda y vuelve a ejecutar `python main.py casos`. **Todo** (números, gráficas,
tablas, conclusiones y el PDF) se recalcula solo. No hay ningún número escrito a
mano en el reporte: todos salen del cálculo.

### 8.2 Analizar un caso completamente nuevo (plantilla)

Crea un archivo `mi_caso.py` con esto y ejecútalo con `python mi_caso.py`:

```python
from dinamica import (SistemaSDOF, CargaArmonica, PulsoTriangular,
                      rigidez_columna, rigidez_paralelo, resolver, Rd,
                      transmisibilidad)
from dinamica.graficos import graficar_historia, graficar_Rd
from dinamica.verificacion import verificar_todo

# --- 1. IDEALIZACIÓN: de la estructura real a m, k, ζ -----------------
k_columnas = rigidez_columna(E=200e9, I=1.2e-4, L=4.0,
                             condicion="empotrada-empotrada", n=6)
k_muro     = 45e6                                   # otro elemento resistente
k = rigidez_paralelo(k_columnas, k_muro)            # trabajan en paralelo

sistema = SistemaSDOF(masa=95_000, rigidez=k, zeta=0.05, nombre="Mi estructura")
print(sistema.resumen())

# --- 2. EXCITACIÓN ----------------------------------------------------
carga = CargaArmonica(p0=12_000, omega=25.0)        # o PulsoTriangular(...), etc.

# --- 3. RESPUESTA -----------------------------------------------------
r = resolver(sistema, carga, t_final=30.0)
print(r.resumen())

# --- 4. VERIFICACIÓN --------------------------------------------------
print(verificar_todo(r).texto())

# --- 5. GRÁFICAS ------------------------------------------------------
graficar_historia(r, titulo="Mi caso", nombre_archivo="mi_caso")
graficar_Rd(marcar=dict(beta=sistema.beta(carga.omega), zeta=sistema.zeta),
            nombre_archivo="mi_caso_Rd")
```

### 8.3 Usar un sismo real en lugar del sintético

El registro que trae el proyecto es **sintético** (generado con un filtro de
Kanai-Tajimi y semilla fija, para que sea reproducible). Para usar uno real:

1. Descarga un registro de la base **PEER** (<https://ngawest2.berkeley.edu>) en
   formato `.AT2`, o consigue un CSV de dos columnas `tiempo, aceleración`.
2. Úsalo directamente:

```bash
python main.py arbitraria --masa 80545 --periodo 0.77 --zeta 0.05 \
                          --archivo RSN1111_KOBE.AT2
```

o desde código:

```python
from dinamica import leer_peer_at2, ExcitacionBase, resolver_base
t, ag = leer_peer_at2("RSN1111_KOBE.AT2")       # devuelve ag en m/s²
exc = ExcitacionBase(t, ag, nombre="Kobe 1995")
exc = exc.escalar_a_pga(0.30 * 9.80665)         # escalar a 0.30 g si hace falta
r = resolver_base(sistema, exc)
```

Para cambiarlo también en el caso 2, edita `construir_excitacion()` en
`casos/caso2_tanque.py`.

### 8.4 Si tu señal son **desplazamientos** del terreno y no aceleraciones

```bash
python main.py arbitraria ... --tipo-senal desplazamiento --unidad mm
```

El programa deriva dos veces la señal para obtener la aceleración
(`io_senales.derivar_aceleracion`).

---

## 9. Mapa de archivos

```
trabajoZapata/
├── README.md                      ← este documento
├── requirements.txt               ← librerías necesarias
├── menu.py                        ← ★ MENÚ INTERACTIVO POR CONSOLA
├── main.py                        ← interfaz de línea de comandos
├── app_streamlit.py               ← interfaz gráfica interactiva
├── pytest.ini · Makefile          ← configuración y atajos
│
├── dinamica/                      ← ★ EL MOTOR DE CÁLCULO
│   ├── unidades.py                   constantes y conversión de unidades
│   ├── sistema.py                    SistemaSDOF, serie/paralelo, Rayleigh
│   ├── cargas.py                     armónicas, pulsos, chirp, arbitrarias, sismo
│   ├── solucionadores.py             Newmark, interpolación exacta, Duhamel, analíticas
│   ├── frecuencia.py                 Rd, Rv, Ra, fase, transmisibilidad, aislamiento
│   ├── espectros.py                  espectros de respuesta y de choque
│   ├── parametrico.py                barridos paramétricos automáticos
│   ├── verificacion.py               equilibrio, energía, convergencia
│   ├── graficos.py                   15 tipos de figura normalizada
│   └── io_senales.py                 CSV, PEER .AT2, filtros, registro sintético
│
├── casos/
│   ├── caso1_maquinaria.py        ← caso 1 (carga armónica)
│   ├── caso2_tanque.py            ← caso 2 (sismo + impulso)
│   └── datos/
│       ├── registro_sintetico.csv    acelerograma de ejemplo (t, g)
│       └── fuerza_impactos.csv       serie de fuerzas de ejemplo (t, N)
│
├── tests/test_motor.py            ← 71 pruebas de verificación (+14 doctests)
├── reporte/generar_reporte.py     ← construye el PDF
└── salidas/                       ← TODO lo que genera el programa
    ├── Reporte-Tecnico-Respuesta-Dinamica.pdf
    ├── figuras/{caso1,caso2}/*.png
    └── menu/                         resultados generados desde el menú
```

---

## 10. Cómo se verificó que los resultados son correctos

Esto es lo que separa un trabajo de 3 de uno de 5: **ningún número se entrega sin
verificar**. Se usan cuatro verificaciones independientes.

**1) Contra soluciones analíticas exactas**

| Comparación | Error |
|---|---|
| Carga armónica: Newmark vs. solución cerrada | 0.16 % |
| Amplitud permanente medida vs. (p₀/k)·Rd | 0.22 % |
| Pulso triangular sin amortiguamiento: cerrada vs. numérica | 1.2 × 10⁻⁹ % |
| Pulso con ζ = 5 %: Newmark vs. interpolación exacta | 4 × 10⁻⁵ % |
| Sismo: Newmark vs. interpolación exacta | 0.05 % |
| Sd(Tn) del espectro vs. pico de la historia | 0.05 % |
| Aproximación impulsiva I/(m·ωn) vs. solución cerrada | 0.46 % |

**2) Equilibrio dinámico.** En cada instante se evalúa el residual
`r(t) = m·a + c·v + k·u − p(t)`. Sale del orden de **10⁻¹³** (adimensional), es
decir, precisión de máquina.

**3) Balance de energía.** La energía que introduce la carga debe repartirse
entre cinética, de deformación y disipada. El error de cierre es **< 0.01 %**.

**4) Convergencia.** Se repite el análisis con pasos Δt = Tn/5 … Tn/500 y se
comprueba que el error cae con **orden 2** (se divide por ~4 al reducir Δt a la
mitad), como corresponde al método. Con Tn/100 el error ya es < 1 %.

Además, la batería de `pytest` comprueba límites teóricos: Rd = 1/(2ζ) en
resonancia, TR = 1 en β = √2, Rd = 2 para el escalón, Rd → 1 con β → 0,
conservación de energía sin amortiguamiento, recuperación de ζ por decremento
logarítmico y que una estructura muy rígida se mueva solidariamente con el terreno.

---

## 11. Preguntas típicas de la sustentación (con respuesta)

**— ¿Por qué el sistema es de un grado de libertad?**
Porque la masa se concentra en un punto y el diafragma (o la geometría) obliga a
que todo se mueva con un único desplazamiento independiente. En el caso 1 lo
garantiza la losa rígida; en el caso 2, la masa concentrada arriba del voladizo.

**— ¿Por qué las columnas van en paralelo y no en serie?**
Porque **comparten el mismo desplazamiento** (la losa los obliga) y sus fuerzas se
suman ⇒ k_eq = Σk. En serie sería si compartieran la fuerza y sumaran deformaciones.

**— ¿Qué pasa si duplico la masa?**
ωn baja en √2 (Tn sube en √2). Si estabas en β > 1 te acercas a la resonancia; si
estabas en β < 1 te alejas. **En sismo, más masa = más fuerza inercial pero también
otro periodo**, así que el efecto no es monótono: hay que mirar el espectro.

**— ¿Y si duplico el amortiguamiento?**
Si estás en resonancia, la respuesta cae a la mitad (Rd = 1/(2ζ)). Fuera de
resonancia casi no cambia nada. Ante un impulso corto, prácticamente nada,
porque no hay tiempo para disipar energía.

**— ¿Por qué el desplazamiento máximo del impacto ocurre después del impacto?**
Porque con td ≪ Tn la carga se va antes de que la estructura “arranque”. El pulso
sólo le entrega **cantidad de movimiento**; el máximo aparece un cuarto de periodo
después, ya en vibración libre.

**— ¿Por qué usaron Newmark con β = 1/4 y no β = 1/6?**
Porque β = 1/4 (aceleración promedio) es **incondicionalmente estable**. β = 1/6 es
algo más preciso pero exige Δt ≤ 0.551·Tn; el programa verifica ese límite y
lanza un error si no se cumple.

**— ¿Cómo saben que el resultado no está mal?**
Sección 10: contraste con soluciones analíticas, residual de la ecuación de
movimiento ~10⁻¹³, balance de energía con cierre < 0.01 %, convergencia de orden 2
y 85 pruebas automáticas.

**— ¿Qué haría para controlar la respuesta?**
Depende del parámetro que la controla: en carga armónica, **desintonizar** (mover β
lejos de 1) y, si no se puede, amortiguar; en sismo, alargar el periodo con
aislamiento (baja fuerzas, sube desplazamientos) o aumentar la disipación; ante
impulsos, aumentar la masa (u ≈ I/(m·ωn)) o alargar el tiempo de aplicación de la
carga (amortiguadores de impacto).

**— ¿Cuál es la limitación más importante del modelo?**
Es **elástico y lineal**, de un solo grado de libertad, con amortiguamiento viscoso
constante, base rígida y, en el tanque, sin modo convectivo del agua.

---

## 12. Problemas frecuentes y soluciones

| Síntoma | Causa | Solución |
|---|---|---|
| `ModuleNotFoundError: No module named 'dinamica'` | estás en otra carpeta | `cd` a la carpeta del proyecto (donde está `main.py`) |
| `ModuleNotFoundError: No module named 'numpy'` | el entorno no está activo | `source .venv/bin/activate` (Windows: `.venv\Scripts\Activate.ps1`) |
| `command not found: python` | en macOS/Linux el ejecutable es `python3` | usa `python3` o activa el entorno virtual |
| `streamlit: command not found` | falta la librería opcional | `pip install streamlit` |
| `ValueError: Paso de tiempo ... supera el límite de estabilidad` | usaste β = 1/6 con Δt grande | reduce `--dt` o quita `familia="aceleracion_lineal"` |
| El PDF no se genera | falta `reportlab` o `pillow` | `pip install reportlab pillow` |
| Los resultados dan absurdos (metros de desplazamiento) | mezclaste unidades (kN con N, o t con kg) | revisa la sección 6.6 y usa `a_si()` |
| PowerShell no deja activar el entorno | política de ejecución | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Las figuras salen en blanco | ejecutaste sin permisos de escritura | ejecuta desde una carpeta con permisos; se crean en `salidas/` |

---

## 13. Glosario rápido

| Símbolo | Nombre | Unidad | Qué significa |
|---|---|---|---|
| m | masa | kg | cuánta inercia tiene |
| k | rigidez | N/m | fuerza necesaria para moverla 1 m |
| c | amortiguamiento | N·s/m | cuánta energía disipa |
| c_cr | amortiguamiento crítico | N·s/m | `2·m·ωn`; el límite entre oscilar y no oscilar |
| ζ | fracción de amortiguamiento | – | `c/c_cr`; acero ≈ 2 %, concreto ≈ 5 % |
| ωn | frecuencia natural circular | rad/s | `√(k/m)` |
| fn | frecuencia natural | Hz | `ωn/2π`, ciclos por segundo |
| Tn | periodo natural | s | `1/fn`, lo que tarda un ciclo |
| ω | frecuencia de la excitación | rad/s | el “reloj” de la carga |
| β | relación de frecuencias | – | `ω/ωn`; **el parámetro clave** |
| Rd | factor de amplificación dinámica | – | cuántas veces amplifica respecto al estático |
| TR | transmisibilidad | – | qué fracción de la fuerza llega al apoyo |
| td | duración del pulso | s | para impulsos; se compara con Tn |
| I | impulso | N·s | `∫p·dt`; lo que gobierna los pulsos cortos |
| Sd, PSv, PSa | valores espectrales | m, m/s, m/s² | respuesta pico ante un sismo, por periodo |
| PGA | aceleración pico del terreno | m/s² o g | el pico del acelerograma |

---

## 14. Checklist de entrega

- [x] **Plataforma o motor de cálculo** funcional, general, organizado y documentado
      (paquete `dinamica`, 10 módulos, con docstrings en todas las funciones).
- [x] Permite modificar los parámetros del sistema y de la excitación **sin
      reconstruir el modelo** (menú interactivo, bloque `DATOS`, CLI e interfaz
      gráfica).
- [x] Resuelve carga **armónica**, **impulsiva** y **arbitraria** (Newmark directo).
- [x] Admite señales de **aceleración o desplazamiento** en forma de vector.
- [x] **Unidades declaradas** de entrada y de salida.
- [x] **Gráficas** con título, ejes, unidades e información suficiente.
- [x] **Análisis paramétrico** completo (m, k, ζ, β, amplitud, duración, cond. iniciales).
- [x] **Factor de amplificación dinámica** y **transmisibilidad** con sus curvas.
- [x] **Verificación** contra soluciones analíticas y comprobaciones físicas.
- [x] **Dos casos de estudio** resueltos con idealización, hipótesis, resultados,
      interpretación y conclusiones.
- [x] **Reporte técnico en PDF** de 26 páginas (`salidas/Reporte-Tecnico-Respuesta-Dinamica.pdf`).

### Antes de entregar

```bash
pytest                 # 85 pruebas deben pasar
python main.py casos   # regenera resultados y figuras
python main.py reporte # regenera el PDF
python main.py         # abre el menú interactivo (para la sustentación)
```

Y entrega: **toda la carpeta del proyecto** (sin `.venv/`) + el **PDF** de `salidas/`.

---

### Una última recomendación 🎓

Antes de la sustentación, abre la interfaz gráfica y juega 15 minutos: mueve el
amortiguamiento en resonancia, mueve β, cambia td/Tn en la pestaña de impulsos y
observa el espectro de choque. **Predice** qué va a pasar antes de mover el
deslizador y luego compruébalo. Eso es exactamente lo que el profesor va a pedir
que hagas en la sustentación: *predecir cualitativamente el efecto de modificar
una variable antes de realizar el cálculo*.

¡Éxitos! 🚀
