from datetime import datetime, time, date
import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu
from streamlit_calendar import calendar
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Cronograma - Admin - Zona 1", page_icon="🏫", layout="wide"
)

# --- CONEXIÓN DIRECTA A GOOGLE SHEETS (SIN CACHÉ PARA FORZAR CAMBIOS) ---
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
    sheet_principal = spreadsheet.get_worksheet(0) # Pestaña 1: General
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

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
def cargar_datos_principales():
    data = sheet_principal.get_all_records()
    if not data:
        df = pd.DataFrame(columns=["Actividad", "Fecha Inicio", "Fecha Fin", "Privado", "Estado", "Color"])
    else:
        df = pd.DataFrame(data)
        # Limpiar nombres de columnas por espacios o mayúsculas
        df.columns = [str(col).strip() for col in df.columns]
        
        # Mapeo de seguridad para Fecha Fin
        if "Fecha FIn" in df.columns and "Fecha Fin" not in df.columns:
        # Si existe Fecha FIn con i minúscula/mayúscula
            pass # Ya lo manejamos abajo
        
        for col in ["Actividad", "Fecha Inicio", "Fecha Fin", "Privado", "Estado", "Color"]:
            if col not in df.columns:
                # Buscar variaciones comunes
                match = [c for c in df.columns if col.lower().replace(" ", "") in c.lower().replace(" ", "")]
                if match:
                    df.rename(columns={match[0]: col}, inplace=True)
                else:
                    df[col] = ""
                    
        # ASEGURAR QUE LAS FECHAS SE LEAN CORRECTAMENTE
        df["Fecha Inicio"] = df["Fecha Inicio"].astype(str).str.split("T").str[0].str.strip()
        
        # Detectar columna de fin (puede venir como 'Fecha Fin', 'Fecha FIn', etc.)
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

