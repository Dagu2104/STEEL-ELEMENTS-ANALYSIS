"""Aplicación Streamlit para clasificación de perfiles de acero."""

from __future__ import annotations

from html import escape

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


def _flechas_eje(eje: str) -> str:
    """Devuelve ejes locales y la dirección de flexión perpendicular."""
    elementos = [
        '<line x1="65" y1="170" x2="335" y2="170" class="axis"/>',
        '<line x1="200" y1="35" x2="200" y2="305" class="axis"/>',
        '<text x="315" y="161" class="axis-label">x-x</text>',
        '<text x="210" y="52" class="axis-label">y-y</text>',
    ]

    if eje in {"x-x", "Ambos ejes"}:
        elementos.extend(
            [
                '<line x1="355" y1="105" x2="355" y2="235" class="bend"/>',
                '<polygon points="355,92 347,108 363,108" class="bend-fill"/>',
                '<polygon points="355,248 347,232 363,232" class="bend-fill"/>',
                '<text x="365" y="166" class="bend-label">Flexión ⟂ x-x</text>',
            ]
        )

    if eje in {"y-y", "Ambos ejes"}:
        elementos.extend(
            [
                '<line x1="125" y1="325" x2="275" y2="325" class="bend"/>',
                '<polygon points="112,325 128,317 128,333" class="bend-fill"/>',
                '<polygon points="288,325 272,317 272,333" class="bend-fill"/>',
                '<text x="155" y="348" class="bend-label">Flexión ⟂ y-y</text>',
            ]
        )

    return "".join(elementos)


