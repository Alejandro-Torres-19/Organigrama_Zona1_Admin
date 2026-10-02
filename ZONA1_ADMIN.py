# IMPORTAR DEPENDENCIAS NECESARIAS
import datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
from streamlit_calendar import calendar
import streamlit.components.v1 as components

# CONFIGURACIÓN INICIAL PÁGINA
st.set_page_config(
    page_title="CRONOGRAMA Zona 1 (Admin)", page_icon="🔒", layout="wide"
)

# SCRIPT DE JAVASCRIPT / CSS PARA FORZAR EL SALTO DE LÍNEA EN EL CALENDARIO INTERNO
st.markdown(
    """
    <style>
    .fc-event-title {
        white-space: normal !important;
        overflow: visible !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
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
  client = gspread.service_account_from_dict(creds_dict)
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

  # SELECCIÓN DE PESTAÑAS EN LA BARRA LATERAL
  st.sidebar.markdown("---")
  menu_opcion = st.sidebar.radio(
      "📌 Navegación", ["📅 Cronograma y Gestión", "✅ Tareas Completadas"]
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


  # OBTENER DATOS DE TAREAS COMPLETADAS DESDE GOOGLE SHEETS
  @st.cache_data(ttl=2)
  def obtener_tareas_completadas():
    try:
      spreadsheet = sheet.spreadsheet
      sheet_completadas = spreadsheet.worksheet("Completadas")
      rows = sheet_completadas.get_all_values()
      if len(rows) > 1:
        headers = [str(h).strip() for h in rows[0]]
        data_rows = rows[1:]
        return pd.DataFrame(data_rows, columns=headers)
      elif len(rows) == 1 and rows[0]:
        # Si solo existen encabezados guardados
        headers = [str(h).strip() for h in rows[0]]
        return pd.DataFrame(columns=headers)
    except Exception:
      pass
    return pd.DataFrame(
        columns=["Actividad", "Inicio", "Fin", "AllDay", "Privado", "Estado"]
    )


  # CALLBACK: MUEVE LA TAREA A LA PESTAÑA "Completadas" Y LA BORRA DE LA PRINCIPAL
  def completar_tarea_callback(fila_index):
    try:
      num_fila_sheets = int(fila_index) + 2
      row_data = sheet.row_values(num_fila_sheets)

      spreadsheet = sheet.spreadsheet

      try:
        sheet_completadas = spreadsheet.worksheet("Completadas")
      except:
        sheet_completadas = spreadsheet.add_worksheet(
            title="Completadas", rows=100, cols=10
        )
        # Asegurar encabezados si se crea de cero
        if len(sheet.get_all_values()) > 0:
          sheet_completadas.append_row(sheet.row_values(1))

      sheet_completadas.append_row(row_data)
      sheet.delete_rows(num_fila_sheets)
      st.cache_data.clear()
    except Exception as err:
      st.error(f"Error al procesar la tarea completada: {err}")


  # ==========================================
  # VISTA 1: CRONOGRAMA Y GESTIÓN PRINCIPAL
  # ==========================================
  if menu_opcion == "📅 Cronograma y Gestión":

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
          "Fecha de la Actividad",
          value=datetime.date.today(),
          format="DD/MM/YYYY",
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
        es_priv = str(row.get("Privado", "false")).upper() == "TRUE"
        titulo = str(row.get("Actividad", "Sin nombre"))
        candado = "🔒 " if es_priv else ""
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

        titulo_display = str(row.get("Actividad", "Sin Nombre"))
        if is_private:
          titulo_display = f"🔒 {titulo_display}"

        evento = {
            "title": titulo_display,
            "start": str(row.get("Inicio", "")),
            "end": str(row.get("Fin", "")),
            "allDay": is_all_day,
            "backgroundColor": color_seleccionado,
            "borderColor": color_seleccionado,
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
        "dayMaxEvents": False,
        "selectable": True,
        "editable": False,
        "locale": "es",
        "buttonText": {
            "today": "Hoy",
            "month": "Mes",
            "week": "Semana",
            "day": "Día",
            "list": "Agenda",
        },
    }

    calendar(
        events=eventos_calendario,
        options=calendar_options,
        key="calendario_principal_fijo",
    )

    # INYECCIÓN DE JS PARA FORZAR EL ESTILO MULTILÍNEA
    components.html(
        """
      <script>
      const observer = new MutationObserver(() => {
          const doc = window.parent.document;
          const events = doc.querySelectorAll('.fc-event, .fc-event-main, .fc-event-title, .fc-daygrid-event');
          events.forEach(el => {
              el.style.whiteSpace = 'normal';
              el.style.overflow = 'visible';
              el.style.textOverflow = 'initial';
              el.style.height = 'auto';
          });
          const frames = doc.querySelectorAll('.fc-daygrid-day-frame');
          frames.forEach(f => {
              f.style.minHeight = '130px';
          });
      });
      observer.observe(window.parent.document.body, { childList: true, subtree: true });
      </script>
      """,
        height=0,
    )

    st.markdown("---")

    # SECCIÓN PESTAÑA LISTA DE TAREAS Y GESTIÓN
    st.subheader("📋 Lista de Tareas y Gestión")

    if not df_actividades.empty:
      for idx, row in df_actividades.iterrows():
        inicio_raw = str(row.get("Inicio", ""))
        titulo_act = str(row.get("Actividad", ""))

        fecha_fmt = inicio_raw
        hora_fmt = ""

        try:
          if "T" in inicio_raw:
            partes = inicio_raw.split("T")
            fecha_fmt = pd.to_datetime(partes[0]).strftime("%d-%m-%Y")
            if len(partes) > 1 and len(partes[1]) >= 5:
              hora_fmt = partes[1][:5]
          elif " " in inicio_raw:
            partes = inicio_raw.split(" ")
            fecha_fmt = pd.to_datetime(partes[0]).strftime("%d-%m-%Y")
            if len(partes) > 1 and len(partes[1]) >= 5:
              hora_fmt = partes[1][:5]
          else:
            fecha_fmt = pd.to_datetime(inicio_raw).strftime("%d-%m-%Y")
        except Exception:
          pass

        c1, c2, c3, c4, c5 = st.columns([0.2, 0.15, 0.35, 0.15, 0.15])

        with c1:
          st.write(f"**{fecha_fmt}**")
        with c2:
          st.write(hora_fmt if hora_fmt else "--:--")
        with c3:
          st.write(titulo_act)
        with c4:
          st.markdown("🟡 **Pendiente**")
        with c5:
          st.button(
              "☑️ Marcar Lista",
              key=f"btn_tab_gestion_{idx}",
              on_click=completar_tarea_callback,
              args=(idx,),
          )
        st.divider()
    else:
      st.info("No hay tareas registradas")


  # ==========================================
  # VISTA 2: TAREAS COMPLETADAS
  # ==========================================
  elif menu_opcion == "✅ Tareas Completadas":
    st.subheader("✅ Historial de Actividades Completadas")
    st.markdown(
        "Aquí se muestran todas las tareas que han sido marcadas como listas"
        " y guardadas en la hoja de datos."
    )

    df_completadas = obtener_tareas_completadas()

    if not df_completadas.empty and "Actividad" in df_completadas.columns:
      # Filtrar filas que tengan contenido real en la columna Actividad
      df_completadas = df_completadas[df_completadas["Actividad"].str.strip() != ""]

      if not df_completadas.empty:
        for idx, row in df_completadas.iterrows():
          inicio_raw = str(row.get("Inicio", ""))
          titulo_act = str(row.get("Actividad", ""))

          fecha_fmt = inicio_raw
          hora_fmt = ""

          try:
            if "T" in inicio_raw:
              partes = inicio_raw.split("T")
              fecha_fmt = pd.to_datetime(partes[0]).strftime("%d-%m-%Y")
              if len(partes) > 1 and len(partes[1]) >= 5:
                hora_fmt = partes[1][:5]
            elif " " in inicio_raw:
              partes = inicio_raw.split(" ")
              fecha_fmt = pd.to_datetime(partes[0]).strftime("%d-%m-%Y")
              if len(partes) > 1 and len(partes[1]) >= 5:
                hora_fmt = partes[1][:5]
            else:
              fecha_fmt = pd.to_datetime(inicio_raw).strftime("%d-%m-%Y")
          except Exception:
            pass

          c1, c2, c3, c4 = st.columns([0.25, 0.2, 0.4, 0.15])
          with c1:
            st.write(f"**{fecha_fmt}**")
          with c2:
            st.write(hora_fmt if hora_fmt else "--:--")
          with c3:
            st.write(f"~~{titulo_act}~~")  # Texto tachado para completadas
          with c4:
            st.markdown("🟢 **Completada**")
          st.divider()
      else:
        st.info(
            "Aún no hay tareas marcadas como completadas en la hoja de datos."
        )
    else:
      st.info("Aún no hay tareas marcadas como completadas en la hoja de datos.")