# --- BARRA LATERAL: REGISTRO DE ACTIVIDADES (ARRIBA) Y NAVEGACIÓN (ABAJO) ---
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

    hoy_dt = pd.Timestamp(date.today()).normalize()
    
    if not df_tareas.empty:
        df_tareas["Fecha_Inicio_dt"] = pd.to_datetime(df_tareas["Fecha Inicio"].astype(str).str.split("T").str[0], errors='coerce').dt.normalize()
        df_tareas["Fecha_Fin_dt"] = pd.to_datetime(df_tareas["Fecha Fin"].astype(str).str.split("T").str[0], errors='coerce').dt.normalize()
        df_tareas["Fecha_Fin_dt"] = df_tareas["Fecha_Fin_dt"].fillna(df_tareas["Fecha_Inicio_dt"])
        
        # 1. Bloque de Atrasadas (Fecha fin estrictamente menor a hoy y no completadas)
        atrasadas_df = df_tareas[
            (df_tareas["Fecha_Fin_dt"] < hoy_dt) & 
            (df_tareas["Estado"].str.lower() != "completada")
        ]
        
        # 2. Bloque de Hoy (La fecha actual está entre inicio y fin inclusive)
        hoy_df = df_tareas[
            (df_tareas["Fecha_Inicio_dt"] <= hoy_dt) & 
            (df_tareas["Fecha_Fin_dt"] >= hoy_dt) & 
            (df_tareas["Estado"].str.lower() != "completada")
        ]

        # --- SECCIÓN: ACTIVIDADES ATRASADAS ---
        st.markdown("### ⚠️ Actividades Atrasadas")
        if not atrasadas_df.empty:
            for idx, row in atrasadas_df.iterrows():
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
                    col_p1, col_p2, col_p3 = st.columns([3.5, 1, 0.8])
                    with col_p1:
                        st.markdown(f"**{icono} {row['Actividad']}** &nbsp;|&nbsp; *<small>{rango_fechas}</small>*", unsafe_allow_html=True)
                    with col_p2:
                        st.markdown("🔴 Atrasada", unsafe_allow_html=True)
                    with col_p3:
                        if st.button("✔️ Marcar", key=f"btn_atrasada_{idx}"):
                            sheet_principal.update_cell(idx + 2, 5, "Completada")
                            st.success("¡Completada!")
                            st.rerun()
        else:
            st.success("🎉 ¡Excelente! No tienes actividades atrasadas.")

        st.markdown("---")

        # --- SECCIÓN: PENDIENTES DE HOY ---
        st.markdown("### 🔔 Pendientes de Hoy")
        if not hoy_df.empty:
            for idx, row in hoy_df.iterrows():
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
                    col_h1, col_h2, col_h3 = st.columns([3.5, 1, 0.8])
                    with col_h1:
                        st.markdown(f"**{icono} {row['Actividad']}** &nbsp;|&nbsp; *<small>{rango_fechas}</small>*", unsafe_allow_html=True)
                    with col_h2:
                        st.markdown("🟠 Pendiente", unsafe_allow_html=True)
                    with col_h3:
                        if st.button("✔️ Marcar", key=f"btn_hoy_{idx}"):
                            sheet_principal.update_cell(idx + 2, 5, "Completada")
                            st.success("¡Completada!")
                            st.rerun()
        else:
            st.success("🎉 ¡Excelente! No hay actividades programadas específicamente para el día de hoy.")
    else:
        st.info("No hay actividades registradas en el sistema.")

    st.markdown("---")

    # --- CALENDARIO GLOBAL Y AGENDA QUINCENAL (EXTENDIDO CORRECTAMENTE EN TODO EL RANGO VISUAL) ---
    st.markdown("### 🗓️ Visualización del Calendario y Agenda")

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
                # FullCalendar requiere fecha final exclusiva (+1 día) para abarcar todo el rango visualmente
                f_fin_dt = (pd.to_datetime(f_fin_raw) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            except:
                f_ini_dt = f_ini_raw
                f_fin_dt = f_fin_raw

            calendar_events.append({
                "title": f"{icono_titulo}{row['Actividad']}",
                "start": f_ini_dt,
                "end": f_fin_dt,
                "color": row["Color"] if row["Color"] else "#3788d8",
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
            },
            "dayGridMonth": {
                "buttonText": "Mes"
            }
        },
        "initialView": "listFortnight",
        "locale": "es",
    }

    calendar(events=calendar_events, options=calendar_options)

    st.markdown("---")

   # --- SECCIÓN: GESTIÓN DE TAREAS (RANGO FORZADO) ---
    st.markdown("### 📋 Gestión y Control de Actividades Individuales")
    st.markdown("Marca aquí las actividades que has concluido de forma personal o interna como administrador.")

    if not df_tareas.empty:
        for idx, row in df_tareas.iterrows():
            priv_val = str(row["Privado"]).strip().lower()
            es_privada_bool = priv_val in ["true", "sí", "si", "1"]
            icono = "🔒 " if es_privada_bool else "🏫 "
            
            f_ini_raw = str(row["Fecha Inicio"]).split("T")[0]
            f_fin_raw = str(row["Fecha Fin"]).split("T")[0] if row["Fecha Fin"] else f_ini_raw
            
            f_ini_fmt = formatear_fecha_corta(f_ini_raw)
            f_fin_fmt = formatear_fecha_corta(f_fin_raw)
            
            # IMPRESIÓN FORZADA DEL RANGO PARA VERIFICACIÓN VISUAL
            if f_ini_fmt != f_fin_fmt and f_fin_fmt != "":
                rango_fechas = f"📅 Del {f_ini_fmt} al {f_fin_fmt} (Rango Activo)"
            else:
                rango_fechas = f"📅 {f_ini_fmt}"
            
            estado_actual = row["Estado"] if "Estado" in df_tareas.columns and row["Estado"] else "Pendiente"
            
            with st.container(border=True):
                col_t1, col_t2, col_t3 = st.columns([3.5, 1, 0.8])
                with col_t1:
                    st.markdown(f"**{icono} {row['Actividad']}** &nbsp;|&nbsp; *<small>{rango_fechas}</small>*", unsafe_allow_html=True)
                with col_t2:
                    if estado_actual.lower() == "completada":
                        st.markdown("🟢 Completada", unsafe_allow_html=True)
                    else:
                        st.markdown("🟠 Pendiente", unsafe_allow_html=True)
                with col_t3:
                    if estado_actual.lower() != "completada":
                        if st.button("✔️ Marcar", key=f"btn_terminar_{idx}"):
                            sheet_principal.update_cell(idx + 2, 5, "Completada")
                            st.success("¡Completada!")
                            st.rerun()
                    else:
                        st.markdown("✅ *Lista*", unsafe_allow_html=True)
    else:
        st.info("No hay actividades registradas.")


# --- 2. SECCIÓN: DASHBOARD DE ZONA ---
elif selected == "Dashboard de Zona":
    st.title("📊 Dashboard Ejecutivo de Avance por Escuela")
    st.markdown("Monitoreo en tiempo real del cumplimiento de las 12 escuelas de la Zona 1.")

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
    st.title("✅ Historial de Tareas Completadas")
    st.markdown("Visualiza por separado las actividades concluidas a nivel zona y las concluidas individualmente.")

    tab_zona, tab_admin = st.tabs(["🌍 Completadas a Nivel Zona (100% Escuelas)", "👤 Completadas Individualmente (Admin)"])

    with tab_zona:
        st.subheader("Tareas con 100% de Cumplimiento en la Zona")
        if not df_tareas.empty and "Estado" in df_tareas.columns:
            completadas_zona = df_tareas[df_tareas["Estado"] == "Completada Global"]
            if not completadas_zona.empty:
                st.dataframe(completadas_zona[["Actividad", "Fecha Inicio", "Fecha Fin", "Privado"]], use_container_width=True)
            else:
                st.info("Aún no hay actividades completadas por el 100% de las escuelas en la zona.")
        else:
            st.info("No hay registros disponibles.")

    with tab_admin:
        st.subheader("Tareas Marcadas como Terminadas por el Administrador")
        if not df_tareas.empty and "Estado" in df_tareas.columns:
            completadas_admin = df_tareas[df_tareas["Estado"] == "Completada"]
            if not completadas_admin.empty:
                st.dataframe(completadas_admin[["Actividad", "Fecha Inicio", "Fecha Fin", "Privado"]], use_container_width=True)
            else:
                st.info("Aún no has marcado ninguna tarea como terminada individualmente.")
        else:
            st.info("No hay registros disponibles.")
