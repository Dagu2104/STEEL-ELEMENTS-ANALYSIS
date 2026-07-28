"""Aplicación Streamlit para clasificación de elementos en compresión uniforme."""

from __future__ import annotations

import streamlit as st

from funciones import (
    evaluar_angulo,
    evaluar_canal,
    evaluar_hss_circular,
    evaluar_hss_rectangular,
    evaluar_perfil_i,
    evaluar_tee,
)


st.set_page_config(
    page_title="Clasificación de perfiles de acero",
    page_icon="🏗️",
    layout="wide",
)

st.title("Clasificación de elementos de perfiles de acero")
st.caption("Selección automática de elementos rigidizados y no rigidizados — Tabla B4.1a")

with st.expander("Alcance y convenciones", expanded=False):
    st.markdown(
        """
        - La aplicación trabaja únicamente con perfiles estándar incluidos en el menú.
        - La condición **rigidizado/no rigidizado** se asigna automáticamente.
        - El eje de análisis se guarda para futuras verificaciones de flexión y pandeo; no modifica esta tabla.
        - En perfiles I, canales y tees se adopta la orientación convencional: **x-x horizontal** y **y-y vertical**.
        - `E` y `Fy` deben ingresarse en unidades consistentes.
        - Verifique las definiciones geométricas con la edición de AISC aplicable al proyecto.
        """
    )

st.sidebar.header("Configuración")

perfil = st.sidebar.selectbox(
    "Tipo de perfil",
    [
        "Perfil I",
        "Canal",
        "Tee",
        "Ángulo simple",
        "Ángulo doble con separadores",
        "HSS cuadrado",
        "HSS rectangular",
        "HSS circular",
    ],
)

eje = st.sidebar.radio(
    "Eje de análisis",
    ["x-x", "y-y", "Ambos ejes"],
    help="Se conserva para módulos posteriores. No afecta la Tabla B4.1a.",
)

st.sidebar.subheader("Material")
unidades = st.sidebar.selectbox("Sistema de esfuerzo", ["MPa", "ksi"])
if unidades == "MPa":
    E_predeterminado = 200_000.0
    Fy_predeterminado = 345.0
else:
    E_predeterminado = 29_000.0
    Fy_predeterminado = 50.0

E = st.sidebar.number_input(
    f"Módulo de elasticidad E [{unidades}]",
    min_value=0.001,
    value=E_predeterminado,
    step=1000.0 if unidades == "MPa" else 100.0,
)
Fy = st.sidebar.number_input(
    f"Esfuerzo de fluencia Fy [{unidades}]",
    min_value=0.001,
    value=Fy_predeterminado,
    step=5.0,
)

st.info(
    f"**Perfil seleccionado:** {perfil}  |  **Eje guardado:** {eje}. "
    "El eje no interviene en esta verificación de compresión uniforme."
)

st.subheader("Geometría")
st.write("Solo se muestran los datos necesarios para el perfil seleccionado.")

resultados = None
error = None

