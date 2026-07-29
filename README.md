# Diseño de perfiles de acero

Aplicación Streamlit para perfiles estándar de acero. Incluye:

- clasificación local de elementos en compresión según la Tabla B4.1a;
- selección automática de la ruta del Capítulo E;
- verificaciones E2, E3, E4, E5, E6 y E7 incorporadas progresivamente;
- dibujo dinámico del perfil y del eje de análisis;
- cálculo automático de propiedades geométricas desde las dimensiones ingresadas.

## Propiedades calculadas

Para cada perfil se calculan, según corresponda:

- área bruta `Ag`;
- centroide `x̄`, `ȳ`;
- `Ix`, `Iy`, `Ixy`;
- radios de giro `rx`, `ry` y radios principales;
- inercias principales y orientación de ejes principales;
- módulos elásticos superior, inferior, derecho e izquierdo;
- módulos plásticos `Zx` y `Zy`;
- constante torsional `J`;
- `Cw` aproximado únicamente para perfiles I doblemente simétricos.

## Convenciones y limitaciones

- Se ignoran radios de filete en perfiles abiertos.
- Los tubos cuadrados y rectangulares se calculan con esquinas rectas. Para tubos `Rolled`, las propiedades son aproximadas porque no se incluyen los radios reales de esquina.
- En canales, tees y ángulos todavía no se calculan automáticamente el centro de cortante ni `Cw`; cuando E4 los requiere, deben ingresarse.
- En ángulos dobles se considera la separación libre entre las caras interiores y no se incluye el área de los separadores.
- Para cubreplacas se distinguen el ancho total `Bcp`, usado en propiedades, y el ancho `b` entre líneas de conexión, usado en la Tabla B4.1a.

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud

Sube los archivos a la raíz del repositorio y selecciona `app.py` como archivo principal.

## Unidades personalizadas

La barra lateral permite seleccionar independientemente las unidades de longitud, esfuerzo, fuerza y momento. El programa conserva un sistema interno consistente (`mm`, `MPa`, `N`, `N·mm`) y convierte automáticamente los valores ya ingresados cuando se cambia una unidad.


## Perfil I asimétrico

Se admite una sección I monosimétrica con patines superior e inferior de anchos y espesores diferentes. En compresión axial se evalúan ambos patines por separado y el alma mediante B4.1a. En flexión mayor se evalúa el patín comprimido y el alma mediante el caso 16 cuando corresponde; en flexión menor se evalúan ambos patines por separado.

La multiplicidad usada en E7 se determina automáticamente desde la geometría y no es editable.

## Aplicabilidad automática de E4

La aplicación determina E4 mediante los estados límite seleccionados por la ruta automática del Capítulo E:

- `TB` muestra **E4 — Pandeo torsional**;
- `FTB` muestra **E4 — Pandeo flexotorsional**;
- si la ruta no contiene `TB` ni `FTB`, el bloque E4 no aparece.

Por ello, E4 permanece oculto para tubos cuadrados, rectangulares y circulares. La verificación aplicable ya no puede activarse ni desactivarse mediante una casilla manual.

## Flexión — Capítulo F

La pestaña **Flexión** conserva la clasificación local de la Tabla B4.1b y añade:

- selección automática de la ruta F2 a F12 mediante la Tabla User Note F1.1;
- cálculo de `Cb` con F1-1 o ingreso directo;
- resistencia nominal `Mn`, resistencia LRFD `ϕbMn` y resistencia ASD `Mn/Ωb`;
- F2/F3 para perfiles I doblemente simétricos y canales compactos;
- F4/F5 para perfiles I monosimétricos, con almas no compactas o esbeltas;
- F6 para perfiles I y canales flexionados respecto al eje menor;
- F7 para tubos cuadrados/rectangulares y cajones `Built-up`;
- F8 para tubos circulares;
- F9 para tees y ángulos dobles cargados en el plano de simetría;
- F10 para ángulos simples con opciones de ejes geométricos o principales.

Los cálculos internos utilizan `mm`, `MPa`, `N` y `N·mm`. Los momentos se convierten
a la unidad seleccionada por el usuario. Se adoptan `ϕb = 0.90` y `Ωb = 1.67`.

### Alcance actual de F11, F12 y F13

- La interfaz no genera barras macizas, por lo que F11 queda preparado en el módulo,
  pero no aparece como tipo de perfil seleccionable.
- La interfaz no crea secciones completamente asimétricas personalizadas; F12 se
  identifica como ruta de análisis cuando corresponde, pero no se calcula con
  fórmulas cerradas.
- F13.1 identifica automáticamente el ala de tracción y solo incorpora una cubreplaca cuando está ubicada en ese lado. El usuario selecciona el diámetro comercial del perno, el tipo de agujero, la cantidad de agujeros atravesados por la trayectoria crítica y si están alineados o escalonados. El programa obtiene la dimensión nominal del agujero, aplica la adición de B4.3b y calcula automáticamente `Afg`, `Afn` y `Yt`.
- F13.2 verifica automáticamente las proporciones disponibles de perfiles I; la separación
  entre rigidizadores se solicita cuando el alma es esbelta.
- Los requisitos de detalle de cubreplacas y vigas armadas de F13.3/F13.4 dependen de
  soldaduras, pernos y distribución de carga, por lo que se muestran como advertencias.

## Visualización de Fcr en flexión

La tabla de resultados del Capítulo F incluye una columna `Fcr` en la unidad de esfuerzo seleccionada. Cuando la ecuación normativa define `Fcr` explícitamente, se muestra ese valor. Cuando la ecuación calcula `Mn` directamente, se muestra `Fcr equivalente = Mn/S` únicamente como trazabilidad y se identifica claramente en la observación.
