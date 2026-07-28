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
    fe_flexotorsional_monosimetrico,
    fe_torsional_doble_simetria,
    longitud_efectiva,
    pandeo_flexional,
    pandeo_torsional_o_flexotorsional,
    radio_polar_centro_cortante,
    ruta_capitulo_e,
)


from propiedades import calcular_propiedades, PropiedadesSeccion

from funciones import (
    evaluar_angulo,
    evaluar_canal,
    evaluar_perfil_i,
    evaluar_tee,
    evaluar_tubo_circular,
    evaluar_tubo_rectangular,
)

st.set_page_config(page_title="Diseño de perfiles de acero", page_icon="🏗️", layout="wide")


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

    if perfil == "Perfil I":
        bf, tf, h, tw = geo["bf"], geo["tf"], geo["h"], geo["tw"]
        maxdim = max(bf, h + 2 * tf)
        bw = escala(bf, maxdim, 240, 80)
        th = escala(tf, maxdim, 240, 8)
        wh = escala(h, maxdim, 240, 90)
        ww = escala(tw, maxdim, 240, 6)
        x = cx - bw / 2
        y = cy - (wh + 2 * th) / 2
        rect(x, y, bw, th)
        rect(cx - ww / 2, y + th, ww, wh)
        rect(x, y + th + wh, bw, th)
        labels += [
            f'<text x="{x+bw+12:.1f}" y="{y+th/2+5:.1f}" class="label">Patín superior</text>',
            f'<text x="{cx+ww/2+12:.1f}" y="{cy+5:.1f}" class="label">Alma</text>',
            f'<text x="{x+bw+12:.1f}" y="{y+th+wh+th/2+5:.1f}" class="label">Patín inferior</text>',
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
            rect(cx-cpw/2, y+2*th+wh+4, cpw, cpt, fill_override=cp_fill)
            labels.append(f'<text x="{cx-cpw/2:.1f}" y="{y+2*th+wh+cpt+24:.1f}" class="cp-label">Cubreplaca inferior</text>')

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


def mostrar_propiedades(prop: PropiedadesSeccion, unidades_longitud: str) -> None:
    """Presenta propiedades geométricas calculadas automáticamente."""
    u = unidades_longitud
    with st.expander("Propiedades geométricas calculadas", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Área Ag", f"{prop.Ag:,.3f} {u}²")
        c2.metric("Centroide x̄", f"{prop.x_bar:,.3f} {u}")
        c3.metric("Centroide ȳ", f"{prop.y_bar:,.3f} {u}")
        c4.metric("J", f"{prop.J:,.3f} {u}⁴")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ix", f"{prop.Ix:,.3f} {u}⁴")
        c2.metric("Iy", f"{prop.Iy:,.3f} {u}⁴")
        c3.metric("Ixy", f"{prop.Ixy:,.3f} {u}⁴")
        c4.metric("Cw", "No calculado" if prop.Cw is None else f"{prop.Cw:,.3f} {u}⁶")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("rx", f"{prop.rx:,.3f} {u}")
        c2.metric("ry", f"{prop.ry:,.3f} {u}")
        c3.metric("r máximo", f"{prop.r1:,.3f} {u}")
        c4.metric("r mínimo", f"{prop.r2:,.3f} {u}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sx superior", f"{prop.Sx_sup:,.3f} {u}³")
        c2.metric("Sx inferior", f"{prop.Sx_inf:,.3f} {u}³")
        c3.metric("Sy derecha", f"{prop.Sy_der:,.3f} {u}³")
        c4.metric("Sy izquierda", f"{prop.Sy_izq:,.3f} {u}³")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Zx", f"{prop.Zx:,.3f} {u}³")
        c2.metric("Zy", f"{prop.Zy:,.3f} {u}³")
        c3.metric("I principal mayor", f"{prop.I1:,.3f} {u}⁴")
        c4.metric("I principal menor", f"{prop.I2:,.3f} {u}⁴")

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



def mostrar_ruta_y_diseno_capitulo_e(perfil, resultados, E, Fy, geo, cubreplacas_grafico, prop):
    """Muestra la ruta E1.1 y ejecuta E2/E3/E4/E7 con propiedades ingresadas."""
    if perfil == "Perfil I":
        sup = cubreplacas_grafico.get("superior")
        inf = cubreplacas_grafico.get("inferior")
        if not sup and not inf:
            simetria = "Doble simetría"
        elif sup and inf and abs(sup["b"]-inf["b"]) < 1e-9 and abs(sup["t"]-inf["t"]) < 1e-9:
            simetria = "Doble simetría"
        else:
            simetria = "Monosimétrica"
    elif perfil in {"Canal", "Tee"}:
        simetria = "Monosimétrica"
    elif perfil in {"Tubo cuadrado", "Tubo rectangular", "Tubo circular"}:
        simetria = "Doble simetría"
    else:
        simetria = "Según ejes principales"

    # E6 se detecta automáticamente. Solo aplica a perfiles formados por dos
    # componentes completos interconectados a intervalos. En la lista actual,
    # este caso corresponde únicamente al ángulo doble con separadores.
    perfiles_e6 = {"Ángulo doble con separadores", "Canal doble", "Perfil I doble"}
    aplica_e6 = perfil in perfiles_e6

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
        a.metric("Área bruta Ag", f"{Ag:,.3f}")
        b.metric("Radio de giro rx", f"{rx:,.3f}")
        c.metric("Radio de giro ry", f"{ry:,.3f}")
        a, b, c, d = st.columns(4)
        Lx = a.number_input("Longitud no arriostrada Lx", min_value=0.001, value=3000.0, key="Lx_E")
        Kx = b.number_input("Factor Kx", min_value=0.001, value=1.0, key="Kx_E")
        Ly = c.number_input("Longitud no arriostrada Ly", min_value=0.001, value=3000.0, key="Ly_E")
        Ky = d.number_input("Factor Ky", min_value=0.001, value=1.0, key="Ky_E")
        Lcx, Lcy = longitud_efectiva(Kx, Lx), longitud_efectiva(Ky, Ly)
        st.write(f"**Lcx = {Lcx:.3f}** · **Lcy = {Lcy:.3f}** · **Lcx/rx = {Lcx/rx:.3f}** · **Lcy/ry = {Lcy/ry:.3f}**")
        if max(Lcx/rx, Lcy/ry) > 200:
            st.warning("La nota de usuario de E2 recomienda que Lc/r no exceda 200 para miembros diseñados a compresión.")

    with st.expander("E3 — Pandeo flexional", expanded=True):
        try:
            res_x = pandeo_flexional(eje="x-x", E=E, Fy=Fy, Ag=Ag, K=Kx, L=Lx, r=rx)
            res_y = pandeo_flexional(eje="y-y", E=E, Fy=Fy, Ag=Ag, K=Ky, L=Ly, r=ry)
            for r in (res_x, res_y):
                with st.container(border=True):
                    st.markdown(f"**{r.modo} alrededor de {r.eje}**")
                    q1,q2,q3,q4=st.columns(4)
                    q1.metric("Lc/r", f"{r.esbeltez:.3f}")
                    q2.metric("Fe", f"{r.Fe:.3f}")
                    q3.metric("Fn", f"{r.Fn:.3f}")
                    q4.metric("Pn", f"{r.Pn:.3f}")
                    st.caption(f"Fn por {r.ecuacion_fn}; {r.observacion}")
            gob = min((res_x,res_y), key=lambda r:r.Pn)
            st.warning(f"Gobierna E3 alrededor de **{gob.eje}**, con Pn = **{gob.Pn:.3f}**.")
        except ValueError as exc:
            st.error(str(exc))

    with st.expander("E4 — Pandeo torsional o flexotorsional", expanded=False):
        activar_e4 = st.checkbox("Calcular E4", value=("E4" in ruta.secciones), key="activar_E4")
        if activar_e4:
            G0 = 77200.0 if E > 1000 else 11200.0
            G = st.number_input("Módulo de corte G", min_value=0.001, value=G0, key="G_E4")
            Ix, Iy, J = prop.Ix, prop.Iy, prop.J
            q1,q2,q3,q4 = st.columns(4)
            q1.metric("Ix automático", f"{Ix:,.3f}")
            q2.metric("Iy automático", f"{Iy:,.3f}")
            q3.metric("J automático", f"{J:,.3f}")
            if prop.Cw is None:
                Cw = q4.number_input("Cw (requiere ingreso)", min_value=0.0, value=0.0, key="Cw_E4")
            else:
                Cw = prop.Cw
                q4.metric("Cw automático", f"{Cw:,.3f}")
            q1,q2 = st.columns(2)
            Lz = q1.number_input("Longitud torsional no arriostrada Lz", min_value=0.001, value=max(Lx,Ly), key="Lz_E4")
            Kz = q2.number_input("Factor Kz", min_value=0.001, value=1.0, key="Kz_E4")
            Lcz = Kz*Lz
            try:
                if ruta.simetria == "Doble simetría":
                    Fe4 = fe_torsional_doble_simetria(E=E,G=G,Cw=max(Cw,1e-12),J=J,Lcz=Lcz,Ix=Ix,Iy=Iy)
                    modo="Pandeo torsional"
                else:
                    q1,q2=st.columns(2)
                    x0=q1.number_input("x0: centro de cortante respecto al centroide", value=0.0, key="x0_E4")
                    y0=q2.number_input("y0: centro de cortante respecto al centroide", value=20.0, key="y0_E4")
                    r0=radio_polar_centro_cortante(x0=x0,y0=y0,Ix=Ix,Iy=Iy,Ag=Ag)
                    Hf=1-(x0*x0+y0*y0)/(r0*r0)
                    # Para canal con eje x de simetría, la nota indica reemplazar Fey por Fex.
                    Fes = res_x.Fe if perfil in {"Canal", "Tee"} else min(res_x.Fe,res_y.Fe)
                    Fez=((3.141592653589793**2*E*Cw/Lcz**2)+G*J)/(Ag*r0**2)
                    Fe4=fe_flexotorsional_monosimetrico(Fes=Fes,Fez=Fez,H=Hf)
                    modo="Pandeo flexotorsional"
                r4=pandeo_torsional_o_flexotorsional(modo=modo,Fe=Fe4,Fy=Fy,Ag=Ag)
                q1,q2,q3=st.columns(3)
                q1.metric("Fe E4",f"{r4.Fe:.3f}")
                q2.metric("Fn",f"{r4.Fn:.3f}")
                q3.metric("Pn",f"{r4.Pn:.3f}")
                st.caption(f"Fn por {r4.ecuacion_fn}. Comparar Pn de E4 con Pn de E3 y adoptar el menor.")
            except ValueError as exc:
                st.error(str(exc))

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
                st.write(f"**Fe = {Fe_e5:.3f}**, **Fn = {Fn_e5:.3f}** por **{eq_e5}**.")
            except ValueError as exc:
                st.error(str(exc))

    if "E6" in ruta.secciones:
        with st.expander("E6 — Miembros armados por dos perfiles", expanded=False):
            st.info("Esta sección corresponde a dos perfiles unidos mediante conectores intermedios; no es la fabricación de un cajón con cuatro placas continuas.")
            tipo_con = st.selectbox("Conectores intermedios", ["pernos snug-tight", "soldado o pernos pretensionados"], key="con_E6")
            esb_global = st.number_input("Esbeltez global (Lc/r)o", min_value=0.001, value=max(Lcx/rx,Lcy/ry), key="esb_global_E6")
            a_e6 = st.number_input("Separación entre conectores a", min_value=0.001, value=300.0, key="a_E6")
            ri_e6 = st.number_input("Radio mínimo del componente individual ri", min_value=0.001, value=20.0, key="ri_E6")
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
            Fn_global = st.number_input("Fn global para E7", min_value=0.001, value=min(res_x.Fn,res_y.Fn), key="Fn_E7")
            if perfil == "Tubo circular":
                try:
                    Ae,eq=area_efectiva_tubo_circular(D=geo["D"],t=geo["t"],E=E,Fy=Fy,Ag=Ag)
                    st.write(f"**Ae = {Ae:.3f}** por **{eq}**")
                    st.metric("Pn = Fn·Ae",f"{Fn_global*Ae:.3f}")
                except ValueError as exc:
                    st.error(str(exc))
            else:
                elementos=[]
                for i,r in enumerate(resultados):
                    if r.clasificacion != "ESBELTO":
                        continue
                    with st.container(border=True):
                        st.markdown(f"**{r.elemento}**")
                        q1,q2,q3=st.columns(3)
                        b_el=q1.number_input("b",min_value=0.001,value=max(1.0,r.lambda_real),key=f"b_E7_{i}")
                        t_el=q2.number_input("t",min_value=0.001,value=1.0,key=f"t_E7_{i}")
                        mult=q3.number_input("Multiplicidad",min_value=1,value=1,step=1,key=f"m_E7_{i}")
                        if "Pared" in r.elemento and perfil in {"Tubo cuadrado","Tubo rectangular"}:
                            tipo_e7="pared de tubo cuadrado o rectangular"
                        elif r.condicion_borde == "Rigidizado":
                            tipo_e7="rigidizado excepto pared de tubo"
                        else:
                            tipo_e7="otro elemento"
                        be,Fel,c1,eq=ancho_efectivo_e7(b=b_el,t=t_el,lambda_r=r.lambda_r,Fy=Fy,Fn=Fn_global,tipo_elemento=tipo_e7)
                        st.caption(f"Tipo E7.1: {tipo_e7}; be={be:.3f}; Fel={Fel:.3f}; {eq}.")
                        elementos.append({"nombre":r.elemento,"b":b_el,"t":t_el,"be":be,"multiplicidad":mult})
                if elementos:
                    try:
                        Ae,detalle=area_efectiva_desde_elementos(Ag=Ag,elementos=elementos)
                        st.metric("Área efectiva Ae",f"{Ae:.3f}")
                        st.metric("Resistencia nominal Pn = Fn·Ae",f"{Fn_global*Ae:.3f}")
                    except ValueError as exc:
                        st.error(str(exc))

# -----------------------------------------------------------------------------
# Barra lateral
# -----------------------------------------------------------------------------
st.sidebar.title("Datos del perfil")
with st.sidebar.expander("Configuración general", expanded=True):
    perfil = st.selectbox("Tipo de perfil", [
        "Perfil I", "Canal", "Tee", "Ángulo simple", "Ángulo doble con separadores",
        "Tubo cuadrado", "Tubo rectangular", "Tubo circular",
    ])
    eje = st.radio("Eje de análisis", ["x-x", "y-y"], help="Se conserva para flexión y flexocompresión.")

with st.sidebar.expander("Material", expanded=False):
    unidades = st.selectbox("Sistema de esfuerzo", ["MPa", "ksi"])
    unidades_longitud = "mm" if unidades == "MPa" else "in"
    E0, Fy0 = (200000.0, 345.0) if unidades == "MPa" else (29000.0, 50.0)
    E = st.number_input(f"Módulo de elasticidad E [{unidades}]", min_value=0.001, value=E0)
    Fy = st.number_input(f"Esfuerzo de fluencia Fy [{unidades}]", min_value=0.001, value=Fy0)

geo: dict[str, float] = {}
fabricacion: str | None = None
cubreplacas_grafico: dict = {}
cubreplacas_calculo: list[dict[str, object]] = []

with st.sidebar.expander("Geometría", expanded=True):
    if perfil == "Perfil I":
        fabricacion = st.selectbox("Fabricación", ["Rolled", "Built-up"])
        geo["bf"] = st.number_input("Ancho total del patín bf", min_value=0.001, value=200.0)
        geo["tf"] = st.number_input("Espesor del patín tf", min_value=0.001, value=12.0)
        geo["h"] = st.number_input("Altura libre del alma h", min_value=0.001, value=450.0)
        geo["tw"] = st.number_input("Espesor del alma tw", min_value=0.001, value=8.0)

        tiene_cp = st.checkbox("Incluir cubreplaca(s) de ala — Caso 7")
        if tiene_cp:
            ubicacion = st.selectbox("Ubicación", ["Solo superior", "Solo inferior", "Ambas alas"])
            conexion = st.selectbox("Líneas de conexión", ["Soldaduras", "Pernos"])
            iguales = True
            if ubicacion == "Ambas alas":
                iguales = st.checkbox("Cubreplacas iguales", value=True)

            if ubicacion in {"Solo superior", "Ambas alas"}:
                st.markdown("**Cubreplaca superior**")
                B_sup = st.number_input("Ancho total Bcp — superior", min_value=0.001, value=180.0, key="B_cp_sup")
                b_sup = st.number_input("Ancho entre líneas b — superior", min_value=0.001, value=160.0, max_value=B_sup, key="b_cp_sup")
                t_sup = st.number_input("Espesor tcp — superior", min_value=0.001, value=10.0, key="t_cp_sup")
                cubreplacas_grafico["superior"] = {"B": B_sup, "b": b_sup, "t": t_sup}
                cubreplacas_calculo.append({"nombre": "Cubreplaca superior", "b": b_sup, "t": t_sup, "conexion": conexion})

            if ubicacion in {"Solo inferior", "Ambas alas"}:
                if ubicacion == "Ambas alas" and iguales:
                    B_inf, b_inf, t_inf = B_sup, b_sup, t_sup
                    st.caption("La cubreplaca inferior adopta las mismas dimensiones que la superior.")
                else:
                    st.markdown("**Cubreplaca inferior**")
                    B_inf = st.number_input("Ancho total Bcp — inferior", min_value=0.001, value=180.0, key="B_cp_inf")
                    b_inf = st.number_input("Ancho entre líneas b — inferior", min_value=0.001, value=160.0, max_value=B_inf, key="b_cp_inf")
                    t_inf = st.number_input("Espesor tcp — inferior", min_value=0.001, value=10.0, key="t_cp_inf")
                cubreplacas_grafico["inferior"] = {"B": B_inf, "b": b_inf, "t": t_inf}
                cubreplacas_calculo.append({"nombre": "Cubreplaca inferior", "b": b_inf, "t": t_inf, "conexion": conexion})

    elif perfil == "Canal":
        fabricacion = "Rolled"
        geo["b"] = st.number_input("Ancho saliente del patín b", min_value=0.001, value=70.0)
        geo["tf"] = st.number_input("Espesor del patín tf", min_value=0.001, value=10.0)
        geo["h"] = st.number_input("Altura libre del alma h", min_value=0.001, value=250.0)
        geo["tw"] = st.number_input("Espesor del alma tw", min_value=0.001, value=7.0)
    elif perfil == "Tee":
        fabricacion = "Rolled"
        geo["b"] = st.number_input("Ancho saliente de media ala b", min_value=0.001, value=75.0)
        geo["tf"] = st.number_input("Espesor del patín tf", min_value=0.001, value=12.0)
        geo["d"] = st.number_input("Profundidad del vástago d", min_value=0.001, value=150.0)
        geo["tw"] = st.number_input("Espesor del vástago tw", min_value=0.001, value=8.0)
    elif perfil in {"Ángulo simple", "Ángulo doble con separadores"}:
        geo["b1"] = st.number_input("Ancho de pata 1 b1", min_value=0.001, value=75.0)
        geo["b2"] = st.number_input("Ancho de pata 2 b2", min_value=0.001, value=75.0)
        geo["t"] = st.number_input("Espesor t", min_value=0.001, value=8.0)
        if perfil == "Ángulo doble con separadores":
            geo["separacion"] = st.number_input("Separación libre entre ángulos", min_value=0.0, value=20.0)
    elif perfil in {"Tubo cuadrado", "Tubo rectangular"}:
        fabricacion = st.selectbox("Fabricación", ["Rolled", "Built-up"], help="Rolled → caso 6; Built-up con placas soldadas → caso 8.")
        geo["B"] = st.number_input("Ancho exterior B", min_value=0.001, value=200.0)
        if perfil == "Tubo cuadrado":
            geo["H"] = geo["B"]
            st.caption("Para tubo cuadrado se adopta H = B.")
        else:
            geo["H"] = st.number_input("Altura exterior H", min_value=0.001, value=300.0)
        geo["t"] = st.number_input("Espesor t", min_value=0.001, value=8.0)
    else:
        fabricacion = "Rolled"
        geo["D"] = st.number_input("Diámetro exterior D", min_value=0.001, value=200.0)
        geo["t"] = st.number_input("Espesor t", min_value=0.001, value=8.0)


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

st.title("Verificación de perfiles estándar de acero")
st.caption("La geometría y el eje seleccionados se conservarán para los módulos posteriores.")

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
            mostrar_propiedades(propiedades, unidades_longitud)
        if tab is tab_axial:
            st.info("En esta pestaña el eje de análisis no modifica la Tabla B4.1a; se muestra y se guarda para verificaciones posteriores.")
            if error:
                st.error(error)
            elif resultados:
                mostrar_resultados(resultados)
                mostrar_ruta_y_diseno_capitulo_e(perfil, resultados, E, Fy, geo, cubreplacas_grafico, propiedades)
        else:
            st.info("Las propiedades geométricas ya se calculan automáticamente. La resistencia de flexión y las ecuaciones de interacción se incorporarán en los módulos siguientes.")

st.caption("Herramienta de apoyo. Confirme siempre las definiciones geométricas y la edición normativa aplicable al proyecto.")
