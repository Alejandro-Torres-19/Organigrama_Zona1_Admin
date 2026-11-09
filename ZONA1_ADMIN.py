import hashlib
import hmac
import json
import time
from datetime import date

import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu
from streamlit_calendar import calendar
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
from streamlit_cookies_manager import EncryptedCookieManager

# Si es True, las actividades publicas que el admin ya movio a "Completadas"
# tambien cuentan en el total contra el que se mide el avance de cada escuela.
INCLUIR_HISTORIAL_EN_AVANCE = False

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Cronograma - Admin - Zona 1", page_icon="🏫", layout="wide"
)


# ======================= HELPERS (sin dependencia de la UI) =======================
def es_privado(val):
    return str(val).strip().lower() in ["true", "sí", "si", "1"]


def es_publica(val):
    return str(val).strip().lower() in ["false", "no", "0", "f"]


def _norm_fecha(v):
    return str(v).split("T")[0].strip()


def formatear_fecha_corta(fecha_val):
    if not fecha_val or str(fecha_val).strip() == "":
        return ""
    try:
        dt = pd.to_datetime(str(fecha_val).split("T")[0])
        return dt.strftime("%d-%m-%y")
    except Exception:
        return str(fecha_val).split("T")[0]


def clave_tarea(actividad, fecha_inicio):
    """Identifica una actividad por nombre + fecha de inicio (el nombre solo puede repetirse)."""
    return f"{str(actividad).strip()}|{_norm_fecha(fecha_inicio)}"


def hash_fila(row):
    base = f"{row['Actividad']}|{row['Fecha Inicio']}|{row['Fecha Fin']}|{row['Privado']}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()[:10]


def key_tarea(prefijo, row, vistos):
    """Key de widget basada en el CONTENIDO de la fila (no en su posicion).
    Si dos filas son identicas se les agrega un contador para evitar claves duplicadas."""
    h = hash_fila(row)
    n = vistos.get(h, 0)
    vistos[h] = n + 1
    return f"{prefijo}_{h}_{n}"


def borrar_fila_segura(ws, row):
    """Borra la fila que coincide por CONTENIDO (actividad, inicio, fin, privado).
    Evita borrar otra fila cuando la tabla en cache ya esta desactualizada."""
    act = str(row["Actividad"]).strip()
    ini = _norm_fecha(row["Fecha Inicio"])
    fin = _norm_fecha(row.get("Fecha Fin", "")) or ini
    priv = str(row.get("Privado", "")).strip().lower()
    filas = ws.get_all_values()
    for n, f in enumerate(filas[1:], start=2):
        f = list(f) + [""] * (4 - len(f))
        if (
            f[0].strip() == act
            and _norm_fecha(f[1]) == ini
            and (_norm_fecha(f[2]) or _norm_fecha(f[1])) == fin
            and f[3].strip().lower() == priv
        ):
            ws.delete_rows(n)
            return True
    return False


def calcular_avance_zona_core(spreadsheet, sheet_principal, lista_ccts, incluir_historial):
    """Avance por escuela = actividades PUBLICAS completadas por la escuela / total de
    actividades publicas. Una escuela sin filas en su pestana cuenta como 0 completadas
    (antes el denominador era el numero de filas de su pestana, lo que inflaba el %)."""
    hojas = {ws.title: ws for ws in spreadsheet.worksheets()}

    publicas = []
    fuentes = [sheet_principal]
    if incluir_historial and "Completadas" in hojas:
        fuentes.append(hojas["Completadas"])
    vistas = set()
    for ws in fuentes:
        for r in ws.get_all_records():
            actividad = str(r.get("Actividad", "")).strip()
            if not actividad or not es_publica(r.get("Privado", "")):
                continue
            f_ini = _norm_fecha(r.get("Fecha Inicio", ""))
            f_fin = _norm_fecha(r.get("Fecha Fin", "")) or f_ini
            clave = (clave_tarea(actividad, f_ini), f_fin)
            if clave in vistas:
                continue
            vistas.add(clave)
            publicas.append({"Actividad": actividad, "Fecha Inicio": f_ini, "Fecha Fin": f_fin})

    avances, detalles = [], {}
    for cct in lista_ccts:
        estatus = {}
        ws = hojas.get(cct)
        if ws is not None:
            try:
                for r in ws.get_all_records():
                    estatus[clave_tarea(r.get("Actividad", ""), r.get("Fecha Inicio", ""))] = (
                        str(r.get("Estado", "Pendiente")).strip().lower()
                    )
            except Exception:
                pass
        filas = []
        for t in publicas:
            hecho = estatus.get(clave_tarea(t["Actividad"], t["Fecha Inicio"])) == "completada"
            filas.append({**t, "Estado": "Completada" if hecho else "Pendiente"})
        df_esc = pd.DataFrame(filas, columns=["Actividad", "Fecha Inicio", "Fecha Fin", "Estado"])
        total = len(df_esc)
        completadas = int((df_esc["Estado"] == "Completada").sum()) if total else 0
        # sin actividades publicas asignadas no hay nada pendiente
        porcentaje = int(round(100 * completadas / total)) if total else 100
        avances.append({"Escuela": cct, "Porcentaje": porcentaje})
        detalles[cct] = df_esc
    return avances, detalles
