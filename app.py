"""Aplicación Streamlit para clasificación de perfiles de acero."""

from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

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


def _safe(value: float, minimum: float = 0.001) -> float:
    return max(float(value), minimum)


def _fit_rect(width: float, height: float, max_width: float = 220, max_height: float = 220):
    """Escala un rectángulo manteniendo sus proporciones dentro del área indicada."""
    width = _safe(width)
    height = _safe(height)
    scale = min(max_width / width, max_height / height)
    return width * scale, height * scale, scale


def _axis_svg(eje: str, cx: float, cy: float, span_x: float, span_y: float) -> str:
    """Dibuja solo el eje seleccionado y la dirección perpendicular de flexión."""
    if eje == "x-x":
        x1 = max(30, cx - span_x / 2 - 35)
        x2 = min(470, cx + span_x / 2 + 35)
        arrow_x = min(455, cx + span_x / 2 + 55)
        return f"""
        <line x1="{x1:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" y2="{cy:.1f}" class="axis"/>
        <text x="{x2 - 28:.1f}" y="{cy - 10:.1f}" class="axis-label">x-x</text>
        <line x1="{arrow_x:.1f}" y1="{cy - span_y/2:.1f}" x2="{arrow_x:.1f}" y2="{cy + span_y/2:.1f}" class="bend"/>
        <polygon points="{arrow_x:.1f},{cy-span_y/2-12:.1f} {arrow_x-8:.1f},{cy-span_y/2+4:.1f} {arrow_x+8:.1f},{cy-span_y/2+4:.1f}" class="bend-fill"/>
        <polygon points="{arrow_x:.1f},{cy+span_y/2+12:.1f} {arrow_x-8:.1f},{cy+span_y/2-4:.1f} {arrow_x+8:.1f},{cy+span_y/2-4:.1f}" class="bend-fill"/>
        <text x="{arrow_x+10:.1f}" y="{cy+5:.1f}" class="bend-label">Flexión ⟂ x-x</text>
        """

    y1 = max(30, cy - span_y / 2 - 35)
    y2 = min(315, cy + span_y / 2 + 35)
    arrow_y = min(335, cy + span_y / 2 + 55)
    return f"""
    <line x1="{cx:.1f}" y1="{y1:.1f}" x2="{cx:.1f}" y2="{y2:.1f}" class="axis"/>
    <text x="{cx+10:.1f}" y="{y1+18:.1f}" class="axis-label">y-y</text>
    <line x1="{cx-span_x/2:.1f}" y1="{arrow_y:.1f}" x2="{cx+span_x/2:.1f}" y2="{arrow_y:.1f}" class="bend"/>
    <polygon points="{cx-span_x/2-12:.1f},{arrow_y:.1f} {cx-span_x/2+4:.1f},{arrow_y-8:.1f} {cx-span_x/2+4:.1f},{arrow_y+8:.1f}" class="bend-fill"/>
    <polygon points="{cx+span_x/2+12:.1f},{arrow_y:.1f} {cx+span_x/2-4:.1f},{arrow_y-8:.1f} {cx+span_x/2-4:.1f},{arrow_y+8:.1f}" class="bend-fill"/>
    <text x="{cx-50:.1f}" y="{arrow_y+24:.1f}" class="bend-label">Flexión ⟂ y-y</text>
    """


