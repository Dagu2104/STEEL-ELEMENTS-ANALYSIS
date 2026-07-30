"""Aplicación Streamlit para clasificación local de perfiles estándar de acero."""

from __future__ import annotations

import html
import hashlib
import json
from io import BytesIO
from math import ceil

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from capitulo_e import (
    area_efectiva_desde_elementos,
    area_efectiva_tubo_circular,
    ancho_efectivo_e7,
    esfuerzo_nominal_compresion,
    esbeltez_modificada_angulo,
    esbeltez_modificada_builtup,
    fe_flexotorsional_asimetrico,
    fe_flexotorsional_monosimetrico,
    fe_torsional_doble_simetria,
    longitud_efectiva,
    pandeo_flexional,
    pandeo_torsional_o_flexotorsional,
    radio_polar_centro_cortante,
    ruta_capitulo_e,
)


from propiedades import calcular_propiedades, PropiedadesSeccion
from unidades import a_interno, desde_interno, unidad_propiedad
from flexion_b4 import evaluar_flexion_b4, clasificacion_global
from capitulo_f import (
    calcular_cb,
    calcular_f2,
    calcular_f3,
    calcular_f4,
    calcular_f5,
    calcular_f6,
    calcular_f7,
    calcular_f8,
    calcular_f9,
    calcular_f10,
    EstadoLimiteMomento,
    agregar_estados,
    ruta_capitulo_f,
    verificar_agujeros_ala_tension,
    verificaciones_proporcion_i_f13,
    opciones_pernos_comerciales,
    dimensiones_agujero_j33,
    deduccion_ancho_seccion_neta,
)


from capitulo_h import (
    OMEGA_T,
    PHI_T,
    calcular_h11,
    calcular_h36,
    calcular_torsion_hss_circular,
    calcular_torsion_hss_rectangular,
    ruta_capitulo_h,
    verificar_h33_manual,
)

from capitulo_g import (
    ResultadoCortante,
    calcular_g2_sin_rigidizadores,
    calcular_g2_panel,
    calcular_separacion_maxima_g2,
    calcular_g3,
    calcular_g4,
    calcular_g5,
    calcular_g6,
    capacidad_disponible,
    rigidizadores_requeridos_g24,
    ruta_capitulo_g,
    verificar_rigidizador_g24,
)

from funciones import (
    evaluar_angulo,
    evaluar_canal,
    evaluar_perfil_i,
    evaluar_perfil_i_asimetrico,
    evaluar_tee,
    evaluar_tubo_circular,
    evaluar_tubo_rectangular,
)

st.set_page_config(page_title="Diseño de perfiles de acero", page_icon="🏗️", layout="wide")


# -----------------------------------------------------------------------------
# Entradas y salidas con conversión automática de unidades
# -----------------------------------------------------------------------------
def entrada_magnitud(label: str, *, key: str, magnitud: str, unidad: str,
                      valor_inicial_interno: float, min_interno: float | None = None,
                      max_interno: float | None = None, potencia: int = 1,
                      help: str | None = None) -> float:
    """Muestra una entrada en la unidad elegida y devuelve el valor interno.

    El valor interno se conserva al cambiar de unidad; por ejemplo, 3000 mm se
    transforma automáticamente en 3 m y no en 3000 m.
    """
    base_key = f"_base_{key}"
    unit_key = f"_unit_{key}"
    widget_key = f"_widget_{key}"
    if base_key not in st.session_state:
        st.session_state[base_key] = float(valor_inicial_interno)

    unidad_actual = (unidad, potencia)

    # Streamlit elimina del estado las claves de widgets que dejan de renderizarse.
    # Esto ocurre, por ejemplo, al cambiar de un tubo a un perfil I y regresar.
    # Las claves auxiliares _base_* y _unit_* pueden permanecer, por lo que no es
    # suficiente comprobar únicamente si cambió la unidad: también debemos
    # reconstruir el valor visible cuando la clave del widget ya no existe.
    if (
        widget_key not in st.session_state
        or st.session_state.get(unit_key) != unidad_actual
    ):
        st.session_state[widget_key] = desde_interno(
            st.session_state[base_key], magnitud, unidad, potencia
        )
        st.session_state[unit_key] = unidad_actual

    # Trabaja con un valor local seguro antes de aplicar límites dinámicos.
    # Así nunca se intenta leer una clave ausente del session_state.
    valor_widget = float(
        st.session_state.get(
            widget_key,
            desde_interno(st.session_state[base_key], magnitud, unidad, potencia),
        )
    )

    if min_interno is not None:
        minimo_visible = desde_interno(min_interno, magnitud, unidad, potencia)
        valor_widget = max(valor_widget, minimo_visible)
    if max_interno is not None:
        maximo_visible = desde_interno(max_interno, magnitud, unidad, potencia)
        valor_widget = min(valor_widget, maximo_visible)

    st.session_state[widget_key] = valor_widget
    kwargs = {"key": widget_key, "help": help}
    if min_interno is not None:
        kwargs["min_value"] = desde_interno(min_interno, magnitud, unidad, potencia)
    if max_interno is not None:
        kwargs["max_value"] = desde_interno(max_interno, magnitud, unidad, potencia)
    valor_visible = st.number_input(f"{label} [{unidad_propiedad(unidad, potencia) if magnitud == 'longitud' else unidad}]", **kwargs)
    valor_base = a_interno(valor_visible, magnitud, unidad, potencia)
    st.session_state[base_key] = valor_base
    return valor_base


def valor_mostrado(valor_interno: float, magnitud: str, unidad: str, potencia: int = 1) -> float:
    return desde_interno(valor_interno, magnitud, unidad, potencia)


def formato(valor_interno: float, magnitud: str, unidad: str, potencia: int = 1, decimales: int = 3) -> str:
    valor = valor_mostrado(valor_interno, magnitud, unidad, potencia)
    etiqueta = unidad_propiedad(unidad, potencia) if magnitud == "longitud" else unidad
    return f"{valor:,.{decimales}f} {etiqueta}"


