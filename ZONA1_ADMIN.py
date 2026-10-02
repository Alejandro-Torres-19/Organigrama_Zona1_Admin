# IMPORTAR DEPENDENCIAS NECESARIAS
import datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
from streamlit_calendar import calendar

# CONFIGURACIÓN INICIAL PÁGINA
st.set_page_config(
    page_title="CRONOGRAMA Zona 1 (Admin)", page_icon="🔒", layout="wide"
)

# DEFINIR CONTRASEÑA CORRECTA
PASWORD_CORRECTA = "Taguch_77"

# AUTENTICACIÓN USUARIO
if "autenticado" not in st.session_state:
  st.session_state.autenticado = False


def verificar_password():
  if st.session_state.get("Ingrese Contraseña") == PASWORD_CORRECTA:
    st.session_state.autenticado = True
    if "Ingrese Contraseña" in st.session_state:
      del st.session_state["Ingrese Contraseña"]
  else:
    st.session_state.autenticado = False
    st.error("Contraseña incorrecta, intente nuevamente")


# CONEXIÓN GOOGLE SHEETS
@st.cache_resource
def conectar_google_sheets():
  scope = [
      "https://spreadsheets.google.com/feeds",
      "https://www.googleapis.com/auth/drive",
  ]
  creds_dict = dict(st.secrets["gcp_service_account"])
  creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
  client = gspread.authorize(creds)
  sheet = client.open("ORGANIGRAMA_ZONA1").sheet1
  return sheet


# PANTALLA DE LOGIN
if not st.session_state.autenticado:
  st.title("🔒 Acceso Restringido🔒")
  st.subheader("Ingresa la contraseña para acceder")

  st.text_input(
      "Contraseña:",
      type="password",
      key="Ingrese Contraseña",
      on_change=verificar_password,
  )
  st.button("Iniciar Sesión", on_click=verificar_password)