def diagrama_perfil(perfil: str, eje: str, g: dict[str, float]) -> str:
    """Genera un SVG dinámico, escalado con las dimensiones ingresadas."""
    titulo = escape(perfil)
    cx, cy = 225.0, 170.0
    forma = ""
    etiquetas = ""
    dimensiones = ""

    if perfil == "Perfil I":
        bf, tf, h, tw = g["bf"], g["tf"], g["h"], g["tw"]
        d = h + 2 * tf
        W, H, s = _fit_rect(bf, d)
        tf_s = max(5.0, tf * s)
        tw_s = max(4.0, tw * s)
        x0, y0 = cx - W / 2, cy - H / 2
        forma = f"""
        <rect x="{x0:.1f}" y="{y0:.1f}" width="{W:.1f}" height="{tf_s:.1f}" class="section"/>
        <rect x="{cx-tw_s/2:.1f}" y="{y0+tf_s:.1f}" width="{tw_s:.1f}" height="{max(1,H-2*tf_s):.1f}" class="section"/>
        <rect x="{x0:.1f}" y="{y0+H-tf_s:.1f}" width="{W:.1f}" height="{tf_s:.1f}" class="section"/>
        """
        etiquetas = f"""
        <text x="{x0+6:.1f}" y="{y0-10:.1f}" class="part-label">Patín</text>
        <text x="{cx+tw_s/2+10:.1f}" y="{cy+5:.1f}" class="part-label">Alma</text>
        """
        dimensiones = f"bf={bf:g}, tf={tf:g}, h={h:g}, tw={tw:g}"
        span_x, span_y = W, H

    elif perfil == "Canal":
        b, tf, h, tw = g["b_ala"], g["tf"], g["h"], g["tw"]
        B = b + tw
        d = h + 2 * tf
        W, H, s = _fit_rect(B, d)
        tf_s = max(5.0, tf * s)
        tw_s = max(4.0, tw * s)
        x0, y0 = cx - W / 2, cy - H / 2
        forma = f"""
        <rect x="{x0:.1f}" y="{y0:.1f}" width="{W:.1f}" height="{tf_s:.1f}" class="section"/>
        <rect x="{x0:.1f}" y="{y0+tf_s:.1f}" width="{tw_s:.1f}" height="{max(1,H-2*tf_s):.1f}" class="section"/>
        <rect x="{x0:.1f}" y="{y0+H-tf_s:.1f}" width="{W:.1f}" height="{tf_s:.1f}" class="section"/>
        """
        etiquetas = f"""
        <text x="{x0+W+8:.1f}" y="{y0+tf_s:.1f}" class="part-label">Patín</text>
        <text x="{x0-48:.1f}" y="{cy+5:.1f}" class="part-label">Alma</text>
        """
        dimensiones = f"b={b:g}, tf={tf:g}, h={h:g}, tw={tw:g}"
        span_x, span_y = W, H

    elif perfil == "Tee":
        b, tf, d_stem, tw = g["b_ala"], g["tf"], g["d_vastago"], g["tw"]
        bf = 2 * b
        d = tf + d_stem
        W, H, s = _fit_rect(bf, d)
        tf_s = max(5.0, tf * s)
        tw_s = max(4.0, tw * s)
        x0, y0 = cx - W / 2, cy - H / 2
        forma = f"""
        <rect x="{x0:.1f}" y="{y0:.1f}" width="{W:.1f}" height="{tf_s:.1f}" class="section"/>
        <rect x="{cx-tw_s/2:.1f}" y="{y0+tf_s:.1f}" width="{tw_s:.1f}" height="{max(1,H-tf_s):.1f}" class="section"/>
        """
        etiquetas = f"""
        <text x="{x0+6:.1f}" y="{y0-10:.1f}" class="part-label">Patín</text>
        <text x="{cx+tw_s/2+10:.1f}" y="{cy+15:.1f}" class="part-label">Vástago</text>
        """
        dimensiones = f"b={b:g}, tf={tf:g}, d={d_stem:g}, tw={tw:g}"
        span_x, span_y = W, H

    elif perfil in {"Ángulo simple", "Ángulo doble con separadores"}:
        b1, b2, t = g["b1"], g["b2"], g["t"]
        W, H, s = _fit_rect(b2, b1)
        t_s = max(5.0, t * s)
        x0, y0 = cx - W / 2, cy - H / 2
        if perfil == "Ángulo simple":
            forma = f"""
            <rect x="{x0:.1f}" y="{y0:.1f}" width="{t_s:.1f}" height="{H:.1f}" class="section"/>
            <rect x="{x0:.1f}" y="{y0+H-t_s:.1f}" width="{W:.1f}" height="{t_s:.1f}" class="section"/>
            """
        else:
            gap = max(18.0, 0.18 * W)
            each_w = (W - gap) / 2
            forma = f"""
            <rect x="{cx-gap/2-each_w:.1f}" y="{y0:.1f}" width="{t_s:.1f}" height="{H:.1f}" class="section"/>
            <rect x="{cx-gap/2-each_w:.1f}" y="{y0+H-t_s:.1f}" width="{each_w:.1f}" height="{t_s:.1f}" class="section"/>
            <rect x="{cx+gap/2+each_w-t_s:.1f}" y="{y0:.1f}" width="{t_s:.1f}" height="{H:.1f}" class="section"/>
            <rect x="{cx+gap/2:.1f}" y="{y0+H-t_s:.1f}" width="{each_w:.1f}" height="{t_s:.1f}" class="section"/>
            <line x1="{cx:.1f}" y1="{y0+H*0.25:.1f}" x2="{cx:.1f}" y2="{y0+H*0.75:.1f}" class="separator"/>
            """
        etiquetas = f"""
        <text x="{x0-5:.1f}" y="{y0-10:.1f}" class="part-label">Pata vertical</text>
        <text x="{cx-35:.1f}" y="{y0+H+22:.1f}" class="part-label">Pata horizontal</text>
        """
        dimensiones = f"b1={b1:g}, b2={b2:g}, t={t:g}"
        span_x, span_y = W, H

    elif perfil in {"HSS cuadrado", "HSS rectangular"}:
        B, Hreal, t = g["B_plano"], g["H_plano"], g["t"]
        W, H, s = _fit_rect(B, Hreal)
        t_s = max(5.0, min(t * s, min(W, H) / 3))
        x0, y0 = cx - W / 2, cy - H / 2
        forma = f"""
        <rect x="{x0:.1f}" y="{y0:.1f}" width="{W:.1f}" height="{H:.1f}" rx="{min(16,t_s):.1f}" class="section"/>
        <rect x="{x0+t_s:.1f}" y="{y0+t_s:.1f}" width="{max(1,W-2*t_s):.1f}" height="{max(1,H-2*t_s):.1f}" rx="{max(3,min(10,t_s/2)):.1f}" class="void"/>
        """
        etiquetas = f"""
        <text x="{x0:.1f}" y="{y0-12:.1f}" class="part-label">Pared horizontal</text>
        <text x="{x0+W+8:.1f}" y="{cy+5:.1f}" class="part-label">Pared vertical</text>
        """
        dimensiones = f"B={B:g}, H={Hreal:g}, t={t:g}"
        span_x, span_y = W, H

    else:  # HSS circular
        D, t = g["D"], g["t"]
        outer = 210.0
        s = outer / _safe(D)
        t_s = max(5.0, min(t * s, outer / 3))
        r = outer / 2
        forma = f"""
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" class="section"/>
        <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{max(1,r-t_s):.1f}" class="void"/>
        """
        etiquetas = f"""
        <text x="{cx+r+8:.1f}" y="{cy-r/2:.1f}" class="part-label">Pared tubular</text>
        """
        dimensiones = f"D={D:g}, t={t:g}"
        span_x = span_y = outer

    ejes = _axis_svg(eje, cx, cy, span_x, span_y)

    return f"""
    <div class="profile-card">
      <div class="profile-heading">{titulo} · eje {escape(eje)} · geometría dinámica</div>
      <svg viewBox="0 0 500 370" role="img" aria-label="Diagrama de {titulo}">
        <defs>
          <style>
            .section {{ fill:#dce6f1; stroke:#1f2937; stroke-width:2.4; }}
            .void {{ fill:white; stroke:#1f2937; stroke-width:1.8; }}
            .axis {{ stroke:#c0392b; stroke-width:2; stroke-dasharray:8 6; }}
            .axis-label {{ font:700 15px sans-serif; fill:#c0392b; }}
            .part-label {{ font:600 14px sans-serif; fill:#273444; }}
            .bend {{ stroke:#1565c0; stroke-width:2.5; }}
            .bend-fill {{ fill:#1565c0; }}
            .bend-label {{ font:600 13px sans-serif; fill:#1565c0; }}
            .separator {{ stroke:#59636e; stroke-width:4; stroke-dasharray:5 5; }}
          </style>
        </defs>
        {forma}
        {ejes}
        {etiquetas}
      </svg>
      <div class="profile-note">
        <b>Dimensiones:</b> {escape(dimensiones)}. Solo se muestra el eje seleccionado; la flexión se representa perpendicular a dicho eje.
      </div>
    </div>
    """


