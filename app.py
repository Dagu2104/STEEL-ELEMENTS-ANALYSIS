"""Aplicación Streamlit: clasificación local AISC B4.1a y B4.1b."""
from __future__ import annotations

import html
import streamlit as st
import streamlit.components.v1 as components

from funciones import (
    crear_resultado, evaluar_angulo, evaluar_canal, evaluar_hss_circular,
    evaluar_hss_rectangular, evaluar_perfil_i, evaluar_tee,
)
from flexion_b4 import evaluar_flexion, clasificacion_global
from propiedades import calcular_propiedades
from unidades import (
    LONGITUD_A_MM, ESFUERZO_A_MPA, FUERZA_A_N, MOMENTO_A_NMM,
    a_interno, desde_interno, unidad_propiedad,
)

st.set_page_config(page_title="Diseño de perfiles de acero", page_icon="🏗️", layout="wide")
st.title("Diseño de perfiles de acero")
st.caption("Clasificación local de elementos — Tablas AISC B4.1a y B4.1b")

# ---------------------------- utilidades UI ----------------------------
def selector_unidades():
    with st.sidebar.expander("Unidades", expanded=False):
        ul = st.selectbox("Longitud", list(LONGITUD_A_MM), index=0, key="unidad_longitud")
        ue = st.selectbox("Esfuerzo", list(ESFUERZO_A_MPA), index=0, key="unidad_esfuerzo")
        uf = st.selectbox("Fuerza", list(FUERZA_A_N), index=1, key="unidad_fuerza")
        um = st.selectbox("Momento", list(MOMENTO_A_NMM), index=2, key="unidad_momento")
    return ul, ue, uf, um


def numero_interno(label, key, default_internal, unidad, magnitud="longitud", min_internal=1e-6, step_internal=None):
    """Número mostrado en la unidad elegida, almacenado internamente en mm/MPa."""
    ik=f"_int_{key}"; uk=f"_unit_{key}"; wk=f"_widget_{key}"
    if ik not in st.session_state:
        st.session_state[ik]=float(default_internal)
    if uk not in st.session_state or st.session_state[uk] != unidad:
        st.session_state[wk]=desde_interno(st.session_state[ik],magnitud,unidad)
        st.session_state[uk]=unidad
    valor=st.number_input(
        f"{label} [{unidad}]", min_value=float(desde_interno(min_internal,magnitud,unidad)),
        value=float(st.session_state.get(wk, desde_interno(default_internal,magnitud,unidad))),
        step=float(desde_interno(step_internal or max(default_internal/100, min_internal),magnitud,unidad)),
        key=wk,
    )
    st.session_state[ik]=a_interno(valor,magnitud,unidad)
    return st.session_state[ik]