# ======================= FIN HELPERS =======================


# --- CONEXIÓN DIRECTA A GOOGLE SHEETS CON CACHÉ ---
@st.cache_resource
def conectar_gspread():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    if "gcp_service_account" in st.secrets:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(credentials_dict, scopes=scope)
    else:
        st.error("No se encontraron las credenciales 'gcp_service_account' en secrets.toml")
        st.stop()
    client = gspread.authorize(creds)
    return client.open("ORGANIGRAMA_ZONA1")


# --- SEGURIDAD: LOGIN ADMINISTRADOR PERSISTENTE ---
# Se mantiene la contraseña original de st.secrets["admin_password"].
# Requiere instalar: streamlit-cookies-manager-v2
# Usa la contraseña original de admin_password para derivar internamente
# la clave de la cookie. NO se requiere auth_cookie_key en Secrets.
#
# IMPORTANTE: una cookie no puede durar eternamente. El navegador la guarda hasta
# un año y renovamos su vigencia cuando el administrador vuelve a utilizar la app.
# Esto evita cierre por inactividad y permite abrir Chrome otra vez sin contraseña.

COOKIE_NOMBRE = "admin_login_v1"
COOKIE_VIGENCIA_SEGUNDOS = 365 * 24 * 60 * 60
RENOVAR_DESPUES_SEGUNDOS = 7 * 24 * 60 * 60

password_admin = st.secrets.get("admin_password")
if not password_admin:
    st.error("Falta 'admin_password' en Secrets. No es seguro continuar.")
    st.stop()

# Solo se necesita tu contraseña de siempre: de ella se deriva una clave
# distinta para cifrar la cookie, sin guardarla en Chrome ni pedir otra clave.
# La protección de esta clave depende de la fortaleza de admin_password.
auth_cookie_key = hashlib.pbkdf2_hmac(
    "sha256",
    str(password_admin).encode("utf-8"),
    b"cronograma-zona1-admin-cookie-key-v1",
    200_000,
).hex()

cookies = EncryptedCookieManager(
    prefix="cronograma_zona1_admin/",
    password=str(auth_cookie_key),
)
if not cookies.ready():
    st.info("Cargando la sesión guardada...")
    st.stop()