def mostrar_diagrama(perfil: str, eje: str, geometria: dict[str, float]) -> None:
    contenido = f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <style>
        html, body {{ margin:0; padding:0; background:transparent; font-family:Arial,sans-serif; }}
        .profile-card {{ box-sizing:border-box; border:1px solid rgba(128,128,128,.35); border-radius:14px; padding:.8rem 1rem .9rem; background:rgba(128,128,128,.035); width:100%; }}
        .profile-heading {{ font-size:1.05rem; font-weight:700; margin-bottom:.25rem; }}
        .profile-card svg {{ display:block; width:100%; max-width:760px; height:390px; margin:auto; }}
        .profile-note {{ text-align:center; font-size:.92rem; opacity:.85; margin-top:.2rem; }}
      </style>
    </head>
    <body>{diagrama_perfil(perfil, eje, geometria)}</body>
    </html>
    """
    components.html(contenido, height=485, scrolling=False)


def cargar_geometria(perfil: str) -> tuple[dict[str, Any], str | None]:
    """Muestra únicamente los controles geométricos aplicables al perfil."""
    st.sidebar.subheader("Geometría")
    fab: str | None = None

    if perfil == "Perfil I":
        fab = st.sidebar.selectbox(
            "Fabricación", ["Rolled", "Built-up"],
            help="Rolled: laminado. Built-up: armado con placas.",
        )
        return {
            "bf": st.sidebar.number_input("Ancho total del patín bf", min_value=0.001, value=200.0),
            "tf": st.sidebar.number_input("Espesor del patín tf", min_value=0.001, value=12.0),
            "h": st.sidebar.number_input("Altura libre del alma h", min_value=0.001, value=450.0),
            "tw": st.sidebar.number_input("Espesor del alma tw", min_value=0.001, value=8.0),
        }, fab

    if perfil == "Canal":
        return {
            "b_ala": st.sidebar.number_input("Ancho saliente del patín b", min_value=0.001, value=70.0),
            "tf": st.sidebar.number_input("Espesor del patín tf", min_value=0.001, value=10.0),
            "h": st.sidebar.number_input("Altura libre del alma h", min_value=0.001, value=250.0),
            "tw": st.sidebar.number_input("Espesor del alma tw", min_value=0.001, value=7.0),
        }, None

    if perfil == "Tee":
        return {
            "b_ala": st.sidebar.number_input("Ancho saliente de medio patín b", min_value=0.001, value=75.0),
            "tf": st.sidebar.number_input("Espesor del patín tf", min_value=0.001, value=12.0),
            "d_vastago": st.sidebar.number_input("Profundidad del vástago d", min_value=0.001, value=150.0),
            "tw": st.sidebar.number_input("Espesor del vástago tw", min_value=0.001, value=8.0),
        }, "Rolled"

    if perfil in {"Ángulo simple", "Ángulo doble con separadores"}:
        return {
            "b1": st.sidebar.number_input("Ancho de la pata 1, b1", min_value=0.001, value=75.0),
            "b2": st.sidebar.number_input("Ancho de la pata 2, b2", min_value=0.001, value=75.0),
            "t": st.sidebar.number_input("Espesor t", min_value=0.001, value=8.0),
        }, None

    if perfil in {"HSS cuadrado", "HSS rectangular"}:
        B = st.sidebar.number_input("Ancho plano B", min_value=0.001, value=180.0)
        if perfil == "HSS cuadrado":
            H = B
            st.sidebar.caption("Para HSS cuadrado se adopta H = B automáticamente.")
        else:
            H = st.sidebar.number_input("Altura plana H", min_value=0.001, value=280.0)
        return {
            "B_plano": B,
            "H_plano": H,
            "t": st.sidebar.number_input("Espesor de diseño t", min_value=0.001, value=8.0),
        }, None

    return {
        "D": st.sidebar.number_input("Diámetro exterior D", min_value=0.001, value=200.0),
        "t": st.sidebar.number_input("Espesor de diseño t", min_value=0.001, value=8.0),
    }, None


st.title("Análisis de perfiles de acero")
st.caption("Verificación de perfiles estándar según el tipo de solicitación")

st.sidebar.header("Configuración general")
perfil = st.sidebar.selectbox(
    "Tipo de perfil",
    ["Perfil I", "Canal", "Tee", "Ángulo simple", "Ángulo doble con separadores", "HSS cuadrado", "HSS rectangular", "HSS circular"],
)
eje = st.sidebar.radio(
    "Eje de análisis",
    ["x-x", "y-y"],
    help="Solo se dibuja el eje seleccionado. La dirección de flexión se representa perpendicular a ese eje.",
)

st.sidebar.subheader("Material")
unidades = st.sidebar.selectbox("Sistema de esfuerzo", ["MPa", "ksi"])
if unidades == "MPa":
    E_predeterminado, Fy_predeterminado = 200_000.0, 345.0
else:
    E_predeterminado, Fy_predeterminado = 29_000.0, 50.0

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

geometria, fabricacion = cargar_geometria(perfil)

tab_axial, tab_flexion, tab_flexocompresion = st.tabs(["Carga axial", "Flexión", "Flexocompresión"])

with tab_axial:
    st.header("Elementos sujetos a carga axial de compresión")
    st.caption("Clasificación de elementos rigidizados y no rigidizados — Tabla B4.1a")
    mostrar_diagrama(perfil, eje, geometria)

    with st.expander("Alcance y convenciones", expanded=False):
        st.markdown(
            """
            - La condición **rigidizado/no rigidizado** se asigna automáticamente.
            - El eje seleccionado no modifica los límites de la Tabla B4.1a, pero se conserva para módulos posteriores.
            - La figura se actualiza automáticamente al cambiar cualquier dimensión geométrica.
            - `E` y `Fy` deben ingresarse en unidades consistentes.
            """
        )

    resultados = None
    error = None
    try:
        if perfil == "Perfil I":
            resultados = evaluar_perfil_i(fabricacion=fabricacion, E=E, Fy=Fy, **geometria)
        elif perfil == "Canal":
            resultados = evaluar_canal(E=E, Fy=Fy, **geometria)
        elif perfil == "Tee":
            resultados = evaluar_tee(E=E, Fy=Fy, **geometria)
        elif perfil in {"Ángulo simple", "Ángulo doble con separadores"}:
            resultados = evaluar_angulo(tipo=perfil, E=E, Fy=Fy, **geometria)
        elif perfil in {"HSS cuadrado", "HSS rectangular"}:
            resultados = evaluar_hss_rectangular(E=E, Fy=Fy, perfil=perfil, **geometria)
        else:
            resultados = evaluar_hss_circular(E=E, Fy=Fy, **geometria)
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
        mensaje = f"Elemento más crítico: **{gobierna.elemento}**, con λ/λr = **{utilizacion:.3f}**."
        if utilizacion <= 1.0:
            st.success(mensaje)
        else:
            st.warning(mensaje)

with tab_flexion:
    st.header("Elementos sujetos a flexión")
    mostrar_diagrama(perfil, eje, geometria)
    st.info("Módulo reservado para la clasificación y resistencia a flexión. El eje seleccionado determinará las propiedades y fórmulas aplicables.")

with tab_flexocompresion:
    st.header("Elementos sujetos a flexocompresión")
    mostrar_diagrama(perfil, eje, geometria)
    st.info("Módulo reservado para verificaciones combinadas de carga axial y momento respecto al eje seleccionado.")
