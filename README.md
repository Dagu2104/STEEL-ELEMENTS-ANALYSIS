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
- F13.1 se verifica para agujeros en el ala de tensión y puede gobernar el momento nominal.
- F13.2 verifica automáticamente las proporciones disponibles de perfiles I; la separación
  entre rigidizadores se solicita cuando el alma es esbelta.
- Los requisitos de detalle de cubreplacas y vigas armadas de F13.3/F13.4 dependen de
  soldaduras, pernos y distribución de carga, por lo que se muestran como advertencias.

## Visualización de Fcr en flexión

La tabla de resultados del Capítulo F incluye una columna `Fcr` en la unidad de esfuerzo seleccionada. El valor se muestra únicamente cuando la ecuación normativa define `Fcr` explícitamente. Cuando AISC calcula `Mn` directamente, la tabla indica `No definido`; cuando el estado límite no aplica, indica `No aplica`. Las ecuaciones que emplean el momento crítico `Mcr` lo reportan en la observación y no lo presentan como `Fcr`.

## Cortante — Capítulo G

La pestaña **Cortante**, ubicada después de Flexión, selecciona automáticamente la ruta normativa según el perfil y el eje de análisis:

- G2 para perfiles I y canales con cortante paralelo al alma;
- G3 para ángulos simples y el vástago de tees;
- G4 para HSS rectangulares, cajones y secciones dobles simétricas soportadas;
- G5 para HSS circulares;
- G6 para cortante respecto al eje menor en perfiles I, canales, tees y configuraciones dobles soportadas;
- G7 se muestra como advertencia cuando existen aberturas en el alma o en las paredes resistentes.

Para G2, el programa usa un flujo longitudinal desde la cara de la columna:

- el usuario ingresa el cortante máximo en la cara de la columna;
- ingresa la distancia `Lz` hasta la sección donde desea que el perfil continúe sin rigidizadores;
- ingresa el cortante existente en esa sección `Vu(Lz)` o `Va(Lz)`;
- el perfil sin rigidizadores se verifica con el cortante al final de la zona;
- todos los paneles y rigidizadores se diseñan conservadoramente con el máximo cortante de la zona;
- el programa calcula la separación longitudinal máxima `amax` mediante G2.1 para el panel extremo;
- calcula automáticamente el número mínimo de paneles y permite adoptar cualquier cantidad mayor;
- distribuye los rigidizadores uniformemente y coloca el último en `x=Lz`;
- muestra una tabla con la posición de cada rigidizador y los límites de cada panel;
- verifica los paneles interiores con G2.2 cuando se activa la acción de campo de tracción;
- verifica esbeltez e inercia de las placas mediante G2-16 a G2-19.

G2.3 no se calcula. Por ello, `amax` se obtiene conservadoramente con G2.1 para el panel extremo. Cuando ni una separación muy pequeña permite que ese panel alcance la demanda, se informa que debe modificarse la sección o realizarse un análisis especializado.

La cantidad de paneles no suma resistencias. Cada panel debe resistir individualmente el mismo cortante máximo adoptado. La separación uniforme real es `a=Lz/n`, y debe cumplir `a≤amax`.

El ancho saliente `bst` corresponde a cada placa rigidizadora y queda limitado automáticamente por la geometría del perfil: `(bf-tw)/2` para un perfil I simétrico, el menor espacio disponible de los dos patines para un perfil I asimétrico y el ancho saliente del patín para un canal. Los radios interiores y holguras de soldadura no se descuentan, por lo que el detalle final puede requerir un ancho menor.

## Comparación demanda/capacidad

Las pestañas **Carga axial**, **Flexión** y **Cortante** permiten seleccionar LRFD o ASD e ingresar la solicitación correspondiente. La aplicación muestra mediante métricas:

- demanda;
- capacidad disponible;
- relación demanda/capacidad `D/C`;
- estado `CUMPLE` o `NO CUMPLE`.

La comparación es únicamente una capa de verificación y no modifica las ecuaciones ni los resultados nominales ya implementados en los capítulos E, F y G.

En G2, la recomendación de rigidizadores distingue la causa de la insuficiencia:

