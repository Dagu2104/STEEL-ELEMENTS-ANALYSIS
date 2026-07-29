"""Aplicación Streamlit para clasificación local de perfiles estándar de acero."""

from __future__ import annotations

import html
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
    if st.session_state.get(unit_key) != (unidad, potencia):
        st.session_state[widget_key] = desde_interno(
            st.session_state[base_key], magnitud, unidad, potencia
        )
        st.session_state[unit_key] = (unidad, potencia)
    # Ajusta el valor visible si cambian límites dinámicos, por ejemplo b <= Bcp.
    if min_interno is not None:
        minimo_visible = desde_interno(min_interno, magnitud, unidad, potencia)
        st.session_state[widget_key] = max(st.session_state[widget_key], minimo_visible)
    if max_interno is not None:
        maximo_visible = desde_interno(max_interno, magnitud, unidad, potencia)
        st.session_state[widget_key] = min(st.session_state[widget_key], maximo_visible)
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
    st.caption("Esta pestaña solo aplica la Tabla B4.1b. No calcula resistencia a flexión ni aplica el Capítulo F.")



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
    perfil, resultados, E, Fy, geo, cubreplacas_grafico, prop,
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
                    st.metric("Pn = Fn·Ae",f"{cvP(Fn_global*Ae):.3f} {uP}")
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
                        st.metric("Resistencia nominal Pn = Fn·Ae",f"{cvP(Fn_global*Ae):.3f} {uP}")
                    except ValueError as exc:
                        st.error(str(exc))

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

tab_axial, tab_flexion, tab_interaccion = st.tabs(["Carga axial", "Flexión", "Flexocompresión"])

for tab, titulo in [
    (tab_axial, "Elementos sujetos a carga axial de compresión"),
    (tab_flexion, "Elementos sujetos a flexión"),
    (tab_interaccion, "Elementos sujetos a flexocompresión"),
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
                    perfil, resultados, E, Fy, geo, cubreplacas_grafico,
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
        else:
            st.info("Las propiedades geométricas ya se calculan automáticamente. Las ecuaciones de interacción se incorporarán en un módulo posterior.")

st.caption("Herramienta de apoyo. Confirme siempre las definiciones geométricas y la edición normativa aplicable al proyecto.")
