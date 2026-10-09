from datetime import datetime, time, date
import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu
from streamlit_calendar import calendar
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Panel Maestro - Zona 1", page_icon="🏫", layout="wide"
)

# --- CREDENCIALES Y CONEXIÓN A GOOGLE SHEETS ---
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
    sheet_principal = spreadsheet.get_worksheet(0) # Pestaña 1: Maestro / General
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# --- SEGURIDAD: LOGIN MAESTRO (DISEÑO MEJORADO Y AMIGABLE) ---
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
                st.markdown("<h2 style='text-align: center;'>🏫 Panel Maestro</h2>", unsafe_allow_html=True)
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
                st.markdown("<h2 style='text-align: center;'>🏫 Panel Maestro</h2>", unsafe_allow_html=True)
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

# --- CARGAR DATOS DE LA HOJA PRINCIPAL ---
def cargar_datos_principales():
    data = sheet_principal.get_all_records()
    if not data:
        df = pd.DataFrame(
            columns=[
                "Actividad",
                "Fecha Inicio",
                "Fecha Fin",
                "Privado",
                "Estado",
                "Color",
            ]
        )
    else:
        df = pd.DataFrame(data)
    return df

df_tareas = cargar_datos_principales()

# --- BARRA LATERAL DE NAVEGACIÓN ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/school.png", width=80)
    st.title("Supervisión Zona 1")
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
    st.title("📅 Cronograma Global y Gestión de Actividades (Maestro)")
    st.markdown("Administra las actividades generales para las 12 escuelas y controla tus tareas privadas.")

    # --- SECCIÓN: PENDIENTES DE HOY (CORREGIDA Y FUNCIONAL) ---
    st.markdown("### 🔔 Pendientes de Hoy")
    hoy_actual = date.today()
    
    if not df_tareas.empty:
        df_tareas["Fecha Inicio"] = pd.to_datetime(df_tareas["Fecha Inicio"]).dt.date
        df_tareas["Fecha Fin"] = pd.to_datetime(df_tareas["Fecha Fin"]).dt.date
        
        pendientes_hoy = df_tareas[
            (df_tareas["Fecha Inicio"] <= hoy_actual) & 
            (df_tareas["Fecha Fin"] >= hoy_actual)
        ]
        
        if not pendientes_hoy.empty:
            cols_hoy = st.columns(min(len(pendientes_hoy), 3))
            for idx, row in pendientes_hoy.iterrows():
                col_idx = idx % len(cols_hoy)
                with cols_hoy[col_idx]:
                    tipo = "🔒 Privada" if row["Privado"] == "Sí" else "🏫 General"
                    st.info(f"**{row['Actividad']}**\n\n*Tipo:* {tipo}\n*Vigencia:* {row['Fecha Inicio']} al {row['Fecha Fin']}")
        else:
            st.success("🎉 ¡Excelente! No hay actividades programadas para el día de hoy.")
    else:
        st.info("No hay actividades registradas en el sistema.")

    st.markdown("---")

    # --- FORMULARIO DE NUEVA ACTIVIDAD ---
    with st.expander("➕ Registrar Nueva Actividad / Tarea", expanded=False):
        with st.form("form_nueva_actividad"):
            col1, col2 = st.columns(2)
            with col1:
                nom_actividad = st.text_input("Nombre de la Actividad")
                es_privada = st.selectbox("¿Es una tarea privada?", ["No", "Sí"])
            with col2:
                f_inicio = st.date_input("Fecha de Inicio", value=date.today())
                
                solo_un_dia = st.checkbox("¿La actividad es de un solo día?")
                if solo_un_dia:
                    f_fin = f_inicio
                    st.caption("Se asignará la misma fecha de inicio como cierre.")
                else:
                    f_fin = st.date_input("Fecha de Fin", value=date.today())

            color_actividad = st.color_picker("Color en el Calendario", "#3788d8")
            
            submit_btn = st.form_submit_button("Guardar Actividad")
            if submit_btn:
                if nom_actividad:
                    nueva_fila = [
                        nom_actividad,
                        str(f_inicio),
                        str(f_fin),
                        es_privada,
                        "Pendiente",
                        color_actividad,
                    ]
                    sheet_principal.append_row(nueva_fila)
                    st.success("¡Actividad registrada exitosamente!")
                    st.rerun()
                else:
                    st.warning("Por favor, ingresa al menos el nombre de la actividad.")

    st.markdown("---")

    # --- CALENDARIO GLOBAL Y AGENDA QUINCENAL ---
    st.markdown("### 🗓️ Visualización del Calendario y Agenda")

    calendar_events = []
    if not df_tareas.empty:
        for _, row in df_tareas.iterrows():
            try:
                f_fin_obj = datetime.strptime(str(row["Fecha Fin"]), "%Y-%m-%d").date()
                f_fin_ajustada = str(pd.to_datetime(row["Fecha Fin"]) + pd.Timedelta(days=1)).split()[0]
            except:
                f_fin_ajustada = str(row["Fecha Fin"])

            calendar_events.append({
                "title": f"{'🔒 ' if row['Privado']=='Sí' else '🏫 '}{row['Actividad']}",
                "start": str(row["Fecha Inicio"]),
                "end": f_fin_ajustada,
                "color": row["Color"],
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
            "listFortnight": {
                "type": "list",
                "duration": {"days": 15},
                "buttonText": "Agenda Quincenal"
            }
        },
        "initialView": "listFortnight",
        "locale": "es",
    }

    calendar(events=calendar_events, options=calendar_options)