def _firma_clave_actual():
    """Cambia al cambiar la contraseña de administrador: invalida cookies anteriores."""
    return hmac.new(
        str(auth_cookie_key).encode("utf-8"),
        ("cronograma-admin-v1:" + str(password_admin)).encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def _crear_cookie_login():
    """Guarda un comprobante cifrado; NUNCA guarda la contraseña en el navegador."""
    contenido = {"v": 1, "issued_at": int(time.time()), "fingerprint": _firma_clave_actual()}
    cookies[COOKIE_NOMBRE] = json.dumps(contenido, separators=(",", ":"))
    cookies.save()


def _cookie_login_valida():
    try:
        valor = cookies.get(COOKIE_NOMBRE)
        if not valor:
            return False
        contenido = json.loads(valor)
        ahora = int(time.time())
        creado = contenido.get("issued_at")
        if contenido.get("v") != 1 or type(creado) is not int:
            return False
        if creado > ahora + 60 or ahora - creado >= COOKIE_VIGENCIA_SEGUNDOS:
            return False
        firma = contenido.get("fingerprint", "")
        if not isinstance(firma, str) or not hmac.compare_digest(firma, _firma_clave_actual()):
            return False
        # Renovación deslizante: si regresan después de una semana,
        # la cookie vuelve a tener hasta 365 días desde esa visita.
        if ahora - creado >= RENOVAR_DESPUES_SEGUNDOS:
            _crear_cookie_login()
        return True
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def check_password():
    # Al volver a entrar desde este MISMO navegador, restaura la sesión.
    if not st.session_state.get("admin_sesion_cerrada") and _cookie_login_valida():
        return True

    _, col_centro, _ = st.columns([1, 1.5, 1])
    with col_centro:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center;'>🏫 Cronograma - Admin</h2>", unsafe_allow_html=True)
            st.markdown(
                "<p style='text-align: center; color: gray;'>Sistema de Gestión y Seguimiento - Zona 1</p>",
                unsafe_allow_html=True,
            )
            st.markdown("---")
            with st.form("form_acceso_admin", clear_on_submit=True):
                ingresada = st.text_input(
                    "🔑 Contraseña de Administrador",
                    type="password",
                    placeholder="Ingresa tu contraseña",
                )
                enviado = st.form_submit_button("Iniciar sesión", use_container_width=True)
            if enviado:
                if hmac.compare_digest(
                    str(ingresada).encode("utf-8"), str(password_admin).encode("utf-8")
                ):
                    st.session_state["admin_sesion_cerrada"] = False
                    _crear_cookie_login()
                    st.rerun()
                else:
                    st.error("😕 Contraseña incorrecta. Inténtalo de nuevo.")
    return False


def cerrar_sesion():
    """Elimina el recordatorio de acceso de ESTE navegador."""
    if COOKIE_NOMBRE in cookies:
        del cookies[COOKIE_NOMBRE]
    cookies.save()
    st.session_state["admin_sesion_cerrada"] = True
    st.rerun()


if not check_password():
    st.stop()

# --- CONEXIÓN (solo después de autenticarse) ---
try:
    spreadsheet = conectar_gspread()
    sheet_principal = spreadsheet.get_worksheet(0)  # Pestaña 1: General (Hoja 1)
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


# --- CARGAR Y DEPURAR DATOS DE LA HOJA PRINCIPAL ---
@st.cache_data(ttl=5)
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


@st.cache_data(ttl=15)
def calcular_avance_zona(lista_ccts):
    return calcular_avance_zona_core(
        spreadsheet, sheet_principal, list(lista_ccts), INCLUIR_HISTORIAL_EN_AVANCE
    )


# --- ACCIONES SOBRE ACTIVIDADES ---
def completar_actividad(row):
    """Copia la actividad a 'Completadas' y SOLO si se guardó, la borra de la hoja principal."""
    try:
        ws_comp = spreadsheet.worksheet("Completadas")
        ws_comp.append_row(
            [row["Actividad"], row["Fecha Inicio"], row["Fecha Fin"], row["Privado"], "Completada", row["Color"]]
        )
    except Exception as e:
        st.error(f"No se pudo guardar en 'Completadas': {e}")
        return False
    if not borrar_fila_segura(sheet_principal, row):
        st.warning("La actividad ya no estaba en la hoja principal (quizá se completó desde otro lugar).")
    st.cache_data.clear()
    return True


def eliminar_actividad(row):
    borrar_fila_segura(sheet_principal, row)
    try:
        borrar_fila_segura(spreadsheet.worksheet("Completadas"), row)
    except Exception:
        pass
    st.cache_data.clear()


def texto_rango(row, sufijo=""):
    f_ini_raw = _norm_fecha(row["Fecha Inicio"])
    f_fin_raw = _norm_fecha(row["Fecha Fin"]) if row["Fecha Fin"] else f_ini_raw
    f_ini_fmt = formatear_fecha_corta(f_ini_raw)
    f_fin_fmt = formatear_fecha_corta(f_fin_raw)
    if f_ini_raw == f_fin_raw or not row["Fecha Fin"] or str(row["Fecha Fin"]).strip() == "":
        return f"📅 {f_ini_fmt}"
    return f"📅 Del {f_ini_fmt} al {f_fin_fmt}{sufijo}"


def render_tarjeta(row, prefijo, etiqueta, vistos, sufijo_rango=""):
    icono = "🔒 " if es_privado(row["Privado"]) else "🏫 "
    rango = texto_rango(row, sufijo_rango)
    k = key_tarea(prefijo, row, vistos)
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([3, 1, 0.7, 0.7])
        with c1:
            st.markdown(
                f"**{icono} {row['Actividad']}** &nbsp;|&nbsp; *<small>{rango}</small>*",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(etiqueta, unsafe_allow_html=True)
        with c3:
            if st.button("✔️ Marcar", key=f"ok_{k}"):
                if completar_actividad(row):
                    st.success("¡Completada y movida al historial!")
                    st.rerun()
        with c4:
            if st.button("🗑️ Borrar", key=f"del_{k}"):
                eliminar_actividad(row)
                st.success("¡Eliminada por completo!")
                st.rerun()


# --- FUNCIÓN PARA GENERAR GRÁFICA CIRCULAR TIPO DONA ---
def crear_grafica_dona(porcentaje, titulo_centro=""):
    completado = porcentaje
    pendiente = 100 - porcentaje

    fig = go.Figure(
        data=[
            go.Pie(
                values=[completado, pendiente if completado > 0 else 100],
                labels=["Completado", "Pendiente"],
                hole=0.6,
                marker=dict(colors=["#198754", "#dc3545"]),
                textinfo="none",
                hoverinfo="none",
            )
        ]
    )

    fig.update_layout(
        showlegend=False,
        margin=dict(t=10, b=10, l=10, r=10),
        height=220,
        annotations=[
            dict(
                text=f"<b>{completado}%</b><br><span style='font-size:12px; color:gray;'>{titulo_centro}</span>",
                x=0.5,
                y=0.5,
                font_size=18,
                showarrow=False,
            )
        ],
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
            "⚪ Gris (Extra)": "#6c757d",
        }
        color_seleccionado_key = st.selectbox("Función / Color", list(opciones_colores.keys()))
        color_actividad = opciones_colores[color_seleccionado_key]

        submit_btn = st.form_submit_button("Guardar en Calendario")
        if submit_btn:
            if nom_actividad:
                nueva_fila = [
                    nom_actividad,
                    f_inicio.strftime("%Y-%m-%d"),
                    f_fin.strftime("%Y-%m-%d"),
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

    st.markdown("---")
    if st.button("🚪 Cerrar sesión", use_container_width=True, key="cerrar_sesion_admin"):
        cerrar_sesion()

# --- 1. SECCIÓN: CRONOGRAMA Y GESTIÓN ---
if selected == "Cronograma y Gestión":
    st.title("📅 Cronograma Global y Gestión de Actividades")
    st.markdown("Administra las actividades generales para las 12 escuelas y controla tus tareas privadas.")

    hoy_dt = pd.Timestamp(date.today()).normalize()

    if not df_tareas.empty:
        df_tareas["Fecha_Inicio_dt"] = pd.to_datetime(
            df_tareas["Fecha Inicio"].astype(str).str.split("T").str[0], errors="coerce"
        ).dt.normalize()
        df_tareas["Fecha_Fin_dt"] = pd.to_datetime(
            df_tareas["Fecha Fin"].astype(str).str.split("T").str[0], errors="coerce"
        ).dt.normalize()
        df_tareas["Fecha_Fin_dt"] = df_tareas["Fecha_Fin_dt"].fillna(df_tareas["Fecha_Inicio_dt"])

        no_completada = df_tareas["Estado"].str.lower() != "completada"
        atrasadas_df = df_tareas[(df_tareas["Fecha_Fin_dt"] < hoy_dt) & no_completada]
        hoy_df = df_tareas[
            (df_tareas["Fecha_Inicio_dt"] <= hoy_dt) & (df_tareas["Fecha_Fin_dt"] >= hoy_dt) & no_completada
        ]

        # --- SECCIÓN: ACTIVIDADES ATRASADAS ---
        st.markdown("### ⚠️ Actividades Atrasadas")
        if not atrasadas_df.empty:
            vistos = {}
            for _, row in atrasadas_df.iterrows():
                render_tarjeta(row, "atrasada", "🔴 Atrasada", vistos)
        else:
            st.success("🎉 ¡Excelente! No tienes actividades atrasadas.")

        st.markdown("---")

        # --- SECCIÓN: PENDIENTES DE HOY ---
        st.markdown("### 🔔 Pendientes de Hoy")
        if not hoy_df.empty:
            vistos = {}
            for _, row in hoy_df.iterrows():
                render_tarjeta(row, "hoy", "🟠 Pendiente", vistos)
        else:
            st.success("🎉 ¡Excelente! No hay actividades programadas específicamente para el día de hoy.")
    else:
        st.info("No hay actividades registradas en el sistema.")

    st.markdown("---")

    # --- CALENDARIO GLOBAL Y AGENDA QUINCENAL ---
    st.markdown("### 🗓️ Visualización del Calendario y Agenda")

    st.markdown(
        """
        <style>
        .fc-list-event-time { display: none !important; }
        .fc-view-harness { min-height: 700px !important; }
        </style>
    """,
        unsafe_allow_html=True,
    )

    calendar_events = []
    if not df_tareas.empty:
        for _, row in df_tareas.iterrows():
            es_priv = es_privado(row["Privado"])
            icono_titulo = "🔒 " if es_priv else "🏫 "

            f_ini_raw = _norm_fecha(row["Fecha Inicio"])
            f_fin_raw = _norm_fecha(row["Fecha Fin"]) if row["Fecha Fin"] else f_ini_raw

            try:
                f_ini_dt = pd.to_datetime(f_ini_raw).strftime("%Y-%m-%d")
                f_fin_dt = (pd.to_datetime(f_fin_raw) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            except Exception:
                f_ini_dt = f_ini_raw
                f_fin_dt = f_fin_raw

            estado_evt = str(row["Estado"]).strip().lower()
            if es_priv and estado_evt == "completada":
                color_evento = "#28a745"
            else:
                color_evento = row["Color"] if row["Color"] else "#3788d8"

            calendar_events.append(
                {
                    "title": f"{icono_titulo}{row['Actividad']}",
                    "start": f_ini_dt,
                    "end": f_fin_dt,
                    "color": color_evento,
                    "allDay": True,
                }
            )

    calendar_options = {
        "editable": False,
        "selectable": True,
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "listFortnight,dayGridMonth",
        },
        "views": {
            "listFortnight": {"type": "list", "duration": {"days": 15}, "buttonText": "Agenda Quincenal"},
            "dayGridMonth": {"buttonText": "Mes"},
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
        vistos = {}
        for _, row in df_tareas.iterrows():
            render_tarjeta(row, "gestion", "🟠 Pendiente", vistos, sufijo_rango=" (Rango Activo)")
    else:
        st.info("No hay actividades registradas.")


# --- 2. SECCIÓN: DASHBOARD DE ZONA ---
elif selected == "Dashboard de Zona":
    st.title("📊 Dashboard Ejecutivo de Avance por Escuela")
    st.markdown("Monitoreo en tiempo real del cumplimiento de los planteles de la Zona 1.")

    lista_ccts = (
        df_usuarios_admin["CCT"].astype(str).str.strip().unique().tolist()
        if not df_usuarios_admin.empty and "CCT" in df_usuarios_admin.columns
        else []
    )

    avances_data, detalles_escuelas = calcular_avance_zona(tuple(lista_ccts))
    df_avances = pd.DataFrame(avances_data)

    promedio_zona = int(df_avances["Porcentaje"].mean()) if not df_avances.empty else 0
    st.metric(label="📈 Avance Global Promedio de la Zona 1", value=f"{promedio_zona}%")
    st.caption("El avance de cada escuela es: actividades públicas completadas ÷ total de actividades públicas.")

    st.markdown("---")

    # Galería de Gráficas Circulares Tipo Dona por CCT
    st.markdown("### 📈 Avance de la Zona 1")
    st.markdown("Estatus de cumplimiento de todos los planteles de la zona:")

    if not df_avances.empty:
        cols = st.columns(3)
        for idx, row in df_avances.iterrows():
            with cols[idx % 3]:
                with st.container(border=True):
                    fig_dona = crear_grafica_dona(row["Porcentaje"], row["Escuela"])
                    st.plotly_chart(fig_dona, use_container_width=True, key=f"admin_dona_{idx}")

    st.markdown("---")

    # Auditoría y Desglose Detallado por CCT
    st.markdown("### 🔍 Auditoría y Desglose por Plantel")
    st.markdown(
        "Selecciona una escuela (CCT) para revisar puntualmente qué actividades ha completado y cuáles tiene pendientes o atrasadas."
    )

    if lista_ccts:
        escuela_seleccionada_admin = st.selectbox(
            "🏫 Selecciona el Plantel a Auditar (CCT)", lista_ccts, key="select_audit_cct"
        )
        df_audit = detalles_escuelas.get(escuela_seleccionada_admin, pd.DataFrame())

        if not df_audit.empty:
            col_completadas_admin = df_audit[df_audit["Estado"] == "Completada"]
            col_pendientes_admin = df_audit[df_audit["Estado"] != "Completada"]

            tab_det_comp, tab_det_pend = st.tabs(
                [
                    f"✅ Completadas ({len(col_completadas_admin)})",
                    f"⏳ Pendientes / Atrasadas ({len(col_pendientes_admin)})",
                ]
            )

            def _rango(r):
                f_ini = formatear_fecha_corta(r.get("Fecha Inicio", ""))
                f_fin = formatear_fecha_corta(r.get("Fecha Fin", ""))
                return f"📅 Del {f_ini} al {f_fin}" if f_ini != f_fin else f"📅 {f_ini}"

            with tab_det_comp:
                if not col_completadas_admin.empty:
                    for _, row_c in col_completadas_admin.iterrows():
                        with st.container(border=True):
                            st.markdown(
                                f"**✅ {row_c['Actividad']}** &nbsp;|&nbsp; *<small>{_rango(row_c)}</small>*",
                                unsafe_allow_html=True,
                            )
                else:
                    st.info(f"{escuela_seleccionada_admin} aún no registra actividades completadas.")

            with tab_det_pend:
                if not col_pendientes_admin.empty:
                    hoy_ts = pd.Timestamp(date.today()).normalize()
                    for _, row_p in col_pendientes_admin.iterrows():
                        fin_dt = pd.to_datetime(row_p["Fecha Fin"], errors="coerce")
                        etiqueta = (
                            "🔴 *Atrasada*" if pd.notna(fin_dt) and fin_dt.normalize() < hoy_ts else "🟠 *Pendiente*"
                        )
                        with st.container(border=True):
                            st.markdown(
                                f"**⏳ {row_p['Actividad']}** &nbsp;|&nbsp; *<small>{_rango(row_p)}</small>* &nbsp;|&nbsp; {etiqueta}",
                                unsafe_allow_html=True,
                            )
                else:
                    st.success(f"¡{escuela_seleccionada_admin} está al corriente con el 100% de sus actividades!")
        else:
            st.info("No hay actividades públicas registradas.")
    else:
        st.warning("No se encontraron CCTs en la pestaña 'INICIOS SESIÓN'.")


# --- 3. SECCIÓN: TAREAS COMPLETADAS ---
elif selected == "Tareas Completadas":
    st.title("✅ Historial de Tareas Completadas")
    st.markdown("Visualiza por separado las actividades concluidas a nivel zona y las concluidas individualmente.")

    tab_zona, tab_admin = st.tabs(
        ["🌍 Completadas a Nivel Zona (100% Escuelas)", "👤 Completadas Individualmente (Admin)"]
    )

    with tab_zona:
        st.subheader("Tareas con 100% de Cumplimiento en la Zona")
        if not df_tareas.empty and "Estado" in df_tareas.columns:
            completadas_zona = df_tareas[df_tareas["Estado"] == "Completada Global"]
            if not completadas_zona.empty:
                st.dataframe(
                    completadas_zona[["Actividad", "Fecha Inicio", "Fecha Fin", "Privado"]],
                    use_container_width=True,
                    hide_index=True,
                )
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
                vistos = {}

                for _, row in df_completadas_admin.iterrows():
                    actividad_nombre = row.get("Actividad", "Sin nombre")
                    f_ini = formatear_fecha_corta(_norm_fecha(row.get("Fecha Inicio", "")))
                    f_fin = formatear_fecha_corta(_norm_fecha(row.get("Fecha Fin", "")))
                    badge_privado = "🔒 Privada" if es_privado(row.get("Privado", "False")) else "🏫 General"

                    fila_h = {
                        "Actividad": actividad_nombre,
                        "Fecha Inicio": row.get("Fecha Inicio", ""),
                        "Fecha Fin": row.get("Fecha Fin", ""),
                        "Privado": row.get("Privado", ""),
                    }
                    k = key_tarea("hist", fila_h, vistos)

                    with st.container(border=True):
                        col_card1, col_card2, col_card3 = st.columns([3, 1.5, 0.8])
                        with col_card1:
                            st.markdown(f"#### ✅ {actividad_nombre}")
                            st.markdown(f"*<small>📅 Del {f_ini} al {f_fin}</small>*", unsafe_allow_html=True)
                        with col_card2:
                            st.markdown(f"<br>**Tipo:** {badge_privado}", unsafe_allow_html=True)
                        with col_card3:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("🗑️ Eliminar", key=f"del_{k}"):
                                borrar_fila_segura(sheet_completadas, pd.Series(fila_h))
                                st.cache_data.clear()
                                st.success("¡Registro eliminado del historial!")
                                st.rerun()
            else:
                st.info("Aún no hay registros en la hoja de completadas.")
        except Exception:
            st.info(
                "Aún no has marcado ninguna tarea como terminada individualmente o la pestaña 'Completadas' no está configurada."
            )
