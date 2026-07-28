# Clasificación de perfiles de acero con Streamlit

Aplicación para seleccionar un perfil estándar, ingresar únicamente su geometría relevante y clasificar automáticamente sus elementos como rigidizados o no rigidizados conforme a los casos implementados de la Tabla B4.1a.

## Archivos

- `app.py`: interfaz principal de Streamlit.
- `funciones.py`: funciones de cálculo y validación.
- `requirements.txt`: dependencias para Streamlit Community Cloud.
- `.gitignore`: archivos que no deben subirse al repositorio.

## Ejecución local

```bash
python -m venv .venv
```

En Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Publicación en Streamlit Community Cloud

1. Cree un repositorio en GitHub.
2. Suba todos los archivos manteniéndolos en la raíz del repositorio.
3. En Streamlit Community Cloud seleccione el repositorio, la rama y `app.py` como archivo principal.
4. Pulse **Deploy**.

## Alcance

La aplicación trabaja con:

- Perfil I Rolled y Built-up.
- Canal.
- Tee.
- Ángulo simple.
- Ángulo doble con separadores.
- HSS cuadrado y rectangular.
- HSS circular.

El eje `x-x`, `y-y` o ambos se almacena como dato de configuración para futuras ampliaciones, pero no modifica la clasificación de esta tabla.

> Verifique las definiciones geométricas y los límites con la edición de AISC aplicable al proyecto antes de emplear los resultados en un diseño definitivo.