try:
    if perfil == "Perfil I":
        fabricacion = st.selectbox(
            "Fabricación",
            ["Rolled", "Built-up"],
            help="Rolled: laminado. Built-up: armado con placas.",
        )
        c1, c2 = st.columns(2)
        with c1:
            bf = st.number_input("Ancho total del ala bf", min_value=0.001, value=200.0)
            tf = st.number_input("Espesor del ala tf", min_value=0.001, value=12.0)
        with c2:
            h = st.number_input("Altura libre del alma h", min_value=0.001, value=450.0)
            tw = st.number_input("Espesor del alma tw", min_value=0.001, value=8.0)
        resultados = evaluar_perfil_i(
            fabricacion=fabricacion, bf=bf, tf=tf, h=h, tw=tw, E=E, Fy=Fy
        )

    elif perfil == "Canal":
        st.caption("La fabricación queda definida internamente como perfil laminado para este caso.")
        c1, c2 = st.columns(2)
        with c1:
            b_ala = st.number_input("Ancho saliente del ala b", min_value=0.001, value=70.0)
            tf = st.number_input("Espesor del ala tf", min_value=0.001, value=10.0)
        with c2:
            h = st.number_input("Altura libre del alma h", min_value=0.001, value=250.0)
            tw = st.number_input("Espesor del alma tw", min_value=0.001, value=7.0)
        resultados = evaluar_canal(b_ala=b_ala, tf=tf, h=h, tw=tw, E=E, Fy=Fy)

    elif perfil == "Tee":
        fabricacion = st.selectbox("Fabricación", ["Rolled"], disabled=True)
        c1, c2 = st.columns(2)
        with c1:
            b_ala = st.number_input("Ancho saliente de media ala b", min_value=0.001, value=75.0)
            tf = st.number_input("Espesor del ala tf", min_value=0.001, value=12.0)
        with c2:
            d_vastago = st.number_input("Profundidad del vástago d", min_value=0.001, value=150.0)
            tw = st.number_input("Espesor del vástago tw", min_value=0.001, value=8.0)
        resultados = evaluar_tee(
            b_ala=b_ala, tf=tf, d_vastago=d_vastago, tw=tw, E=E, Fy=Fy
        )

    elif perfil in {"Ángulo simple", "Ángulo doble con separadores"}:
        st.caption("La fabricación no cambia la fórmula de este caso y se asigna como 'No aplica'.")
        c1, c2 = st.columns(2)
        with c1:
            b1 = st.number_input("Ancho de la pata 1, b1", min_value=0.001, value=75.0)
            t = st.number_input("Espesor t", min_value=0.001, value=8.0)
        with c2:
            b2 = st.number_input("Ancho de la pata 2, b2", min_value=0.001, value=75.0)
        resultados = evaluar_angulo(tipo=perfil, b1=b1, b2=b2, t=t, E=E, Fy=Fy)

    elif perfil in {"HSS cuadrado", "HSS rectangular"}:
        st.caption("La fabricación se reconoce por el tipo HSS; no se solicita Rolled/Built-up.")
        c1, c2, c3 = st.columns(3)
        with c1:
            B_plano = st.number_input("Ancho plano B", min_value=0.001, value=180.0)
        with c2:
            H_plano = st.number_input(
                "Altura plana H",
                min_value=0.001,
                value=180.0 if perfil == "HSS cuadrado" else 280.0,
            )
        with c3:
            t = st.number_input("Espesor de diseño t", min_value=0.001, value=8.0)
        resultados = evaluar_hss_rectangular(
            B_plano=B_plano, H_plano=H_plano, t=t, E=E, Fy=Fy, perfil=perfil
        )

    elif perfil == "HSS circular":
        st.caption("La fabricación se reconoce por el tipo HSS; se aplica el caso circular específico.")
        c1, c2 = st.columns(2)
        with c1:
            D = st.number_input("Diámetro exterior D", min_value=0.001, value=200.0)
        with c2:
            t = st.number_input("Espesor de diseño t", min_value=0.001, value=8.0)
        resultados = evaluar_hss_circular(D=D, t=t, E=E, Fy=Fy)

except ValueError as exc:
    error = str(exc)

if error:
    st.error(error)
elif resultados:
    st.subheader("Resultados")

    for resultado in resultados:
        estado = "✅" if resultado.clasificacion == "NO ESBELTO" else "⚠️"
        with st.container(border=True):
            st.markdown(f"### {estado} {resultado.elemento}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("λ real", f"{resultado.lambda_real:.3f}")
            c2.metric("λr", f"{resultado.lambda_r:.3f}")
            c3.metric("Condición", resultado.condicion_borde)
            c4.metric("Clasificación", resultado.clasificacion)

            st.write(f"**Caso de tabla:** {resultado.caso_tabla}")
            st.write(f"**Relación empleada:** `{resultado.relacion}`")
            st.write(f"**Fórmula límite:** `{resultado.formula}`")
            if resultado.observacion:
                st.caption(resultado.observacion)

    gobierna = max(resultados, key=lambda r: r.lambda_real / r.lambda_r)
    utilizacion = gobierna.lambda_real / gobierna.lambda_r
    st.success(
        f"Elemento más crítico: **{gobierna.elemento}**, "
        f"con λ/λr = **{utilizacion:.3f}**."
    ) if utilizacion <= 1.0 else st.warning(
        f"Elemento más crítico: **{gobierna.elemento}**, "
        f"con λ/λr = **{utilizacion:.3f}**."
    )

st.divider()
st.caption(
    "Herramienta de apoyo. Antes del diseño definitivo, confirme la edición normativa, "
    "las definiciones de ancho efectivo/plano y los espesores de diseño aplicables."
)