def diagrama_perfil(perfil: str, eje: str) -> str:
    """Genera un SVG esquemático para el perfil estándar seleccionado."""
    titulo = escape(perfil)
    forma = ""
    etiquetas = ""

    if perfil == "Perfil I":
        forma = """
        <rect x="105" y="70" width="190" height="30" class="section"/>
        <rect x="185" y="100" width="30" height="140" class="section"/>
        <rect x="105" y="240" width="190" height="30" class="section"/>
        """
        etiquetas = """
        <text x="112" y="62" class="part-label">Patín superior</text>
        <line x1="165" y1="66" x2="165" y2="84" class="leader"/>
        <text x="225" y="174" class="part-label">Alma</text>
        <line x1="218" y1="170" x2="207" y2="170" class="leader"/>
        <text x="112" y="292" class="part-label">Patín inferior</text>
        <line x1="165" y1="278" x2="165" y2="258" class="leader"/>
        """
    elif perfil == "Canal":
        forma = """
        <rect x="120" y="75" width="145" height="28" class="section"/>
        <rect x="120" y="103" width="28" height="134" class="section"/>
        <rect x="120" y="237" width="145" height="28" class="section"/>
        """
        etiquetas = """
        <text x="270" y="94" class="part-label">Patín</text>
        <line x1="262" y1="98" x2="245" y2="91" class="leader"/>
        <text x="72" y="174" class="part-label">Alma</text>
        <line x1="105" y1="170" x2="126" y2="170" class="leader"/>
        """
    elif perfil == "Tee":
        forma = """
        <rect x="105" y="75" width="190" height="30" class="section"/>
        <rect x="185" y="105" width="30" height="165" class="section"/>
        """
        etiquetas = """
        <text x="112" y="63" class="part-label">Patín</text>
        <line x1="155" y1="67" x2="155" y2="84" class="leader"/>
        <text x="225" y="190" class="part-label">Vástago</text>
        <line x1="218" y1="186" x2="208" y2="186" class="leader"/>
        """
    elif perfil in {"Ángulo simple", "Ángulo doble con separadores"}:
        if perfil == "Ángulo simple":
            forma = """
            <rect x="125" y="85" width="30" height="180" class="section"/>
            <rect x="155" y="235" width="135" height="30" class="section"/>
            """
        else:
            forma = """
            <rect x="95" y="85" width="28" height="180" class="section"/>
            <rect x="123" y="237" width="90" height="28" class="section"/>
            <rect x="277" y="85" width="28" height="180" class="section"/>
            <rect x="187" y="237" width="90" height="28" class="section"/>
            <line x1="200" y1="120" x2="200" y2="220" class="separator"/>
            """
        etiquetas = """
        <text x="58" y="178" class="part-label">Pata vertical</text>
        <text x="205" y="292" class="part-label">Pata horizontal</text>
        """
    elif perfil in {"HSS cuadrado", "HSS rectangular"}:
        if perfil == "HSS cuadrado":
            x, y, w, h = 115, 85, 170, 170
            xi, yi, wi, hi = 145, 115, 110, 110
        else:
            x, y, w, h = 105, 65, 190, 210
            xi, yi, wi, hi = 135, 95, 130, 150
        forma = f"""
        <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" class="section"/>
        <rect x="{xi}" y="{yi}" width="{wi}" height="{hi}" rx="8" class="void"/>
        """
        etiquetas = """
        <text x="113" y="52" class="part-label">Pared horizontal</text>
        <text x="300" y="176" class="part-label">Pared vertical</text>
        """
    else:  # HSS circular
        forma = """
        <circle cx="200" cy="170" r="96" class="section"/>
        <circle cx="200" cy="170" r="68" class="void"/>
        """
        etiquetas = """
        <text x="285" y="102" class="part-label">Pared tubular</text>
        <line x1="278" y1="108" x2="255" y2="125" class="leader"/>
        """

    return f"""
    <div class="profile-card">
      <div class="profile-heading">{titulo} · ejes locales y elementos</div>
      <svg viewBox="0 0 500 370" role="img" aria-label="Diagrama de {titulo}">
        <defs>
          <style>
            .section {{ fill:#dce6f1; stroke:#1f2937; stroke-width:2.5; }}
            .void {{ fill:white; stroke:#1f2937; stroke-width:2; }}
            .axis {{ stroke:#c0392b; stroke-width:2; stroke-dasharray:8 6; }}
            .axis-label {{ font:700 15px sans-serif; fill:#c0392b; }}
            .part-label {{ font:600 14px sans-serif; fill:#273444; }}
            .leader {{ stroke:#52606d; stroke-width:1.4; }}
            .bend {{ stroke:#1565c0; stroke-width:2.5; }}
            .bend-fill {{ fill:#1565c0; }}
            .bend-label {{ font:600 13px sans-serif; fill:#1565c0; }}
            .separator {{ stroke:#59636e; stroke-width:4; stroke-dasharray:5 5; }}
          </style>
        </defs>
        {forma}
        {_flechas_eje(eje)}
        {etiquetas}
      </svg>
      <div class="profile-note">
        El eje seleccionado es <b>{escape(eje)}</b>. La dirección esquemática de flexión se muestra perpendicular al eje de giro.
      </div>
    </div>
    """