- si `Cv < 1.0`, la resistencia está reducida por pandeo del alma y los rigidizadores pueden aumentar `kv` y `Cv`;
- si `Cv = 1.0`, gobierna la fluencia `0.6FyAw` y los rigidizadores no aumentan ese límite; debe modificarse el alma, reforzarse la sección o elegirse un perfil mayor.

## Fuerzas combinadas y torsión — Capítulo H

La pestaña **Flexocompresión** incorpora el Capítulo H y reutiliza las resistencias disponibles calculadas en las pestañas anteriores. Las ecuaciones de los capítulos E, F y G no se recalculan ni se sustituyen.

La pestaña permite:

- ingresar varias combinaciones en una tabla editable;
- descargar una plantilla Excel con hojas `Combinaciones`, `Configuracion` e `Instrucciones`;
- cargar la plantilla completada y editar sus valores antes del cálculo;
- descargar la tabla actual y un libro de resultados;
- definir la convención de signos de `Mrx` y `Mry` para identificar el lado comprimido;
- aplicar H1-1a o H1-1b a miembros doble o simplemente simétricos;
- calcular automáticamente la resistencia torsional de HSS circular, cuadrado y rectangular mediante H3.1;
- aplicar H3-6 cuando `Tr/Tc > 0.20`, incluyendo fuerza axial, flexión biaxial, cortante y torsión;
- identificar la combinación gobernante y exportar el desarrollo de los términos de interacción.

### Formato de la hoja `Combinaciones`

Los encabezados fijos son:

```text
Combinacion | Tipo_axial | Pr | Mrx | Mry | Vrx | Vry | Tr
```

`Pr`, `Vrx` y `Vry` usan la unidad de fuerza indicada en `Configuracion`. `Mrx`, `Mry` y `Tr` usan la unidad de momento. `Pr` se ingresa como magnitud positiva y `Tipo_axial` define si corresponde a compresión o tensión. Los momentos se ingresan con signo.

### Recuperación de resistencias

Las capacidades se almacenan con una firma del perfil, material y geometría actuales. Al cambiar dimensiones, material, fabricación o cubreplacas, las capacidades antiguas dejan de ser válidas automáticamente.

Para disponer de las resistencias en ambos ejes, seleccione cada eje y lado comprimido en la barra lateral. La pestaña de flexión guarda `Mcx` o `Mcy` para el lado calculado, y la pestaña de cortante guarda `Vcx` o `Vcy` para el eje calculado.

### Límites actuales del Capítulo H

- La aplicación axial existente corresponde al Capítulo E, es decir, compresión. Las combinaciones con tensión axial se conservan en la tabla, pero no se aprueban hasta incorporar la resistencia del Capítulo D.
- H2 requiere esfuerzos disponibles en ejes principales y en puntos críticos de la sección. La aplicación no reemplaza esa evaluación con capacidades geométricas `x-x/y-y`; por ello, los perfiles completamente asimétricos se reportan como no evaluados.
- H3.3 para perfiles no HSS requiere un análisis de torsión y alabeo que determine los esfuerzos y `Fcr`. La interfaz muestra los límites H3-7 a H3-9, pero no genera una interacción automática usando solamente `Tr`.
- H4 requiere la resistencia de rotura axial del Capítulo D y la resistencia de rotura por flexión de F13.1 para cada patín. Se identifica la ruta, pero no se aprueba hasta que esté disponible el Capítulo D.
- H1.3 está preparado en `capitulo_h.py`, pero no se selecciona automáticamente porque requiere una resistencia a LTB calculada específicamente con `Cb=1.0` y las capacidades separadas en el plano y fuera del plano.

## Corrección: cortante en ambos ejes y estados con color

- La resistencia base de G2 se guarda ahora como capacidad de cortante `x-x`, por lo que el Capítulo H puede recuperarla junto con la capacidad `y-y` de G6.
- El valor almacenado para G2 corresponde conservadoramente al perfil sin rigidizadores transversales.
- La tabla de resultados del Capítulo H colorea `CUMPLE` en verde, `NO CUMPLE` en rojo y `NO EVALUADA` en amarillo.
- La combinación gobernante y cada combinación individual muestran una tarjeta de estado con el mismo código de colores.
