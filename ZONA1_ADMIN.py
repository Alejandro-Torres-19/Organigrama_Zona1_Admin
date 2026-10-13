from datetime import datetime, time, date
import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu
from streamlit_calendar import calendar
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Cronograma - Admin - Zona 1", page_icon="🏫", layout="wide"
)

# --- CONEXIÓN DIRECTA A GOOGLE SHEETS CON CACHÉ ---
@st.cache_resource
def conectar_gspread():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    if "gcp_service_account" in st.secrets:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(
            credentials_dict, scopes=scope
        )
    else:
        st.error(
            "No se encontraron las credenciales 'gcp_service_account' en secrets.toml"
        )
        st.stop()
    client = gspread.authorize(creds)
    return client.open("ORGANIGRAMA_ZONA1")

try:
    spreadsheet = conectar_gspread()
    sheet_principal = spreadsheet.get_worksheet(0) # Pestaña 1: General (Hoja 1)
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# --- CARGAR USUARIOS DESDE 'INICIOS SESIÓN' CON CACHÉ ---
@st.cache_data(ttl=300)
def cargar_credenciales_admin():
    try:
        sheet_cred = spreadsheet.worksheet("INICIOS SESIÓN")
        data_cred = sheet_cred.get_all_records()
        if data_cred:
            df_cred = pd.DataFrame(data_cred)
            df_cred.columns = [str(col).strip().upper() for col in df_cred.columns]
            return df_cred
    except Exception as e:
        st.error(f"No se pudo cargar la pestaña 'INICIOS SESIÓN': {e}")
    return pd.DataFrame()

df_usuarios_admin = cargar_credenciales_admin()