def _firma_modelo(
    *, perfil: str, E: float, Fy: float, geo: dict,
    fabricacion: str | None, cubreplacas: dict,
) -> str:
    """Firma estable para invalidar capacidades almacenadas cuando cambia el perfil."""
    datos = {
        "perfil": perfil,
        "E": round(float(E), 10),
        "Fy": round(float(Fy), 10),
        "fabricacion": fabricacion,
        "geo": geo,
        "cubreplacas": cubreplacas,
    }
    texto = json.dumps(datos, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _guardar_capacidad(clave: str, datos: dict) -> None:
    st.session_state[clave] = datos


def _leer_capacidad(clave: str, firma: str) -> dict | None:
    datos = st.session_state.get(clave)
    if not isinstance(datos, dict) or datos.get("firma") != firma:
        return None
    return datos


# -----------------------------------------------------------------------------
# Dibujo SVG dinámico
# -----------------------------------------------------------------------------
def escala(valor: float, maximo: float, salida_max: float, salida_min: float = 3.0) -> float:
    if maximo <= 0:
        return salida_min
    return max(salida_min, valor / maximo * salida_max)


def dibujo_perfil(perfil: str, eje: str, geo: dict, fabricacion: str | None = None,
                  cubreplacas: dict | None = None) -> str:
    W, H = 760, 390
    cx, cy = 360, 195
    stroke = "#263445"
    fill = "#dce6f2"
    cp_fill = "#f5d59a"
    axis = "#d13a2f"
    arrow = "#1565c0"
    shapes: list[str] = []
    labels: list[str] = []

    def rect(x, y, w, h, rx=0, cls="section", fill_override=None):
        f = fill_override or fill
        shapes.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{f}" stroke="{stroke}" stroke-width="3"/>')

    if perfil in {"Perfil I", "Perfil I asimétrico"}:
        if perfil == "Perfil I asimétrico":
            bf_sup, tf_sup = geo["bf_superior"], geo["tf_superior"]
            bf_inf, tf_inf = geo["bf_inferior"], geo["tf_inferior"]
        else:
            bf_sup = bf_inf = geo["bf"]
            tf_sup = tf_inf = geo["tf"]
        h, tw = geo["h"], geo["tw"]
        maxdim = max(bf_sup, bf_inf, h + tf_sup + tf_inf)
        bw_sup = escala(bf_sup, maxdim, 240, 80)
        bw_inf = escala(bf_inf, maxdim, 240, 80)
        th_sup = escala(tf_sup, maxdim, 240, 8)
        th_inf = escala(tf_inf, maxdim, 240, 8)
        wh = escala(h, maxdim, 240, 90)
        ww = escala(tw, maxdim, 240, 6)
        x_sup, x_inf = cx-bw_sup/2, cx-bw_inf/2
        y = cy-(wh+th_sup+th_inf)/2
        rect(x_sup, y, bw_sup, th_sup)
        rect(cx-ww/2, y+th_sup, ww, wh)
        rect(x_inf, y+th_sup+wh, bw_inf, th_inf)
        labels += [
            f'<text x="{x_sup+bw_sup+12:.1f}" y="{y+th_sup/2+5:.1f}" class="label">Patín superior</text>',
            f'<text x="{cx+ww/2+12:.1f}" y="{cy+5:.1f}" class="label">Alma</text>',
            f'<text x="{x_inf+bw_inf+12:.1f}" y="{y+th_sup+wh+th_inf/2+5:.1f}" class="label">Patín inferior</text>',
        ]
        cp = cubreplacas or {}
        if cp.get("superior"):
            bcp, tcp = cp["superior"].get("B", cp["superior"]["b"]), cp["superior"]["t"]
            cpw = escala(bcp, max(maxdim, bcp), 240, 45)
            cpt = escala(tcp, max(maxdim, bcp), 240, 5)
            rect(cx-cpw/2, y-cpt-4, cpw, cpt, fill_override=cp_fill)
            labels.append(f'<text x="{cx-cpw/2:.1f}" y="{y-cpt-10:.1f}" class="cp-label">Cubreplaca superior</text>')
        if cp.get("inferior"):
            bcp, tcp = cp["inferior"].get("B", cp["inferior"]["b"]), cp["inferior"]["t"]
            cpw = escala(bcp, max(maxdim, bcp), 240, 45)
            cpt = escala(tcp, max(maxdim, bcp), 240, 5)
            y_inf_cp = y + th_sup + wh + th_inf + 4
            rect(cx-cpw/2, y_inf_cp, cpw, cpt, fill_override=cp_fill)
            labels.append(f'<text x="{cx-cpw/2:.1f}" y="{y_inf_cp+cpt+20:.1f}" class="cp-label">Cubreplaca inferior</text>')

    elif perfil == "Canal":
        b, tf, h, tw = geo["b"], geo["tf"], geo["h"], geo["tw"]
        maxdim = max(b, h + 2 * tf)
        bw, th, wh, ww = escala(b, maxdim, 220, 70), escala(tf, maxdim, 220, 8), escala(h, maxdim, 220, 90), escala(tw, maxdim, 220, 6)
        x, y = cx - bw/2, cy-(wh+2*th)/2
        rect(x, y, bw, th); rect(x, y+th, ww, wh); rect(x, y+th+wh, bw, th)
        labels += [f'<text x="{x+bw+12:.1f}" y="{y+th/2+5:.1f}" class="label">Patín</text>', f'<text x="{x+ww+12:.1f}" y="{cy+5:.1f}" class="label">Alma</text>']

    elif perfil == "Tee":
        b, tf, d, tw = geo["b"], geo["tf"], geo["d"], geo["tw"]
        maxdim = max(2*b, d+tf)
        bw, th, wh, ww = escala(2*b, maxdim, 230, 90), escala(tf, maxdim, 230, 8), escala(d, maxdim, 230, 80), escala(tw, maxdim, 230, 6)
        x, y = cx-bw/2, cy-(wh+th)/2
        rect(x, y, bw, th); rect(cx-ww/2, y+th, ww, wh)
        labels += [f'<text x="{x+bw+12:.1f}" y="{y+th/2+5:.1f}" class="label">Patín</text>', f'<text x="{cx+ww/2+12:.1f}" y="{y+th+wh/2:.1f}" class="label">Vástago</text>']

    elif perfil in {"Ángulo simple", "Ángulo doble con separadores"}:
        b1, b2, t = geo["b1"], geo["b2"], geo["t"]
        maxdim = max(b1, b2)
        vh, hw, tt = escala(b1, maxdim, 210, 90), escala(b2, maxdim, 210, 90), escala(t, maxdim, 210, 8)
        x, y = cx-hw/2, cy-vh/2
        rect(x, y, tt, vh); rect(x, y+vh-tt, hw, tt)
        if perfil == "Ángulo doble con separadores":
            sep = geo.get("separacion", 20.0)
            gap = max(18.0, escala(sep, maxdim, 210, 18.0))
            rect(cx+gap/2, y, tt, vh); rect(cx+gap/2-hw+tt, y+vh-tt, hw, tt)
        labels.append(f'<text x="{x+hw+16:.1f}" y="{cy+5:.1f}" class="label">Patas</text>')

    elif perfil in {"Tubo cuadrado", "Tubo rectangular"}:
        B, HH, t = geo["B"], geo["H"], geo["t"]
        maxdim = max(B, HH)
        bw, bh, tt = escala(B, maxdim, 230, 110), escala(HH, maxdim, 230, 110), escala(t, maxdim, 230, 7)
        x, y = cx-bw/2, cy-bh/2
        rounded = 16 if fabricacion == "Rolled" else 0
        shapes.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="{rounded}" fill="{fill}" stroke="{stroke}" stroke-width="3"/>')
        shapes.append(f'<rect x="{x+tt:.1f}" y="{y+tt:.1f}" width="{max(2,bw-2*tt):.1f}" height="{max(2,bh-2*tt):.1f}" rx="{max(0,rounded-tt/2):.1f}" fill="white" stroke="{stroke}" stroke-width="2"/>')
        if fabricacion == "Built-up":
            for sx, sy in [(x,y),(x+bw,y),(x,y+bh),(x+bw,y+bh)]:
                shapes.append(f'<line x1="{sx-5:.1f}" y1="{sy-5:.1f}" x2="{sx+5:.1f}" y2="{sy+5:.1f}" stroke="#b36b00" stroke-width="3"/>')
        labels += [f'<text x="{x+bw+14:.1f}" y="{cy+5:.1f}" class="label">Pared vertical</text>', f'<text x="{cx-55:.1f}" y="{y-14:.1f}" class="label">Pared horizontal</text>']

    elif perfil == "Tubo circular":
        D, t = geo["D"], geo["t"]
        r = 105
        tt = min(28, max(7, 2*r*t/D))
        shapes.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="3"/>')
        shapes.append(f'<circle cx="{cx}" cy="{cy}" r="{r-tt}" fill="white" stroke="{stroke}" stroke-width="2"/>')
        labels.append(f'<text x="{cx+r+16}" y="{cy+5}" class="label">Pared circular</text>')

    # Solo se dibuja el eje seleccionado.
    if eje == "x-x":
        axis_markup = f'<line x1="{cx-190}" y1="{cy}" x2="{cx+190}" y2="{cy}" class="axis"/><text x="{cx+155}" y="{cy-10}" class="axis-label">x-x</text>'
        flex_markup = f'<line x1="{cx+285}" y1="{cy-85}" x2="{cx+285}" y2="{cy+85}" class="flex" marker-start="url(#arrow)" marker-end="url(#arrow)"/><text x="{cx+300}" y="{cy+5}" class="flex-label">Flexión ⟂ x-x</text>'
    else:
        axis_markup = f'<line x1="{cx}" y1="{cy-155}" x2="{cx}" y2="{cy+155}" class="axis"/><text x="{cx+10}" y="{cy-135}" class="axis-label">y-y</text>'
        flex_markup = f'<line x1="{cx-100}" y1="{cy+125}" x2="{cx+100}" y2="{cy+125}" class="flex" marker-start="url(#arrow)" marker-end="url(#arrow)"/><text x="{cx-58}" y="{cy+155}" class="flex-label">Flexión ⟂ y-y</text>'

    title = html.escape(f"{perfil} · {fabricacion or ''}")
    return f"""
    <html><body style="margin:0;background:white;font-family:Arial,sans-serif;">
    <div style="border:1px solid #d8d8d8;border-radius:14px;padding:12px 16px;">
      <div style="font-weight:700;font-size:17px;margin-bottom:4px;">{title}</div>
      <svg viewBox="0 0 {W} {H}" width="100%" height="390" role="img">
        <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="{arrow}"/></marker></defs>
        <style>.label{{font-size:16px;fill:#17202a;font-weight:600}} .cp-label{{font-size:15px;fill:#8a5300;font-weight:700}} .axis{{stroke:{axis};stroke-width:2.5;stroke-dasharray:9 7}} .axis-label{{font-size:17px;fill:{axis};font-weight:700}} .flex{{stroke:{arrow};stroke-width:3}} .flex-label{{font-size:16px;fill:{arrow};font-weight:700}}</style>
        {''.join(shapes)}{axis_markup}{flex_markup}{''.join(labels)}
      </svg>
      <div style="text-align:center;font-size:15px;color:#333;">Solo se muestra el eje seleccionado. La dirección esquemática de flexión es perpendicular a dicho eje.</div>
    </div></body></html>
    """


def mostrar_propiedades(prop: PropiedadesSeccion, unidad_longitud: str) -> None:
    """Presenta propiedades internas en la unidad de longitud seleccionada."""
    u1 = unidad_propiedad(unidad_longitud, 1)
    u2 = unidad_propiedad(unidad_longitud, 2)
    u3 = unidad_propiedad(unidad_longitud, 3)
    u4 = unidad_propiedad(unidad_longitud, 4)
    u6 = unidad_propiedad(unidad_longitud, 6)
    cv = lambda v, p=1: valor_mostrado(v, "longitud", unidad_longitud, p)
    with st.expander("Propiedades geométricas calculadas", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Área Ag", f"{cv(prop.Ag,2):,.3f} {u2}")
        c2.metric("Centroide x̄", f"{cv(prop.x_bar):,.3f} {u1}")
        c3.metric("Centroide ȳ", f"{cv(prop.y_bar):,.3f} {u1}")
        c4.metric("J", f"{cv(prop.J,4):,.3f} {u4}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ix", f"{cv(prop.Ix,4):,.3f} {u4}")
        c2.metric("Iy", f"{cv(prop.Iy,4):,.3f} {u4}")
        c3.metric("Ixy", f"{cv(prop.Ixy,4):,.3f} {u4}")
        c4.metric("Cw", "No calculado" if prop.Cw is None else f"{cv(prop.Cw,6):,.3f} {u6}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("rx", f"{cv(prop.rx):,.3f} {u1}")
        c2.metric("ry", f"{cv(prop.ry):,.3f} {u1}")
        c3.metric("r máximo", f"{cv(prop.r1):,.3f} {u1}")
        c4.metric("r mínimo", f"{cv(prop.r2):,.3f} {u1}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sx superior", f"{cv(prop.Sx_sup,3):,.3f} {u3}")
        c2.metric("Sx inferior", f"{cv(prop.Sx_inf,3):,.3f} {u3}")
        c3.metric("Sy derecha", f"{cv(prop.Sy_der,3):,.3f} {u3}")
        c4.metric("Sy izquierda", f"{cv(prop.Sy_izq,3):,.3f} {u3}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Zx", f"{cv(prop.Zx,3):,.3f} {u3}")
        c2.metric("Zy", f"{cv(prop.Zy,3):,.3f} {u3}")
        c3.metric("I principal mayor", f"{cv(prop.I1,4):,.3f} {u4}")
        c4.metric("I principal menor", f"{cv(prop.I2,4):,.3f} {u4}")

        st.write(f"**Ángulo del eje principal:** {prop.theta_p_deg:.3f}°")
        if prop.observacion:
            st.caption(prop.observacion)


def mostrar_resultados(resultados):
    st.subheader("Resultados — Tabla B4.1a")
    for r in resultados:
        estado = "✅" if r.clasificacion == "NO ESBELTO" else "⚠️"
        with st.container(border=True):
            st.markdown(f"### {estado} {r.elemento}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("λ real", f"{r.lambda_real:.3f}")
            c2.metric("λr", f"{r.lambda_r:.3f}")
            c3.metric("Condición", r.condicion_borde)
            c4.metric("Clasificación", r.clasificacion)
            st.write(f"**Caso:** {r.caso_tabla}  ·  **Relación:** `{r.relacion}`  ·  **Límite:** `{r.formula}`")
            if r.observacion:
                st.caption(r.observacion)
    gobierna = max(resultados, key=lambda x: x.lambda_real / x.lambda_r)
    u = gobierna.lambda_real / gobierna.lambda_r
    mensaje = f"Elemento más crítico: **{gobierna.elemento}**, con λ/λr = **{u:.3f}**."
    if u <= 1.0:
        st.success(mensaje)
    else:
        st.warning(mensaje)



def mostrar_resultados_flexion(resultados):
    """Presenta la clasificación local de la Tabla B4.1b."""
    st.subheader("Clasificación local — Tabla B4.1b")
    filas = []
    for r in resultados:
        filas.append({
            "Elemento": r.elemento,
            "Caso": r.caso_tabla,
            "Relación": r.relacion,
            "λ": round(r.lambda_real, 4),
            "λp": round(r.lambda_p, 4),
            "λr": round(r.lambda_r, 4),
            "Clasificación": r.clasificacion,
        })
    st.dataframe(filas, use_container_width=True, hide_index=True)

    for r in resultados:
        icono = {"COMPACTO": "✅", "NO COMPACTO": "🟡", "ESBELTO": "⚠️"}[r.clasificacion]
        with st.expander(f"{icono} {r.elemento} — {r.clasificacion}", expanded=False):
            c1, c2, c3 = st.columns(3)
            c1.metric("λ", f"{r.lambda_real:.4f}")
            c2.metric("λp", f"{r.lambda_p:.4f}")
            c3.metric("λr", f"{r.lambda_r:.4f}")
            st.write(
                f"**{r.caso_tabla}** · Relación: `{r.relacion}` · "
                f"λp: `{r.formula_lambda_p}` · λr: `{r.formula_lambda_r}`"
            )
            if r.observacion:
                st.caption(r.observacion)

    global_clas, gobierna = clasificacion_global(resultados)
    mensaje = (
        f"Clasificación global: **{global_clas}**. "
        f"Gobierna: **{gobierna.elemento}** ({gobierna.caso_tabla})."
    )
    if global_clas == "COMPACTO":
        st.success(mensaje)
    elif global_clas == "NO COMPACTO":
        st.warning(mensaje)
    else:
        st.error(mensaje)
    st.caption("La clasificación B4.1b se utiliza a continuación para seleccionar automáticamente la sección aplicable del Capítulo F.")



def determinar_simetria_perfil(perfil: str, geo: dict, cubreplacas: dict) -> str:
    """Determina la simetría de la sección sin pedirla al usuario."""
    if perfil in {"Perfil I", "Perfil I asimétrico"}:
        sup = cubreplacas.get("superior")
        inf = cubreplacas.get("inferior")
        geometria_simetrica = perfil == "Perfil I" or (
            abs(geo["bf_superior"] - geo["bf_inferior"]) < 1e-9
            and abs(geo["tf_superior"] - geo["tf_inferior"]) < 1e-9
        )
        if geometria_simetrica and not sup and not inf:
            return "Doble simetría"
        if (
            geometria_simetrica and sup and inf
            and abs(float(sup["B"]) - float(inf["B"])) < 1e-9
            and abs(float(sup["t"]) - float(inf["t"])) < 1e-9
        ):
            return "Doble simetría"
        return "Monosimétrica"
    if perfil in {"Canal", "Tee", "Ángulo doble con separadores"}:
        return "Monosimétrica"
    if perfil in {"Tubo cuadrado", "Tubo rectangular", "Tubo circular"}:
        return "Doble simetría"
    return "Asimétrica"


def _entrada_cb(unidad_momento: str, prefijo: str) -> float:
    """Permite ingresar Cb o calcularlo con la ecuación F1-1."""
    ayuda_cb = (
        "Cb es el factor de modificación por gradiente de momentos para pandeo "
        "lateral-torsional. Puede ingresarse directamente o calcularse mediante "
        "F1-1 usando Mmax, MA, MB y MC del mismo segmento no arriostrado."
    )
    modo = st.radio(
        "Obtención de Cb",
        ["Ingresar Cb", "Calcular con Mmax, MA, MB y MC"],
        horizontal=True,
        key=f"{prefijo}_modo_cb",
        help=ayuda_cb,
    )
    if modo == "Ingresar Cb":
        return st.number_input(
            "Factor Cb", min_value=0.001, value=1.0, key=f"{prefijo}_Cb",
            help=(
                "Factor de modificación por gradiente de momentos del segmento no "
                "arriostrado. Para momento uniforme, Cb = 1.0. Ingrese un valor "
                "obtenido de un análisis compatible con AISC 360, Sección F1."
            ),
        )

    st.caption(
        "F1-1 usa los valores absolutos de los momentos en el mismo tramo no "
        "arriostrado. MA, MB y MC corresponden a Lb/4, Lb/2 y 3Lb/4."
    )
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        Mmax = entrada_magnitud(
            "Mmax", key=f"{prefijo}_Mmax", magnitud="momento", unidad=unidad_momento,
            valor_inicial_interno=100_000_000.0, min_interno=0.0,
            help=(
                "Valor absoluto del momento máximo dentro del segmento lateralmente "
                "no arriostrado de longitud Lb. Use la misma combinación y diagrama "
                "de momentos empleados para MA, MB y MC."
            ),
        )
    with c2:
        MA = entrada_magnitud(
            "MA", key=f"{prefijo}_MA", magnitud="momento", unidad=unidad_momento,
            valor_inicial_interno=100_000_000.0, min_interno=0.0,
            help=(
                "Valor absoluto del momento en el punto situado a un cuarto del "
                "segmento no arriostrado: x = Lb/4, medido desde uno de sus extremos."
            ),
        )
    with c3:
        MB = entrada_magnitud(
            "MB", key=f"{prefijo}_MB", magnitud="momento", unidad=unidad_momento,
            valor_inicial_interno=100_000_000.0, min_interno=0.0,
            help=(
                "Valor absoluto del momento en el centro del segmento no "
                "arriostrado: x = Lb/2."
            ),
        )
    with c4:
        MC = entrada_magnitud(
            "MC", key=f"{prefijo}_MC", magnitud="momento", unidad=unidad_momento,
            valor_inicial_interno=100_000_000.0, min_interno=0.0,
            help=(
                "Valor absoluto del momento en el punto situado a tres cuartos del "
                "segmento no arriostrado: x = 3Lb/4, medido desde el mismo extremo "
                "utilizado para MA."
            ),
        )
    cb = calcular_cb(Mmax, MA, MB, MC)
    st.metric(
        "Cb calculado — F1-1", f"{cb:.4f}",
        help="Resultado de Cb calculado con la ecuación F1-1 de AISC 360.",
    )
    return cb


def mostrar_ruta_y_diseno_capitulo_f(
    perfil: str, resultados_b4, E: float, Fy: float, geo: dict, fabricacion: str | None,
    cubreplacas: dict, prop, eje: str, lado_compresion: str,
    unidad_esfuerzo: str, unidad_longitud: str, unidad_fuerza: str, unidad_momento: str,
) -> None:
    """Selecciona F2–F12 y calcula Mn para las secciones soportadas."""
    simetria = determinar_simetria_perfil(perfil, geo, cubreplacas)
    ruta = ruta_capitulo_f(
        perfil=perfil, eje=eje, simetria=simetria, resultados_b4=resultados_b4,
    )
    uL, uF, uP, uM = unidad_longitud, unidad_esfuerzo, unidad_fuerza, unidad_momento
    cvM = lambda v: valor_mostrado(v, "momento", uM)
    cvF = lambda v: valor_mostrado(v, "esfuerzo", uF)

    with st.expander("Ruta automática del Capítulo F", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Sección aplicable", ruta.seccion)
        c2.metric("Clasificación del patín", ruta.clasificacion_patin)
        c3.metric("Clasificación del alma", ruta.clasificacion_alma)
        c1, c2, c3 = st.columns(3)
        c1.metric("Eje de flexión", ruta.eje)
        c2.metric("Simetría", ruta.simetria)
        c3.metric("Estados límite", " · ".join(ruta.estados_limite) if ruta.estados_limite else "—")
        st.caption(ruta.explicacion)
        st.code(
            f"{perfil} → {ruta.simetria} → eje {eje} → "
            f"patín {ruta.clasificacion_patin} / alma {ruta.clasificacion_alma} → {ruta.seccion}"
        )
        for advertencia in ruta.advertencias:
            st.warning(advertencia)

    if not ruta.aplicable:
        st.error("La geometría y el eje seleccionados no tienen una ruta directa de cálculo implementable con la Tabla F1.1.")
        return

    with st.expander(f"{ruta.seccion} — Resistencia nominal a flexión", expanded=True):
        st.info(
            f"Los cálculos internos usan N·mm. Los resultados se muestran en **{uM}**. "
            "Se reportan Mn, ϕbMn con ϕb=0.90 y Mn/Ωb con Ωb=1.67."
        )
        try:
            resultado_f = None
            if ruta.seccion in {"F2", "F3", "F4", "F5"}:
                Lb = entrada_magnitud(
                    "Longitud lateral no arriostrada Lb", key=f"{ruta.seccion}_Lb",
                    magnitud="longitud", unidad=uL, valor_inicial_interno=3000.0, min_interno=0.001,
                    help=(
                        "Distancia entre puntos que impiden el desplazamiento lateral "
                        "del ala comprimida o que evitan el giro de la sección. Debe "
                        "corresponder al mismo segmento usado para obtener Cb."
                    ),
                )
                Cb = _entrada_cb(uM, ruta.seccion)
                Cw = None
                if ruta.seccion in {"F2", "F3"} and (prop.Cw is None or prop.Cw <= 0):
                    Cw = entrada_magnitud(
                        "Constante de alabeo Cw", key=f"{ruta.seccion}_Cw",
                        magnitud="longitud", unidad=uL, potencia=6,
                        valor_inicial_interno=1_000_000_000.0, min_interno=0.001,
                        help="F2/F3 requieren Cw para calcular rts y Lr.",
                    )
                if ruta.seccion == "F2":
                    resultado_f = calcular_f2(
                        perfil=perfil, E=E, Fy=Fy, prop=prop, geo=geo, Lb=Lb, Cb=Cb,
                        Cw=Cw, cubreplacas=cubreplacas,
                    )
                elif ruta.seccion == "F3":
                    resultado_f = calcular_f3(
                        E=E, Fy=Fy, prop=prop, geo=geo, Lb=Lb, Cb=Cb,
                        resultados_b4=resultados_b4, Cw=Cw, cubreplacas=cubreplacas,
                    )
                elif ruta.seccion == "F4":
                    resultado_f = calcular_f4(
                        E=E, Fy=Fy, prop=prop, geo=geo, lado_compresion=lado_compresion,
                        Lb=Lb, Cb=Cb, resultados_b4=resultados_b4, cubreplacas=cubreplacas,
                    )
                else:
                    resultado_f = calcular_f5(
                        E=E, Fy=Fy, prop=prop, geo=geo, lado_compresion=lado_compresion,
                        Lb=Lb, Cb=Cb, resultados_b4=resultados_b4, cubreplacas=cubreplacas,
                    )

            elif ruta.seccion == "F6":
                resultado_f = calcular_f6(
                    E=E, Fy=Fy, prop=prop, lado_compresion=lado_compresion,
                    resultados_b4=resultados_b4,
                )

            elif ruta.seccion == "F7":
                es_cuadrada = abs(geo["B"] - geo["H"]) <= 1e-9
                eje_mayor = "x-x" if prop.Ix >= prop.Iy else "y-y"
                aplica_ltb = (not es_cuadrada) and eje == eje_mayor
                Lb = None
                Cb = 1.0
                if aplica_ltb:
                    st.caption("F7 verifica LTB porque la sección es rectangular y se flexiona sobre el eje mayor.")
                    Lb = entrada_magnitud(
                        "Longitud lateral no arriostrada Lb", key="F7_Lb",
                        magnitud="longitud", unidad=uL, valor_inicial_interno=3000.0, min_interno=0.001,
                        help=(
                            "Distancia entre puntos que impiden el desplazamiento lateral "
                            "de la región comprimida o que evitan el giro de la sección. "
                            "Debe corresponder al mismo segmento usado para obtener Cb."
                        ),
                    )
                    Cb = _entrada_cb(uM, "F7")
                else:
                    st.caption("Según la nota de F7, LTB no aplica a secciones cuadradas ni a flexión sobre el eje menor.")
                resultado_f = calcular_f7(
                    E=E, Fy=Fy, prop=prop, geo=geo, fabricacion=fabricacion or "Rolled",
                    eje=eje, lado_compresion=lado_compresion, resultados_b4=resultados_b4,
                    Lb=Lb, Cb=Cb,
                )

            elif ruta.seccion == "F8":
                resultado_f = calcular_f8(E=E, Fy=Fy, prop=prop, geo=geo, resultados_b4=resultados_b4)

            elif ruta.seccion == "F9":
                Lb = entrada_magnitud(
                    "Longitud lateral no arriostrada Lb", key="F9_Lb",
                    magnitud="longitud", unidad=uL, valor_inicial_interno=3000.0, min_interno=0.001,
                    help=(
                        "Distancia entre puntos que impiden el desplazamiento lateral "
                        "de la región comprimida o que evitan el giro de la sección. "
                        "Debe corresponder al mismo segmento usado para obtener Cb."
                    ),
                )
                resultado_f = calcular_f9(
                    perfil=perfil, E=E, Fy=Fy, prop=prop, geo=geo,
                    lado_compresion=lado_compresion, Lb=Lb, resultados_b4=resultados_b4,
                )

            elif ruta.seccion == "F10":
                st.markdown("**Configuración específica del ángulo simple**")
                modo_eje = st.selectbox(
                    "Eje usado en F10", ["Geométrico", "Principal mayor", "Principal menor"],
                    key="F10_modo_eje",
                )
                restriccion_continua = st.checkbox(
                    "Restricción lateral-torsional continua", value=False, key="F10_restr_cont",
                )
                restriccion_solo_mmax = False
                if not restriccion_continua:
                    restriccion_solo_mmax = st.checkbox(
                        "Restricción lateral-torsional únicamente en el punto de momento máximo",
                        value=False, key="F10_restr_mmax",
                    )
                    Lb = entrada_magnitud(
                        "Longitud lateral no arriostrada Lb", key="F10_Lb",
                        magnitud="longitud", unidad=uL, valor_inicial_interno=3000.0, min_interno=0.001,
                        help=(
                            "Distancia entre puntos que impiden el desplazamiento lateral "
                            "de la región comprimida o que evitan el giro de la sección. "
                            "Debe corresponder al mismo segmento usado para obtener Cb."
                        ),
                    )
                    Cb = _entrada_cb(uM, "F10")
                else:
                    Lb, Cb = 1.0, 1.0
                extremo_libre = st.radio(
                    "Estado del extremo libre (toe)", ["Compresión", "Tracción"],
                    horizontal=True, key="F10_toe",
                )
                pata_comprimida = st.radio(
                    "Pata cuyo extremo libre se evalúa", ["Pata 1", "Pata 2"],
                    horizontal=True, key="F10_pata",
                )
                beta_w = 0.0
                if modo_eje == "Principal mayor" and abs(geo["b1"] - geo["b2"]) > 1e-9:
                    beta_w = st.number_input(
                        "Propiedad βw con signo", value=0.0, key="F10_beta_w",
                        help="Use el signo correspondiente al extremo de la pata más larga en compresión o tracción.",
                    )
                resultado_f = calcular_f10(
                    E=E, Fy=Fy, prop=prop, geo=geo, resultados_b4=resultados_b4,
                    Lb=Lb, Cb=Cb, modo_eje=modo_eje, eje_geometrico=eje,
                    lado_compresion=lado_compresion, restriccion_continua=restriccion_continua,
                    restriccion_solo_mmax=restriccion_solo_mmax, extremo_libre=extremo_libre,
                    pata_comprimida=pata_comprimida, beta_w=beta_w,
                )

            if resultado_f is None:
                st.warning(f"La sección {ruta.seccion} todavía no tiene una geometría compatible en la interfaz.")
                return

            # F13 contiene disposiciones adicionales. Se automatizan las que
            # dependen de datos geométricos disponibles y se solicitan únicamente
            # los datos de agujeros/rigidizadores que no pueden inferirse.
            estados_f13 = []
            if eje == "x-x" and perfil in {"Perfil I", "Perfil I asimétrico", "Canal"}:
                mostrar_f13 = st.checkbox(
                    "Mostrar verificaciones adicionales de F13",
                    value=False, key=f"mostrar_F13_{perfil}",
                )
                if mostrar_f13:
                    st.markdown("### F13 — Provisiones adicionales")
                    st.markdown("**F13.1 — Agujeros en el ala de tensión**")

                    # El lado en tracción es el opuesto al lado seleccionado en
                    # compresión. Solo una cubreplaca ubicada en ese lado forma
                    # parte de Afg y Afn para F13.1.
                    lado_tension = "Inferior" if lado_compresion == "Superior" else "Superior"
                    clave_tension = lado_tension.lower()
                    clave_estado = f"{perfil}_{clave_tension}".replace(" ", "_")

                    componentes_tension: list[dict[str, float | str]] = []
                    if perfil in {"Perfil I", "Perfil I asimétrico"}:
                        if perfil == "Perfil I":
                            bf_t, tf_t = geo["bf"], geo["tf"]
                        elif lado_tension == "Inferior":
                            bf_t, tf_t = geo["bf_inferior"], geo["tf_inferior"]
                        else:
                            bf_t, tf_t = geo["bf_superior"], geo["tf_superior"]
                        componentes_tension.append({
                            "nombre": f"Patín {lado_tension.lower()}",
                            "b": float(bf_t), "t": float(tf_t),
                        })
                        cp_tension = cubreplacas.get(clave_tension)
                        if cp_tension:
                            componentes_tension.append({
                                "nombre": f"Cubreplaca {lado_tension.lower()}",
                                "b": float(cp_tension.get("B", cp_tension.get("b", 0.0))),
                                "t": float(cp_tension.get("t", 0.0)),
                            })
                    else:
                        # En el canal, geo['b'] es el vuelo del patín medido desde
                        # la cara del alma; se suma tw para obtener el ancho total.
                        componentes_tension.append({
                            "nombre": f"Ala {lado_tension.lower()} del canal",
                            "b": float(geo["b"] + geo["tw"]),
                            "t": float(geo["tf"]),
                        })

                    st.info(
                        f"El lado seleccionado en compresión es **{lado_compresion}**; "
                        f"por tanto, el ala de tracción es la **{lado_tension.lower()}**. "
                        "Solo los componentes de ese lado se incluyen en Afg y Afn."
                    )
                    if perfil in {"Perfil I", "Perfil I asimétrico"}:
                        clave_compresion = lado_compresion.lower()
                        if cubreplacas.get(clave_compresion) and not cubreplacas.get(clave_tension):
                            st.caption(
                                f"La cubreplaca {clave_compresion} está en compresión y no "
                                "participa en el área del ala de tracción de F13.1."
                            )

                    hay_agujeros = st.checkbox(
                        "¿Existen agujeros de pernos en el ala de tracción?",
                        value=False, key=f"F13_agujeros_{clave_estado}",
                        help=(
                            "Active esta opción únicamente cuando la sección neta crítica "
                            "del ala que trabaja a tracción atraviesa agujeros de pernos."
                        ),
                    )
                    if hay_agujeros:
                        Fu = entrada_magnitud(
                            "Esfuerzo último Fu", key=f"F13_Fu_{clave_estado}",
                            magnitud="esfuerzo", unidad=uF,
                            valor_inicial_interno=450.0, min_interno=0.001,
                            help="Resistencia mínima especificada a tracción del acero.",
                        )

                        c_perno1, c_perno2, c_perno3 = st.columns(3)
                        serie_predeterminada = 1 if uL in {"in", "ft"} else 0
                        serie_perno = c_perno1.selectbox(
                            "Serie del perno",
                            ["Métrica", "Imperial"],
                            index=serie_predeterminada,
                            key=f"F13_serie_perno_{clave_estado}",
                            help="La serie controla los diámetros comerciales y la adición para área neta de B4.3b.",
                        )
                        diametros_disponibles = opciones_pernos_comerciales(serie_perno)
                        perno = c_perno2.selectbox(
                            "Diámetro nominal comercial",
                            diametros_disponibles,
                            index=min(2, len(diametros_disponibles) - 1),
                            key=f"F13_perno_{clave_estado}_{serie_perno}",
                            help="Seleccione el diámetro nominal del perno; el programa obtiene internamente el agujero de J3.3.",
                        )
                        tipo_agujero = c_perno3.selectbox(
                            "Tipo de agujero",
                            ["Estándar", "Sobredimensionado", "Ranura corta", "Ranura larga"],
                            key=f"F13_tipo_agujero_{clave_estado}",
                            help="Dimensiones máximas nominales según la Tabla J3.3.",
                        )

                        orientacion_ranura = "Paralela a la fuerza"
                        if tipo_agujero.startswith("Ranura"):
                            orientacion_ranura = st.radio(
                                "Orientación de la ranura",
                                ["Paralela a la fuerza", "Perpendicular a la fuerza"],
                                horizontal=True,
                                key=f"F13_orientacion_ranura_{clave_estado}",
                                help=(
                                    "Si la ranura es paralela a la fuerza, la sección neta "
                                    "descuenta su dimensión corta. Si es perpendicular, "
                                    "descuenta su dimensión larga."
                                ),
                            )

                        db, ancho_agujero, largo_agujero, d_neta = dimensiones_agujero_j33(
                            serie=serie_perno, perno=perno, tipo=tipo_agujero,
                            orientacion_ranura=orientacion_ranura,
                        )
                        qh1, qh2, qh3 = st.columns(3)
                        qh1.metric("Diámetro nominal del perno", f"{valor_mostrado(db, 'longitud', uL):,.3f} {uL}")
                        if abs(ancho_agujero - largo_agujero) <= 1e-9:
                            dim_agujero_texto = f"{valor_mostrado(ancho_agujero, 'longitud', uL):,.3f} {uL}"
                        else:
                            dim_agujero_texto = (
                                f"{valor_mostrado(ancho_agujero, 'longitud', uL):,.3f} × "
                                f"{valor_mostrado(largo_agujero, 'longitud', uL):,.3f} {uL}"
                            )
                        qh2.metric("Agujero nominal J3.3", dim_agujero_texto)
                        qh3.metric(
                            "Dimensión descontada dₙ",
                            f"{valor_mostrado(d_neta, 'longitud', uL):,.3f} {uL}",
                            help=(
                                "Dimensión transversal nominal del agujero más la adición "
                                "de B4.3b para calcular el área neta."
                            ),
                        )

                        n_agujeros = st.number_input(
                            "Número de agujeros atravesados por la sección neta crítica",
                            min_value=1, value=2, step=1,
                            key=f"F13_n_agujeros_{clave_estado}",
                            help=(
                                "Ingrese los agujeros que corta una sola trayectoria crítica "
                                "transversal. No ingrese el número total de pernos de toda la conexión."
                            ),
                        )
                        opciones_disposicion = ["Alineados"] if n_agujeros == 1 else ["Alineados", "Escalonados"]
                        disposicion = st.radio(
                            "Disposición de los agujeros en la trayectoria crítica",
                            opciones_disposicion,
                            horizontal=True,
                            key=f"F13_disposicion_{clave_estado}_{n_agujeros}",
                            help=(
                                "Para agujeros escalonados se revisa una trayectoria diagonal "
                                "o en zigzag mediante la adición s²/(4g)."
                            ),
                        )

                        numero_diagonales = 0
                        s_escalonado = None
                        g_escalonado = None
                        if disposicion == "Escalonados":
                            ce1, ce2, ce3 = st.columns(3)
                            numero_diagonales = ce1.number_input(
                                "Tramos diagonales de la trayectoria",
                                min_value=1, max_value=max(1, int(n_agujeros) - 1),
                                value=max(1, int(n_agujeros) - 1), step=1,
                                key=f"F13_n_diagonales_{clave_estado}",
                                help="Cantidad de términos s²/(4g) presentes en la trayectoria neta evaluada.",
                            )
                            with ce2:
                                s_escalonado = entrada_magnitud(
                                    "Separación longitudinal s", key=f"F13_s_{clave_estado}",
                                    magnitud="longitud", unidad=uL,
                                    valor_inicial_interno=75.0, min_interno=0.001,
                                    help="Separación centro a centro en la dirección de la fuerza entre agujeros escalonados.",
                                )
                            with ce3:
                                g_escalonado = entrada_magnitud(
                                    "Separación transversal g", key=f"F13_g_{clave_estado}",
                                    magnitud="longitud", unidad=uL,
                                    valor_inicial_interno=60.0, min_interno=0.001,
                                    help="Separación centro a centro perpendicular a la fuerza entre líneas de agujeros.",
                                )

                        nombres_componentes = [str(c["nombre"]) for c in componentes_tension]
                        if len(nombres_componentes) == 1:
                            componentes_perforados = nombres_componentes
                            st.caption(f"Componente perforado: **{nombres_componentes[0]}**.")
                        else:
                            componentes_perforados = st.multiselect(
                                "Componentes atravesados por los agujeros",
                                nombres_componentes,
                                default=nombres_componentes,
                                key=f"F13_componentes_perforados_{clave_estado}",
                                help=(
                                    "Seleccione si la trayectoria atraviesa el patín, la "
                                    "cubreplaca de tracción o ambos componentes."
                                ),
                            )
                            if not componentes_perforados:
                                raise ValueError("Seleccione al menos un componente perforado.")

                        deduccion_ancho = deduccion_ancho_seccion_neta(
                            numero_agujeros=int(n_agujeros), d_neta=d_neta,
                            disposicion=disposicion,
                            numero_diagonales=int(numero_diagonales),
                            s=s_escalonado, g=g_escalonado,
                        )

                        Afg = 0.0
                        Afn = 0.0
                        filas_areas = []
                        for componente in componentes_tension:
                            nombre_comp = str(componente["nombre"])
                            b_comp = float(componente["b"])
                            t_comp = float(componente["t"])
                            area_bruta_comp = b_comp * t_comp
                            perforado = nombre_comp in componentes_perforados
                            if perforado:
                                ancho_neto_comp = b_comp - deduccion_ancho
                                if ancho_neto_comp <= 0:
                                    raise ValueError(
                                        f"La deducción de agujeros ({deduccion_ancho:.3f} mm) "
                                        f"agota el ancho del componente '{nombre_comp}' ({b_comp:.3f} mm)."
                                    )
                                area_neta_comp = ancho_neto_comp * t_comp
                            else:
                                area_neta_comp = area_bruta_comp
                            Afg += area_bruta_comp
                            Afn += area_neta_comp
                            filas_areas.append({
                                "Componente del ala de tracción": nombre_comp,
                                f"b [{uL}]": round(valor_mostrado(b_comp, "longitud", uL), 4),
                                f"t [{uL}]": round(valor_mostrado(t_comp, "longitud", uL), 4),
                                "Perforado": "SÍ" if perforado else "NO",
                                f"Ag [{unidad_propiedad(uL, 2)}]": round(valor_mostrado(area_bruta_comp, "longitud", uL, 2), 4),
                                f"An [{unidad_propiedad(uL, 2)}]": round(valor_mostrado(area_neta_comp, "longitud", uL, 2), 4),
                            })

                        st.dataframe(filas_areas, use_container_width=True, hide_index=True)
                        qa1, qa2, qa3 = st.columns(3)
                        qa1.metric(
                            "Deducción total de ancho",
                            f"{valor_mostrado(deduccion_ancho, 'longitud', uL):,.3f} {uL}",
                        )
                        qa2.metric(
                            "Área bruta del ala de tracción Afg",
                            f"{valor_mostrado(Afg, 'longitud', uL, 2):,.4f} {unidad_propiedad(uL, 2)}",
                        )
                        qa3.metric(
                            "Área neta del ala de tracción Afn",
                            f"{valor_mostrado(Afn, 'longitud', uL, 2):,.4f} {unidad_propiedad(uL, 2)}",
                        )

                        Sx_min = min(prop.Sx_sup, prop.Sx_inf)
                        reduce, Mn13, Yt, explicacion13 = verificar_agujeros_ala_tension(
                            Fu=Fu, Fy=Fy, Afg=Afg, Afn=Afn, Sx=Sx_min,
                        )
                        st.write(
                            f"**Yt = {Yt:.2f}** "
                            f"(Yt = 1.0 cuando Fy/Fu ≤ 0.8; en caso contrario, Yt = 1.1). "
                            f"{explicacion13}"
                        )
                        if reduce and Mn13 is not None:
                            estados_f13.append(EstadoLimiteMomento(
                                "F13 — Ruptura del ala de tensión", Mn13, "F13-1", explicacion13,
                            ))
                            st.warning(f"Momento nominal por F13-1: {cvM(Mn13):,.4f} {uM}.")
                        else:
                            st.success("La ruptura del ala de tensión no reduce la resistencia nominal.")

                    if perfil in {"Perfil I", "Perfil I asimétrico"}:
                        st.markdown("**F13.2 — Límites de proporción para perfiles I**")
                        alma_esbelta = ruta.clasificacion_alma == "ESBELTO"
                        a_rigid = None
                        if alma_esbelta:
                            tiene_rigidizadores = st.checkbox(
                                "El alma posee rigidizadores transversales",
                                value=False, key=f"F13_rigidizadores_{perfil}",
                            )
                            if tiene_rigidizadores:
                                a_rigid = entrada_magnitud(
                                    "Separación libre entre rigidizadores a",
                                    key=f"F13_a_{perfil}", magnitud="longitud", unidad=uL,
                                    valor_inicial_interno=1000.0, min_interno=0.001,
                                )
                        revisiones = verificaciones_proporcion_i_f13(
                            E=E, Fy=Fy, prop=prop, geo=geo, cubreplacas=cubreplacas,
                            lado_compresion=lado_compresion, simetria=simetria,
                            alma_esbelta=alma_esbelta, separacion_rigidizadores_a=a_rigid,
                        )
                        if revisiones:
                            filas_f13 = [{
                                "Verificación": nombre,
                                "Valor": round(valor, 5),
                                "Límite": round(limite, 5),
                                "Cumple": "SÍ" if cumple else "NO",
                                "Referencia": ecuacion,
                            } for nombre, valor, limite, cumple, ecuacion in revisiones]
                            st.dataframe(filas_f13, use_container_width=True, hide_index=True)
                            if any(not x[3] for x in revisiones):
                                st.error("Existe al menos una proporción que no satisface F13.2.")
                            else:
                                st.success("Las proporciones verificadas satisfacen F13.2.")
                        if cubreplacas:
                            st.info(
                                "F13.3 exige revisar el desarrollo, empalmes, separación longitudinal "
                                "y terminación de las cubreplacas. Estas condiciones dependen del detalle "
                                "de soldaduras o pernos y no se infieren solo con la sección transversal."
                            )

            if estados_f13:
                resultado_f = agregar_estados(resultado_f, estados_f13)

            filas = []
            for estado in resultado_f.estados:
                if estado.Fcr is not None:
                    fcr_mostrado = round(cvF(estado.Fcr), 5)
                else:
                    detalle_fcr = estado.descripcion_Fcr.lower()
                    if "mcr" in detalle_fcr:
                        fcr_mostrado = "Usa Mcr"
                    elif "no aplica" in detalle_fcr:
                        fcr_mostrado = "No aplica"
                    elif "no define fcr" in detalle_fcr:
                        fcr_mostrado = "No definido"
                    else:
                        fcr_mostrado = "—"
                observacion = estado.observacion
                if estado.descripcion_Fcr:
                    observacion = (observacion + " " + estado.descripcion_Fcr).strip()
                filas.append({
                    "Estado límite": estado.estado,
                    "Ecuación": estado.ecuacion,
                    f"Fcr [{uF}]": fcr_mostrado,
                    f"Mn [{uM}]": round(cvM(estado.Mn), 5),
                    "Observación": observacion,
                })
            st.dataframe(filas, use_container_width=True, hide_index=True)
            st.caption(
                "Fcr se muestra únicamente cuando la ecuación normativa lo define de forma "
                "explícita. Si AISC calcula Mn directamente, la tabla indica «No definido»; "
                "si el estado límite no aplica, indica «No aplica». Mcr es un momento crítico "
                "y se reporta en la observación, no como Fcr."
            )

            st.success(
                f"Gobierna **{resultado_f.gobernante.estado}** ({resultado_f.gobernante.ecuacion})."
            )
            c1, c2, c3 = st.columns(3)
            c1.metric("Momento nominal Mn", f"{cvM(resultado_f.Mn):,.4f} {uM}")
            c2.metric("LRFD: ϕbMn", f"{cvM(resultado_f.phi_Mn):,.4f} {uM}")
            c3.metric("ASD: Mn/Ωb", f"{cvM(resultado_f.Mn_sobre_omega):,.4f} {uM}")

            firma = _firma_modelo(
                perfil=perfil, E=E, Fy=Fy, geo=geo,
                fabricacion=fabricacion, cubreplacas=cubreplacas,
            )
            M_yield_n = Fy * (prop.Zx if eje == "x-x" else prop.Zy)
            _guardar_capacidad(
                f"_capacidad_flexion_{eje}_{lado_compresion}",
                {
                    "firma": firma,
                    "perfil": perfil,
                    "eje": eje,
                    "lado_compresion": lado_compresion,
                    "seccion": ruta.seccion,
                    "clasificacion": clasificacion_global(resultados_b4)[0],
                    "Mn": float(resultado_f.Mn),
                    "LRFD": float(resultado_f.phi_Mn),
                    "ASD": float(resultado_f.Mn_sobre_omega),
                    "Mn_fluencia": float(M_yield_n),
                    "LRFD_fluencia": float(0.90 * M_yield_n),
                    "ASD_fluencia": float(M_yield_n / 1.67),
                    "gobernante": resultado_f.gobernante.estado,
                    "ecuacion": resultado_f.gobernante.ecuacion,
                },
            )
            for obs in resultado_f.observaciones:
                st.caption(obs)

            with st.expander("Verificación de la solicitación a flexión", expanded=False):
                metodo_f = st.radio(
                    "Método de diseño para la comparación", ["LRFD", "ASD"],
                    horizontal=True, key=f"F_metodo_demanda_{perfil}_{eje}_{ruta.seccion}",
                    help=(
                        "LRFD compara Mu con ϕbMn. ASD compara Ma con Mn/Ωb. "
                        "Este bloque no modifica el cálculo de Mn."
                    ),
                )
                comparar_f = st.checkbox(
                    "Comparar con un momento requerido", value=False,
                    key=f"F_comparar_demanda_{perfil}_{eje}_{ruta.seccion}",
                )
                if comparar_f:
                    etiqueta_m = "Momento requerido Mu" if metodo_f == "LRFD" else "Momento requerido Ma"
                    Mreq = entrada_magnitud(
                        etiqueta_m, key=f"F_Mreq_{perfil}_{eje}_{ruta.seccion}_{metodo_f}",
                        magnitud="momento", unidad=uM, valor_inicial_interno=10_000_000.0,
                        min_interno=0.0,
                        help=(
                            "Ingrese el momento solicitante del mismo eje y combinación de carga. "
                            "Use combinaciones factorizadas para LRFD y de servicio para ASD."
                        ),
                    )
                    capacidad_f = resultado_f.phi_Mn if metodo_f == "LRFD" else resultado_f.Mn_sobre_omega
                    _mostrar_verificacion_solicitacion(
                        demanda=cvM(Mreq), capacidad=cvM(capacidad_f), unidad=uM, metodo=metodo_f,
                        etiqueta_demanda="Demanda Mu" if metodo_f == "LRFD" else "Demanda Ma",
                        etiqueta_capacidad="Capacidad ϕbMn" if metodo_f == "LRFD" else "Capacidad Mn/Ωb",
                    )

        except (ValueError, ZeroDivisionError) as exc:
            st.error(str(exc))


def _datos_patines_g2(perfil: str, geo: dict, cubreplacas: dict, lado_compresion: str):
    """Áreas y anchos de patines para las condiciones geométricas de G2.2."""
    if perfil == "Perfil I":
        sup = {"b": geo["bf"], "A": geo["bf"] * geo["tf"]}
        inf = {"b": geo["bf"], "A": geo["bf"] * geo["tf"]}
    elif perfil == "Perfil I asimétrico":
        sup = {"b": geo["bf_superior"], "A": geo["bf_superior"] * geo["tf_superior"]}
        inf = {"b": geo["bf_inferior"], "A": geo["bf_inferior"] * geo["tf_inferior"]}
    elif perfil == "Canal":
        sup = {"b": geo["b"], "A": geo["b"] * geo["tf"]}
        inf = {"b": geo["b"], "A": geo["b"] * geo["tf"]}
    else:
        raise ValueError("G2.2 solo se implementa para perfiles I y canales.")

    for lado, datos in (("superior", sup), ("inferior", inf)):
        cp = cubreplacas.get(lado)
        if cp:
            Bcp = float(cp.get("B", cp.get("b", 0.0)))
            tcp = float(cp["t"])
            datos["A"] += Bcp * tcp
            datos["b"] = max(datos["b"], Bcp)

    if lado_compresion == "Superior":
        comp, trac = sup, inf
    else:
        comp, trac = inf, sup
    return comp["A"], trac["A"], comp["b"], trac["b"]


def _mostrar_verificacion_solicitacion(
    *, demanda: float, capacidad: float, unidad: str, metodo: str,
    etiqueta_demanda: str, etiqueta_capacidad: str, titulo: str = "Verificación de la solicitación",
) -> float:
    """Muestra demanda, capacidad, relación D/C y estado sin alterar cálculos normativos."""
    razon = demanda / capacidad if capacidad > 0 else float("inf")
    estado = "CUMPLE" if razon <= 1.0 else "NO CUMPLE"

    st.markdown(f"### {titulo}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(etiqueta_demanda, f"{demanda:,.4f} {unidad}")
    c2.metric(etiqueta_capacidad, f"{capacidad:,.4f} {unidad}")
    c3.metric("Relación demanda/capacidad", f"{razon:,.4f}")
    c4.metric("Estado", estado)

    mensaje = (
        f"{metodo}: demanda/capacidad = {razon:.4f}. "
        f"{etiqueta_demanda} = {demanda:,.4f} {unidad}; "
        f"{etiqueta_capacidad} = {capacidad:,.4f} {unidad}."
    )
    if razon > 1.0:
        st.error(mensaje + " No cumple.")
    elif razon > 0.95:
        st.warning(mensaje + " Cumple, pero está próximo al límite.")
    else:
        st.success(mensaje + " Cumple.")
    return razon


def _mostrar_resultado_cortante(resultado, unidad_fuerza: str, unidad_esfuerzo: str) -> None:
    cvP = lambda v: valor_mostrado(v, "fuerza", unidad_fuerza)
    cvF = lambda v: valor_mostrado(v, "esfuerzo", unidad_esfuerzo)
    filas = []
    for e in resultado.estados:
        filas.append({
            "Estado / componente": e.estado,
            "Ecuación": e.ecuacion,
            "λv": "—" if e.lambda_v is None else round(e.lambda_v, 5),
            "kv": "—" if e.kv is None else round(e.kv, 5),
            "Cv": "—" if e.Cv is None else round(e.Cv, 5),
            f"Fcr [{unidad_esfuerzo}]": "—" if e.Fcr is None else round(cvF(e.Fcr), 5),
            f"Vn [{unidad_fuerza}]": round(cvP(e.Vn), 5),
            "Observación": e.observacion,
        })
    st.dataframe(filas, use_container_width=True, hide_index=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Resistencia nominal Vn", f"{cvP(resultado.Vn):,.4f} {unidad_fuerza}")
    c2.metric("LRFD: ϕvVn", f"{cvP(resultado.phi_Vn):,.4f} {unidad_fuerza}")
    c3.metric("ASD: Vn/Ωv", f"{cvP(resultado.Vn_sobre_omega):,.4f} {unidad_fuerza}")
    for obs in resultado.observaciones:
        st.caption(obs)


def _comparar_cortante(resultado, metodo: str, Vr: float, unidad_fuerza: str, etiqueta: str = "") -> float:
    disponible = capacidad_disponible(resultado.adoptado, metodo)
    demanda_mostrada = valor_mostrado(Vr, "fuerza", unidad_fuerza)
    capacidad_mostrada = valor_mostrado(disponible, "fuerza", unidad_fuerza)
    simbolo_demanda = "Vu" if metodo == "LRFD" else "Va"
    simbolo_capacidad = "ϕvVn" if metodo == "LRFD" else "Vn/Ωv"
    titulo = "Verificación de la solicitación"
    if etiqueta:
        titulo += f" — {etiqueta}"
    return _mostrar_verificacion_solicitacion(
        demanda=demanda_mostrada, capacidad=capacidad_mostrada, unidad=unidad_fuerza,
        metodo=metodo, etiqueta_demanda=f"Demanda {simbolo_demanda}",
        etiqueta_capacidad=f"Capacidad {simbolo_capacidad}", titulo=titulo,
    )


def mostrar_ruta_y_diseno_capitulo_g(
    perfil: str, E: float, Fy: float, geo: dict, fabricacion: str | None,
    cubreplacas: dict, prop, eje: str, lado_compresion: str,
    unidad_esfuerzo: str, unidad_longitud: str, unidad_fuerza: str,
) -> None:
    """Ruta automática y diseño a cortante conforme al alcance del Capítulo G."""
    ruta = ruta_capitulo_g(perfil, eje)
    uL, uF, uP = unidad_longitud, unidad_esfuerzo, unidad_fuerza
    cvP = lambda v: valor_mostrado(v, "fuerza", uP)
    cvL = lambda v, p=1: valor_mostrado(v, "longitud", uL, p)

    def guardar_capacidad_cortante(resultado: ResultadoCortante, fuente: str) -> None:
        firma = _firma_modelo(
            perfil=perfil, E=E, Fy=Fy, geo=geo,
            fabricacion=fabricacion, cubreplacas=cubreplacas,
        )
        _guardar_capacidad(
            f"_capacidad_cortante_{eje}",
            {
                "firma": firma,
                "perfil": perfil,
                "eje": eje,
                "seccion": resultado.seccion,
                "Vn": float(resultado.Vn),
                "LRFD": float(resultado.phi_Vn),
                "ASD": float(resultado.Vn_sobre_omega),
                "fuente": fuente,
                "ecuacion": resultado.adoptado.ecuacion,
            },
        )

    with st.expander("Ruta automática del Capítulo G", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Sección aplicable", ruta.seccion)
        c2.metric("Dirección asociada", eje)
        c3.metric("Elemento resistente", ruta.elemento_resistente)
        st.caption(ruta.descripcion)
        st.code(f"{perfil} → eje {eje} → {ruta.elemento_resistente} → {ruta.seccion}")
        st.write("**Ecuaciones consideradas:** " + " · ".join(ruta.ecuaciones_principales))
        for aviso in ruta.advertencias:
            st.warning(aviso)

    st.info(
        f"Los cálculos internos usan N y MPa. Los resultados se muestran en **{uP}**. "
        "Salvo la excepción G2.1(a), se usa ϕv=0.90 y Ωv=1.67."
    )

    metodo = st.radio(
        "Método para comparar la demanda",
        ["LRFD", "ASD"], horizontal=True, key=f"G_metodo_{perfil}_{eje}",
        help=(
            "LRFD compara el cortante factorizado Vu con ϕvVn. ASD compara el cortante "
            "de servicio Va con Vn/Ωv."
        ),
    )

    # Para G2 se usa el flujo longitudinal acordado: demanda máxima en la cara,
    # longitud de la zona rigidizada y demanda al final de dicha zona. Las demás
    # secciones del Capítulo G conservan la comparación general anterior.
    Vr_general = None
    if ruta.seccion != "G2":
        comparar = st.checkbox(
            "Comparar con un cortante requerido",
            value=False, key=f"G_comparar_{perfil}_{eje}",
            help="Actívelo para obtener la relación demanda/capacidad.",
        )
        if comparar:
            Vr_general = entrada_magnitud(
                "Cortante requerido Vu" if metodo == "LRFD" else "Cortante requerido Va",
                key=f"G_Vr_{perfil}_{eje}_{metodo}", magnitud="fuerza", unidad=uP,
                valor_inicial_interno=100_000.0, min_interno=0.0,
                help=(
                    "Cortante que actúa en la sección evaluada. Use combinaciones "
                    "factorizadas para LRFD y combinaciones de servicio para ASD."
                ),
            )

    tiene_aberturas = st.checkbox(
        "Existen aberturas en el alma o en las paredes resistentes",
        value=False, key=f"G7_aberturas_{perfil}_{eje}",
        help=(
            "G7 exige considerar expresamente el efecto de cada abertura. La resistencia "
            "de la sección sin abertura no puede aplicarse directamente en esa zona."
        ),
    )
    if tiene_aberturas:
        st.error(
            "G7 — La resistencia calculada abajo corresponde a la sección sin abertura. "
            "La zona de la abertura requiere un análisis específico y refuerzo cuando la "
            "demanda exceda la resistencia disponible local."
        )

    try:
        if ruta.seccion == "G2":
            h, tw = geo["h"], geo["tw"]
            if perfil == "Perfil I":
                d = h + 2.0 * geo["tf"]
            elif perfil == "Perfil I asimétrico":
                d = h + geo["tf_superior"] + geo["tf_inferior"]
            else:
                d = h + 2.0 * geo["tf"]

            st.subheader("Demanda de cortante a lo largo de la zona próxima a la columna")
            st.caption(
                "El perfil se verifica sin rigidizadores con el cortante existente al final de la "
                "zona. Los paneles rigidizados y las placas se verifican conservadoramente con el "
                "cortante máximo en la cara de la columna."
            )
            c1, c2, c3 = st.columns(3)
            with c1:
                Vr_cara = entrada_magnitud(
                    "Cortante máximo en la cara de la columna Vu,max" if metodo == "LRFD"
                    else "Cortante máximo en la cara de la columna Va,max",
                    key=f"G2_Vr_cara_{perfil}_{eje}_{metodo}", magnitud="fuerza", unidad=uP,
                    valor_inicial_interno=300_000.0, min_interno=0.0,
                    help=(
                        "Máximo valor absoluto de la envolvente de cortante en la cara de la columna. "
                        "Este valor se usa para dimensionar todos los paneles y rigidizadores de la zona."
                    ),
                )
            with c2:
                Lz = entrada_magnitud(
                    "Distancia desde la cara hasta la sección sin rigidizadores",
                    key=f"G2_Lz_transicion_{perfil}_{eje}", magnitud="longitud", unidad=uL,
                    valor_inicial_interno=1000.0, min_interno=0.001,
                    help=(
                        "Distancia desde la cara de la columna hasta el último rigidizador. A partir de "
                        "esta sección se pretende que el perfil continúe resistiendo sin rigidizadores."
                    ),
                )
            with c3:
                Vr_fin = entrada_magnitud(
                    "Cortante en la sección ubicada a esa distancia Vu(Lz)" if metodo == "LRFD"
                    else "Cortante en la sección ubicada a esa distancia Va(Lz)",
                    key=f"G2_Vr_fin_{perfil}_{eje}_{metodo}", magnitud="fuerza", unidad=uP,
                    valor_inicial_interno=200_000.0, min_interno=0.0,
                    help=(
                        "Cortante que actúa en la sección donde termina la zona rigidizada. Este valor "
                        "debe ser resistido por el perfil sin ayuda de rigidizadores transversales."
                    ),
                )

            Vr_zona = max(Vr_cara, Vr_fin)
            if Vr_fin > Vr_cara + 1e-9:
                st.warning(
                    "El cortante ingresado al final de la zona es mayor que el de la cara. Para no "
                    "subestimar la demanda, se adopta el mayor de ambos valores para los paneles y "
                    "rigidizadores. Revise la envolvente si se esperaba un diagrama decreciente."
                )

            st.subheader("G2.1 — Perfil sin rigidizadores transversales")
            base = calcular_g2_sin_rigidizadores(
                perfil=perfil, fabricacion=fabricacion, E=E, Fy=Fy,
                h=h, tw=tw, d=d,
            )
            _mostrar_resultado_cortante(base, uP, uF)
            # G2 también debe guardar su resistencia para que el Capítulo H pueda
            # recuperar simultáneamente Vcx y Vcy. Se almacena conservadoramente
            # la resistencia del perfil sin rigidizadores transversales.
            guardar_capacidad_cortante(base, "G2 — sin rigidizadores")
            disponible_base = capacidad_disponible(base.adoptado, metodo)
            Cv_base = 1.0 if base.adoptado.Cv is None else float(base.adoptado.Cv)

            _comparar_cortante(
                base, metodo, Vr_fin, uP,
                f"Perfil sin rigidizadores en x=Lz={cvL(Lz):,.3f} {uL}",
            )
            _comparar_cortante(
                base, metodo, Vr_cara, uP,
                "Cara de la columna sin rigidizadores",
            )

            cumple_fin = Vr_fin <= disponible_base + 1e-9
            requiere_en_cara = Vr_zona > disponible_base + 1e-9
            pandeo_reduce = Cv_base < 1.0 - 1e-9

            if not cumple_fin:
                st.error(
                    "El perfil seleccionado no cumple sin rigidizadores en la distancia indicada. "
                    "Para que la zona rigidizada termine allí, debe aumentar el área del alma, elegir "
                    "otro perfil o desplazar el final de la zona hasta una sección con menor cortante."
                )
            elif not requiere_en_cara:
                st.success(
                    "El perfil cumple tanto en la cara como al final de la zona sin rigidizadores; "
                    "no se requieren rigidizadores transversales por resistencia a cortante."
                )
            elif not pandeo_reduce:
                st.error(
                    "La demanda máxima supera la capacidad, pero Cv=1.00. Los rigidizadores no pueden "
                    "aumentar el límite 0.6FyAw; debe aumentar o reforzar el alma, o seleccionar una "
                    "sección mayor."
                )
            else:
                separacion = calcular_separacion_maxima_g2(
                    perfil=perfil, fabricacion=fabricacion, E=E, Fy=Fy,
                    h=h, tw=tw, d=d, cortante_requerido=Vr_zona, metodo=metodo,
                )
                for obs in separacion.observaciones:
                    st.caption(obs)

                if not separacion.es_posible or separacion.a_max is None:
                    cap_max = separacion.capacidad_maxima_panel
                    st.error(
                        f"La máxima capacidad disponible del panel extremo dentro del alcance implementado "
                        f"es {cvP(cap_max):,.4f} {uP}, menor que la demanda adoptada de "
                        f"{cvP(Vr_zona):,.4f} {uP}. No existe una separación que resuelva este caso con "
                        "G2.1; debe modificarse la sección o estudiarse G2.3 mediante análisis especializado."
                    )
                else:
                    a_max = separacion.a_max
                    n_min = max(1, ceil(Lz / a_max - 1e-12))

                    st.markdown("### Separación longitudinal y cantidad de rigidizadores")
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Separación máxima amax", f"{cvL(a_max):,.4f} {uL}")
                    m2.metric("amax/h", f"{a_max/h:.4f}")
                    m3.metric("Paneles mínimos", str(n_min))
                    m4.metric("Rigidizadores mínimos", str(n_min))
                    st.info(
                        "El último rigidizador se coloca en x=Lz. Como la cara de la columna es el límite "
                        "inicial, el número de paneles coincide con el número de rigidizadores ubicados "
                        "dentro de la zona."
                    )

                    key_n = f"G2_num_paneles_{perfil}_{eje}_{metodo}"
                    max_paneles = max(200, n_min + 100)
                    if key_n not in st.session_state:
                        st.session_state[key_n] = n_min
                    else:
                        st.session_state[key_n] = min(
                            max(int(st.session_state[key_n]), n_min), max_paneles
                        )
                    numero_paneles = int(st.number_input(
                        "Número de paneles adoptado en la zona rigidizada",
                        min_value=n_min,
                        max_value=max_paneles,
                        step=1,
                        key=key_n,
                        help=(
                            "Puede adoptar más paneles que el mínimo. El programa distribuye los "
                            "rigidizadores uniformemente y mantiene el último en x=Lz."
                        ),
                    ))
                    a = Lz / numero_paneles
                    cumple_separacion = a <= a_max * (1.0 + 1e-9)
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Separación uniforme adoptada a", f"{cvL(a):,.4f} {uL}")
                    c2.metric("a/h", f"{a/h:.4f}")
                    c3.metric("Comprobación a≤amax", "CUMPLE" if cumple_separacion else "NO CUMPLE")

                    if numero_paneles <= 8:
                        esquema = "Cara de columna ┃"
                        for i in range(1, numero_paneles + 1):
                            esquema += f"── Panel {i} ──┃ R{i} "
                        esquema += f"→ zona sin rigidizadores desde x={cvL(Lz):,.3f} {uL}"
                        st.code(esquema)
                    else:
                        st.code(
                            f"Cara de columna ┃── {numero_paneles} paneles uniformes de "
                            f"{cvL(a):,.3f} {uL} ──┃ R{numero_paneles} en x=Lz"
                        )

                    filas_posicion = []
                    for i in range(numero_paneles):
                        x_ini = i * a
                        x_fin = (i + 1) * a
                        filas_posicion.append({
                            "Panel": i + 1,
                            "Tipo": "Extremo" if i == 0 else "Interior",
                            f"Inicio [{uL}]": round(cvL(x_ini), 4),
                            f"Fin [{uL}]": round(cvL(x_fin), 4),
                            "Rigidizador al final": f"R{i+1}",
                            f"Posición del rigidizador [{uL}]": round(cvL(x_fin), 4),
                        })
                    st.dataframe(filas_posicion, use_container_width=True, hide_index=True)

                    Afc, Aft, bfc, bft = _datos_patines_g2(
                        perfil, geo, cubreplacas, lado_compresion,
                    )
                    usar_tfa = False
                    if numero_paneles > 1:
                        usar_tfa = st.checkbox(
                            "Aprovechar acción de campo de tracción G2.2 en todos los paneles interiores",
                            value=True,
                            key=f"G2_TFA_uniforme_{perfil}_{eje}",
                            disabled=(a / h > 3.0),
                            help=(
                                "La opción solo afecta a los paneles interiores. El primer panel se "
                                "mantiene conservadoramente con G2.1 porque G2.3 no está implementado."
                            ),
                        )
                        if a / h > 3.0:
                            st.warning("a/h>3.0; G2.2 no es aplicable.")

                    panel_extremo = calcular_g2_panel(
                        perfil=perfil, fabricacion=fabricacion, tipo_panel="Extremo",
                        E=E, Fy=Fy, h=h, tw=tw, d=d, a=a,
                        Afc=Afc, Aft=Aft, bfc=bfc, bft=bft,
                        usar_campo_traccion=False,
                    )
                    estados_ext = [panel_extremo.g21]
                    resultado_extremo = ResultadoCortante(
                        "G2 — panel extremo", tuple(estados_ext), panel_extremo.adoptado,
                        panel_extremo.observaciones,
                    )
                    st.markdown("### Verificación del panel extremo representativo")
                    _mostrar_resultado_cortante(resultado_extremo, uP, uF)
                    _comparar_cortante(resultado_extremo, metodo, Vr_zona, uP, "Panel 1 — extremo")
                    st.warning(
                        "G2.3 no se calcula. El panel extremo se verifica conservadoramente mediante G2.1."
                    )

                    panel_interior = None
                    resultado_interior = None
                    if numero_paneles > 1:
                        panel_interior = calcular_g2_panel(
                            perfil=perfil, fabricacion=fabricacion, tipo_panel="Interior",
                            E=E, Fy=Fy, h=h, tw=tw, d=d, a=a,
                            Afc=Afc, Aft=Aft, bfc=bfc, bft=bft,
                            usar_campo_traccion=usar_tfa,
                        )
                        estados_int = [panel_interior.g21]
                        if panel_interior.g22 is not None:
                            estados_int.append(panel_interior.g22)
                        resultado_interior = ResultadoCortante(
                            "G2 — panel interior", tuple(estados_int), panel_interior.adoptado,
                            panel_interior.observaciones,
                        )
                        st.markdown("### Verificación del panel interior representativo")
                        _mostrar_resultado_cortante(resultado_interior, uP, uF)
                        _comparar_cortante(
                            resultado_interior, metodo, Vr_zona, uP,
                            f"Paneles 2 a {numero_paneles} — interiores",
                        )

                    filas_paneles = []
                    for i in range(numero_paneles):
                        panel = panel_extremo if i == 0 else panel_interior
                        disponible = capacidad_disponible(panel.adoptado, metodo)
                        dc = Vr_zona / disponible if disponible > 0 else float("inf")
                        filas_paneles.append({
                            "Panel": i + 1,
                            "Tipo": "Extremo" if i == 0 else "Interior",
                            f"a [{uL}]": round(cvL(a), 4),
                            "a/h": round(a / h, 4),
                            "kv": None if panel.adoptado.kv is None else round(panel.adoptado.kv, 4),
                            "Cv": None if panel.adoptado.Cv is None else round(panel.adoptado.Cv, 4),
                            f"Demanda [{uP}]": round(cvP(Vr_zona), 4),
                            f"Capacidad [{uP}]": round(cvP(disponible), 4),
                            "D/C": round(dc, 4),
                            "Estado": "CUMPLE" if dc <= 1.0 + 1e-9 else "NO CUMPLE",
                        })
                    st.dataframe(filas_paneles, use_container_width=True, hide_index=True)
                    st.caption(
                        "La misma demanda máxima se aplica a todos los paneles. Las capacidades no se "
                        "suman; cada panel debe cumplir de manera individual."
                    )

                    st.markdown("### G2.4 — Dimensionamiento y verificación de los rigidizadores")
                    st.caption(
                        f"Todos los rigidizadores se verifican con la demanda máxima adoptada de "
                        f"{cvP(Vr_zona):,.4f} {uP}."
                    )
                    mismo_acero = st.checkbox(
                        "Usar el mismo Fy del perfil para los rigidizadores",
                        value=True, key=f"G24_mismo_acero_{perfil}",
                        help=(
                            "Fyst es el esfuerzo mínimo de fluencia del acero del rigidizador transversal. "
                            "Puede diferir del acero del alma."
                        ),
                    )
                    Fyst = Fy if mismo_acero else entrada_magnitud(
                        "Esfuerzo de fluencia del rigidizador Fyst",
                        key=f"G24_Fyst_{perfil}", magnitud="esfuerzo", unidad=uF,
                        valor_inicial_interno=250.0, min_interno=0.001,
                        help="Esfuerzo mínimo de fluencia especificado para la placa del rigidizador.",
                    )
                    numero_placas = st.radio(
                        "Placas por rigidizador",
                        [1, 2], horizontal=True, key=f"G24_num_placas_{perfil}",
                        help=(
                            "Una placa se coloca a un lado del alma. Dos placas forman un par, una a cada "
                            "lado. bst corresponde al ancho saliente de cada placa."
                        ),
                    )

                    if perfil == "Perfil I":
                        b_st_max = max((geo["bf"] - tw) / 2.0, 0.0)
                        descripcion_bmax = "(bf−tw)/2"
                    elif perfil == "Perfil I asimétrico":
                        b_sup = (geo["bf_superior"] - tw) / 2.0
                        b_inf = (geo["bf_inferior"] - tw) / 2.0
                        b_st_max = max(min(b_sup, b_inf), 0.0)
                        descripcion_bmax = "mínimo espacio disponible entre ambos patines"
                    else:
                        b_st_max = max(geo["b"], 0.0)
                        descripcion_bmax = "ancho saliente del patín del canal"
                    if b_st_max <= 0:
                        raise ValueError("La geometría no deja espacio disponible para el rigidizador.")

                    st.metric(
                        "Ancho saliente geométrico máximo bst,max",
                        f"{cvL(b_st_max):,.4f} {uL}",
                    )
                    st.caption(
                        f"Límite geométrico usado: {descripcion_bmax}. El programa no descuenta radios "
                        "interiores ni holguras de soldadura; el detalle final puede requerir un bst menor."
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        b_st = entrada_magnitud(
                            "Ancho saliente de cada placa bst",
                            key=f"G24_bst_{perfil}", magnitud="longitud", unidad=uL,
                            valor_inicial_interno=min(80.0, 0.80 * b_st_max),
                            min_interno=0.001, max_interno=b_st_max,
                            help=(
                                "Distancia desde la cara del alma hasta el borde libre de cada placa. "
                                "Está limitada automáticamente por la geometría de los patines."
                            ),
                        )
                    with c2:
                        t_st = entrada_magnitud(
                            "Espesor de cada placa tst",
                            key=f"G24_tst_{perfil}", magnitud="longitud", unidad=uL,
                            valor_inicial_interno=8.0, min_interno=0.001,
                            help="Espesor de la placa transversal utilizada como rigidizador.",
                        )

                    paneles_representativos = [("Panel extremo", panel_extremo)]
                    if panel_interior is not None:
                        paneles_representativos.append(("Panel interior", panel_interior))

                    filas_st = []
                    for nombre_panel, panel in paneles_representativos:
                        Vc1 = capacidad_disponible(panel.adoptado, metodo)
                        Vc2_nom = panel.Vn_Cv2
                        Vc2 = 0.90 * Vc2_nom if metodo == "LRFD" else Vc2_nom / 1.67
                        ver = verificar_rigidizador_g24(
                            E=E, Fyw=Fy, Fyst=Fyst, h=h, tw=tw, a=a,
                            b_st=b_st, t_st=t_st, numero_placas=numero_placas,
                            Vr=Vr_zona, Vc1=Vc1, Vc2=Vc2,
                        )
                        filas_st.append({
                            "Panel de control": nombre_panel,
                            "bst/tst": round(ver.lambda_st, 4),
                            "Límite G2-16": round(ver.lambda_limite, 4),
                            "Esbeltez": "Cumple" if ver.cumple_esbeltez else "No cumple",
                            f"Ist prov. [{unidad_propiedad(uL,4)}]": round(cvL(ver.Ist_proporcionado, 4), 4),
                            f"Ist req. [{unidad_propiedad(uL,4)}]": round(cvL(ver.Ist_requerido, 4), 4),
                            "Inercia": "Cumple" if ver.cumple_inercia else "No cumple",
                            "ρw": round(ver.rho_w, 4),
                        })
                        if ver.demanda_supera_panel:
                            st.error(
                                f"{nombre_panel}: la demanda supera la capacidad del panel. Aumentar "
                                "únicamente las dimensiones del rigidizador no resuelve la insuficiencia."
                            )
                        for obs in ver.observaciones:
                            st.caption(f"{nombre_panel}: {obs}")
                    st.dataframe(filas_st, use_container_width=True, hide_index=True)
                    st.caption(
                        "Las dimensiones bst y tst corresponden a la placa transversal. Las posiciones "
                        "longitudinales R1, R2, … se muestran en la tabla de distribución anterior."
                    )

        elif ruta.seccion == "G3":
            if perfil == "Tee":
                b, t, mult, desc = geo["d"], geo["tw"], 1, "vástago de la Tee"
            else:
                pata = st.radio(
                    "Pata que resiste el cortante",
                    ["Pata 1", "Pata 2"], horizontal=True, key=f"G3_pata_{eje}",
                    help="Seleccione la pata aproximadamente paralela a la dirección de la fuerza cortante.",
                )
                b = geo["b1"] if pata == "Pata 1" else geo["b2"]
                t, mult, desc = geo["t"], 1, pata.lower()
            resultado = calcular_g3(E=E, Fy=Fy, b=b, t=t, multiplicidad=mult, descripcion=desc)
            _mostrar_resultado_cortante(resultado, uP, uF)
            guardar_capacidad_cortante(resultado, "G3")
            if Vr_general is not None:
                _comparar_cortante(resultado, metodo, Vr_general, uP)

        elif ruta.seccion == "G4":
            if perfil in {"Tubo cuadrado", "Tubo rectangular"}:
                dimension = geo["H"] if eje == "x-x" else geo["B"]
                descuento = 3.0 * geo["t"] if fabricacion == "Rolled" else 2.0 * geo["t"]
                h_res = dimension - descuento
                desc = "paredes verticales" if eje == "x-x" else "paredes horizontales"
                resultado = calcular_g4(
                    E=E, Fy=Fy, h=h_res, t=geo["t"], numero_almas=2,
                    descripcion=desc,
                )
            else:
                resultado = calcular_g4(
                    E=E, Fy=Fy, h=geo["b1"], t=geo["t"], numero_almas=2,
                    descripcion="patas verticales de los dos ángulos",
                )
            _mostrar_resultado_cortante(resultado, uP, uF)
            guardar_capacidad_cortante(resultado, "G4")
            if Vr_general is not None:
                _comparar_cortante(resultado, metodo, Vr_general, uP)

        elif ruta.seccion == "G5":
            Lv = entrada_magnitud(
                "Distancia desde el cortante máximo hasta el punto de cortante cero Lv",
                key="G5_Lv", magnitud="longitud", unidad=uL,
                valor_inicial_interno=3000.0, min_interno=0.001,
                help=(
                    "Longitud medida a lo largo del miembro entre la sección de cortante máximo y "
                    "la sección donde el diagrama de cortante llega a cero."
                ),
            )
            resultado = calcular_g5(E=E, Fy=Fy, Ag=prop.Ag, D=geo["D"], t=geo["t"], Lv=Lv)
            _mostrar_resultado_cortante(resultado, uP, uF)
            guardar_capacidad_cortante(resultado, "G5")
            if Vr_general is not None:
                _comparar_cortante(resultado, metodo, Vr_general, uP)

        elif ruta.seccion == "G6":
            elementos = []
            if perfil == "Perfil I":
                elementos = [
                    ("patín superior", geo["bf"], geo["tf"], 2.0),
                    ("patín inferior", geo["bf"], geo["tf"], 2.0),
                ]
            elif perfil == "Perfil I asimétrico":
                elementos = [
                    ("patín superior", geo["bf_superior"], geo["tf_superior"], 2.0),
                    ("patín inferior", geo["bf_inferior"], geo["tf_inferior"], 2.0),
                ]
            elif perfil == "Canal":
                elementos = [
                    ("patín superior", geo["b"], geo["tf"], 1.0),
                    ("patín inferior", geo["b"], geo["tf"], 1.0),
                ]
            elif perfil == "Tee":
                elementos = [("patín de la Tee", 2.0 * geo["b"], geo["tf"], 2.0)]
            else:
                elementos = [
                    ("pata horizontal del ángulo 1", geo["b2"], geo["t"], 1.0),
                    ("pata horizontal del ángulo 2", geo["b2"], geo["t"], 1.0),
                ]

            if cubreplacas and perfil in {"Perfil I", "Perfil I asimétrico"}:
                participa_cp = st.checkbox(
                    "Las cubreplacas participan en la resistencia a cortante del eje menor",
                    value=False, key=f"G6_cp_participa_{perfil}",
                    help=(
                        "Actívelo solo cuando la conexión entre cubreplaca y patín puede desarrollar y "
                        "transferir el cortante longitudinal correspondiente."
                    ),
                )
                if participa_cp:
                    for lado, q in cubreplacas.items():
                        Bcp = float(q.get("B", q.get("b", 0.0)))
                        elementos.append((f"cubreplaca {lado}", Bcp, float(q["t"]), 2.0))

            resultado = calcular_g6(E=E, Fy=Fy, elementos=elementos)
            _mostrar_resultado_cortante(resultado, uP, uF)
            guardar_capacidad_cortante(resultado, "G6")
            if Vr_general is not None:
                _comparar_cortante(resultado, metodo, Vr_general, uP)

    except (ValueError, ZeroDivisionError) as exc:
        st.error(str(exc))


def datos_fisicos_e7(perfil: str, elemento: str, geo: dict, cubreplacas: dict, fabricacion: str | None) -> tuple[float, float, int]:
    """Devuelve b, t y multiplicidad física automática para E7."""
    e = elemento.lower()
    if perfil == "Perfil I":
        if "alma" in e: return geo["h"], geo["tw"], 1
        if "patín" in e or "ala" in e: return geo["bf"]/2.0, geo["tf"], 2
    if perfil == "Perfil I asimétrico":
        if "alma" in e: return geo["h"], geo["tw"], 1
        if "superior" in e: return geo["bf_superior"]/2.0, geo["tf_superior"], 1
        if "inferior" in e: return geo["bf_inferior"]/2.0, geo["tf_inferior"], 1
    if "cubreplaca superior" in e:
        q=cubreplacas["superior"]; return float(q["b"]), float(q["t"]), 1
    if "cubreplaca inferior" in e:
        q=cubreplacas["inferior"]; return float(q["b"]), float(q["t"]), 1
    if perfil == "Canal":
        return (geo["h"], geo["tw"], 1) if "alma" in e else (geo["b"], geo["tf"], 2)
    if perfil == "Tee":
        return (geo["d"], geo["tw"], 1) if "vástago" in e else (geo["b"], geo["tf"], 2)
    if perfil in {"Ángulo simple", "Ángulo doble con separadores"}:
        mult=2 if perfil == "Ángulo doble con separadores" else 1
        return (geo["b1"], geo["t"], mult) if "pata 1" in e else (geo["b2"], geo["t"], mult)
    if perfil in {"Tubo cuadrado", "Tubo rectangular"}:
        descuento=3.0*geo["t"] if fabricacion == "Rolled" else 2.0*geo["t"]
        if "horizontal" in e: return geo["B"]-descuento, geo["t"], 2
        return geo["H"]-descuento, geo["t"], 2
    raise ValueError(f"No se pudieron determinar automáticamente b, t y multiplicidad para {elemento}.")


def mostrar_ruta_y_diseno_capitulo_e(
    perfil, resultados, E, Fy, geo, fabricacion, cubreplacas_grafico, prop,
    unidad_esfuerzo: str, unidad_longitud: str, unidad_fuerza: str, unidad_momento: str,
):
    """Muestra la ruta E1.1 y ejecuta E2/E3/E4/E7 en unidades internas."""
    uF = unidad_esfuerzo
    uL = unidad_longitud
    uP = unidad_fuerza
    uM = unidad_momento
    uA = unidad_propiedad(uL, 2)
    uI = unidad_propiedad(uL, 4)
    uCw = unidad_propiedad(uL, 6)
    cvL = lambda v, p=1: valor_mostrado(v, "longitud", uL, p)
    cvF = lambda v: valor_mostrado(v, "esfuerzo", uF)
    cvP = lambda v: valor_mostrado(v, "fuerza", uP)
    Pn_comparacion = None
    fuente_Pn_comparacion = ""
    if perfil in {"Perfil I", "Perfil I asimétrico"}:
        sup = cubreplacas_grafico.get("superior")
        inf = cubreplacas_grafico.get("inferior")
        geometria_simetrica = perfil == "Perfil I" or (
            abs(geo["bf_superior"]-geo["bf_inferior"]) < 1e-9
            and abs(geo["tf_superior"]-geo["tf_inferior"]) < 1e-9
        )
        if geometria_simetrica and not sup and not inf:
            simetria = "Doble simetría"
        elif geometria_simetrica and sup and inf and abs(sup["B"]-inf["B"]) < 1e-9 and abs(sup["t"]-inf["t"]) < 1e-9:
            simetria = "Doble simetría"
        else:
            simetria = "Monosimétrica"
    elif perfil in {"Canal", "Tee"}:
        simetria = "Monosimétrica"
    elif perfil in {"Tubo cuadrado", "Tubo rectangular", "Tubo circular"}:
        simetria = "Doble simetría"
    elif perfil == "Ángulo doble con separadores":
        simetria = "Monosimétrica"
    else:
        simetria = "Asimétrica"

    # E6 se detecta automáticamente. Solo aplica a perfiles formados por dos
    # componentes completos interconectados a intervalos. En la lista actual,
    # este caso corresponde únicamente al ángulo doble con separadores.
    perfiles_e6 = {"Ángulo doble con separadores", "Canal doble", "Perfil I doble"}
    aplica_e6 = perfil in perfiles_e6

    st.info(
        f"**Unidades activas:** longitudes en **{uL}**, áreas en **{uA}**, "
        f"inercias y J en **{uI}**, Cw en **{uCw}**, esfuerzos en **{uF}**, "
        f"fuerzas en **{uP}** y momentos en **{uM}**. Las relaciones λ, λr y Lc/r son adimensionales."
    )

    with st.expander("Ruta automática del Capítulo E", expanded=True):
        ruta = ruta_capitulo_e(
            perfil=perfil,
            resultados_locales=resultados,
            simetria=simetria,
            miembro_builtup_dos_componentes=aplica_e6,
        )

        if aplica_e6:
            st.info(
                "La aplicación detectó automáticamente un miembro formado por "
                "dos perfiles interconectados. Por ello, corresponde revisar E6."
            )
        else:
            st.caption(
                "E6 no aplica: el perfil seleccionado no está formado por dos "
                "perfiles completos interconectados a intervalos."
            )
        c1, c2, c3 = st.columns(3)
        c1.metric("Clasificación global", "CON ELEMENTOS ESBELTOS" if ruta.tiene_elementos_esbeltos else "SIN ELEMENTOS ESBELTOS")
        c2.metric("Simetría", ruta.simetria)
        c3.metric("Secciones aplicables", " · ".join(ruta.secciones))
        st.write("**Estados límite:** " + ", ".join(ruta.estados_limite))
        st.caption(ruta.explicacion)
        st.code(f"{perfil} → {ruta.simetria} → {'con' if ruta.tiene_elementos_esbeltos else 'sin'} elementos esbeltos → {' / '.join(ruta.secciones)}")

    e4_valido_para_comparar = not any(estado in ruta.estados_limite for estado in ("TB", "FTB"))
    e7_valido_para_comparar = not ruta.tiene_elementos_esbeltos

    with st.expander("E2 — Longitudes efectivas", expanded=False):
        st.info("Ag, rx, ry, Ix, Iy y J se toman automáticamente de la geometría ingresada.")
        Ag, rx, ry = prop.Ag, prop.rx, prop.ry
        a, b, c = st.columns(3)
        a.metric("Área bruta Ag", f"{cvL(Ag,2):,.3f} {uA}")
        b.metric("Radio de giro rx", f"{cvL(rx):,.3f} {uL}")
        c.metric("Radio de giro ry", f"{cvL(ry):,.3f} {uL}")
        a, b, c, d = st.columns(4)
        Lx = entrada_magnitud("Longitud no arriostrada Lx", key="Lx_E", magnitud="longitud", unidad=uL, valor_inicial_interno=3000.0, min_interno=0.001)
        Kx = b.number_input("Factor Kx", min_value=0.001, value=1.0, key="Kx_E")
        Ly = entrada_magnitud("Longitud no arriostrada Ly", key="Ly_E", magnitud="longitud", unidad=uL, valor_inicial_interno=3000.0, min_interno=0.001)
        Ky = d.number_input("Factor Ky", min_value=0.001, value=1.0, key="Ky_E")
        Lcx, Lcy = longitud_efectiva(Kx, Lx), longitud_efectiva(Ky, Ly)
        st.write(
            f"**Lcx = {cvL(Lcx):.3f} {uL}** · **Lcy = {cvL(Lcy):.3f} {uL}** · "
            f"**Lcx/rx = {Lcx/rx:.3f}** · **Lcy/ry = {Lcy/ry:.3f}**"
        )
        if max(Lcx/rx, Lcy/ry) > 200:
            st.warning("La nota de usuario de E2 recomienda que Lc/r no exceda 200 para miembros diseñados a compresión.")

    res_x = None
    res_y = None
    with st.expander("E3 — Pandeo flexional", expanded=True):
        try:
            res_x = pandeo_flexional(eje="x-x", E=E, Fy=Fy, Ag=Ag, K=Kx, L=Lx, r=rx)
            res_y = pandeo_flexional(eje="y-y", E=E, Fy=Fy, Ag=Ag, K=Ky, L=Ly, r=ry)
            for r in (res_x, res_y):
                with st.container(border=True):
                    st.markdown(f"**{r.modo} alrededor de {r.eje}**")
                    q1,q2,q3,q4=st.columns(4)
                    q1.metric("Lc/r", f"{r.esbeltez:.3f}")
                    q2.metric("Fe", f"{cvF(r.Fe):.3f} {uF}")
                    q3.metric("Fn", f"{cvF(r.Fn):.3f} {uF}")
                    q4.metric("Pn", f"{cvP(r.Pn):.3f} {uP}")
                    st.caption(f"Fn por {r.ecuacion_fn}; {r.observacion}")
            gob = min((res_x,res_y), key=lambda r:r.Pn)
            Pn_comparacion = gob.Pn
            fuente_Pn_comparacion = f"E3 alrededor de {gob.eje}"
            st.warning(f"Gobierna E3 alrededor de **{gob.eje}**, con Pn = **{cvP(gob.Pn):.3f} {uP}**.")
        except ValueError as exc:
            st.error(str(exc))

    # E4 no es opcional: se muestra únicamente cuando la ruta normativa incluye
    # pandeo torsional (TB) o flexotorsional (FTB). Para perfiles tubulares, la
    # Tabla E1.1 conduce a E3/E7 y este bloque permanece oculto.
    aplica_e4 = any(estado in ruta.estados_limite for estado in ("TB", "FTB"))
    st.session_state.pop("activar_E4", None)  # limpia la antigua casilla manual

    if aplica_e4:
        es_torsional = "TB" in ruta.estados_limite and "FTB" not in ruta.estados_limite
        titulo_e4 = "E4 — Pandeo torsional" if es_torsional else "E4 — Pandeo flexotorsional"

        with st.expander(titulo_e4, expanded=False):
            st.info(
                "Esta verificación fue activada automáticamente por la ruta del "
                "Capítulo E; no puede omitirse mediante una casilla manual."
            )

            if res_x is None or res_y is None:
                st.error("E4 requiere resultados válidos de E3. Revise las longitudes, factores K y radios de giro.")
            else:
                G0 = 77200.0 if E > 1000 else 11200.0
                G = entrada_magnitud(
                    "Módulo de corte G", key="G_E4", magnitud="esfuerzo", unidad=uF,
                    valor_inicial_interno=G0, min_interno=0.001,
                )
                Ix, Iy, J = prop.Ix, prop.Iy, prop.J
                q1, q2, q3, q4 = st.columns(4)
                q1.metric("Ix automático", f"{cvL(Ix,4):,.3f} {uI}")
                q2.metric("Iy automático", f"{cvL(Iy,4):,.3f} {uI}")
                q3.metric("J automático", f"{cvL(J,4):,.3f} {uI}")

                if prop.Cw is None:
                    Cw = entrada_magnitud(
                        "Cw (requiere ingreso)", key="Cw_E4", magnitud="longitud",
                        unidad=uL, potencia=6, valor_inicial_interno=0.0, min_interno=0.0,
                    )
                    q4.metric("Cw ingresado", f"{cvL(Cw,6):,.3f} {uCw}")
                else:
                    Cw = prop.Cw
                    q4.metric("Cw automático", f"{cvL(Cw,6):,.3f} {uCw}")

                q1, q2 = st.columns(2)
                Lz = entrada_magnitud(
                    "Longitud torsional no arriostrada Lz", key="Lz_E4",
                    magnitud="longitud", unidad=uL,
                    valor_inicial_interno=max(Lx, Ly), min_interno=0.001,
                )
                Kz = q2.number_input("Factor Kz", min_value=0.001, value=1.0, key="Kz_E4")
                Lcz = Kz * Lz

                try:
                    if es_torsional:
                        if Cw <= 0:
                            raise ValueError(
                                "Para aplicar E4 por pandeo torsional a esta sección abierta, "
                                "Cw debe ser mayor que cero. Revise su cálculo o ingréselo manualmente."
                            )
                        Fe4 = fe_torsional_doble_simetria(
                            E=E, G=G, Cw=Cw, J=J, Lcz=Lcz, Ix=Ix, Iy=Iy,
                        )
                        modo = "Pandeo torsional"

                    elif ruta.simetria == "Monosimétrica":
                        # E4-3 supone simetría respecto a y-y. Para canales, cuya
                        # simetría es respecto a x-x, la nota de E4 ordena usar Fex.
                        if perfil == "Canal":
                            x0 = entrada_magnitud(
                                "x0: centro de cortante respecto al centroide",
                                key="x0_E4", magnitud="longitud", unidad=uL,
                                valor_inicial_interno=20.0,
                            )
                            y0 = 0.0
                            Fes = res_x.Fe
                            st.caption("Canal: eje x-x de simetría; se usa Fex en E4-3.")
                        else:
                            x0 = 0.0
                            y0 = entrada_magnitud(
                                "y0: centro de cortante respecto al centroide",
                                key="y0_E4", magnitud="longitud", unidad=uL,
                                valor_inicial_interno=20.0,
                            )
                            Fes = res_y.Fe
                            st.caption("Sección monosimétrica respecto a y-y; se usa Fey en E4-3.")

                        r0 = radio_polar_centro_cortante(
                            x0=x0, y0=y0, Ix=Ix, Iy=Iy, Ag=Ag,
                        )
                        Hf = 1.0 - (x0*x0 + y0*y0) / (r0*r0)
                        Fez = ((3.141592653589793**2 * E * Cw / Lcz**2) + G*J) / (Ag*r0**2)
                        Fe4 = fe_flexotorsional_monosimetrico(Fes=Fes, Fez=Fez, H=Hf)
                        modo = "Pandeo flexotorsional"

                    else:
                        st.warning(
                            "La sección es asimétrica. E4-4 requiere longitudes efectivas "
                            "respecto a los ejes principales y las coordenadas del centro "
                            "de cortante en esos ejes. Ingrese estos datos para continuar."
                        )
                        c1, c2, c3, c4 = st.columns(4)
                        L1 = entrada_magnitud(
                            "Longitud no arriostrada L1", key="L1_E4",
                            magnitud="longitud", unidad=uL,
                            valor_inicial_interno=Lx, min_interno=0.001,
                        )
                        K1 = c2.number_input("Factor K1", min_value=0.001, value=1.0, key="K1_E4")
                        L2 = entrada_magnitud(
                            "Longitud no arriostrada L2", key="L2_E4",
                            magnitud="longitud", unidad=uL,
                            valor_inicial_interno=Ly, min_interno=0.001,
                        )
                        K2 = c4.number_input("Factor K2", min_value=0.001, value=1.0, key="K2_E4")
                        x0 = entrada_magnitud(
                            "x0 respecto al eje principal 1", key="x0_asim_E4",
                            magnitud="longitud", unidad=uL, valor_inicial_interno=0.0,
                        )
                        y0 = entrada_magnitud(
                            "y0 respecto al eje principal 2", key="y0_asim_E4",
                            magnitud="longitud", unidad=uL, valor_inicial_interno=0.0,
                        )
                        Lc1, Lc2 = K1*L1, K2*L2
                        r0 = radio_polar_centro_cortante(
                            x0=x0, y0=y0, Ix=prop.I1, Iy=prop.I2, Ag=Ag,
                        )
                        Fe1 = 3.141592653589793**2 * E / (Lc1/prop.r1)**2
                        Fe2 = 3.141592653589793**2 * E / (Lc2/prop.r2)**2
                        Fez = ((3.141592653589793**2 * E * Cw / Lcz**2) + G*J) / (Ag*r0**2)
                        Fe4 = fe_flexotorsional_asimetrico(
                            Fex=Fe1, Fey=Fe2, Fez=Fez, x0=x0, y0=y0, r0=r0,
                        )
                        modo = "Pandeo flexotorsional"

                    r4 = pandeo_torsional_o_flexotorsional(
                        modo=modo, Fe=Fe4, Fy=Fy, Ag=Ag,
                    )
                    q1, q2, q3 = st.columns(3)
                    q1.metric("Fe E4", f"{cvF(r4.Fe):.3f} {uF}")
                    q2.metric("Fn", f"{cvF(r4.Fn):.3f} {uF}")
                    q3.metric("Pn", f"{cvP(r4.Pn):.3f} {uP}")
                    st.caption(
                        f"Fn por {r4.ecuacion_fn}. Comparar Pn de E4 con Pn de E3 "
                        "y adoptar el menor."
                    )
                    e4_valido_para_comparar = True
                    if Pn_comparacion is None or r4.Pn < Pn_comparacion:
                        Pn_comparacion = r4.Pn
                        fuente_Pn_comparacion = modo
                except ValueError as exc:
                    st.error(str(exc))
    else:
        # Borra estados de widgets E4 que pudieran quedar al cambiar desde un
        # perfil para el cual sí era aplicable.
        for clave in (
            "Kz_E4", "K1_E4", "K2_E4",
            "_base_G_E4", "_unit_G_E4", "_widget_G_E4",
            "_base_Cw_E4", "_unit_Cw_E4", "_widget_Cw_E4",
            "_base_Lz_E4", "_unit_Lz_E4", "_widget_Lz_E4",
            "_base_x0_E4", "_unit_x0_E4", "_widget_x0_E4",
            "_base_y0_E4", "_unit_y0_E4", "_widget_y0_E4",
            "_base_L1_E4", "_unit_L1_E4", "_widget_L1_E4",
            "_base_L2_E4", "_unit_L2_E4", "_widget_L2_E4",
            "_base_x0_asim_E4", "_unit_x0_asim_E4", "_widget_x0_asim_E4",
            "_base_y0_asim_E4", "_unit_y0_asim_E4", "_widget_y0_asim_E4",
        ):
            st.session_state.pop(clave, None)

    if "E5" in ruta.secciones:
        with st.expander("E5 — Miembros a compresión de ángulo simple", expanded=False):
            st.warning("E5 solo es válido cuando se cumplen las condiciones de carga, conexión y ausencia de cargas transversales indicadas en la sección.")
            caso_e5 = st.selectbox("Configuración del ángulo", ["cercha", "miembro de celosía"], key="caso_E5")
            L_ra = st.number_input("L/ra", min_value=0.001, value=80.0, key="Lra_E5")
            pata_corta = st.checkbox("Conectado por la pata corta", key="pata_corta_E5")
            razon = st.number_input("Razón pata larga/pata corta", min_value=1.0, value=1.0, key="razon_E5")
            try:
                esb_e5 = esbeltez_modificada_angulo(caso=caso_e5, L_sobre_ra=L_ra, razon_patas=razon, conexion_pata_corta=pata_corta)
                st.metric("Esbeltez efectiva Lc/r según E5", f"{esb_e5:.3f}")
                Fe_e5 = 3.141592653589793**2 * E / esb_e5**2
                Fn_e5, eq_e5 = esfuerzo_nominal_compresion(Fy, Fe_e5)
                st.write(f"**Fe = {cvF(Fe_e5):.3f} {uF}**, **Fn = {cvF(Fn_e5):.3f} {uF}** por **{eq_e5}**.")
            except ValueError as exc:
                st.error(str(exc))

    if "E6" in ruta.secciones:
        with st.expander("E6 — Miembros armados por dos perfiles", expanded=False):
            st.info("Esta sección corresponde a dos perfiles unidos mediante conectores intermedios; no es la fabricación de un cajón con cuatro placas continuas.")
            tipo_con = st.selectbox("Conectores intermedios", ["pernos snug-tight", "soldado o pernos pretensionados"], key="con_E6")
            esb_global = st.number_input("Esbeltez global (Lc/r)o", min_value=0.001, value=max(Lcx/rx,Lcy/ry), key="esb_global_E6")
            a_e6 = entrada_magnitud("Separación entre conectores a", key="a_E6", magnitud="longitud", unidad=uL, valor_inicial_interno=300.0, min_interno=0.001)
            ri_e6 = entrada_magnitud("Radio mínimo del componente individual ri", key="ri_E6", magnitud="longitud", unidad=uL, valor_inicial_interno=20.0, min_interno=0.001)
            Ki_e6 = st.number_input("Ki", min_value=0.001, value=0.50, key="Ki_E6", help="0.50 ángulos espalda con espalda; 0.75 canales; 0.86 otros casos.")
            try:
                esb_mod, eq_e6 = esbeltez_modificada_builtup(tipo_conector=tipo_con, esbeltez_global=esb_global, a=a_e6, ri=ri_e6, Ki=Ki_e6)
                st.metric("Esbeltez modificada (Lc/r)m", f"{esb_mod:.3f}")
                st.caption(f"Calculada con {eq_e6}.")
            except ValueError as exc:
                st.error(str(exc))

    if ruta.tiene_elementos_esbeltos:
        with st.expander("E7 — Miembros con elementos esbeltos", expanded=True):
            st.info("E7 usa Fn obtenido de E3 o E4. Seleccione el menor Fn global antes de calcular el área efectiva.")
            Fn_global = entrada_magnitud("Fn global para E7", key="Fn_E7", magnitud="esfuerzo", unidad=uF, valor_inicial_interno=min(res_x.Fn,res_y.Fn), min_interno=0.001)
            if perfil == "Tubo circular":
                try:
                    Ae,eq=area_efectiva_tubo_circular(D=geo["D"],t=geo["t"],E=E,Fy=Fy,Ag=Ag)
                    st.write(f"**Ae = {cvL(Ae,2):.3f} {uA}** por **{eq}**")
                    Pn_e7 = Fn_global * Ae
                    Pn_comparacion = Pn_e7
                    fuente_Pn_comparacion = "E7 — área efectiva"
                    e7_valido_para_comparar = True
                    st.metric("Pn = Fn·Ae",f"{cvP(Pn_e7):.3f} {uP}")
                except ValueError as exc:
                    st.error(str(exc))
            else:
                elementos=[]
                for i,r in enumerate(resultados):
                    if r.clasificacion != "ESBELTO":
                        continue
                    b_el, t_el, mult = datos_fisicos_e7(perfil, r.elemento, geo, cubreplacas_grafico, fabricacion)
                    with st.container(border=True):
                        st.markdown(f"**{r.elemento}**")
                        c1, c2, c3 = st.columns(3)
                        c1.metric("b físico", f"{cvL(b_el):.3f} {uL}")
                        c2.metric("t físico", f"{cvL(t_el):.3f} {uL}")
                        c3.metric("Cantidad equivalente", str(mult))
                        if "Pared" in r.elemento and perfil in {"Tubo cuadrado","Tubo rectangular"}:
                            tipo_e7="pared de tubo cuadrado o rectangular"
                        elif r.condicion_borde == "Rigidizado":
                            tipo_e7="rigidizado excepto pared de tubo"
                        else:
                            tipo_e7="otro elemento"
                        be,Fel,c1e,eq=ancho_efectivo_e7(b=b_el,t=t_el,lambda_r=r.lambda_r,Fy=Fy,Fn=Fn_global,tipo_elemento=tipo_e7)
                        st.caption(f"Tipo E7.1: {tipo_e7}; be = {cvL(be):.3f} {uL}; Fel = {cvF(Fel):.3f} {uF}; {eq}.")
                        elementos.append({"nombre":r.elemento,"b":b_el,"t":t_el,"be":be,"multiplicidad":mult})
                if elementos:
                    try:
                        Ae,detalle=area_efectiva_desde_elementos(Ag=Ag,elementos=elementos)
                        st.metric("Área efectiva Ae",f"{cvL(Ae,2):.3f} {uA}")
                        Pn_e7 = Fn_global * Ae
                        Pn_comparacion = Pn_e7
                        fuente_Pn_comparacion = "E7 — área efectiva"
                        e7_valido_para_comparar = True
                        st.metric("Resistencia nominal Pn = Fn·Ae",f"{cvP(Pn_e7):.3f} {uP}")
                    except ValueError as exc:
                        st.error(str(exc))

    comparacion_axial_completa = (
        Pn_comparacion is not None
        and e4_valido_para_comparar
        and e7_valido_para_comparar
        and "E5" not in ruta.secciones
        and "E6" not in ruta.secciones
    )
    if comparacion_axial_completa:
        firma = _firma_modelo(
            perfil=perfil, E=E, Fy=Fy, geo=geo,
            fabricacion=fabricacion, cubreplacas=cubreplacas_grafico,
        )
        datos_axiales = {
            "firma": firma,
            "perfil": perfil,
            "Pn": float(Pn_comparacion),
            "LRFD": float(0.90 * Pn_comparacion),
            "ASD": float(Pn_comparacion / 1.67),
            "fuente": fuente_Pn_comparacion,
        }
        if res_x is not None:
            datos_axiales.update({
                "Pn_x_E3": float(res_x.Pn),
                "LRFD_x_E3": float(0.90 * res_x.Pn),
                "ASD_x_E3": float(res_x.Pn / 1.67),
            })
        if res_y is not None:
            datos_axiales.update({
                "Pn_y_E3": float(res_y.Pn),
                "LRFD_y_E3": float(0.90 * res_y.Pn),
                "ASD_y_E3": float(res_y.Pn / 1.67),
            })
        if "Lcx" in locals():
            datos_axiales["Lcx"] = float(Lcx)
        if "Lcy" in locals():
            datos_axiales["Lcy"] = float(Lcy)
        if "Lcz" in locals():
            datos_axiales["Lcz"] = float(Lcz)
        _guardar_capacidad("_capacidad_axial_compresion", datos_axiales)

        with st.expander("Verificación de la solicitación axial", expanded=False):
            st.caption(f"Capacidad nominal adoptada para comparar: {fuente_Pn_comparacion}.")
            metodo_e = st.radio(
                "Método de diseño para la comparación", ["LRFD", "ASD"],
                horizontal=True, key=f"E_metodo_demanda_{perfil}",
                help=(
                    "LRFD compara Pu con ϕcPn usando ϕc=0.90. "
                    "ASD compara Pa con Pn/Ωc usando Ωc=1.67. "
                    "Este bloque no modifica los cálculos del Capítulo E."
                ),
            )
            comparar_e = st.checkbox(
                "Comparar con una carga axial requerida", value=False,
                key=f"E_comparar_demanda_{perfil}",
            )
            if comparar_e:
                etiqueta_p = "Carga axial requerida Pu" if metodo_e == "LRFD" else "Carga axial requerida Pa"
                Preq = entrada_magnitud(
                    etiqueta_p, key=f"E_Preq_{perfil}_{metodo_e}", magnitud="fuerza",
                    unidad=uP, valor_inicial_interno=100_000.0, min_interno=0.0,
                    help=(
                        "Ingrese la compresión solicitante. Use combinaciones factorizadas para LRFD "
                        "y combinaciones de servicio para ASD."
                    ),
                )
                capacidad_e = 0.90 * Pn_comparacion if metodo_e == "LRFD" else Pn_comparacion / 1.67
                _mostrar_verificacion_solicitacion(
                    demanda=cvP(Preq), capacidad=cvP(capacidad_e), unidad=uP, metodo=metodo_e,
                    etiqueta_demanda="Demanda Pu" if metodo_e == "LRFD" else "Demanda Pa",
                    etiqueta_capacidad="Capacidad ϕcPn" if metodo_e == "LRFD" else "Capacidad Pn/Ωc",
                )
    elif Pn_comparacion is not None:
        st.caption(
            "La comparación axial se habilita cuando todos los estados límite aplicables "
            "han producido una resistencia nominal final. Revise los bloques E4, E5, E6 o E7 pendientes."
        )

# -----------------------------------------------------------------------------
# Capítulo H — fuerzas combinadas y torsión
# -----------------------------------------------------------------------------
COLUMNAS_COMBINACIONES_H = [
    "Combinacion", "Tipo_axial", "Pr", "Mrx", "Mry", "Vrx", "Vry", "Tr",
]


def _normalizar_tipo_axial(valor: object) -> str:
    texto = str(valor or "").strip().lower()
    traducciones = str.maketrans("áéíóúü", "aeiouu")
    texto = texto.translate(traducciones)
    if texto in {"compresion", "compression", "c"}:
        return "Compresión"
    if texto in {"tension", "traccion", "t", "tensile"}:
        return "Tensión"
    raise ValueError(f"Tipo_axial no reconocido: {valor!r}. Use Compresión o Tensión.")


def _tabla_inicial_h() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Combinacion": "U1", "Tipo_axial": "Compresión",
            "Pr": 0.0, "Mrx": 0.0, "Mry": 0.0,
            "Vrx": 0.0, "Vry": 0.0, "Tr": 0.0,
        }
    ], columns=COLUMNAS_COMBINACIONES_H)


def _convertir_tabla_unidades_h(
    tabla: pd.DataFrame, *, fuerza_origen: str, momento_origen: str,
    fuerza_destino: str, momento_destino: str,
) -> pd.DataFrame:
    salida = tabla.copy()
    for columna in ("Pr", "Vrx", "Vry"):
        salida[columna] = pd.to_numeric(salida[columna], errors="coerce").fillna(0.0).map(
            lambda v: desde_interno(a_interno(float(v), "fuerza", fuerza_origen), "fuerza", fuerza_destino)
        )
    for columna in ("Mrx", "Mry", "Tr"):
        salida[columna] = pd.to_numeric(salida[columna], errors="coerce").fillna(0.0).map(
            lambda v: desde_interno(a_interno(float(v), "momento", momento_origen), "momento", momento_destino)
        )
    return salida


def _crear_excel_combinaciones_h(
    tabla: pd.DataFrame, *, metodo: str, unidad_fuerza: str, unidad_momento: str,
    resultados: pd.DataFrame | None = None,
    resistencias: pd.DataFrame | None = None,
    desarrollo: pd.DataFrame | None = None,
) -> bytes:
    """Crea la plantilla o el archivo de resultados del Capítulo H."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        libro = writer.book
        fmt_titulo = libro.add_format({
            "bold": True, "font_color": "#FFFFFF", "bg_color": "#1F4E78",
            "align": "center", "valign": "vcenter", "border": 1,
        })
        fmt_celda = libro.add_format({"border": 1, "num_format": "0.0000"})
        fmt_texto = libro.add_format({"border": 1})
        fmt_nota = libro.add_format({"text_wrap": True, "valign": "top"})

        tabla_exportar = tabla[COLUMNAS_COMBINACIONES_H].copy()
        tabla_exportar.to_excel(writer, sheet_name="Combinaciones", index=False)
        ws = writer.sheets["Combinaciones"]
        ws.freeze_panes(1, 0)
        ws.set_row(0, 24, fmt_titulo)
        ws.set_column("A:A", 20, fmt_texto)
        ws.set_column("B:B", 16, fmt_texto)
        ws.set_column("C:H", 16, fmt_celda)
        ws.autofilter(0, 0, max(len(tabla_exportar), 1), len(COLUMNAS_COMBINACIONES_H) - 1)
        ws.data_validation(1, 1, 5000, 1, {
            "validate": "list", "source": ["Compresión", "Tensión"],
        })

        config = pd.DataFrame([
            ("Metodo", metodo),
            ("Unidad_fuerza", unidad_fuerza),
            ("Unidad_momento", unidad_momento),
            ("Version_norma", "AISC 360-22"),
        ], columns=["Campo", "Valor"])
        config.to_excel(writer, sheet_name="Configuracion", index=False)
        wc = writer.sheets["Configuracion"]
        wc.set_row(0, 24, fmt_titulo)
        wc.set_column("A:A", 24, fmt_texto)
        wc.set_column("B:B", 24, fmt_texto)

        instrucciones = pd.DataFrame({"Instrucciones": [
            "Cada fila debe corresponder a una combinación de carga y a una misma sección del miembro.",
            "Pr es una magnitud positiva; el sentido axial se define en Tipo_axial.",
            "Mrx y Mry se ingresan con signo. La aplicación usa la convención de compresión positiva configurada en la pestaña.",
            "Vrx, Vry y Tr pueden ingresarse con signo; las ecuaciones resistentes usan sus valores absolutos.",
            "No cambie los nombres de las columnas ni de las hojas Combinaciones y Configuracion.",
            "Las unidades de Pr, Vrx y Vry son las indicadas en Unidad_fuerza.",
            "Las unidades de Mrx, Mry y Tr son las indicadas en Unidad_momento.",
            "Use solicitaciones LRFD o ASD coherentes con el método indicado en Configuracion.",
        ]})
        instrucciones.to_excel(writer, sheet_name="Instrucciones", index=False)
        wi = writer.sheets["Instrucciones"]
        wi.set_row(0, 24, fmt_titulo)
        wi.set_column("A:A", 110, fmt_nota)
        for fila in range(1, len(instrucciones) + 1):
            wi.set_row(fila, 36)

        if resultados is not None:
            resultados.to_excel(writer, sheet_name="Resumen", index=False)
            wr = writer.sheets["Resumen"]
            wr.freeze_panes(1, 0)
            wr.set_row(0, 24, fmt_titulo)
            wr.set_column(0, max(len(resultados.columns) - 1, 0), 18)
        if resistencias is not None:
            resistencias.to_excel(writer, sheet_name="Resistencias", index=False)
            wres = writer.sheets["Resistencias"]
            wres.set_row(0, 24, fmt_titulo)
            wres.set_column(0, max(len(resistencias.columns) - 1, 0), 22)
        if desarrollo is not None:
            desarrollo.to_excel(writer, sheet_name="Desarrollo", index=False)
            wd = writer.sheets["Desarrollo"]
            wd.set_row(0, 24, fmt_titulo)
            wd.set_column(0, max(len(desarrollo.columns) - 1, 0), 22)
    return buffer.getvalue()


def _leer_excel_combinaciones_h(
    contenido: bytes, *, unidad_fuerza_actual: str, unidad_momento_actual: str,
) -> tuple[pd.DataFrame, dict[str, str]]:
    hojas = pd.read_excel(BytesIO(contenido), sheet_name=None, engine="openpyxl")
    if "Combinaciones" not in hojas:
        raise ValueError("El archivo no contiene la hoja 'Combinaciones'.")
    tabla = hojas["Combinaciones"].copy()
    faltantes = [c for c in COLUMNAS_COMBINACIONES_H if c not in tabla.columns]
    if faltantes:
        raise ValueError("Faltan las columnas: " + ", ".join(faltantes))
    tabla = tabla[COLUMNAS_COMBINACIONES_H]

    configuracion: dict[str, str] = {}
    if "Configuracion" in hojas and {"Campo", "Valor"}.issubset(hojas["Configuracion"].columns):
        for _, fila in hojas["Configuracion"].iterrows():
            if pd.notna(fila["Campo"]):
                configuracion[str(fila["Campo"]).strip()] = str(fila["Valor"]).strip()
    uf_archivo = configuracion.get("Unidad_fuerza", unidad_fuerza_actual)
    um_archivo = configuracion.get("Unidad_momento", unidad_momento_actual)
    # Valida unidades a través de los convertidores existentes.
    a_interno(1.0, "fuerza", uf_archivo)
    a_interno(1.0, "momento", um_archivo)
    tabla = _convertir_tabla_unidades_h(
        tabla, fuerza_origen=uf_archivo, momento_origen=um_archivo,
        fuerza_destino=unidad_fuerza_actual, momento_destino=unidad_momento_actual,
    )
    tabla["Combinacion"] = tabla["Combinacion"].fillna("").astype(str)
    tabla["Tipo_axial"] = tabla["Tipo_axial"].fillna("Compresión").map(_normalizar_tipo_axial)
    return tabla, configuracion


def _lado_opuesto_h(eje: str, lado: str) -> str:
    if eje == "x-x":
        return "Inferior" if lado == "Superior" else "Superior"
    return "Izquierda" if lado == "Derecha" else "Derecha"


def _capacidad_flexion_h(
    *, eje: str, momento: float, lado_positivo: str, firma: str,
    metodo: str, simetria: str,
) -> tuple[float | None, str, dict | None]:
    if abs(momento) <= 1e-12:
        return 1.0, "Sin demanda", None
    lado = lado_positivo if momento >= 0 else _lado_opuesto_h(eje, lado_positivo)
    datos = _leer_capacidad(f"_capacidad_flexion_{eje}_{lado}", firma)
    if datos is None and simetria == "Doble simetría":
        datos = _leer_capacidad(
            f"_capacidad_flexion_{eje}_{_lado_opuesto_h(eje, lado)}", firma
        )
    if datos is None:
        return None, lado, None
    return float(datos[metodo]), lado, datos


def _capacidad_cortante_h(
    *, eje: str, demanda: float, firma: str, metodo: str,
    perfil: str,
) -> tuple[float | None, dict | None]:
    if abs(demanda) <= 1e-12:
        return 1.0, None
    datos = _leer_capacidad(f"_capacidad_cortante_{eje}", firma)
    if datos is None and perfil in {"Tubo cuadrado", "Tubo circular"}:
        otro = "y-y" if eje == "x-x" else "x-x"
        datos = _leer_capacidad(f"_capacidad_cortante_{otro}", firma)
    if datos is None:
        return None, None
    return float(datos[metodo]), datos


def _fila_resistencia_h(nombre: str, datos: dict | None, metodo: str,
                        magnitud: str, unidad: str) -> dict[str, object]:
    if datos is None:
        return {"Resistencia": nombre, "Estado": "No disponible", "Valor": "—", "Fuente": "—"}
    valor = float(datos[metodo])
    return {
        "Resistencia": nombre,
        "Estado": "Disponible",
        "Valor": f"{valor_mostrado(valor, magnitud, unidad):,.4f} {unidad}",
        "Fuente": datos.get("fuente", datos.get("seccion", "—")),
    }


def _estilo_estado_h(valor: object) -> str:
    """Colorea las celdas de estado en las tablas del Capítulo H."""
    estado = str(valor).strip().upper()
    if estado == "NO CUMPLE":
        return "background-color: #fee2e2; color: #991b1b; font-weight: 700;"
    if estado in {"CUMPLE", "EVALUADA", "EVALUADA H3.2"}:
        return "background-color: #dcfce7; color: #166534; font-weight: 700;"
    if estado == "NO APLICA":
        return "background-color: #f3f4f6; color: #374151; font-weight: 700;"
    return "background-color: #fef3c7; color: #92400e; font-weight: 700;"


def _estilo_interaccion_h(valor: object) -> str:
    """Colorea la interacción de acuerdo con el límite unitario."""
    try:
        ir = float(valor)
    except (TypeError, ValueError):
        return ""
    if ir > 1.0:
        return "background-color: #fee2e2; color: #991b1b; font-weight: 700;"
    if ir > 0.95:
        return "background-color: #fef3c7; color: #92400e; font-weight: 700;"
    return "background-color: #dcfce7; color: #166534; font-weight: 700;"


def _tarjeta_estado_h(etiqueta: str, estado: str) -> None:
    """Muestra un estado con apariencia de métrica y color semántico."""
    estado_normalizado = str(estado).strip().upper()
    if estado_normalizado == "NO CUMPLE":
        fondo, borde, texto = "#fee2e2", "#ef4444", "#991b1b"
    elif estado_normalizado in {"CUMPLE", "EVALUADA", "EVALUADA H3.2"}:
        fondo, borde, texto = "#dcfce7", "#22c55e", "#166534"
    elif estado_normalizado == "NO APLICA":
        fondo, borde, texto = "#f3f4f6", "#9ca3af", "#374151"
    else:
        fondo, borde, texto = "#fef3c7", "#f59e0b", "#92400e"
    st.markdown(
        f"""
        <div style="padding:0.55rem 0.75rem;border-radius:0.55rem;
                    border-left:0.38rem solid {borde};background:{fondo};">
          <div style="font-size:0.82rem;color:#4b5563;margin-bottom:0.15rem;">
            {html.escape(etiqueta)}
          </div>
          <div style="font-size:1.65rem;line-height:1.15;font-weight:700;color:{texto};">
            {html.escape(estado_normalizado)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def mostrar_capitulo_h(
    *, perfil: str, E: float, Fy: float, geo: dict, fabricacion: str | None,
    cubreplacas: dict, prop: PropiedadesSeccion,
    unidad_fuerza: str, unidad_momento: str, unidad_longitud: str,
    unidad_esfuerzo: str,
) -> None:
    """Interfaz del Capítulo H sin recalcular E, F o G."""
    firma = _firma_modelo(
        perfil=perfil, E=E, Fy=Fy, geo=geo,
        fabricacion=fabricacion, cubreplacas=cubreplacas,
    )
    simetria = determinar_simetria_perfil(perfil, geo, cubreplacas)
    es_hss = perfil in {"Tubo cuadrado", "Tubo rectangular", "Tubo circular"}

    st.info(
        "El Capítulo H reutiliza las resistencias disponibles almacenadas por las pestañas "
        "de carga axial, flexión y cortante. No modifica ni repite sus ecuaciones. Para "
        "guardar las capacidades de ambos ejes, cambie el eje y el lado comprimido en la "
        "barra lateral y permita que las pestañas correspondientes se recalculen."
    )

    metodo = st.radio(
        "Método de diseño para todas las combinaciones",
        ["LRFD", "ASD"], horizontal=True, key="H_metodo",
        help="Todas las solicitaciones y resistencias de la tabla deben corresponder al mismo método.",
    )

    st.subheader("Convención de signos de los momentos")
    c1, c2 = st.columns(2)
    lado_mx_positivo = c1.selectbox(
        "Mx positivo comprime el lado", ["Superior", "Inferior"], key="H_lado_mx_positivo",
    )
    lado_my_positivo = c2.selectbox(
        "My positivo comprime el lado", ["Derecha", "Izquierda"], key="H_lado_my_positivo",
    )
    st.caption(
        "Los signos de Mrx y Mry se usan únicamente para elegir la resistencia del lado "
        "comprimido. Las ecuaciones H1-1 y H3-6 toman las razones como positivas."
    )

    # Mantiene los valores físicos cuando el usuario cambia las unidades visibles.
    unidades_actuales = (unidad_fuerza, unidad_momento)
    if "H_tabla_combinaciones" not in st.session_state:
        st.session_state["H_tabla_combinaciones"] = _tabla_inicial_h()
        st.session_state["H_unidades_tabla"] = unidades_actuales
    elif st.session_state.get("H_unidades_tabla") != unidades_actuales:
        uf_ant, um_ant = st.session_state.get("H_unidades_tabla", unidades_actuales)
        st.session_state["H_tabla_combinaciones"] = _convertir_tabla_unidades_h(
            st.session_state["H_tabla_combinaciones"],
            fuerza_origen=uf_ant, momento_origen=um_ant,
            fuerza_destino=unidad_fuerza, momento_destino=unidad_momento,
        )
        st.session_state.pop("H_editor_combinaciones", None)
        st.session_state["H_unidades_tabla"] = unidades_actuales

    plantilla = _crear_excel_combinaciones_h(
        _tabla_inicial_h(), metodo=metodo,
        unidad_fuerza=unidad_fuerza, unidad_momento=unidad_momento,
    )
    st.download_button(
        "Descargar plantilla Excel de combinaciones",
        data=plantilla,
        file_name="plantilla_combinaciones_capitulo_H.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="H_descargar_plantilla",
    )

    archivo = st.file_uploader(
        "Cargar combinaciones desde Excel", type=["xlsx"], key="H_archivo_excel",
        help="Use la plantilla descargable para conservar nombres de hojas, columnas y unidades.",
    )
    if archivo is not None:
        contenido = archivo.getvalue()
        huella = hashlib.sha256(contenido).hexdigest()
        if st.session_state.get("H_archivo_huella") != huella:
            try:
                tabla_archivo, config_archivo = _leer_excel_combinaciones_h(
                    contenido,
                    unidad_fuerza_actual=unidad_fuerza,
                    unidad_momento_actual=unidad_momento,
                )
                st.session_state["H_tabla_combinaciones"] = tabla_archivo
                st.session_state.pop("H_editor_combinaciones", None)
                st.session_state["H_archivo_huella"] = huella
                st.session_state["H_config_archivo"] = config_archivo
                st.success("El archivo fue leído y sus datos se copiaron a la tabla editable.")
            except (ValueError, KeyError, TypeError) as exc:
                st.error(str(exc))
        config_archivo = st.session_state.get("H_config_archivo", {})
        metodo_archivo = config_archivo.get("Metodo")
        if metodo_archivo in {"LRFD", "ASD"} and metodo_archivo != metodo:
            st.warning(
                f"El archivo indica método {metodo_archivo}, pero la pestaña está configurada como {metodo}. "
                "Cambie el método antes de calcular para mantener consistencia."
            )

    st.subheader("Solicitaciones combinadas")
    st.caption(
        f"Pr, Vrx y Vry se ingresan en {unidad_fuerza}; Mrx, Mry y Tr en {unidad_momento}. "
        "Puede agregar o eliminar filas."
    )
    tabla_editada = st.data_editor(
        st.session_state["H_tabla_combinaciones"],
        num_rows="dynamic", use_container_width=True, hide_index=True,
        key="H_editor_combinaciones",
        column_config={
            "Combinacion": st.column_config.TextColumn("Combinación", required=True),
            "Tipo_axial": st.column_config.SelectboxColumn(
                "Tipo axial", options=["Compresión", "Tensión"], required=True,
            ),
            "Pr": st.column_config.NumberColumn(f"Pr [{unidad_fuerza}]", format="%.4f"),
            "Mrx": st.column_config.NumberColumn(f"Mrx [{unidad_momento}]", format="%.4f"),
            "Mry": st.column_config.NumberColumn(f"Mry [{unidad_momento}]", format="%.4f"),
            "Vrx": st.column_config.NumberColumn(f"Vrx [{unidad_fuerza}]", format="%.4f"),
            "Vry": st.column_config.NumberColumn(f"Vry [{unidad_fuerza}]", format="%.4f"),
            "Tr": st.column_config.NumberColumn(f"Tr [{unidad_momento}]", format="%.4f"),
        },
    )
    st.session_state["H_tabla_combinaciones"] = tabla_editada[COLUMNAS_COMBINACIONES_H].copy()

    archivo_tabla = _crear_excel_combinaciones_h(
        st.session_state["H_tabla_combinaciones"], metodo=metodo,
        unidad_fuerza=unidad_fuerza, unidad_momento=unidad_momento,
    )
    st.download_button(
        "Descargar tabla actual",
        data=archivo_tabla,
        file_name="combinaciones_capitulo_H.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="H_descargar_tabla_actual",
    )

    axial = _leer_capacidad("_capacidad_axial_compresion", firma)
    capacidades_flexion = {
        ("x-x", "Superior"): _leer_capacidad("_capacidad_flexion_x-x_Superior", firma),
        ("x-x", "Inferior"): _leer_capacidad("_capacidad_flexion_x-x_Inferior", firma),
        ("y-y", "Derecha"): _leer_capacidad("_capacidad_flexion_y-y_Derecha", firma),
        ("y-y", "Izquierda"): _leer_capacidad("_capacidad_flexion_y-y_Izquierda", firma),
    }
    cortante_x = _leer_capacidad("_capacidad_cortante_x-x", firma)
    cortante_y = _leer_capacidad("_capacidad_cortante_y-y", firma)

    st.subheader("Resistencias disponibles recuperadas")
    filas_cap = [_fila_resistencia_h("Compresión Pc", axial, metodo, "fuerza", unidad_fuerza)]
    for (eje_cap, lado_cap), datos in capacidades_flexion.items():
        filas_cap.append(_fila_resistencia_h(
            f"Flexión {eje_cap} — {lado_cap}", datos, metodo, "momento", unidad_momento
        ))
    filas_cap.append(_fila_resistencia_h("Cortante x-x", cortante_x, metodo, "fuerza", unidad_fuerza))
    filas_cap.append(_fila_resistencia_h("Cortante y-y", cortante_y, metodo, "fuerza", unidad_fuerza))
    st.dataframe(filas_cap, use_container_width=True, hide_index=True)

    torsion_hss = None
    if es_hss:
        st.subheader("H3.1 — Resistencia a torsión del HSS")
        try:
            if perfil == "Tubo circular":
                L_torsion = entrada_magnitud(
                    "Longitud del miembro L para H3-2a",
                    key="H_L_torsion_circular", magnitud="longitud", unidad=unidad_longitud,
                    valor_inicial_interno=3000.0, min_interno=0.001,
                    help="Longitud L utilizada por H3-2a para el HSS circular.",
                )
                torsion_hss = calcular_torsion_hss_circular(
                    E=E, Fy=Fy, D=geo["D"], t=geo["t"], L=L_torsion,
                )
            else:
                descuento = 3.0 * geo["t"] if fabricacion == "Rolled" else 2.0 * geo["t"]
                h_plano = max(geo["B"], geo["H"]) - descuento
                torsion_hss = calcular_torsion_hss_rectangular(
                    E=E, Fy=Fy, B=geo["B"], H=geo["H"], t=geo["t"], h_plano=h_plano,
                )
            ct1, ct2, ct3, ct4 = st.columns(4)
            ct1.metric("Fcr", f"{valor_mostrado(torsion_hss.Fcr, 'esfuerzo', unidad_esfuerzo):,.4f} {unidad_esfuerzo}")
            ct2.metric("C", f"{valor_mostrado(torsion_hss.C, 'longitud', unidad_longitud, 3):,.4f} {unidad_propiedad(unidad_longitud, 3)}")
            ct3.metric("Tn", f"{valor_mostrado(torsion_hss.Tn, 'momento', unidad_momento):,.4f} {unidad_momento}")
            Tc_mostrado = torsion_hss.phi_Tn if metodo == "LRFD" else torsion_hss.Tn_sobre_omega
            ct4.metric("Tc disponible", f"{valor_mostrado(Tc_mostrado, 'momento', unidad_momento):,.4f} {unidad_momento}")
            st.caption(
                f"Fcr por {torsion_hss.ecuacion_Fcr}; ϕT={PHI_T:.2f} y ΩT={OMEGA_T:.2f}."
            )
            for nota in torsion_hss.observaciones:
                st.caption(nota)
        except (ValueError, ZeroDivisionError) as exc:
            st.error(str(exc))
            torsion_hss = None
    else:
        st.subheader("H3.3 — Torsión en miembros no HSS")
        tabla_actual_h = st.session_state.get("H_tabla_combinaciones", _tabla_inicial_h())
        tr_actual = pd.to_numeric(tabla_actual_h.get("Tr", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        hay_torsion_abierta = bool((tr_actual.abs() > 1e-12).any())
        if hay_torsion_abierta:
            st.warning(
                "Se detectaron combinaciones con torsión en un perfil abierto. La interacción "
                "axial–flexión se evaluará mediante H1 cuando sea aplicable, pero el resultado "
                "general quedará como VERIFICACIÓN INCOMPLETA mientras H3.3 permanezca pendiente. "
                "Los esfuerzos por torsión no uniforme y alabeo pueden obtenerse con IDEA StatiCa "
                "Member u otro software que considere explícitamente esos efectos."
            )
        else:
            st.info(
                "Las combinaciones actuales tienen Tr = 0; por tanto, H3.3 no aplica. Ingrese cero "
                "únicamente cuando el análisis estructural indique que no existe torsión en el elemento."
            )
        usar_h33 = st.checkbox(
            "Mostrar criterios resistentes informativos de H3.3",
            key="H_mostrar_h33",
            help=(
                "Muestra Fy, 0.6Fy y Fcr como límites nominales de esfuerzo. Estos valores no son "
                "una capacidad torsional Tc y, por sí solos, no permiten comparar directamente Tr."
            ),
        )
        if usar_h33:
            Fcr_h33 = entrada_magnitud(
                "Fcr obtenido del análisis torsional",
                key="H_Fcr_h33", magnitud="esfuerzo", unidad=unidad_esfuerzo,
                valor_inicial_interno=0.6 * Fy, min_interno=0.001,
                help=(
                    "Fcr debe proceder de un análisis torsional y de estabilidad compatible con las "
                    "restricciones reales de giro y alabeo del miembro."
                ),
            )
            h33 = verificar_h33_manual(Fy=Fy, Fcr=Fcr_h33)
            st.dataframe([
                {"Estado límite": "Fluencia normal", "Ecuación": "H3-7", "Fn": valor_mostrado(h33.Fn_normal, "esfuerzo", unidad_esfuerzo)},
                {"Estado límite": "Fluencia por cortante", "Ecuación": "H3-8", "Fn": valor_mostrado(h33.Fn_cortante, "esfuerzo", unidad_esfuerzo)},
                {"Estado límite": "Pandeo", "Ecuación": "H3-9", "Fn": valor_mostrado(h33.Fn_pandeo, "esfuerzo", unidad_esfuerzo)},
            ], use_container_width=True, hide_index=True)
            st.caption(f"Límite nominal gobernante: {h33.estado_gobernante}.")
            st.info(
                "Estos valores son límites de esfuerzo y no constituyen una resistencia torsional Tc. "
                "La verificación H3.3 requiere además los esfuerzos demandantes por torsión y alabeo, "
                "obtenidos mediante IDEA StatiCa Member u otro software de análisis torsional especializado."
            )

    tiene_agujeros = st.checkbox(
        "Existen agujeros de pernos en patines sometidos a tensión",
        value=False, key="H_agujeros_patines",
        help="Activa la ruta adicional H4 para combinaciones con tensión axial y flexión alrededor de x-x.",
    )

    tabla = st.session_state["H_tabla_combinaciones"].copy()
    resultados_salida: list[dict[str, object]] = []
    desarrollo_salida: list[dict[str, object]] = []

    for indice, fila in tabla.iterrows():
        rutas: tuple[str, ...] = ()
        nombre = str(fila.get("Combinacion", "")).strip()
        if not nombre:
            continue
        try:
            tipo_axial = _normalizar_tipo_axial(fila.get("Tipo_axial", "Compresión"))
            valores = {}
            for col in ("Pr", "Mrx", "Mry", "Vrx", "Vry", "Tr"):
                valor = pd.to_numeric(pd.Series([fila.get(col, 0.0)]), errors="coerce").iloc[0]
                if pd.isna(valor):
                    raise ValueError(f"{nombre}: la celda {col} no contiene un número válido.")
                valores[col] = float(valor)
            Pr = abs(a_interno(valores["Pr"], "fuerza", unidad_fuerza))
            Mrx = a_interno(valores["Mrx"], "momento", unidad_momento)
            Mry = a_interno(valores["Mry"], "momento", unidad_momento)
            Vrx = a_interno(valores["Vrx"], "fuerza", unidad_fuerza)
            Vry = a_interno(valores["Vry"], "fuerza", unidad_fuerza)
            Tr = a_interno(valores["Tr"], "momento", unidad_momento)

            rutas = ruta_capitulo_h(
                simetria=simetria, es_hss=es_hss, tiene_torsion=abs(Tr) > 1e-12,
                tiene_agujeros_patines=tiene_agujeros, axial_tension=tipo_axial == "Tensión",
            )

            if tipo_axial == "Tensión" and Pr > 1e-12:
                raise ValueError(
                    "La resistencia axial a tensión del Capítulo D todavía no está disponible en las otras pestañas. "
                    "La combinación se conserva, pero no puede aprobarse con una capacidad de compresión."
                )
            Pc = float(axial[metodo]) if axial is not None else (1.0 if Pr <= 1e-12 else 0.0)
            if Pr > 1e-12 and axial is None:
                raise ValueError("No existe una resistencia disponible a compresión del Capítulo E para el perfil actual.")

            Mcx, lado_x, datos_mx = _capacidad_flexion_h(
                eje="x-x", momento=Mrx, lado_positivo=lado_mx_positivo,
                firma=firma, metodo=metodo, simetria=simetria,
            )
            Mcy, lado_y, datos_my = _capacidad_flexion_h(
                eje="y-y", momento=Mry, lado_positivo=lado_my_positivo,
                firma=firma, metodo=metodo, simetria=simetria,
            )
            if Mcx is None:
                raise ValueError(f"Falta calcular la resistencia a flexión x-x con el lado {lado_x} comprimido.")
            if Mcy is None:
                raise ValueError(f"Falta calcular la resistencia a flexión y-y con el lado {lado_y} comprimido.")

            if simetria == "Asimétrica":
                raise ValueError(
                    "H2-1 requiere esfuerzos disponibles en los ejes principales y en los puntos críticos. "
                    "Las resistencias geométricas x-x/y-y almacenadas no sustituyen esa evaluación."
                )

            resultado = None
            ruta_usada = "H1"
            estado_h33 = "NO APLICA"
            verificacion_incompleta_h33 = False
            if es_hss and abs(Tr) > 1e-12:
                if torsion_hss is None:
                    raise ValueError("No se pudo determinar la resistencia torsional Tc del HSS.")
                Tc = torsion_hss.phi_Tn if metodo == "LRFD" else torsion_hss.Tn_sobre_omega
                rt = abs(Tr) / Tc
                if rt <= 0.20 + 1e-12:
                    resultado = calcular_h11(Pr=Pr, Pc=Pc, Mrx=Mrx, Mcx=Mcx, Mry=Mry, Mcy=Mcy)
                    ruta_usada = "H3.2 → H1"
                    observacion_torsion = f"Tr/Tc={rt:.4f} ≤ 0.20; la torsión se omitió en la interacción."
                else:
                    Vcx, datos_vx = _capacidad_cortante_h(
                        eje="x-x", demanda=Vrx, firma=firma, metodo=metodo, perfil=perfil,
                    )
                    Vcy, datos_vy = _capacidad_cortante_h(
                        eje="y-y", demanda=Vry, firma=firma, metodo=metodo, perfil=perfil,
                    )
                    if Vcx is None:
                        raise ValueError("Falta calcular la resistencia a cortante x-x requerida por H3-6.")
                    if Vcy is None:
                        raise ValueError("Falta calcular la resistencia a cortante y-y requerida por H3-6.")
                    resultado = calcular_h36(
                        Pr=Pr, Pc=Pc, Mrx=Mrx, Mcx=Mcx, Mry=Mry, Mcy=Mcy,
                        Vrx=Vrx, Vcx=Vcx, Vry=Vry, Vcy=Vcy, Tr=Tr, Tc=Tc,
                    )
                    ruta_usada = "H3.2"
                    observacion_torsion = f"Tr/Tc={rt:.4f} > 0.20; se aplicó H3-6."
            elif abs(Tr) > 1e-12:
                resultado = calcular_h11(Pr=Pr, Pc=Pc, Mrx=Mrx, Mcx=Mcx, Mry=Mry, Mcy=Mcy)
                ruta_usada = "H1 + H3.3 pendiente"
                estado_h33 = "PENDIENTE"
                verificacion_incompleta_h33 = True
                observacion_torsion = (
                    "La interacción axial–flexión fue evaluada mediante H1. La combinación contiene "
                    "torsión y el elemento es un perfil abierto, por lo que falta completar H3.3. "
                    "Los esfuerzos por torsión no uniforme y alabeo pueden obtenerse mediante IDEA StatiCa "
                    "Member u otro software que considere explícitamente estos efectos."
                )
            else:
                resultado = calcular_h11(Pr=Pr, Pc=Pc, Mrx=Mrx, Mcx=Mcx, Mry=Mry, Mcy=Mcy)
                observacion_torsion = "Sin torsión requerida; H3.3 no aplica."

            if tiene_agujeros and tipo_axial == "Tensión" and (abs(Mrx) > 1e-12 or Pr > 1e-12):
                raise ValueError(
                    "H4 fue identificado, pero requiere Pc de rotura a tensión según D2(b) y Mcx de F13.1 "
                    "para cada patín. La capacidad del Capítulo D aún no está disponible."
                )

            ir = float(resultado.interaccion)
            estado_interaccion = "CUMPLE" if ir <= 1.0 else "NO CUMPLE"
            if verificacion_incompleta_h33 and estado_interaccion == "CUMPLE":
                estado_general = "VERIFICACIÓN INCOMPLETA"
            else:
                estado_general = estado_interaccion
            resultados_salida.append({
                "Combinación": nombre,
                "Tipo axial": tipo_axial,
                "Ruta": ruta_usada,
                "Ecuación": resultado.ecuacion,
                "Interacción": ir,
                "Estado interacción": estado_interaccion,
                "Estado H3.3": estado_h33,
                "Estado": estado_general,
                "Lado Mx": lado_x,
                "Lado My": lado_y,
                "Observación": observacion_torsion,
            })
            for termino, valor in resultado.terminos.items():
                desarrollo_salida.append({
                    "Combinación": nombre, "Ruta": ruta_usada,
                    "Ecuación": resultado.ecuacion, "Término": termino,
                    "Valor": valor,
                })
        except (ValueError, KeyError, ZeroDivisionError) as exc:
            resultados_salida.append({
                "Combinación": nombre,
                "Tipo axial": str(fila.get("Tipo_axial", "")),
                "Ruta": " / ".join(rutas) if "rutas" in locals() else "—",
                "Ecuación": "—",
                "Interacción": None,
                "Estado interacción": "NO EVALUADA",
                "Estado H3.3": "NO DETERMINADO",
                "Estado": "NO EVALUADA",
                "Lado Mx": "—",
                "Lado My": "—",
                "Observación": str(exc),
            })

    st.subheader("Resultados del Capítulo H")
    if not resultados_salida:
        st.warning("No existen combinaciones con nombre para evaluar.")
        return
    df_resultados = pd.DataFrame(resultados_salida)
    columnas_estado_h = [
        columna for columna in ("Estado interacción", "Estado H3.3", "Estado")
        if columna in df_resultados.columns
    ]
    tabla_resultados_estilizada = (
        df_resultados.style
        .map(_estilo_estado_h, subset=columnas_estado_h)
        .map(_estilo_interaccion_h, subset=["Interacción"])
    )
    st.dataframe(tabla_resultados_estilizada, use_container_width=True, hide_index=True)

    evaluados = df_resultados[pd.to_numeric(df_resultados["Interacción"], errors="coerce").notna()].copy()
    if not evaluados.empty:
        idx_gob = pd.to_numeric(evaluados["Interacción"], errors="coerce").idxmax()
        gob = evaluados.loc[idx_gob]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Combinación gobernante", str(gob["Combinación"]))
        c2.metric("Ruta", str(gob["Ruta"]))
        c3.metric("Interacción", f"{float(gob['Interacción']):,.4f}")
        with c4:
            _tarjeta_estado_h("Estado", str(gob["Estado"]))
        estados_generales = set(df_resultados["Estado"].astype(str).str.upper())
        if "NO CUMPLE" in estados_generales:
            st.error("Al menos una combinación no cumple la interacción calculada del Capítulo H.")
        elif "VERIFICACIÓN INCOMPLETA" in estados_generales:
            st.warning(
                "Las interacciones axial–flexión disponibles cumplen, pero existen combinaciones con "
                "torsión en perfiles abiertos y la comprobación H3.3 está pendiente. Complete el análisis "
                "con IDEA StatiCa Member u otro software que considere torsión no uniforme y alabeo."
            )
        elif "NO EVALUADA" in estados_generales:
            st.warning("Existen combinaciones que no pudieron evaluarse por falta de resistencias o datos requeridos.")
        elif float(gob["Interacción"]) > 0.95:
            st.warning("La combinación gobernante cumple, pero se encuentra próxima al límite.")
        else:
            st.success("Las combinaciones evaluadas cumplen el Capítulo H.")

    for fila_resultado in resultados_salida:
        estado_fila = str(fila_resultado["Estado"])
        icono_estado = "🟢" if estado_fila == "CUMPLE" else ("🔴" if estado_fila == "NO CUMPLE" else "🟠")
        with st.expander(
            f"{icono_estado} {fila_resultado['Combinación']} — {estado_fila}", expanded=False
        ):
            ce1, ce2, ce3 = st.columns(3)
            with ce1:
                _tarjeta_estado_h("Interacción calculada", str(fila_resultado.get("Estado interacción", "—")))
            with ce2:
                _tarjeta_estado_h("H3.3", str(fila_resultado.get("Estado H3.3", "—")))
            with ce3:
                _tarjeta_estado_h("Resultado general", estado_fila)
            st.write(f"**Ruta:** {fila_resultado['Ruta']} · **Ecuación:** {fila_resultado['Ecuación']}")
            if fila_resultado["Interacción"] is not None:
                st.metric("Interacción", f"{float(fila_resultado['Interacción']):,.4f}")
                detalle = [x for x in desarrollo_salida if x["Combinación"] == fila_resultado["Combinación"]]
                if detalle:
                    st.dataframe(detalle, use_container_width=True, hide_index=True)
            if str(fila_resultado.get("Estado H3.3", "")).upper() == "PENDIENTE":
                st.warning(str(fila_resultado["Observación"]))
            else:
                st.caption(str(fila_resultado["Observación"]))

    resistencias_exportar = pd.DataFrame(filas_cap)
    desarrollo_exportar = pd.DataFrame(desarrollo_salida)
    archivo_resultados = _crear_excel_combinaciones_h(
        tabla, metodo=metodo, unidad_fuerza=unidad_fuerza,
        unidad_momento=unidad_momento, resultados=df_resultados,
        resistencias=resistencias_exportar,
        desarrollo=desarrollo_exportar,
    )
    st.download_button(
        "Descargar resultados del Capítulo H",
        data=archivo_resultados,
        file_name="resultados_capitulo_H.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="H_descargar_resultados",
    )


# -----------------------------------------------------------------------------
# Barra lateral
# -----------------------------------------------------------------------------
st.sidebar.title("Datos del perfil")

with st.sidebar.expander("Unidades", expanded=True):
    unidad_longitud = st.selectbox("Longitud", ["mm", "cm", "m", "in", "ft"], index=0)
    unidad_esfuerzo = st.selectbox("Esfuerzo", ["MPa", "kPa", "kgf/cm²", "ksi"], index=0)
    unidad_fuerza = st.selectbox("Fuerza", ["N", "kN", "kgf", "tf", "kip"], index=1)
    unidad_momento = st.selectbox(
        "Momento",
        ["N·mm", "N·m", "kN·m", "kgf·m", "tf·m", "kip·in", "kip·ft"],
        index=2,
    )
    st.caption(
        "Los cálculos internos usan mm, MPa, N y N·mm. Al cambiar una unidad, "
        "los valores ya ingresados se convierten automáticamente."
    )

with st.sidebar.expander("Configuración general", expanded=True):
    perfil = st.selectbox("Tipo de perfil", [
        "Perfil I", "Perfil I asimétrico", "Canal", "Tee", "Ángulo simple", "Ángulo doble con separadores",
        "Tubo cuadrado", "Tubo rectangular", "Tubo circular",
    ])
    eje = st.radio("Eje de análisis", ["x-x", "y-y"], help="Se conserva para flexión y flexocompresión.")
    if eje == "x-x":
        lado_compresion = st.radio(
            "Lado en compresión para flexión",
            ["Superior", "Inferior"],
            help="Permite identificar el patín o cubreplaca comprimida en la Tabla B4.1b.",
        )
    else:
        lado_compresion = st.radio(
            "Lado en compresión para flexión",
            ["Derecha", "Izquierda"],
            help="Permite identificar el lado comprimido en flexión alrededor de y-y.",
        )

with st.sidebar.expander("Material", expanded=False):
    E = entrada_magnitud(
        "Módulo de elasticidad E", key="material_E", magnitud="esfuerzo",
        unidad=unidad_esfuerzo, valor_inicial_interno=200000.0, min_interno=0.001,
    )
    Fy = entrada_magnitud(
        "Esfuerzo de fluencia Fy", key="material_Fy", magnitud="esfuerzo",
        unidad=unidad_esfuerzo, valor_inicial_interno=345.0, min_interno=0.001,
    )
    st.caption(
        f"E y Fy se muestran en {unidad_esfuerzo}; las resistencias se presentarán en {unidad_fuerza}."
    )

geo: dict[str, float] = {}
fabricacion: str | None = None
cubreplacas_grafico: dict = {}
cubreplacas_calculo: list[dict[str, object]] = []

with st.sidebar.expander("Geometría", expanded=True):
    U = unidad_longitud
    def gl(label, key, default, minimo=0.001, maximo=None):
        return entrada_magnitud(
            label, key=key, magnitud="longitud", unidad=U,
            valor_inicial_interno=default, min_interno=minimo, max_interno=maximo,
        )

    if perfil in {"Perfil I", "Perfil I asimétrico"}:
        fabricacion = st.selectbox("Fabricación", ["Rolled", "Built-up"])
        if perfil == "Perfil I":
            geo["bf"] = gl("Ancho total del patín bf", "geo_i_bf", 200.0)
            geo["tf"] = gl("Espesor del patín tf", "geo_i_tf", 12.0)
        else:
            st.markdown("**Patín superior**")
            geo["bf_superior"] = gl("Ancho bf superior", "geo_ia_bfs", 220.0)
            geo["tf_superior"] = gl("Espesor tf superior", "geo_ia_tfs", 14.0)
            st.markdown("**Patín inferior**")
            geo["bf_inferior"] = gl("Ancho bf inferior", "geo_ia_bfi", 180.0)
            geo["tf_inferior"] = gl("Espesor tf inferior", "geo_ia_tfi", 10.0)
        geo["h"] = gl("Altura libre del alma h", "geo_i_h", 450.0)
        geo["tw"] = gl("Espesor del alma tw", "geo_i_tw", 8.0)

        tiene_cp = st.checkbox("Incluir cubreplaca(s) de ala — Caso 7")
        if tiene_cp:
            ubicacion = st.selectbox("Ubicación", ["Solo superior", "Solo inferior", "Ambas alas"])
            conexion = st.selectbox("Líneas de conexión", ["Soldaduras", "Pernos"])
            iguales = True
            if ubicacion == "Ambas alas":
                iguales = st.checkbox("Cubreplacas iguales", value=True)

            if ubicacion in {"Solo superior", "Ambas alas"}:
                st.markdown("**Cubreplaca superior**")
                B_sup = gl("Ancho total Bcp — superior", "B_cp_sup", 180.0)
                b_sup = gl("Ancho entre líneas b — superior", "b_cp_sup", 160.0, maximo=B_sup)
                t_sup = gl("Espesor tcp — superior", "t_cp_sup", 10.0)
                cubreplacas_grafico["superior"] = {"B": B_sup, "b": b_sup, "t": t_sup}
                cubreplacas_calculo.append({"nombre": "Cubreplaca superior", "b": b_sup, "t": t_sup, "conexion": conexion})

            if ubicacion in {"Solo inferior", "Ambas alas"}:
                if ubicacion == "Ambas alas" and iguales:
                    B_inf, b_inf, t_inf = B_sup, b_sup, t_sup
                    st.caption("La cubreplaca inferior adopta las mismas dimensiones que la superior.")
                else:
                    st.markdown("**Cubreplaca inferior**")
                    B_inf = gl("Ancho total Bcp — inferior", "B_cp_inf", 180.0)
                    b_inf = gl("Ancho entre líneas b — inferior", "b_cp_inf", 160.0, maximo=B_inf)
                    t_inf = gl("Espesor tcp — inferior", "t_cp_inf", 10.0)
                cubreplacas_grafico["inferior"] = {"B": B_inf, "b": b_inf, "t": t_inf}
                cubreplacas_calculo.append({"nombre": "Cubreplaca inferior", "b": b_inf, "t": t_inf, "conexion": conexion})

    elif perfil == "Canal":
        fabricacion = "Rolled"
        geo["b"] = gl("Ancho saliente del patín b", "geo_c_b", 70.0)
        geo["tf"] = gl("Espesor del patín tf", "geo_c_tf", 10.0)
        geo["h"] = gl("Altura libre del alma h", "geo_c_h", 250.0)
        geo["tw"] = gl("Espesor del alma tw", "geo_c_tw", 7.0)
    elif perfil == "Tee":
        fabricacion = "Rolled"
        geo["b"] = gl("Ancho saliente de media ala b", "geo_t_b", 75.0)
        geo["tf"] = gl("Espesor del patín tf", "geo_t_tf", 12.0)
        geo["d"] = gl("Profundidad del vástago d", "geo_t_d", 150.0)
        geo["tw"] = gl("Espesor del vástago tw", "geo_t_tw", 8.0)
    elif perfil in {"Ángulo simple", "Ángulo doble con separadores"}:
        geo["b1"] = gl("Ancho de pata 1 b1", f"geo_{perfil}_b1", 75.0)
        geo["b2"] = gl("Ancho de pata 2 b2", f"geo_{perfil}_b2", 75.0)
        geo["t"] = gl("Espesor t", f"geo_{perfil}_t", 8.0)
        if perfil == "Ángulo doble con separadores":
            geo["separacion"] = gl("Separación libre entre ángulos", "geo_ad_sep", 20.0, minimo=0.0)
    elif perfil in {"Tubo cuadrado", "Tubo rectangular"}:
        fabricacion = st.selectbox("Fabricación", ["Rolled", "Built-up"], help="Rolled → caso 6; Built-up con placas soldadas → caso 8.")
        geo["B"] = gl("Ancho exterior B", f"geo_{perfil}_B", 200.0)
        if perfil == "Tubo cuadrado":
            geo["H"] = geo["B"]
            st.caption("Para tubo cuadrado se adopta H = B.")
        else:
            geo["H"] = gl("Altura exterior H", "geo_tr_H", 300.0)
        geo["t"] = gl("Espesor t", f"geo_{perfil}_t", 8.0)
    else:
        fabricacion = "Rolled"
        geo["D"] = gl("Diámetro exterior D", "geo_tc_D", 200.0)
        geo["t"] = gl("Espesor t", "geo_tc_t", 8.0)


# -----------------------------------------------------------------------------
# Propiedades geométricas automáticas
# -----------------------------------------------------------------------------
try:
    propiedades = calcular_propiedades(
        perfil,
        geo,
        fabricacion=fabricacion,
        cubreplacas=cubreplacas_grafico,
    )
except ValueError as exc:
    propiedades = None
    error_propiedades = str(exc)
else:
    error_propiedades = None

# -----------------------------------------------------------------------------
# Evaluación axial
# -----------------------------------------------------------------------------
try:
    if perfil == "Perfil I":
        resultados = evaluar_perfil_i(fabricacion=fabricacion, bf=geo["bf"], tf=geo["tf"], h=geo["h"], tw=geo["tw"], E=E, Fy=Fy, cubreplacas=cubreplacas_calculo)
    elif perfil == "Perfil I asimétrico":
        resultados = evaluar_perfil_i_asimetrico(
            fabricacion=fabricacion, bf_superior=geo["bf_superior"], tf_superior=geo["tf_superior"],
            bf_inferior=geo["bf_inferior"], tf_inferior=geo["tf_inferior"],
            h=geo["h"], tw=geo["tw"], E=E, Fy=Fy, cubreplacas=cubreplacas_calculo,
        )
    elif perfil == "Canal":
        resultados = evaluar_canal(b_ala=geo["b"], tf=geo["tf"], h=geo["h"], tw=geo["tw"], E=E, Fy=Fy)
    elif perfil == "Tee":
        resultados = evaluar_tee(b_ala=geo["b"], tf=geo["tf"], d_vastago=geo["d"], tw=geo["tw"], E=E, Fy=Fy)
    elif perfil in {"Ángulo simple", "Ángulo doble con separadores"}:
        resultados = evaluar_angulo(tipo=perfil, b1=geo["b1"], b2=geo["b2"], t=geo["t"], E=E, Fy=Fy)
    elif perfil in {"Tubo cuadrado", "Tubo rectangular"}:
        descuento = 3.0 * geo["t"] if fabricacion == "Rolled" else 2.0 * geo["t"]
        B_plano = geo["B"] - descuento
        H_plano = geo["H"] - descuento
        resultados = evaluar_tubo_rectangular(B_plano=B_plano, H_plano=H_plano, t=geo["t"], E=E, Fy=Fy, perfil=perfil, fabricacion=fabricacion)
    else:
        resultados = evaluar_tubo_circular(D=geo["D"], t=geo["t"], E=E, Fy=Fy)
except ValueError as exc:
    resultados = []
    error = str(exc)
else:
    error = None

if error is None and error_propiedades:
    error = error_propiedades

# -----------------------------------------------------------------------------
# Evaluación de clasificación local para flexión — Tabla B4.1b
# -----------------------------------------------------------------------------
if propiedades is not None:
    try:
        resultados_flexion = evaluar_flexion_b4(
            perfil=perfil,
            fabricacion=fabricacion,
            eje=eje,
            lado_compresion=lado_compresion,
            geo=geo,
            E=E,
            Fy=Fy,
            propiedades=propiedades,
            cubreplacas=cubreplacas_grafico,
        )
    except ValueError as exc:
        resultados_flexion = []
        error_flexion = str(exc)
    else:
        error_flexion = None
else:
    resultados_flexion = []
    error_flexion = error_propiedades

st.title("Verificación de perfiles estándar de acero")
st.caption(
    f"Unidades seleccionadas: longitud {unidad_longitud}, esfuerzo {unidad_esfuerzo}, "
    f"fuerza {unidad_fuerza} y momento {unidad_momento}."
)

tab_axial, tab_flexion, tab_cortante, tab_interaccion = st.tabs(["Carga axial", "Flexión", "Cortante", "Flexocompresión"])

for tab, titulo in [
    (tab_axial, "Elementos sujetos a carga axial de compresión"),
    (tab_flexion, "Elementos sujetos a flexión"),
    (tab_cortante, "Elementos sujetos a cortante"),
    (tab_interaccion, "Capítulo H — Fuerzas combinadas y torsión"),
]:
    with tab:
        st.header(titulo)
        components.html(dibujo_perfil(perfil, eje, geo, fabricacion, cubreplacas_grafico), height=455, scrolling=False)
        if propiedades is not None:
            mostrar_propiedades(propiedades, unidad_longitud)
        if tab is tab_axial:
            st.info("En esta pestaña el eje de análisis no modifica la Tabla B4.1a; se muestra y se guarda para verificaciones posteriores.")
            if error:
                st.error(error)
            elif resultados:
                mostrar_resultados(resultados)
                mostrar_ruta_y_diseno_capitulo_e(
                    perfil, resultados, E, Fy, geo, fabricacion, cubreplacas_grafico,
                    propiedades, unidad_esfuerzo, unidad_longitud, unidad_fuerza, unidad_momento,
                )
        elif tab is tab_flexion:
            st.info(
                f"Flexión alrededor de **{eje}**. Lado indicado en compresión: "
                f"**{lado_compresion}**. La clasificación se realiza únicamente con la Tabla B4.1b."
            )
            if error_flexion:
                st.error(error_flexion)
            elif resultados_flexion:
                mostrar_resultados_flexion(resultados_flexion)
                mostrar_ruta_y_diseno_capitulo_f(
                    perfil, resultados_flexion, E, Fy, geo, fabricacion,
                    cubreplacas_grafico, propiedades, eje, lado_compresion,
                    unidad_esfuerzo, unidad_longitud, unidad_fuerza, unidad_momento,
                )
        elif tab is tab_cortante:
            st.info(
                f"Cortante asociado al eje de análisis **{eje}**. La aplicación selecciona "
                "automáticamente la ruta G2–G6 según el perfil y la dirección."
            )
            if propiedades is None:
                st.error(error_propiedades or "No se pudieron calcular las propiedades geométricas.")
            else:
                mostrar_ruta_y_diseno_capitulo_g(
                    perfil, E, Fy, geo, fabricacion, cubreplacas_grafico,
                    propiedades, eje, lado_compresion,
                    unidad_esfuerzo, unidad_longitud, unidad_fuerza,
                )
        else:
            if propiedades is None:
                st.error(error_propiedades or "No se pudieron calcular las propiedades geométricas.")
            else:
                mostrar_capitulo_h(
                    perfil=perfil, E=E, Fy=Fy, geo=geo, fabricacion=fabricacion,
                    cubreplacas=cubreplacas_grafico, prop=propiedades,
                    unidad_fuerza=unidad_fuerza, unidad_momento=unidad_momento,
                    unidad_longitud=unidad_longitud,
                    unidad_esfuerzo=unidad_esfuerzo,
                )

st.caption("Herramienta de apoyo. Confirme siempre las definiciones geométricas y la edición normativa aplicable al proyecto.")