# --- 2. SECCIÓN: DASHBOARD DE ZONA ---
elif selected == "Dashboard de Zona":
    st.title("📊 Dashboard Ejecutivo de Avance por Escuela")
    st.markdown("Monitoreo en tiempo real del cumplimiento de las 12 escuelas de la Zona 1.")

    nombres_escuelas = [f"Escuela {i}" for i in range(1, 13)]
    avances_data = []
    
    for i in range(1, 13):
        nombre_pestana = f"Escuela_{i}"
        try:
            ws_escuela = spreadsheet.worksheet(nombre_pestana)
            data_escuela = ws_escuela.get_all_records()
            if data_escuela:
                df_esc = pd.DataFrame(data_escuela)
                total_tareas = len(df_esc)
                if total_tareas > 0 and "Completada" in df_esc.columns:
                    completadas = len(df_esc[df_esc["Completada"] == True])
                    porcentaje = int((completadas / total_tareas) * 100)
                else:
                    porcentaje = 0
            else:
                porcentaje = 0
        except Exception:
            porcentaje = 0
            
        avances_data.append({"Escuela": f"Escuela {i}", "Porcentaje": porcentaje})

    df_avances = pd.DataFrame(avances_data)

    promedio_zona = int(df_avances["Porcentaje"].mean())
    st.metric(label="📈 Avance Global Promedio de la Zona 1", value=f"{promedio_zona}%")

    st.markdown("---")
    
    st.markdown("### Porcentaje de Avance Individual por Escuela")
    st.bar_chart(df_avances.set_index("Escuela"), horizontal=True)

    st.markdown("### Detalle Tabular")
    st.dataframe(df_avances, use_container_width=True)


# --- 3. SECCIÓN: TAREAS COMPLETADAS ---
elif selected == "Tareas Completadas":
    st.title("✅ Historial de Tareas Completadas a Nivel Zona")
    st.markdown("Listado de actividades que han cumplido con el 100% de aprobación de las 12 escuelas.")

    if not df_tareas.empty:
        completadas_global = df_tareas[df_tareas["Estado"] == "Completada"]
        if not completadas_global.empty:
            st.dataframe(completadas_global, use_container_width=True)
        else:
            st.info("Aún no hay actividades completadas por el 100% de las escuelas en la zona.")
    else:
        st.info("No hay registros en el sistema.")
