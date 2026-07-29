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

## Clasificación para flexión — Tabla B4.1b

La pestaña **Flexión** clasifica automáticamente los elementos como compactos,
no compactos o esbeltos según el tipo de perfil, fabricación, eje de análisis y
lado indicado en compresión. Esta etapa no calcula resistencia a flexión ni
aplica el Capítulo F.
