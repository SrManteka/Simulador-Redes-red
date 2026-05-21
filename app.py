import streamlit as st
import simpy
import random
import numpy as np
import plotly.graph_objects as go

# ==============================================================================
# CONFIGURACIÓN DE LA PÁGINA WEB
# ==============================================================================
st.set_page_config(page_title="Simulador de Redes SED", layout="wide")

st.title("🖥️ Dashboard Interactivo: Simulación de Eventos Discretos en Redes")
st.markdown("""
Esta aplicación web simula el comportamiento de una topología multi-router bajo el modelo de colas M/M/1. 
Modifica los parámetros en la barra lateral para observar la congestión y pérdidas en tiempo real.
""")

# ==============================================================================
# BARRAS LATERALES DE CONTROL (INPUTS INTERACTIVOS)
# ==============================================================================
st.sidebar.header("⚙️ Configuración de la Red")

# Controles deslizantes (Sliders)
capacidad_canal = st.sidebar.slider("Capacidad del Canal por Router (Bytes/s)", 10000, 150000, 30000, step=5000)
capacidad_buffer = st.sidebar.slider("Capacidad máxima del Buffer (Paquetes)", 10, 100, 30)
prob_fallo = st.sidebar.slider("Probabilidad de Fallo en Enlace Física (%)", 0.0, 10.0, 1.5, step=0.5) / 100

st.sidebar.subheader("🔀 Simulación de Tráfico")
tasa_normal = st.sidebar.slider("Tasa de Tráfico Normal (pqts/s)", 5, 50, 20)

# Switch interactivo para activar el ciberataque
ataque_activo = st.sidebar.toggle("💥 Activar Ciberataque DoS masivo", value=False)
tasa_dos = st.sidebar.slider("Tasa de Tráfico DoS (pqts/s)", 60, 200, 130) if ataque_activo else tasa_normal

# ==============================================================================
# MOTOR DE SIMULACIÓN DE EVENTOS DISCRETOS (SIMPY)
# ==============================================================================
class Router:
    def __init__(self, env, id_router, cap_buffer, cap_canal):
        self.env = env
        self.id_router = id_router
        self.capacidad_buffer = cap_buffer
        self.capacidad_canal = cap_canal
        self.servidor = simpy.Resource(env, capacity=1)
        self.cola_actual = 0

    def recibir_paquete(self, tamano_bytes):
        global log_perdidos_buffer, log_perdidos_fallo, log_exitosos
        
        if self.cola_actual >= self.capacidad_buffer:
            log_perdidos_buffer += 1
            return
        if random.random() < prob_fallo:
            log_perdidos_fallo += 1
            return

        self.cola_actual += 1
        
        # Registrar datos para graficar
        timestamps.append(self.env.now)
        if self.id_router == 1:
            ocupacion_r1.append(self.cola_actual)
            ocupacion_r2.append(ocupacion_r2[-1] if len(ocupacion_r2) > 0 else 0)
        else:
            ocupacion_r2.append(self.cola_actual)
            ocupacion_r1.append(ocupacion_r1[-1] if len(ocupacion_r1) > 0 else 0)

        with self.servidor.request() as peticion:
            yield peticion
            tiempo_tx = tamano_bytes / self.capacidad_canal
            yield self.env.timeout(tiempo_tx)
            
            self.cola_actual -= 1
            log_exitosos += 1
            
            timestamps.append(self.env.now)
            ocupacion_r1.append(ocupacion_r1[-1] if len(ocupacion_r1) > 0 else 0)
            ocupacion_r2.append(ocupacion_r2[-1] if len(ocupacion_r2) > 0 else 0)

def generador_trafico(env, routers):
    id_paquete = 0
    while True:
        # Si el switch de ataque está activo, usamos la tasa DoS permanentemente para fines interactivos
        tasa_actual = tasa_dos if ataque_activo else tasa_normal
        yield env.timeout(random.expovariate(tasa_actual))
        
        id_paquete += 1
        tamano = max(64, min(1500, int(random.normalvariate(800, 300))))
        
        # Balanceador de carga
        router_seleccionado = min(routers, key=lambda r: r.cola_actual)
        env.process(router_seleccionado.recibir_paquete(tamano))

# Botón para iniciar los cálculos
if st.sidebar.button("▶️ Correr Simulación"):
    # Inicializar vectores de datos globales
    global timestamps, ocupacion_r1, ocupacion_r2, log_perdidos_buffer, log_perdidos_fallo, log_exitosos
    timestamps, ocupacion_r1, ocupacion_r2 = [], [], []
    log_perdidos_buffer, log_perdidos_fallo, log_exitosos = 0, 0, 0

    # Ejecutar Simpy
    random.seed(2026)
    env = simpy.Environment()
    lista_routers = [
        Router(env, 1, capacidad_buffer, capacidad_canal),
        Router(env, 2, capacidad_buffer, capacidad_canal)
    ]
    env.process(generador_trafico(env, lista_routers))
    env.run(until=800) # Tiempo fijo de evaluación interactiva

    # ==============================================================================
    # PROCESAMIENTO DE KPIs (TARJETAS MÉTRICAS)
    # ==============================================================================
    total = log_exitosos + log_perdidos_buffer + log_perdidos_fallo
    p_buffer = (log_perdidos_buffer / total) * 100 if total > 0 else 0
    p_fallo = (log_perdidos_fallo / total) * 100 if total > 0 else 0
    throughput = log_exitosos / 800

    # Determinar estado de salud de la red
    if ataque_activo:
        status_texto = "🔴 RED BAJO ATAQUE DOS"
        status_color = "error"
    elif p_buffer > 5:
        status_texto = "🟡 CONGESTIÓN DETECTADA"
        status_color = "warning"
    else:
        status_texto = "🟢 ESTADO ÓPTIMO"
        status_color = "success"

    # Mostrar alertas de estado
    if status_color == "success": st.success(status_texto)
    elif status_color == "warning": st.warning(status_texto)
    else: st.error(status_texto)

    # Crear columnas visuales para las tarjetas de datos
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Paquetes Exitosos", f"{log_exitosos} ({log_exitosos/total*100:.1f}%)" if total > 0 else "0")
    col2.metric("Pérdidas por Buffer (Congestión)", f"{p_buffer:.2f}%")
    col3.metric("Pérdidas por Enlace (Ruido)", f"{p_fallo:.2f}%")
    col4.metric("Throughput Real", f"{throughput:.2f} pqts/s")

    # ==============================================================================
    # GENERACIÓN DE GRÁFICA INTERACTIVA (PLOTLY)
    # ==============================================================================
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=timestamps, y=ocupacion_r1, name="Router 1 (Cola)", line=dict(color='royalblue', width=1.5)))
    fig.add_trace(go.Scatter(x=timestamps, y=ocupacion_r2, name="Router 2 (Cola)", line=dict(color='orange', width=1.5)))
    
    # Línea límite del buffer
    fig.add_hline(y=capacidad_buffer, line_dash="dash", line_color="red", annotation_text="Límite del Buffer (Saturación)")

    fig.update_layout(
        title="Ocupación de los Buffers en Tiempo Real (Eventos Discretos)",
        xaxis_title="Tiempo de Simulación (Segundos)",
        yaxis_title="Cantidad de Paquetes en Cola",
        hovermode="x unified",
        template="plotly_white"
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("💡 Modifica los parámetros a la izquierda y presiona el botón 'Correr Simulación' para ver los resultados dinámicos.")