def svg_perfil(perfil, geo, eje, sentido, fabricacion, cp):
    W,H=520,350; cx,cy=250,175
    stroke="#233142"; fill="#dce7f3"; red="#d83b2d"; blue="#1769c2"
    shapes=[]; labels=[]
    def rect(x,y,w,h,rx=0): shapes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="3"/>')
    if perfil=="Perfil I":
        bf,tf,h,tw=geo['bf'],geo['tf'],geo['h'],geo['tw']; d=h+2*tf
        sc=min(210/max(bf,1),230/max(d,1)); B=bf*sc; T=max(tf*sc,7); WH=max(tw*sc,7); HH=h*sc
        x=cx-B/2; y=cy-(HH+2*T)/2
        rect(x,y,B,T); rect(cx-WH/2,y+T,WH,HH); rect(x,y+T+HH,B,T)
        labels += [(cx+B/2+12,y+T,"Patín"),(cx+WH/2+12,cy,"Alma")]
        if cp.get('superior'):
            q=cp['superior']; BC=q['B']*sc; TC=max(q['t']*sc,5); rect(cx-BC/2,y-TC,BC,TC)
            labels.append((cx+BC/2+12,y-TC/2,"Cubreplaca sup."))
        if cp.get('inferior'):
            q=cp['inferior']; BC=q['B']*sc; TC=max(q['t']*sc,5); rect(cx-BC/2,y+2*T+HH,BC,TC)
            labels.append((cx+BC/2+12,y+2*T+HH+TC/2,"Cubreplaca inf."))
    elif perfil=="Canal":
        b,tf,h,tw=geo['b'],geo['tf'],geo['h'],geo['tw']; B=b+tw; d=h+2*tf; sc=min(190/B,230/d)
        x=cx-B/2; y=cy-d*sc/2; rect(x,y,B*sc,max(tf*sc,7)); rect(x,y+tf*sc,max(tw*sc,7),h*sc); rect(x,y+(tf+h)*sc,B*sc,max(tf*sc,7)); labels=[(x+B*sc+10,y+10,"Patín"),(x-45,cy,"Alma")]
    elif perfil=="Tee":
        b,tf,d,tw=geo['b'],geo['tf'],geo['d'],geo['tw']; bf=2*b+tw; sc=min(200/bf,220/(d+tf)); y=cy-(d+tf)*sc/2
        rect(cx-bf*sc/2,y,bf*sc,max(tf*sc,7)); rect(cx-max(tw*sc,7)/2,y+tf*sc,max(tw*sc,7),d*sc); labels=[(cx+bf*sc/2+10,y+10,"Patín"),(cx+10,cy+60,"Vástago")]
    elif perfil in {"Tubo cuadrado","Tubo rectangular"}:
        B,H0,t=geo['B'],geo['H'],geo['t']; sc=min(220/B,220/H0); bo=B*sc; ho=H0*sc; tt=max(t*sc,6); x=cx-bo/2; y=cy-ho/2
        if fabricacion=="Rolled":
            shapes.append(f'<rect x="{x}" y="{y}" width="{bo}" height="{ho}" rx="18" fill="{fill}" stroke="{stroke}" stroke-width="3"/>')
            shapes.append(f'<rect x="{x+tt}" y="{y+tt}" width="{bo-2*tt}" height="{ho-2*tt}" rx="10" fill="white" stroke="{stroke}" stroke-width="2"/>')
        else:
            rect(x,y,bo,tt); rect(x,y+ho-tt,bo,tt); rect(x,y+tt,tt,ho-2*tt); rect(x+bo-tt,y+tt,tt,ho-2*tt)
        labels=[(cx, y-12,"Pared horizontal"),(x+bo+12,cy,"Pared vertical")]
    elif perfil=="Tubo circular":
        D,t=geo['D'],geo['t']; sc=210/D; R=D*sc/2; tt=max(t*sc,6)
        shapes += [f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="{fill}" stroke="{stroke}" stroke-width="3"/>',f'<circle cx="{cx}" cy="{cy}" r="{R-tt}" fill="white" stroke="{stroke}" stroke-width="2"/>']
    else:
        # ángulo esquemático
        rect(cx-70,cy-80,18,150); rect(cx-52,cy+52,120,18); labels=[(cx-110,cy,"Pata 1"),(cx,cy+95,"Pata 2")]
    # Solo eje activado
    if eje=="x-x":
        axis=f'<line x1="90" y1="{cy}" x2="410" y2="{cy}" stroke="{red}" stroke-width="2" stroke-dasharray="8 6"/><text x="415" y="{cy+5}" fill="{red}" font-weight="700">x-x</text>'
        arrow=f'<line x1="460" y1="100" x2="460" y2="250" stroke="{blue}" stroke-width="3"/><polygon points="460,90 452,105 468,105" fill="{blue}"/><polygon points="460,260 452,245 468,245" fill="{blue}"/>'
    else:
        axis=f'<line x1="{cx}" y1="35" x2="{cx}" y2="315" stroke="{red}" stroke-width="2" stroke-dasharray="8 6"/><text x="{cx+8}" y="45" fill="{red}" font-weight="700">y-y</text>'
        arrow=f'<line x1="100" y1="300" x2="400" y2="300" stroke="{blue}" stroke-width="3"/><polygon points="90,300 105,292 105,308" fill="{blue}"/><polygon points="410,300 395,292 395,308" fill="{blue}"/>'
    texts=''.join(f'<text x="{x}" y="{y}" font-size="14" fill="#111">{html.escape(txt)}</text>' for x,y,txt in labels)
    comp = "Superior" if sentido=="Superior en compresión" else "Inferior"
    return f'''<div style="border:1px solid #ddd;border-radius:12px;padding:8px"><svg viewBox="0 0 {W} {H}" width="100%" height="330">{''.join(shapes)}{axis}{arrow}{texts}<text x="15" y="25" font-size="15" font-weight="700">{html.escape(perfil)} · {html.escape(fabricacion)}</text><text x="15" y="340" font-size="13">Flexión perpendicular al eje {eje}. Lado indicado en compresión: {comp}.</text></svg></div>'''

# ---------------------------- configuración ----------------------------
with st.sidebar.expander("Configuración general", expanded=True):
    perfil=st.selectbox("Tipo de perfil",["Perfil I","Canal","Tee","Ángulo simple","Ángulo doble con separadores","Tubo cuadrado","Tubo rectangular","Tubo circular"])
    eje=st.radio("Eje de análisis",["x-x","y-y"])
    sentido=st.radio("Sentido de flexión",["Superior en compresión","Inferior en compresión"],help="Convención gráfica para identificar el elemento comprimido.")

ul,ue,uf,um=selector_unidades()
with st.sidebar.expander("Material", expanded=False):
    E=numero_interno("Módulo de elasticidad E","E",200000,ue,"esfuerzo",1e-6,1000)
    Fy=numero_interno("Esfuerzo de fluencia Fy","Fy",345,ue,"esfuerzo",1e-6,5)

geo={}; cp={}; fabricacion="Rolled"
with st.sidebar.expander("Geometría", expanded=True):
    if perfil=="Perfil I":
        fabricacion=st.selectbox("Fabricación",["Rolled","Built-up"])
        geo['bf']=numero_interno("Ancho total del patín bf","bf",200,ul)
        geo['tf']=numero_interno("Espesor del patín tf","tf",12,ul)
        geo['h']=numero_interno("Altura libre del alma h","h",450,ul)
        geo['tw']=numero_interno("Espesor del alma tw","tw",8,ul)
        tiene_cp=st.checkbox("Agregar cubreplaca(s)")
        if tiene_cp:
            ubic=st.selectbox("Ubicación",["Solo superior","Solo inferior","Ambas alas"])
            iguales=True
            if ubic=="Ambas alas": iguales=st.checkbox("Cubreplacas iguales",value=True)
            def cp_input(pref,txt):
                B=numero_interno(f"Ancho total {txt} Bcp",f"Bcp_{pref}",180,ul)
                b=numero_interno(f"Ancho entre líneas de conexión {txt} b",f"bcp_{pref}",150,ul)
                t=numero_interno(f"Espesor {txt} tcp",f"tcp_{pref}",8,ul)
                con=st.selectbox(f"Conexión {txt}",["Soldadura","Pernos"],key=f"con_{pref}")
                return {'B':B,'b':b,'t':t,'conexion':con}
            if ubic in {"Solo superior","Ambas alas"}: cp['superior']=cp_input('sup','superior')
            if ubic=="Solo inferior": cp['inferior']=cp_input('inf','inferior')
            elif ubic=="Ambas alas": cp['inferior']=dict(cp['superior']) if iguales else cp_input('inf','inferior')
    elif perfil=="Canal":
        geo['b']=numero_interno("Ancho saliente del patín b","bcanal",70,ul); geo['tf']=numero_interno("Espesor tf","tfcanal",10,ul); geo['h']=numero_interno("Altura libre h","hcanal",250,ul); geo['tw']=numero_interno("Espesor del alma tw","twcanal",7,ul)
    elif perfil=="Tee":
        geo['b']=numero_interno("Ancho saliente de media ala b","btee",75,ul); geo['tf']=numero_interno("Espesor del patín tf","tftee",12,ul); geo['d']=numero_interno("Profundidad del vástago d","dtee",150,ul); geo['tw']=numero_interno("Espesor del vástago tw","twtee",8,ul)
    elif perfil in {"Ángulo simple","Ángulo doble con separadores"}:
        geo['b1']=numero_interno("Pata 1 b1","b1",75,ul); geo['b2']=numero_interno("Pata 2 b2","b2",75,ul); geo['t']=numero_interno("Espesor t","tang",8,ul)
        if perfil.startswith("Ángulo doble"): geo['separacion']=numero_interno("Separación libre","sep",20,ul,"longitud",0.0,5)
    elif perfil in {"Tubo cuadrado","Tubo rectangular"}:
        fabricacion=st.selectbox("Fabricación",["Rolled","Built-up"])
        geo['B']=numero_interno("Ancho exterior B","Btubo",200,ul)
        geo['H']=geo['B'] if perfil=="Tubo cuadrado" else numero_interno("Altura exterior H","Htubo",300,ul)
        geo['t']=numero_interno("Espesor t","ttubo",8,ul)
    else:
        geo['D']=numero_interno("Diámetro exterior D","D",200,ul); geo['t']=numero_interno("Espesor t","tcirc",8,ul)

# propiedades
try:
    props=calcular_propiedades(perfil,geo,fabricacion=fabricacion,cubreplacas=cp)
except Exception as exc:
    st.error(str(exc)); st.stop()

components.html(svg_perfil(perfil,geo,eje,sentido,fabricacion,cp),height=380)

tab_ax,tab_fl,tab_fc,tab_prop=st.tabs(["Carga axial","Flexión","Flexocompresión","Propiedades"])

with tab_ax:
    st.header("Elementos sujetos a carga axial de compresión")
    st.caption("Clasificación esbelto/no esbelto — Tabla B4.1a")
    try:
        if perfil=="Perfil I":
            res=evaluar_perfil_i(fabricacion=fabricacion,bf=geo['bf'],tf=geo['tf'],h=geo['h'],tw=geo['tw'],E=E,Fy=Fy)
            for lado,q in cp.items():
                res.append(crear_resultado(perfil=perfil,elemento=f"Cubreplaca {lado}",condicion_borde="Rigidizado",caso_tabla="Caso 7",formula="1.40·√(E/Fy)",relacion="b/t",lambda_real=q['b']/q['t'],lambda_r=1.40*(E/Fy)**0.5,observacion="Entre líneas de pernos o soldaduras."))
        elif perfil=="Canal": res=evaluar_canal(b_ala=geo['b'],tf=geo['tf'],h=geo['h'],tw=geo['tw'],E=E,Fy=Fy)
        elif perfil=="Tee": res=evaluar_tee(b_ala=geo['b'],tf=geo['tf'],d_vastago=geo['d'],tw=geo['tw'],E=E,Fy=Fy)
        elif perfil in {"Ángulo simple","Ángulo doble con separadores"}: res=evaluar_angulo(tipo=perfil,b1=geo['b1'],b2=geo['b2'],t=geo['t'],E=E,Fy=Fy)
        elif perfil in {"Tubo cuadrado","Tubo rectangular"}: res=evaluar_hss_rectangular(B_plano=geo['B']-2*geo['t'],H_plano=geo['H']-2*geo['t'],t=geo['t'],E=E,Fy=Fy,perfil=perfil,fabricacion=fabricacion)
        else: res=evaluar_hss_circular(D=geo['D'],t=geo['t'],E=E,Fy=Fy)
        rows=[{"Elemento":r.elemento,"Caso":r.caso_tabla,"λ":r.lambda_real,"λr":r.lambda_r,"Clasificación":r.clasificacion} for r in res]
        st.dataframe(rows,use_container_width=True,hide_index=True)
    except Exception as exc: st.error(str(exc))

with tab_fl:
    st.header("Elementos sujetos a flexión")
    st.caption("Clasificación compacto/no compacto/esbelto — Tabla B4.1b. No se calcula todavía la resistencia del Capítulo F.")
    try:
        rf=evaluar_flexion(perfil=perfil,fabricacion=fabricacion,eje=eje,sentido=sentido,geo=geo,E=E,Fy=Fy,propiedades=props,cubreplacas=cp)
        rows=[]
        for r in rf:
            rows.append({"Elemento":r.elemento,"Caso":f"Caso {r.caso}","Condición":r.condicion,"Relación":r.relacion,"λ":round(r.lambda_real,3),"λp":round(r.lambda_p,3),"λr":round(r.lambda_r,3),"Clasificación":r.clasificacion})
        st.dataframe(rows,use_container_width=True,hide_index=True)
        global_,gob=clasificacion_global(rf)
        if global_=="COMPACTO": st.success(f"Clasificación global: **COMPACTA**. Gobierna: **{gob}**.")
        elif global_=="NO COMPACTO": st.warning(f"Clasificación global: **NO COMPACTA**. Gobierna: **{gob}**.")
        else: st.error(f"Clasificación global: **ESBELTA**. Gobierna: **{gob}**.")
        with st.expander("Fórmulas y observaciones"):
            for r in rf:
                st.markdown(f"**{r.elemento} — Caso {r.caso}:** λp = `{r.formula_lp}`; λr = `{r.formula_lr}`. {r.observacion}")
    except Exception as exc: st.error(str(exc))

with tab_fc:
    st.info("La pestaña de flexocompresión se desarrollará después de completar la clasificación y resistencia a flexión.")

with tab_prop:
    st.header("Propiedades geométricas")
    u1=ul; u2=unidad_propiedad(ul,2); u3=unidad_propiedad(ul,3); u4=unidad_propiedad(ul,4); u6=unidad_propiedad(ul,6)
    data={
        f"Ag [{u2}]":desde_interno(props.Ag,"longitud",ul,2),
        f"x̄ [{u1}]":desde_interno(props.x_bar,"longitud",ul), f"ȳ [{u1}]":desde_interno(props.y_bar,"longitud",ul),
        f"Ix [{u4}]":desde_interno(props.Ix,"longitud",ul,4), f"Iy [{u4}]":desde_interno(props.Iy,"longitud",ul,4),
        f"rx [{u1}]":desde_interno(props.rx,"longitud",ul), f"ry [{u1}]":desde_interno(props.ry,"longitud",ul),
        f"Sx sup [{u3}]":desde_interno(props.Sx_sup,"longitud",ul,3), f"Sx inf [{u3}]":desde_interno(props.Sx_inf,"longitud",ul,3),
        f"Zx [{u3}]":desde_interno(props.Zx,"longitud",ul,3), f"Zy [{u3}]":desde_interno(props.Zy,"longitud",ul,3),
        f"J [{u4}]":desde_interno(props.J,"longitud",ul,4), f"Cw [{u6}]":None if props.Cw is None else desde_interno(props.Cw,"longitud",ul,6),
    }
    st.dataframe([data],use_container_width=True,hide_index=True)
    st.caption(props.observacion)

st.divider()
st.caption(f"Unidades activas: longitud {ul}; esfuerzo {ue}; fuerza {uf}; momento {um}. Relaciones λ, λp y λr son adimensionales.")