# PANTALLA PRINCIPAL DESPUÉS DE LOGIN EXITOSO
else:
  st.sidebar.button(
      "🚪 Cerrar Sesión",
      on_click=lambda: st.session_state.update(autenticado=False),
  )

  st.title("👑 CRONOGRAMA ZONA 1 (Admin) 👑")

  try:
    sheet = conectar_google_sheets()
  except Exception as e:
    st.error(f"Error al conectarse a Google Sheets: {e}")
    st.stop()

  # OBTENER DATOS CON CACHÉ Y PROTECCIÓN CONTRA CUOTAS (TTL=2)
  @st.cache_data(ttl=2)
  def obtener_datos_actualizados():
    for intento in range(3):
      try:
        rows = sheet.get_all_values()
        if len(rows) > 1:
          headers = [str(h).strip() for h in rows[0]]
          data_rows = rows[1:]
          df = pd.DataFrame(data_rows, columns=headers)
          return df.loc[:, df.columns != ""]
        else:
          return pd.DataFrame(
              columns=[
                  "Actividad",
                  "Inicio",
                  "Fin",
                  "AllDay",
                  "Privado",
                  "Estado",
              ]
          )
      except gspread.exceptions.APIError:
        time.sleep(1)
    return pd.DataFrame(
        columns=["Actividad", "Inicio", "Fin", "AllDay", "Privado", "Estado"]
    )

  df_actividades = obtener_datos_actualizados()

  # CALLBACK DIRECTO PARA ACTUALIZACIÓN INSTANTÁNEA
  def completar_tarea_callback(fila_index, nuevo_estado=True):
    try:
      num_fila_sheets = int(fila_index) + 2
      valor_escribir = "Completada" if nuevo_estado else "Pendiente"

      # Escribir en Columna 6 (F: Estado / Finalizada)
      sheet.update_cell(num_fila_sheets, 6, valor_escribir)

      # Invalida caché para refrescar
      st.cache_data.clear()
    except Exception as err:
      st.error(f"Error al escribir en Google Sheets: {err}")

  # BARRA LATERAL: AGREGAR ACTIVIDADES
  st.sidebar.header("➕ Agregar nueva actividad")

  actividad = st.sidebar.text_input("Descripción de la Actividad")

  es_all_day = st.sidebar.checkbox(
      "📅 ¿Es actividad de todo el día? 📅", value=False
  )

  if es_all_day:
    col_f1, col_f2 = st.sidebar.columns(2)
    with col_f1:
      fecha_inicio = col_f1.date_input(
          "Fecha Inicio", value=datetime.date.today(), format="DD/MM/YYYY"
      )
    with col_f2:
      fecha_fin = col_f2.date_input(
          "Fecha Final", value=datetime.date.today(), format="DD/MM/YYYY"
      )

    start_str = fecha_inicio.strftime("%Y-%m-%d")
    end_str = (fecha_fin + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

  else:
    fecha_act = st.sidebar.date_input(
        "Fecha de la Actividad", value=datetime.date.today(), format="DD/MM/YYYY"
    )
    hora_act = st.sidebar.time_input("Hora Inicio", value=datetime.time(9, 0))
    duracion_horas = st.sidebar.number_input(
        "Duración (Horas)", min_value=1, max_value=24, value=1
    )

    dt_start = datetime.datetime.combine(fecha_act, hora_act)
    dt_end = dt_start + datetime.timedelta(hours=int(duracion_horas))

    start_str = dt_start.isoformat()
    end_str = dt_end.isoformat()

  es_privado = st.sidebar.toggle(
      "🔒 Actividad privada (Solo Admin)", value=False
  )

  PALETA_COLORES = {
      "🔵 Azul (Predeterminado)": "#3788d8",
      "🔴 Rojo (Urgente)": "#dc3545",
      "🟡 Amarillo (En proceso)": "#ffc107",
      "🟣 Morado (Reunión)": "#6f42c1",
      "🟠 Naranja (Pendiente)": "#fd7e14",
      "⚫ Gris (Extra)": "#6c757d",
  }
  opcion_color = st.sidebar.selectbox(
      "Color de la actividad en Calendario", options=list(PALETA_COLORES.keys())
  )
  color_seleccionado = PALETA_COLORES[opcion_color]

  if st.sidebar.button("💾 Guardar Actividad 💾"):
    if not actividad:
      st.sidebar.warning("Por favor ingresa un título para la actividad")
    else:
      nueva_fila = [
          actividad,
          start_str,
          end_str,
          "TRUE" if es_all_day else "FALSE",
          "TRUE" if es_privado else "FALSE",
          "Pendiente",
      ]

      sheet.append_row(nueva_fila)
      st.cache_data.clear()
      st.sidebar.success("✅ Actividad guardada con éxito")
      st.rerun()

  # SECCIÓN PENDIENTES HOY
  st.subheader("📌 Pendientes de Hoy")

  hoy_iso = datetime.date.today().strftime("%Y-%m-%d")

  actividades_hoy = []
  if not df_actividades.empty:
    for idx, row in df_actividades.iterrows():
      inicio_val = str(row.get("Inicio", ""))
      if inicio_val.startswith(hoy_iso):
        actividades_hoy.append((idx, row))

  if actividades_hoy:
    for idx, row in actividades_hoy:
      val_est = (
          str(row.get("Estado", row.get("Finalizada", ""))).strip().upper()
      )
      is_finalizada = val_est in ["COMPLETADA", "TRUE"]
      es_priv = str(row.get("Privado", "false")).upper() == "TRUE"
      titulo = str(row.get("Actividad", "Sin nombre"))

      col_check, col_info = st.columns([0.08, 0.92])

      with col_check:
        st.checkbox(
            "",
            value=is_finalizada,
            key=f"check_hoy_{idx}_{titulo}",
            on_change=completar_tarea_callback,
            args=(idx, not is_finalizada),
        )

      with col_info:
        candado = "🔒 " if es_priv else ""
        if is_finalizada:
          st.markdown(f"~~{candado}**{titulo}**~~ (🟢 *Completada*)")
        else:
          st.markdown(f"🟡 **{candado}{titulo}** *(Pendiente)*")
  else:
    st.info("🎉 ¡No hay actividades pendientes para hoy!")

  st.markdown("---")

  # SECCIÓN CALENDARIO SIEMPRE VISIBLE
  st.subheader("📅 Vista Calendario")

  eventos_calendario = []
  if not df_actividades.empty:
    for idx, row in df_actividades.iterrows():
      is_all_day = str(row.get("AllDay", "false")).upper() == "TRUE"
      is_private = str(row.get("Privado", "false")).upper() == "TRUE"
      val_est = (
          str(row.get("Estado", row.get("Finalizada", ""))).strip().upper()
      )
      is_finalizada = val_est in ["COMPLETADA", "TRUE"]

      titulo_display = str(row.get("Actividad", "Sin Nombre"))
      if is_private:
        titulo_display = f"🔒 {titulo_display}"
      if is_finalizada:
        titulo_display = f"✅ {titulo_display}"

      color_evento = "#28a745" if is_finalizada else color_seleccionado

      evento = {
          "title": titulo_display,
          "start": str(row.get("Inicio", "")),
          "end": str(row.get("Fin", "")),
          "allDay": is_all_day,
          "backgroundColor": color_evento,
          "borderColor": color_evento,
          "textColor": "#FFFFFF",
          "display": "block",
      }
      eventos_calendario.append(evento)

  calendar_options = {
      "headerToolbar": {
          "left": "today prev,next",
          "center": "title",
          "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek",
      },
      "initialView": "dayGridMonth",
      "displayEventTime": False,
      "eventDisplay": "block",
      "selectable": True,
      "editable": False,
  }

  # Se asigna una key dinámica fija para evitar que se desmonte al navegar
  calendar(
      events=eventos_calendario,
      options=calendar_options,
      key="calendario_principal_fijo",
  )

  st.markdown("---")

  # SECCIÓN PESTAÑA LISTA DE TAREAS Y GESTIÓN
  st.subheader("📋 Lista de Tareas y Gestión")

  if not df_actividades.empty:
    for idx, row in df_actividades.iterrows():
      val_est = (
          str(row.get("Estado", row.get("Finalizada", ""))).strip().upper()
      )
      is_finalizada = val_est in ["COMPLETADA", "TRUE"]
      inicio_raw = str(row.get("Inicio", ""))
      titulo_act = str(row.get("Actividad", ""))

      if "T" in inicio_raw:
        partes = inicio_raw.split("T")
        try:
          fecha_fmt = datetime.datetime.strptime(partes[0], "%Y-%m-%d").strftime(
              "%d-%m-%Y"
          )
        except:
          fecha_fmt = partes[0]
        hora_fmt = partes[1][:5]
      elif " " in inicio_raw:
        partes = inicio_raw.split(" ")
        try:
          fecha_fmt = datetime.datetime.strptime(partes[0], "%Y-%m-%d").strftime(
              "%d-%m-%Y"
          )
        except:
          fecha_fmt = partes[0]
        hora_fmt = partes[1][:5]
      else:
        try:
          fecha_fmt = datetime.datetime.strptime(
              inicio_raw, "%Y-%m-%d"
          ).strftime("%d-%m-%Y")
        except:
          fecha_fmt = inicio_raw
        hora_fmt = ""

      c1, c2, c3, c4, c5 = st.columns([0.2, 0.15, 0.35, 0.15, 0.15])

      with c1:
        st.write(f"**{fecha_fmt}**")
      with c2:
        st.write(hora_fmt if hora_fmt else "--:--")
      with c3:
        st.write(titulo_act)
      with c4:
        if is_finalizada:
          st.markdown("🟢 **Completada**")
        else:
          st.markdown("🟡 **Pendiente**")
      with c5:
        if is_finalizada:
          st.markdown("🟣 **Finalizada**")
        else:
          st.button(
              "☑️ Marcar Lista",
              key=f"btn_tab_gestion_{idx}",
              on_click=completar_tarea_callback,
              args=(idx, True),
          )
      st.divider()
  else:
    st.info("No hay tareas registradas")