def mostrar_diagrama(perfil: str, eje: str) -> None:
    """Renderiza el SVG como HTML real, no como texto Markdown."""
    contenido = f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <style>
        html, body {{
            margin: 0;
            padding: 0;
            background: transparent;
            color: inherit;
            font-family: Arial, sans-serif;
        }}
        .profile-card {{
            box-sizing: border-box;
            border: 1px solid rgba(128,128,128,.35);
            border-radius: 14px;
            padding: .8rem 1rem .9rem;
            background: rgba(128,128,128,.035);
            width: 100%;
        }}
        .profile-heading {{
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: .25rem;
        }}
        .profile-card svg {{
            display: block;
            width: 100%;
            max-width: 720px;
            height: 390px;
            margin: auto;
        }}
        .profile-note {{
            text-align: center;
            font-size: .92rem;
            opacity: .85;
            margin-top: .2rem;
        }}
      </style>
    </head>
    <body>
      {diagrama_perfil(perfil, eje)}
    </body>
    </html>
    """
    components.html(contenido, height=485, scrolling=False)


st.title("Análisis de perfiles de acero")
st.caption("Verificación de perfiles estándar según el tipo de solicitación")

# Configuración común: se mantiene al cambiar de pestaña.
st.sidebar.header("Configuración general")
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
    help="Se usa en los esquemas y se conservará para flexión, pandeo y flexocompresión.",
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

tab_axial, tab_flexion, tab_flexocompresion = st.tabs(
    ["Carga axial", "Flexión", "Flexocompresión"]
)

with tab_axial:
    st.header("Elementos sujetos a carga axial de compresión")
    st.caption("Clasificación de elementos rigidizados y no rigidizados — Tabla B4.1a")
    mostrar_diagrama(perfil, eje)

    with st.expander("Alcance y convenciones", expanded=False):
        st.markdown(
            """
            - La aplicación trabaja únicamente con perfiles estándar incluidos en el menú.
            - La condición **rigidizado/no rigidizado** se asigna automáticamente.
            - El eje seleccionado se muestra y se guarda, pero no modifica los límites de la Tabla B4.1a.
            - `E` y `Fy` deben ingresarse en unidades consistentes.
            - Verifique las definiciones geométricas con la edición de AISC aplicable al proyecto.
            """
        )

    st.info(
        f"**Perfil:** {perfil}  |  **Eje seleccionado:** {eje}. "
        "Para esta tabla de compresión uniforme, el eje no altera la verificación."
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
                key="axial_fab_i",
            )
            c1, c2 = st.columns(2)
            with c1:
                bf = st.number_input("Ancho total del patín bf", min_value=0.001, value=200.0)
                tf = st.number_input("Espesor del patín tf", min_value=0.001, value=12.0)
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
                b_ala = st.number_input("Ancho saliente del patín b", min_value=0.001, value=70.0)
                tf = st.number_input("Espesor del patín tf", min_value=0.001, value=10.0)
            with c2:
                h = st.number_input("Altura libre del alma h", min_value=0.001, value=250.0)
                tw = st.number_input("Espesor del alma tw", min_value=0.001, value=7.0)
            resultados = evaluar_canal(b_ala=b_ala, tf=tf, h=h, tw=tw, E=E, Fy=Fy)

        elif perfil == "Tee":
            st.text_input("Fabricación", value="Rolled", disabled=True)
            c1, c2 = st.columns(2)
            with c1:
                b_ala = st.number_input("Ancho saliente de medio patín b", min_value=0.001, value=75.0)
                tf = st.number_input("Espesor del patín tf", min_value=0.001, value=12.0)
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
        mensaje_critico = (
            f"Elemento más crítico: **{gobierna.elemento}**, "
            f"con λ/λr = **{utilizacion:.3f}**."
        )
        if utilizacion <= 1.0:
            st.success(mensaje_critico)
        else:
            st.warning(mensaje_critico)

    st.divider()
    st.caption(
        "Herramienta de apoyo. Antes del diseño definitivo, confirme la edición normativa, "
        "las definiciones de ancho efectivo/plano y los espesores de diseño aplicables."
    )

with tab_flexion:
    st.header("Elementos sujetos a flexión")
    mostrar_diagrama(perfil, eje)
    st.info(
        "Módulo reservado para la clasificación y resistencia a flexión. "
        "El eje seleccionado determinará las propiedades y fórmulas que se usarán."
    )
    if eje == "x-x":
        st.write("Se analizará la flexión alrededor de **x-x**, con curvatura en el plano perpendicular a ese eje.")
    elif eje == "y-y":
        st.write("Se analizará la flexión alrededor de **y-y**, con curvatura en el plano perpendicular a ese eje.")
    else:
        st.write("Se preparará la comprobación independiente alrededor de **x-x** y **y-y**.")

with tab_flexocompresion:
    st.header("Elementos sujetos a flexocompresión")
    mostrar_diagrama(perfil, eje)
    st.info(
        "Módulo reservado para verificaciones combinadas de carga axial y momentos "
        "alrededor de uno o ambos ejes."
    )