# --- SEGURIDAD: LOGIN ADMINISTRADOR ---
def check_password():
    def password_entered():
        if st.session_state["password"] == "Taguch_77":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        _, col_centro, _ = st.columns([1, 1.5, 1])
        with col_centro:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("<h2 style='text-align: center;'>🏫 Cronograma - Admin</h2>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: gray;'>Sistema de Gestión y Seguimiento - Zona 1</p>", unsafe_allow_html=True)
                st.markdown("---")
                st.text_input(
                    "🔑 Contraseña de Administrador",
                    type="password",
                    on_change=password_entered,
                    key="password",
                    placeholder="Ingresa tu contraseña"
                )
                st.markdown("<br>", unsafe_allow_html=True)
        return False
    elif not st.session_state["password_correct"]:
        _, col_centro, _ = st.columns([1, 1.5, 1])
        with col_centro:
            st.markdown("<br><br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("<h2 style='text-align: center;'>🏫 Cronograma - Admin</h2>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: gray;'>Sistema de Gestión y Seguimiento - Zona 1</p>", unsafe_allow_html=True)
                st.markdown("---")
                st.text_input(
                    "🔑 Contraseña de Administrador",
                    type="password",
                    on_change=password_entered,
                    key="password",
                    placeholder="Ingresa tu contraseña"
                )
                st.error("😕 Contraseña incorrecta. Inténtalo de nuevo.")
        return False
    else:
        return True

if not check_password():
    st.stop()

# --- CARGAR Y DEPURAR DATOS DE LA HOJA PRINCIPAL ---
@st.cache_data(ttl=30)
def cargar_datos_principales():
    data = sheet_principal.get_all_records()
    if not data:
        df = pd.DataFrame(columns=["Actividad", "Fecha Inicio", "Fecha Fin", "Privado", "Estado", "Color"])
    else:
        df = pd.DataFrame(data)
        df.columns = [str(col).strip() for col in df.columns]
        
        for col in ["Actividad", "Fecha Inicio", "Fecha Fin", "Privado", "Estado", "Color"]:
            if col not in df.columns:
                match = [c for c in df.columns if col.lower().replace(" ", "") in c.lower().replace(" ", "")]
                if match:
                    df.rename(columns={match[0]: col}, inplace=True)
                else:
                    df[col] = ""
                    
        df["Fecha Inicio"] = df["Fecha Inicio"].astype(str).str.split("T").str[0].str.strip()
        
        col_fin_real = next((c for c in df.columns if "fin" in c.lower()), "Fecha Fin")
        if col_fin_real != "Fecha Fin":
            df.rename(columns={col_fin_real: "Fecha Fin"}, inplace=True)
            
        df["Fecha Fin"] = df["Fecha Fin"].astype(str).str.split("T").str[0].str.strip()
        df["Fecha Fin"] = df["Fecha Fin"].replace(["", "nan", "NaT", "None"], pd.NA)
        df["Fecha Fin"] = df["Fecha Fin"].fillna(df["Fecha Inicio"])
        
    return df

df_tareas = cargar_datos_principales()

# --- FUNCIÓN AUXILIAR PARA FORMATEAR FECHAS A DD-MM-YY ---
def formatear_fecha_corta(fecha_val):
    if not fecha_val or str(fecha_val).strip() == "":
        return ""
    try:
        dt = pd.to_datetime(str(fecha_val).split("T")[0])
        return dt.strftime("%d-%m-%y")
    except:
        return str(fecha_val).split("T")[0]

# --- FUNCIÓN PARA GENERAR GRÁFICA CIRCULAR TIPO DONA ---
def crear_grafica_dona(porcentaje, titulo_centro=""):
    completado = porcentaje
    pendiente = 100 - porcentaje
    
    fig = go.Figure(data=[go.Pie(
        values=[completado, pendiente if completado > 0 else 100],
        labels=['Completado', 'Pendiente'],
        hole=0.6,
        marker=dict(colors=['#198754', '#dc3545']),
        textinfo='none',
        hoverinfo='none'
    )])
    
    fig.update_layout(
        showlegend=False,
        margin=dict(t=10, b=10, l=10, r=10),
        height=220,
        annotations=[dict(
            text=f"<b>{completado}%</b><br><span style='font-size:12px; color:gray;'>{titulo_centro}</span>",
            x=0.5, y=0.5, font_size=18, showarrow=False
        )]
    )
    return fig

# --- BARRA LATERAL: REGISTRO DE ACTIVIDADES Y NAVEGACIÓN ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/school.png", width=80)
    st.title("Supervisión Zona 1")
    st.markdown("---")
    
    st.subheader("➕ Registrar Actividad")
    with st.form("form_nueva_actividad_sidebar"):
        nom_actividad = st.text_input("Nombre de la Actividad")
        es_privada = st.selectbox("¿Es una tarea privada?", ["No", "Sí"])
        
        f_inicio = st.date_input("Fecha de Inicio", value=date.today(), format="DD/MM/YYYY")
        
        solo_un_dia = st.checkbox("¿Actividad de un solo día?")
        if solo_un_dia:
            f_fin = f_inicio
        else:
            f_fin = st.date_input("Fecha de Fin", value=date.today(), format="DD/MM/YYYY")

        st.markdown("**Selecciona Color / Estado:**")
        opciones_colores = {
            "🔵 Azul (Predeterminado)": "#3788d8",
            "🟡 Amarillo (Pendiente / En proceso)": "#ffc107",
            "🟣 Morado (Especial / Institucional)": "#6f42c1",
            "🔴 Rojo (Urgente / Retrasado)": "#dc3545",
            "⚪ Gris (Extra)": "#6c757d"
        }
        color_seleccionado_key = st.selectbox("Función / Color", list(opciones_colores.keys()))
        color_actividad = opciones_colores[color_seleccionado_key]
        
        submit_btn = st.form_submit_button("Guardar en Calendario")
        if submit_btn:
            if nom_actividad:
                f_ini_fmt_gs = f_inicio.strftime("%Y-%m-%d")
                f_fin_fmt_gs = f_fin.strftime("%Y-%m-%d")
                
                nueva_fila = [
                    nom_actividad,
                    f_ini_fmt_gs,
                    f_fin_fmt_gs,
                    es_privada,
                    "Pendiente",
                    color_actividad,
                ]
                sheet_principal.append_row(nueva_fila)
                st.cache_data.clear()
                st.success("¡Registrada con éxito!")
                st.rerun()
            else:
                st.warning("Ingresa el nombre de la actividad.")

    st.markdown("---")
    
    selected = option_menu(
        menu_title="Navegación",
        options=["Cronograma y Gestión", "Dashboard de Zona", "Tareas Completadas"],
        icons=["calendar-week", "bar-chart-fill", "check-circle-fill"],
        menu_icon="pin-fill",
        default_index=0,
    )

# --- 1. SECCIÓN: CRONOGRAMA Y GESTIÓN ---
if selected == "Cronograma y Gestión":
    st.title("📅 Cronograma Global y Gestión de Actividades")
    st.markdown("Administra las actividades generales para las 12 escuelas y controla tus tareas privadas.")

    hoy_date_obj = date.today()
    hoy_dt = pd.Timestamp(hoy_date_obj).normalize()
    
    if not df_tareas.empty:
        df_tareas["Fecha_Inicio_dt"] = pd.to_datetime(df_tareas["Fecha Inicio"].astype(str).str.split("T").str[0], errors='coerce').dt.normalize()
        df_tareas["Fecha_Fin_dt"] = pd.to_datetime(df_tareas["Fecha Fin"].astype(str).str.split("T").str[0], errors='coerce').dt.normalize()
        df_tareas["Fecha_Fin_dt"] = df_tareas["Fecha_Fin_dt"].fillna(df_tareas["Fecha_Inicio_dt"])
        
        atrasadas_df = df_tareas[
            (df_tareas["Fecha_Fin_dt"] < hoy_dt) & 
            (df_tareas["Estado"].str.lower() != "completada")
        ]
        
        hoy_df = df_tareas[
            (df_tareas["Fecha_Inicio_dt"] <= hoy_dt) & 
            (df_tareas["Fecha_Fin_dt"] >= hoy_dt) & 
            (df_tareas["Estado"].str.lower() != "completada")
        ]

        # --- SECCIÓN: ACTIVIDADES ATRASADAS ---
        st.markdown("### ⚠️ Actividades Atrasadas")
        if not atrasadas_df.empty:
            for idx, row in atrasadas_df.iterrows():
                orig_idx = row.name
                priv_val = str(row["Privado"]).strip().lower()
                es_privada_bool = priv_val in ["true", "sí", "si", "1"]
                icono = "🔒 " if es_privada_bool else "🏫 "
                
                f_ini_raw = str(row["Fecha Inicio"]).split("T")[0]
                f_fin_raw = str(row["Fecha Fin"]).split("T")[0] if row["Fecha Fin"] else f_ini_raw
                f_ini_fmt = formatear_fecha_corta(f_ini_raw)
                f_fin_fmt = formatear_fecha_corta(f_fin_raw)
                
                if f_ini_raw == f_fin_raw or not row["Fecha Fin"] or str(row["Fecha Fin"]).strip() == "":
                    rango_fechas = f"📅 {f_ini_fmt}"
                else:
                    rango_fechas = f"📅 Del {f_ini_fmt} al {f_fin_fmt}"
                
                with st.container(border=True):
                    col_p1, col_p2, col_p3, col_p4 = st.columns([3, 1, 0.7, 0.7])
                    with col_p1:
                        st.markdown(f"**{icono} {row['Actividad']}** &nbsp;|&nbsp; *<small>{rango_fechas}</small>*", unsafe_allow_html=True)
                    with col_p2:
                        st.markdown("🔴 Atrasada", unsafe_allow_html=True)
                    with col_p3:
                        if st.button("✔️ Marcar", key=f"btn_atrasada_{orig_idx}"):
                            try:
                                sheet_completadas = spreadsheet.worksheet("Completadas")
                                sheet_completadas.append_row([row["Actividad"], row["Fecha Inicio"], row["Fecha Fin"], row["Privado"], "Completada", row["Color"]])
                            except Exception:
                                pass
                            sheet_principal.delete_rows(orig_idx + 2)
                            st.cache_data.clear()
                            st.success("¡Completada y movida al historial!")
                            st.rerun()
                    with col_p4:
                        if st.button("🗑️ Borrar", key=f"del_atrasada_{orig_idx}"):
                            sheet_principal.delete_rows(orig_idx + 2)
                            try:
                                sheet_comp = spreadsheet.worksheet("Completadas")
                                registros_comp = sheet_comp.get_all_records()
                                for i, r in enumerate(registros_comp):
                                    if str(r.get("Actividad")) == str(row["Actividad"]) and str(r.get("Fecha Inicio")) == str(row["Fecha Inicio"]):
                                        sheet_comp.delete_rows(i + 2)
                                        break
                            except Exception:
                                pass
                            st.cache_data.clear()
                            st.success("¡Eliminada por completo!")
                            st.rerun()
        else:
            st.success("🎉 ¡Excelente! No tienes actividades atrasadas.")

        st.markdown("---")

        # --- SECCIÓN: PENDIENTES DE HOY ---
        st.markdown("### 🔔 Pendientes de Hoy")
        if not hoy_df.empty:
            for idx, row in hoy_df.iterrows():
                orig_idx = row.name
                priv_val = str(row["Privado"]).strip().lower()
                es_privada_bool = priv_val in ["true", "sí", "si", "1"]
                icono = "🔒 " if es_privada_bool else "🏫 "
                
                f_ini_raw = str(row["Fecha Inicio"]).split("T")[0]
                f_fin_raw = str(row["Fecha Fin"]).split("T")[0] if row["Fecha Fin"] else f_ini_raw
                f_ini_fmt = formatear_fecha_corta(f_ini_raw)
                f_fin_fmt = formatear_fecha_corta(f_fin_raw)
                
                if f_ini_raw == f_fin_raw or not row["Fecha Fin"] or str(row["Fecha Fin"]).strip() == "":
                    rango_fechas = f"📅 {f_ini_fmt}"
                else:
                    rango_fechas = f"📅 Del {f_ini_fmt} al {f_fin_fmt}"
                
                with st.container(border=True):
                    col_h1, col_h2, col_h3, col_h4 = st.columns([3, 1, 0.7, 0.7])
                    with col_h1:
                        st.markdown(f"**{icono} {row['Actividad']}** &nbsp;|&nbsp; *<small>{rango_fechas}</small>*", unsafe_allow_html=True)
                    with col_h2:
                        st.markdown("🟠 Pendiente", unsafe_allow_html=True)
                    with col_h3:
                        if st.button("✔️ Marcar", key=f"btn_hoy_{orig_idx}"):
                            try:
                                sheet_completadas = spreadsheet.worksheet("Completadas")
                                sheet_completadas.append_row([row["Actividad"], row["Fecha Inicio"], row["Fecha Fin"], row["Privado"], "Completada", row["Color"]])
                            except Exception:
                                pass
                            sheet_principal.delete_rows(orig_idx + 2)
                            st.cache_data.clear()
                            st.success("¡Completada y movida al historial!")
                            st.rerun()
                    with col_h4:
                        if st.button("🗑️ Borrar", key=f"del_hoy_{orig_idx}"):
                            sheet_principal.delete_rows(orig_idx + 2)
                            try:
                                sheet_comp = spreadsheet.worksheet("Completadas")
                                registros_comp = sheet_comp.get_all_records()
                                for i, r in enumerate(registros_comp):
                                    if str(r.get("Actividad")) == str(row["Actividad"]) and str(r.get("Fecha Inicio")) == str(row["Fecha Inicio"]):
                                        sheet_comp.delete_rows(i + 2)
                                        break
                            except Exception:
                                pass
                            st.cache_data.clear()
                            st.success("¡Eliminada por completo!")
                            st.rerun()
        else:
            st.success("🎉 ¡Excelente! No hay actividades programadas específicamente para el día de hoy.")
    else:
        st.info("No hay actividades registradas en el sistema.")

    st.markdown("---")

    # --- CALENDARIO GLOBAL Y AGENDA QUINCENAL ---
    st.markdown("### 🗓️ Visualización del Calendario y Agenda")

    st.markdown("""
        <style>
        .fc-list-event-time { display: none !important; }
        .fc-view-harness { min-height: 700px !important; }
        </style>
    """, unsafe_allow_html=True)

    calendar_events = []
    if not df_tareas.empty:
        for _, row in df_tareas.iterrows():
            priv_val = str(row["Privado"]).strip().lower()
            es_privada_bool = priv_val in ["true", "sí", "si", "1"]
            icono_titulo = "🔒 " if es_privada_bool else "🏫 "
            
            f_ini_raw = str(row["Fecha Inicio"]).split("T")[0]
            f_fin_raw = str(row["Fecha Fin"]).split("T")[0] if row["Fecha Fin"] else f_ini_raw
            
            try:
                f_ini_dt = pd.to_datetime(f_ini_raw).strftime("%Y-%m-%d")
                f_fin_dt = (pd.to_datetime(f_fin_raw) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            except:
                f_ini_dt = f_ini_raw
                f_fin_dt = f_fin_raw

            estado_evt = str(row["Estado"]).strip().lower()
            if es_privada_bool and estado_evt == "completada":
                color_evento = "#28a745"
            else:
                color_evento = row["Color"] if row["Color"] else "#3788d8"

            calendar_events.append({
                "title": f"{icono_titulo}{row['Actividad']}",
                "start": f_ini_dt,
                "end": f_fin_dt,
                "color": color_evento,
                "allDay": True
            })

    calendar_options = {
        "editable": False,
        "selectable": True,
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "listFortnight,dayGridMonth"
        },
        "views": {
            "listFortnight": { "type": "list", "duration": {"days": 15}, "buttonText": "Agenda Quincenal" },
            "dayGridMonth": { "buttonText": "Mes" }
        },
        "initialView": "listFortnight",
        "locale": "es",
    }

    calendar(events=calendar_events, options=calendar_options)

    st.markdown("---")

    # --- SECCIÓN: GESTIÓN DE TAREAS ---
    st.markdown("### 📋 Gestión y Control de Actividades Individuales")
    st.markdown("Marca aquí las actividades que has concluido de forma personal o interna como administrador.")

    if not df_tareas.empty:
        for idx, row in df_tareas.iterrows():
            orig_idx = row.name
            priv_val = str(row["Privado"]).strip().lower()
            es_privada_bool = priv_val in ["true", "sí", "si", "1"]
            icono = "🔒 " if es_privada_bool else "🏫 "
            
            f_ini_raw = str(row["Fecha Inicio"]).split("T")[0]
            f_fin_raw = str(row["Fecha Fin"]).split("T")[0] if row["Fecha Fin"] else f_ini_raw
            f_ini_fmt = formatear_fecha_corta(f_ini_raw)
            f_fin_fmt = formatear_fecha_corta(f_fin_raw)
            
            if f_ini_raw == f_fin_raw or not row["Fecha Fin"] or str(row["Fecha Fin"]).strip() == "":
                rango_fechas = f"📅 {f_ini_fmt}"
            else:
                rango_fechas = f"📅 Del {f_ini_fmt} al {f_fin_fmt} (Rango Activo)"
            
            with st.container(border=True):
                col_t1, col_t2, col_t3, col_t4 = st.columns([3, 1, 0.7, 0.7])
                with col_t1:
                    st.markdown(f"**{icono} {row['Actividad']}** &nbsp;|&nbsp; *<small>{rango_fechas}</small>*", unsafe_allow_html=True)
                with col_t2:
                    st.markdown("🟠 Pendiente", unsafe_allow_html=True)
                with col_t3:
                    if st.button("✔️ Marcar", key=f"btn_terminar_{orig_idx}"):
                        try:
                            sheet_completadas = spreadsheet.worksheet("Completadas")
                            sheet_completadas.append_row([row["Actividad"], row["Fecha Inicio"], row["Fecha Fin"], row["Privado"], "Completada", row["Color"]])
                        except Exception:
                            pass
                        sheet_principal.delete_rows(orig_idx + 2)
                        st.cache_data.clear()
                        st.success("¡Completada y movida al historial!")
                        st.rerun()
                with col_t4:
                    if st.button("🗑️ Borrar", key=f"del_gestion_{orig_idx}"):
                        sheet_principal.delete_rows(orig_idx + 2)
                        try:
                            sheet_comp = spreadsheet.worksheet("Completadas")
                            registros_comp = sheet_comp.get_all_records()
                            for i, r in enumerate(registros_comp):
                                if str(r.get("Actividad")) == str(row["Actividad"]) and str(r.get("Fecha Inicio")) == str(row["Fecha Inicio"]):
                                    sheet_comp.delete_rows(i + 2)
                                    break
                        except Exception:
                            pass
                        st.cache_data.clear()
                        st.success("¡Eliminada por completo!")
                        st.rerun()
    else:
        st.info("No hay actividades registradas.")


# --- 2. SECCIÓN: DASHBOARD DE ZONA (CON CCT REALES Y CACHÉ) ---
elif selected == "Dashboard de Zona":
    st.title("📊 Dashboard Ejecutivo de Avance por Escuela")
    st.markdown("Monitoreo en tiempo real del cumplimiento de los planteles de la Zona 1.")

    @st.cache_data(ttl=60)
    def calcular_dashboard_admin():
        lista_ccts = df_usuarios_admin["CCT"].astype(str).str.strip().unique().tolist() if not df_usuarios_admin.empty and "CCT" in df_usuarios_admin.columns else []
        avances = []
        detalles = {}
        
        for cct_item in lista_ccts:
            porcentaje_esc = 0
            df_esc = pd.DataFrame()
            try:
                ws_escuela = spreadsheet.worksheet(cct_item)
                data_escuela = ws_escuela.get_all_records()
                if data_escuela:
                    df_esc = pd.DataFrame(data_escuela)
                    df_esc.columns = [str(col).strip() for col in df_esc.columns]
                    total_tareas = len(df_esc)
                    if total_tareas > 0 and "Estado" in df_esc.columns:
                        completadas = len(df_esc[df_esc["Estado"].str.lower() == "completada"])
                        porcentaje_esc = int((completadas / total_tareas) * 100)
            except Exception:
                pass
                
            avances.append({"Escuela": cct_item, "Porcentaje": porcentaje_esc})
            detalles[cct_item] = df_esc
            
        return avances, detalles

    avances_data, detalles_escuelas = calcular_dashboard_admin()
    df_avances = pd.DataFrame(avances_data)
    
    promedio_zona = int(df_avances["Porcentaje"].mean()) if not df_avances.empty else 0

    st.metric(label="📈 Avance Global Promedio de la Zona 1", value=f"{promedio_zona}%")

    st.markdown("---")

    # Galería de Gráficas Circulares Tipo Dona por CCT
    st.markdown("### 📈 Avance de la Zona 1")
    st.markdown("Estatus de cumplimiento de todos los planteles de la zona:")

    if not df_avances.empty:
        cols = st.columns(3)
        for idx, row in df_avances.iterrows():
            esc_nombre = row["Escuela"]
            esc_porc = row["Porcentaje"]
            
            with cols[idx % 3]:
                with st.container(border=True):
                    fig_dona = crear_grafica_dona(esc_porc, esc_nombre)
                    st.plotly_chart(fig_dona, use_container_width=True, key=f"admin_dona_{idx}")

    st.markdown("---")

    # Auditoría y Desglose Detallado por CCT
    st.markdown("### 🔍 Auditoría y Desglose por Plantel")
    st.markdown("Selecciona una escuela (CCT) para revisar puntualmente qué actividades ha completado y cuáles tiene pendientes o atrasadas.")

    lista_ccts_disponibles = df_usuarios_admin["CCT"].astype(str).str.strip().unique().tolist() if not df_usuarios_admin.empty else []
    
    if lista_ccts_disponibles:
        escuela_seleccionada_admin = st.selectbox("🏫 Selecciona el Plantel a Auditar (CCT)", lista_ccts_disponibles, key="select_audit_cct")
        
        df_audit = detalles_escuelas.get(escuela_seleccionada_admin, pd.DataFrame())

        if not df_audit.empty and "Actividad" in df_audit.columns and "Estado" in df_audit.columns:
            col_completadas_admin = df_audit[df_audit["Estado"].str.lower() == "completada"]
            col_pendientes_admin = df_audit[df_audit["Estado"].str.lower() != "completada"]

            tab_det_comp, tab_det_pend = st.tabs([
                f"✅ Completadas ({len(col_completadas_admin)})", 
                f"⏳ Pendientes / Atrasadas ({len(col_pendientes_admin)})"
            ])

            with tab_det_comp:
                if not col_completadas_admin.empty:
                    for _, row_c in col_completadas_admin.iterrows():
                        f_ini = formatear_fecha_corta(str(row_c.get("Fecha Inicio", "")).split("T")[0])
                        f_fin = formatear_fecha_corta(str(row_c.get("Fecha Fin", "")).split("T")[0])
                        rango = f"📅 Del {f_ini} al {f_fin}" if f_ini != f_fin else f"📅 {f_ini}"
                        
                        with st.container(border=True):
                            st.markdown(f"**✅ {row_c['Actividad']}** &nbsp;|&nbsp; *<small>{rango}</small>*")
                else:
                    st.info(f"{escuela_seleccionada_admin} aún no registra actividades completadas.")

            with tab_det_pend:
                if not col_pendientes_admin.empty:
                    for _, row_p in col_pendientes_admin.iterrows():
                        f_ini = formatear_fecha_corta(str(row_p.get("Fecha Inicio", "")).split("T")[0])
                        f_fin = formatear_fecha_corta(str(row_p.get("Fecha Fin", "")).split("T")[0])
                        rango = f"📅 Del {f_ini} al {f_fin}" if f_ini != f_fin else f"📅 {f_ini}"
                        
                        with st.container(border=True):
                            st.markdown(f"**⏳ {row_p['Actividad']}** &nbsp;|&nbsp; *<small>{rango}</small>* &nbsp;|&nbsp; 🔴 *Pendiente de entrega*")
                else:
                    st.success(f"¡{escuela_seleccionada_admin} está al corriente con el 100% de sus actividades!")
        else:
            st.info(f"No hay registros de actividades disponibles para {escuela_seleccionada_admin}.")
    else:
        st.warning("No se encontraron CCTs en la pestaña 'INICIOS SESIÓN'.")


# --- 3. SECCIÓN: TAREAS COMPLETADAS ---
elif selected == "Tareas Completadas":
    st.title("✅ Historial de Tareas Completadas")
    st.markdown("Visualiza por separado las actividades concluidas a nivel zona y las concluidas individualmente.")

    tab_zona, tab_admin = st.tabs(["🌍 Completadas a Nivel Zona (100% Escuelas)", "👤 Completadas Individualmente (Admin)"])

    with tab_zona:
        st.subheader("Tareas con 100% de Cumplimiento en la Zona")
        if not df_tareas.empty and "Estado" in df_tareas.columns:
            completadas_zona = df_tareas[df_tareas["Estado"] == "Completada Global"]
            if not completadas_zona.empty:
                st.dataframe(completadas_zona[["Actividad", "Fecha Inicio", "Fecha Fin", "Privado"]], use_container_width=True, hide_index=True)
            else:
                st.info("Aún no hay actividades completadas por el 100% de las escuelas en la zona.")
        else:
            st.info("No hay registros disponibles.")

    with tab_admin:
        st.subheader("Historial de Tareas Terminadas por el Administrador")
        try:
            sheet_completadas = spreadsheet.worksheet("Completadas")
            data_completadas = sheet_completadas.get_all_records()
            if data_completadas:
                df_completadas_admin = pd.DataFrame(data_completadas)
                
                for idx, row in df_completadas_admin.iterrows():
                    orig_idx_comp = idx + 2
                    actividad_nombre = row.get("Actividad", "Sin nombre")
                    f_ini = formatear_fecha_corta(str(row.get("Fecha Inicio", "")).split("T")[0])
                    f_fin = formatear_fecha_corta(str(row.get("Fecha Fin", "")).split("T")[0])
                    priv_raw = str(row.get("Privado", "False")).strip().lower()
                    es_priv = priv_raw in ["true", "sí", "si", "1"]
                    
                    badge_privado = "🔒 Privada" if es_priv else "🏫 General"
                    
                    with st.container(border=True):
                        col_card1, col_card2, col_card3 = st.columns([3, 1.5, 0.8])
                        with col_card1:
                            st.markdown(f"#### ✅ {actividad_nombre}")
                            st.markdown(f"*<small>📅 Del {f_ini} al {f_fin}</small>*", unsafe_allow_html=True)
                        with col_card2:
                            st.markdown(f"<br>**Tipo:** {badge_privado}", unsafe_allow_html=True)
                        with col_card3:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("🗑️ Eliminar", key=f"del_historial_{idx}"):
                                sheet_completadas.delete_rows(orig_idx_comp)
                                st.cache_data.clear()
                                st.success("¡Registro eliminado del historial!")
                                st.rerun()
            else:
                st.info("Aún no hay registros en la hoja de completadas.")
        except Exception as e:
            st.info("Aún no has marcado ninguna tarea como terminada individualmente o la pestaña 'Completadas' no está configurada.")
