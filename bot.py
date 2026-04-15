/home/atajashe/TikVoice/botvoice1.py/home/atajashe/TikVoice/botvoice1.pyimport tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading as Thread
import queue
import time
import os
import platform
from datetime import datetime
import glob
import subprocess
import tempfile
import shutil
import sys

# ========================
# CONFIGURACIÓN PORTABLE (PyInstaller compatible)
# ========================

def resource_path(relative_path):
    """Obtiene ruta absoluta compatible con PyInstaller"""
    try:
        # PyInstaller crea carpeta temporal en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Variables globales para verificar disponibilidad
PYDUB_OK = False
EDGE_TTS_OK = False
TIKTOK_OK = False

try:
    from pydub import AudioSegment
    from pydub.playback import play
    PYDUB_OK = True
    print("✓ pydub instalado correctamente")
    
    # Configurar FFmpeg portable para Windows
    if platform.system() == "Windows":
        ffmpeg_exe = resource_path("ffmpeg.exe")
        ffprobe_exe = resource_path("ffprobe.exe")
        
        if os.path.exists(ffmpeg_exe):
            AudioSegment.converter = ffmpeg_exe
            AudioSegment.ffprobe = ffprobe_exe
            print(f"✓ FFmpeg portable cargado: {ffmpeg_exe}")
        else:
            print("⚠ FFmpeg no encontrado en modo portable, buscando en sistema...")
            
except Exception as e:
    PYDUB_OK = False
    print(f"✗ Error pydub: {e}")

try:
    import edge_tts
    EDGE_TTS_OK = True
    print("✓ Edge-TTS instalado correctamente")
except Exception as e:
    EDGE_TTS_OK = False
    print(f"✗ Error Edge-TTS: {e}")

try:
    from TikTokLive import TikTokLiveClient
    from TikTokLive.events import CommentEvent, GiftEvent, FollowEvent
    from TikTokLive.events import ConnectEvent, DisconnectEvent
    TIKTOK_OK = True
    print("✓ TikTokLive instalado correctamente")
except Exception as e:
    TIKTOK_OK = False
    print(f"✗ Error TikTokLive: {e}")

import asyncio

# ========================
# COLORES
# ========================
BG = '#1a1a2e'
BG2 = '#16213e'
BG3 = '#0f3460'
C1 = '#00d9ff'
C2 = '#ffd700'
C3 = '#ff69b4'
C4 = '#00ff88'
C5 = '#ff4444'
C6 = '#ffaa00'
W = '#ffffff'
G = '#888888'

CARPETA_AUDIOS = "audios"


# ========================
# CLASE PRINCIPAL
# ========================

class App:

    def __init__(self, root):
        self.root = root
        self.root.title("TikTok TTS Bot - Portable")
        self.root.geometry("1100x780")
        self.root.configure(bg=BG)

        # Estado
        self.connected = False
        self.tts_on = True
        self.client = None
        self.reproduciendo = False

        # Colas
        self.q_comm = queue.Queue()
        self.q_gift = queue.Queue()
        self.q_follow = queue.Queue()
        self.q_audio = queue.Queue()

        # Estadísticas
        self.stats = {'c': 0, 'g': 0, 'f': 0, 'a': 0, 't': None}

        # Controles
        self.user = tk.StringVar(value="@tu_usuario")
        self.voice = tk.StringVar(value="mexicana_femenina")
        self.vol = tk.IntVar(value=80)

        # Alertas específicas para Regalos y Seguidores
        self.alerta_regalo = tk.StringVar(value="")
        self.alerta_seguidor = tk.StringVar(value="")

        # Fallback si no hay alerta asignada
        self.usar_tts_fallback = tk.BooleanVar(value=True)

        # Carpeta de audios (en la misma carpeta del exe)
        if getattr(sys, 'frozen', False):
            # Si es el exe compilado, usar carpeta donde está el exe
            self.carpeta_base = os.path.dirname(sys.executable)
        else:
            # Si es script Python normal
            self.carpeta_base = os.path.dirname(os.path.abspath(__file__))
            
        self.carpeta_audios = os.path.join(self.carpeta_base, CARPETA_AUDIOS)
        if not os.path.exists(self.carpeta_audios):
            os.makedirs(self.carpeta_audios)

        # Iniciar hilos
        self.hilo_audio = Thread.Thread(target=self.procesar_cola_audio, daemon=True)
        self.hilo_audio.start()

        # Construir UI
        self.build_ui()

        # Actualizar UI
        self.tick()

        # Log inicial
        self.log_add("Sistema", "Bot iniciado correctamente", "ok")
        self.log_add("Sistema", f"Carpeta audios: {self.carpeta_audios}", "info")
        
        if PYDUB_OK:
            self.log_add("Audio", "Reproductor listo", "ok")
        else:
            self.log_add("Audio", "Error: No se pudo cargar pydub", "err")

    def procesar_cola_audio(self):
        """Hilo dedicado para procesar la cola de audio"""
        while True:
            try:
                ruta = self.q_audio.get()
                if ruta and os.path.exists(ruta):
                    self.reproducir_audio_pydub(ruta)
                    # BORRAR INMEDIATAMENTE DESPUÉS DE REPRODUCIR
                    try:
                        os.remove(ruta)
                        self.log_add("Limpieza", f"🗑️ Borrado: {os.path.basename(ruta)}", "ok")
                    except Exception as e:
                        self.log_add("Limpieza", f"Error borrando: {e}", "err")
                self.q_audio.task_done()
            except Exception as e:
                self.log_add("Audio Error", f"Error en cola: {e}", "err")
                self.reproduciendo = False
            time.sleep(0.1)

    def reproducir_audio_pydub(self, ruta):
        """Reproduce audio usando pydub"""
        self.reproduciendo = True
        
        try:
            self.log_add("Audio", f"Reproduciendo: {os.path.basename(ruta)}", "info")
            
            if not os.path.exists(ruta):
                self.log_add("Audio", "Archivo no existe", "err")
                self.reproduciendo = False
                return
            
            tam = os.path.getsize(ruta)
            self.log_add("Audio", f"Tamaño: {tam/1024:.1f} KB", "info")
            
            if not PYDUB_OK:
                self.log_add("Audio", "pydub no disponible", "err")
                self.reproduciendo = False
                return
            
            # Cargar y reproducir con pydub
            audio = AudioSegment.from_file(ruta)
            
            # Aplicar volumen
            volumen_db = (self.vol.get() - 100) / 2
            audio = audio + volumen_db
            
            # Exportar a WAV temporal para reproducir
            temp_wav = tempfile.mktemp(suffix='.wav')
            audio.export(temp_wav, format='wav')
            
            # Reproducir
            play(AudioSegment.from_wav(temp_wav))
            
            # Limpiar temporal
            try:
                os.remove(temp_wav)
            except:
                pass
            
            self.log_add("Audio", "✅ Reproducción completada", "ok")
            self.reproduciendo = False
            
        except Exception as e:
            self.log_add("Audio Error", f"Error: {str(e)[:50]}", "err")
            self.reproduciendo = False

    def encolar_audio(self, ruta):
        """Agrega un audio a la cola de reproducción"""
        if os.path.exists(ruta):
            self.q_audio.put(ruta)
            self.log_add("Audio", f"🎵 Encolado: {os.path.basename(ruta)}", "info")
        else:
            self.log_add("Audio", "❌ Archivo no encontrado", "err")

    def log_add(self, modulo, mensaje, tipo="info"):
        """Agrega un mensaje al área de logs"""
        try:
            colores = {
                "ok": C4,
                "err": C5,
                "warn": C6,
                "info": C1
            }
            color = colores.get(tipo, W)
            timestamp = datetime.now().strftime("%H:%M:%S")
            linea = f"[{timestamp}] [{modulo}] {mensaje}\n"
            
            self.txt_log.config(state=tk.NORMAL)
            self.txt_log.insert(tk.END, linea)
            end_idx = self.txt_log.index("end-1c")
            start_idx = self.txt_log.index("end-2l linestart")
            self.txt_log.tag_add(tipo, start_idx, end_idx)
            self.txt_log.tag_config(tipo, foreground=color)
            self.txt_log.see(tk.END)
            self.txt_log.config(state=tk.DISABLED)
        except:
            pass

# ========================
# INTERFAZ GRÁFICA
# ========================

    def build_ui(self):
        # TOP BAR
        top = tk.Frame(self.root, bg=BG2, height=60)
        top.pack(fill=tk.X, padx=5, pady=5)
        top.pack_propagate(False)

        tk.Label(top, text="TikTok TTS Bot", font=('Arial', 16, 'bold'),
                 bg=BG2, fg=C1).pack(side=tk.LEFT, padx=15)

        f = tk.Frame(top, bg=BG2)
        f.pack(side=tk.LEFT, padx=10)
        tk.Label(f, text="Usuario:", bg=BG2, fg=W).pack(side=tk.LEFT)
        tk.Entry(f, textvariable=self.user, width=14, font=('Arial', 10),
                 bg=BG3, fg=W, insertbackground=W, relief=tk.FLAT).pack(side=tk.LEFT, padx=5)

        self.btn_connect = tk.Button(f, text="CONECTAR", command=self.do_connect,
                                       font=('Arial', 10, 'bold'), bg=C4, fg='white',
                                       relief=tk.FLAT, width=10)
        self.btn_connect.pack(side=tk.LEFT, padx=5)

        self.btn_tts = tk.Button(f, text="TTS ON", command=self.toggle_tts,
                                  font=('Arial', 10, 'bold'), bg=C1, fg='white',
                                  relief=tk.FLAT, width=8)
        self.btn_tts.pack(side=tk.LEFT, padx=3)

        self.lbl_status = tk.Label(top, text="DESCONECTADO", font=('Arial', 10, 'bold'),
                                   bg=BG2, fg=G)
        self.lbl_status.pack(side=tk.RIGHT, padx=15)

        # BODY
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=5)

        # LEFT - Comentarios
        left = tk.Frame(body, bg=BG2)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))

        hdr_c = tk.Frame(left, bg=BG3, height=35)
        hdr_c.pack(fill=tk.X)
        hdr_c.pack_propagate(False)
        tk.Label(hdr_c, text=" COMENTARIOS EN VIVO", font=('Arial', 11, 'bold'),
                 bg=BG3, fg=C1).pack(side=tk.LEFT, padx=10)
        self.lbl_comm_count = tk.Label(hdr_c, text="(0)", font=('Arial', 9), bg=BG3, fg=G)
        self.lbl_comm_count.pack(side=tk.RIGHT, padx=10)

        self.list_comments = tk.Listbox(left, font=('Consolas', 9), bg=BG, fg=W,
                                         selectbackground=BG3, relief=tk.FLAT, bd=0)
        self.list_comments.pack(fill=tk.BOTH, expand=True, pady=3, padx=3)
        sc_c = tk.Scrollbar(self.list_comments, command=self.list_comments.yview)
        sc_c.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_comments.config(yscrollcommand=sc_c.set)

        # RIGHT - Panel de configuración
        right = tk.Frame(body, bg=BG2, width=380)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(3, 0))
        right.pack_propagate(False)

        # SECCIÓN: CONFIGURACIÓN TTS
        hdr_tts = tk.Frame(right, bg=BG3, height=35)
        hdr_tts.pack(fill=tk.X)
        hdr_tts.pack_propagate(False)
        tk.Label(hdr_tts, text=" CONFIGURACIÓN TTS", font=('Arial', 11, 'bold'),
                 bg=BG3, fg=C1).pack(side=tk.LEFT, padx=10)

        tts_frm = tk.Frame(right, bg=BG)
        tts_frm.pack(fill=tk.X, pady=5, padx=5)

        tk.Label(tts_frm, text="Voz:", font=('Arial', 9), bg=BG, fg=W).pack(anchor='w', padx=5)
        
        voices_combo = ttk.Combobox(tts_frm, textvariable=self.voice, width=28, state='readonly')
        voices_combo['values'] = [
            "mexicana_femenina",
            "mexicano_masculino",
            "colombiana",
            "argentina",
            "chilena",
            "espanola_femenina",
            "espanola_masculino"
        ]
        voices_combo.pack(padx=5, pady=2)

        tk.Label(tts_frm, text=f"Volumen: {self.vol.get()}%", 
                font=('Arial', 9), bg=BG, fg=W).pack(anchor='w', padx=5, pady=(10,0))
        
        vol_scale = tk.Scale(tts_frm, from_=0, to=100, orient=tk.HORIZONTAL,
                              variable=self.vol, bg=BG, fg=W, troughcolor=BG3,
                              highlightthickness=0, length=300)
        vol_scale.pack(fill='x', padx=5)

        # --- ALERTAS PERSONALIZADAS ---
        hdr_a = tk.Frame(right, bg=BG3, height=35)
        hdr_a.pack(fill=tk.X, pady=(10, 0))
        hdr_a.pack_propagate(False)
        tk.Label(hdr_a, text=" ALERTAS PERSONALIZADAS", font=('Arial', 11, 'bold'),
                 bg=BG3, fg=C3).pack(side=tk.LEFT, padx=10)

        alertas_frm = tk.Frame(right, bg=BG)
        alertas_frm.pack(fill=tk.X, pady=5, padx=5)

        tk.Label(alertas_frm, 
                text="Asigna sonidos para Regalos y Seguidores.\nLos comentarios siempre se leerán con TTS (Usuario dijo: ...).",
                font=('Arial', 8), bg=BG, fg=G, wraplength=350, justify=tk.LEFT).pack(anchor='w', padx=5, pady=(0,10))

        # Alerta Regalo
        self.crear_campo_alerta(alertas_frm, "🎁 Regalos:", 
                               self.alerta_regalo, 'regalo', C2)

        # Alerta Seguidor
        self.crear_campo_alerta(alertas_frm, "❤️ Seguidores:", 
                               self.alerta_seguidor, 'seguidor', C3)

        # Checkbox fallback
        tk.Checkbutton(alertas_frm, text="Si no hay alerta, usar TTS para Regalos/Seguidores",
                      variable=self.usar_tts_fallback, bg=BG, fg=W, 
                      selectcolor=BG3, activebackground=BG, activeforeground=W).pack(anchor='w', padx=5, pady=10)

        # Botón probar
        tk.Button(alertas_frm, text="🎵 Probar sonidos",
                 command=self.probar_alertas,
                 font=('Arial', 9), bg=C6, fg='white', relief=tk.FLAT).pack(fill=tk.X, padx=5, pady=5)

        # --- ESTADÍSTICAS ---
        hdr_s = tk.Frame(right, bg=BG3, height=35)
        hdr_s.pack(fill=tk.X, pady=(10, 0))
        hdr_s.pack_propagate(False)
        tk.Label(hdr_s, text=" ESTADÍSTICAS", font=('Arial', 11, 'bold'),
                 bg=BG3, fg=C1).pack(side=tk.LEFT, padx=10)

        stats_frm = tk.Frame(right, bg=BG)
        stats_frm.pack(fill=tk.X, pady=5, padx=5)

        self.stat_labels = {}
        for lbl_text, key, color in [
            ("Comentarios:", "c", C1),
            ("Regalos:", "g", C2),
            ("Seguidores:", "f", C3),
            ("Audios TTS:", "a", C1),
            ("Tiempo activo:", "up", G),
            ("Audios guardados:", "total", C2),
        ]:
            row = tk.Frame(stats_frm, bg=BG)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=lbl_text, font=('Arial', 9), bg=BG, fg=color,
                     anchor='w', width=14).pack(side=tk.LEFT)
            val = tk.Label(row, text="0", font=('Arial', 9, 'bold'), bg=BG, fg=W, anchor='e')
            val.pack(side=tk.RIGHT)
            self.stat_labels[key] = val

        # Botón abrir carpeta
        btn_folder = tk.Button(right, text="📁 Abrir carpeta de audios",
                                 command=self.abrir_carpeta,
                                 font=('Arial', 9), bg=BG3, fg=W, relief=tk.FLAT)
        btn_folder.pack(fill=tk.X, padx=5, pady=10)

        # BOTTOM - Logs
        bottom = tk.Frame(self.root, bg=BG2, height=150)
        bottom.pack(fill=tk.X, padx=5, pady=(0, 5))
        bottom.pack_propagate(False)

        hdr_l = tk.Frame(bottom, bg=BG3, height=30)
        hdr_l.pack(fill=tk.X)
        hdr_l.pack_propagate(False)
        tk.Label(hdr_l, text=" LOGS DEL SISTEMA", font=('Arial', 10, 'bold'),
                 bg=BG3, fg=C6).pack(side=tk.LEFT, padx=10)
        
        tk.Button(hdr_l, text="Limpiar", command=self.clear_logs,
                  font=('Arial', 8), bg=BG2, fg=W, relief=tk.FLAT).pack(side=tk.RIGHT, padx=5)
        tk.Button(hdr_l, text="Guardar", command=self.save_logs,
                  font=('Arial', 8), bg=BG2, fg=W, relief=tk.FLAT).pack(side=tk.RIGHT, padx=3)

        self.txt_log = scrolledtext.ScrolledText(bottom, wrap=tk.WORD, font=('Consolas', 8),
                                                 bg=BG, fg=W, insertbackground=W,
                                                 relief=tk.FLAT, state=tk.DISABLED)
        self.txt_log.pack(fill=tk.BOTH, expand=True, pady=3)

    def crear_campo_alerta(self, parent, etiqueta, variable, tipo, color):
        """Crea un campo para seleccionar archivo de alerta"""
        frm = tk.Frame(parent, bg=BG)
        frm.pack(fill=tk.X, pady=5, padx=5)
        
        tk.Label(frm, text=etiqueta, font=('Arial', 9, 'bold'), 
                bg=BG, fg=color, width=12, anchor='w').pack(side=tk.LEFT)
        
        entry = tk.Entry(frm, textvariable=variable, width=20, 
                        font=('Arial', 9), bg=BG3, fg=W, state='readonly')
        entry.pack(side=tk.LEFT, padx=5)
        
        btn = tk.Button(frm, text="...", command=lambda: self.seleccionar_alerta(variable, tipo),
                       font=('Arial', 8), bg=BG3, fg=W, relief=tk.FLAT, width=3)
        btn.pack(side=tk.LEFT, padx=2)
        
        btn_play = tk.Button(frm, text="▶", command=lambda: self.probar_sonido(variable.get()),
                            font=('Arial', 8), bg=C4, fg='white', relief=tk.FLAT, width=2)
        btn_play.pack(side=tk.LEFT, padx=2)

    def seleccionar_alerta(self, variable, tipo):
        """Abre diálogo para seleccionar archivo de alerta"""
        archivo = filedialog.askopenfilename(
            title=f"Seleccionar sonido para {tipo}",
            filetypes=[("Audio", "*.mp3 *.wav"), ("MP3", "*.mp3"), ("WAV", "*.wav")],
            initialdir=self.carpeta_audios
        )
        if archivo:
            variable.set(archivo)
            self.log_add("Alertas", f"{tipo}: {os.path.basename(archivo)}", "ok")

    def probar_sonido(self, ruta):
        """Reproduce un sonido para probar"""
        if ruta and os.path.exists(ruta):
            temp = os.path.join(tempfile.gettempdir(), "test_sound.mp3")
            shutil.copy2(ruta, temp)
            self.encolar_audio(temp)
            self.log_add("Test", f"Probando: {os.path.basename(ruta)}", "info")
        else:
            messagebox.showwarning("Archivo no encontrado", "Selecciona un archivo primero")

    def probar_alertas(self):
        """Prueba todas las alertas configuradas"""
        if self.alerta_regalo.get():
            self.probar_sonido(self.alerta_regalo.get())
            time.sleep(0.5)
        if self.alerta_seguidor.get():
            self.probar_sonido(self.alerta_seguidor.get())

# ========================
# CONTROL DE CONEXIÓN
# ========================

    def do_connect(self):
        if not self.connected:
            self.start_connection()
        else:
            self.stop_connection()

    def start_connection(self):
        u = self.user.get().strip().replace('@', '')
        if not u or u == "tu_usuario":
            messagebox.showerror("Error", "Ingresa tu usuario\n(sin @)")
            return
        if not TIKTOK_OK:
            messagebox.showerror("Error", "Instala TikTokLive:\npip install TikTokLive")
            return
        try:
            self.btn_connect.config(text="CONECTANDO...", bg=C6)
            self.lbl_status.config(text="CONECTANDO...", fg=C6)
            self.log_add("Conexion", f"Conectando a @{u}...", "warn")

            self.client = TikTokLiveClient(unique_id=u)
            self.client.on(ConnectEvent)(self.on_conn)
            self.client.on(CommentEvent)(self.on_comment)
            self.client.on(GiftEvent)(self.on_gift)
            self.client.on(FollowEvent)(self.on_follow)
            self.client.on(DisconnectEvent)(self.on_disc)

            Thread.Thread(target=self.run_client, daemon=True).start()
            self.connected = True
            self.stats['t'] = datetime.now()
        except Exception as e:
            self.log_add("Error", str(e), "err")
            self.btn_connect.config(text="CONECTAR", bg=C4)

    def stop_connection(self):
        self.connected = False
        self.btn_connect.config(text="CONECTAR", bg=C4)
        self.lbl_status.config(text="DESCONECTADO", fg=G)
        self.log_add("Sistema", "Desconectado", "warn")

    def run_client(self):
        try:
            self.client.run()
        except Exception as e:
            self.log_add("Error", str(e), "err")

    def toggle_tts(self):
        self.tts_on = not self.tts_on
        if self.tts_on:
            self.btn_tts.config(text="TTS ON", bg=C1)
            self.log_add("Audio", "ON", "ok")
        else:
            self.btn_tts.config(text="TTS OFF", bg=C5)
            self.log_add("Audio", "OFF", "warn")

# ========================
# EVENTOS TIKTOK
# ========================

    async def on_conn(self, ev):
        self.log_add("Conexion", f"Conectado @{ev.unique_id}", "ok")
        self.root.after(0, lambda: [self.btn_connect.config(text="DESCONECTAR", bg=C5),
                                     self.lbl_status.config(text="EN VIVO", fg=C4)])

    async def on_comment(self, ev):
        """COMENTARIOS: TTS con formato 'Usuario dijo: comentario'"""
        try:
            u = ev.user.nickname
        except:
            u = "Usuario"
        
        try:
            txt = ev.comment[:200]
        except:
            txt = ""
            
        now = datetime.now().strftime("%H:%M:%S")
        self.stats['c'] += 1
        self.q_comm.put((now, u, txt))
        
        if self.tts_on and len(txt.strip()) > 0:
            texto_completo = f"{u} dijo: {txt}"
            self.generate_tts(texto_completo, u)

    async def on_gift(self, ev):
        """REGALOS: Alerta personalizada o TTS fallback"""
        try:
            u = ev.user.nickname
        except:
            u = "Usuario"
        
        try:
            g = ev.gift.name
        except:
            g = "Regalo"
        
        try:
            c = ev.repeat_count
        except:
            try:
                c = ev.repeatCount
            except:
                c = 1
        
        now = datetime.now().strftime("%H:%M:%S")
        self.stats['g'] += 1
        msgs = {"Rose": f"{u} mando rosas!", "GG": f"GG {u}!", "Coin": f"Moneditas de {u}!"}
        msg = msgs.get(g, f"Gracias {u} por {c}x {g}!")
        self.q_gift.put((now, u, g, c))
        
        if self.tts_on:
            if self.alerta_regalo.get() and os.path.exists(self.alerta_regalo.get()):
                self.encolar_audio(self.alerta_regalo.get())
                self.stats['a'] += 1
                self.log_add("Regalo", f"Alerta: {os.path.basename(self.alerta_regalo.get())}", "ok")
            elif self.usar_tts_fallback.get():
                self.generate_tts(msg, u)
            else:
                self.log_add("Regalo", "Sin alerta (silencio)", "warn")

    async def on_follow(self, ev):
        """SEGUIDORES: Alerta personalizada o TTS fallback"""
        try:
            u = ev.user.nickname
        except:
            u = "Usuario"
            
        now = datetime.now().strftime("%H:%M:%S")
        self.stats['f'] += 1
        self.q_follow.put((now, u))
        
        if self.tts_on:
            if self.alerta_seguidor.get() and os.path.exists(self.alerta_seguidor.get()):
                self.encolar_audio(self.alerta_seguidor.get())
                self.stats['a'] += 1
                self.log_add("Seguidor", f"Alerta: {os.path.basename(self.alerta_seguidor.get())}", "ok")
            elif self.usar_tts_fallback.get():
                self.generate_tts(f"Gracias por seguirme {u}!", u)
            else:
                self.log_add("Seguidor", "Sin alerta (silencio)", "warn")

    async def on_disc(self, ev):
        self.log_add("Conexion", "Desconectado", "err")
        self.connected = False
        self.root.after(0, lambda: [self.btn_connect.config(text="CONECTAR", bg=C4),
                                     self.lbl_status.config(text="DESCONECTADO", fg=G)])

# ========================
# SISTEMA TTS
# ========================

    def get_voice_id(self):
        m = {
            "mexicana_femenina": "es-MX-DaliaNeural",
            "mexicano_masculino": "es-MX-JorgeNeural",
            "colombiana": "es-CO-SalomeNeural",
            "argentina": "es-AR-ElenaNeural",
            "chilena": "es-CL-CatalinaNeural",
            "espanola_femenina": "es-ES-ElviraNeural",
            "espanola_masculino": "es-ES-AlvaroNeural"
        }
        return m.get(self.voice.get(), "es-MX-DaliaNeural")

    def generate_tts(self, texto, nombre_usuario="desconocido"):
        hilo = Thread.Thread(
            target=self._tts_worker,
            args=(texto, nombre_usuario),
            daemon=True
        )
        hilo.start()

    def _tts_worker(self, texto, nombre_usuario="desconocido"):
        try:
            self.log_add("TTS", f"Generando: {texto[:50]}...", "warn")
            
            if not EDGE_TTS_OK:
                self.log_add("TTS", "ERROR: edge-tts NO instalado", "err")
                return
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            comm = edge_tts.Communicate(texto, self.get_voice_id())
            
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre = f"{ts}_{nombre_usuario[:12]}.mp3"
            ruta = os.path.join(self.carpeta_audios, nombre)
            
            self.log_add("TTS", f"Guardando: {nombre}", "info")
            
            loop.run_until_complete(comm.save(ruta))
            loop.close()
            
            if not os.path.exists(ruta) or os.path.getsize(ruta) < 100:
                self.log_add("TTS", "ERROR: no se generó", "err")
                return
            
            tam = os.path.getsize(ruta)
            self.log_add("TTS", f"Archivo: {tam:,} bytes ({tam/1024:.1f} KB)", "ok")
            
            if tam > 500:
                self.encolar_audio(ruta)
                self.stats['a'] += 1
                self.actualizar_total()
                self.log_add("TTS", "✅ OK - Audio encolado", "ok")
            
        except Exception as e:
            self.log_add("TTS Error", str(e), "err")

    def actualizar_total(self):
        try:
            c = len(glob.glob(os.path.join(self.carpeta_audios, "*.mp3")))
            self.stat_labels['total'].config(text=str(c))
        except:
            pass

    def abrir_carpeta(self):
        try:
            if platform.system() == "Windows":
                os.startfile(self.carpeta_audios)
            else:
                subprocess.run(["xdg-open", self.carpeta_audios])
        except Exception as e:
            self.log_add("Sistema", f"No se pudo abrir carpeta: {e}", "err")

    def clear_logs(self):
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.delete(1.0, tk.END)
        self.txt_log.config(state=tk.DISABLED)
        self.log_add("Sistema", "Logs limpios", "ok")

    def save_logs(self):
        fn = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt")],
            initialfile=f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if fn:
            try:
                with open(fn, 'w', encoding='utf-8') as f:
                    f.write("=" * 60 + "\n")
                    f.write("TikTok TTS Bot - Log\n")
                    f.write(f"Fecha: {datetime.now()}\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(self.txt_log.get(1.0, tk.END))
                self.log_add("Sistema", f"Guardado en: {fn}", "ok")
            except Exception as e:
                self.log_add("Error", f"No se pudo guardar: {e}", "err")

# ========================
# ACTUALIZAR UI
# ========================

    def tick(self):
        try:
            while not self.q_comm.empty():
                it = self.q_comm.get_nowait()
                self.list_comments.insert(tk.END, f"[{it[0]}] {it[1]}: {it[2]}")
                if self.list_comments.size() > 80:
                    self.list_comments.delete(0)
                self.list_comments.see(tk.END)
                self.lbl_comm_count.config(text=f"({self.stats['c']})")

            while not self.q_gift.empty():
                it = self.q_gift.get_nowait()
                self.list_gifts.insert(tk.END, f"[{it[0]}] {it[1]} -> {it[3]}x {it[2]}")
                if self.list_gifts.size() > 30:
                    self.list_gifts.delete(0)
                self.list_gifts.see(tk.END)
                self.lbl_gift_count.config(text=f"({self.stats['g']})")

            while not self.q_follow.empty():
                it = self.q_follow.get_nowait()
                self.list_comments.insert(tk.END, f"[{it[0]} *** NUEVO SEGUIDOR: {it[1]} ***")
                self.list_comments.itemconfig(tk.END, foreground=C3)
                self.list_comments.see(tk.END)

            for k, v in [('c',str(self.stats['c'])),
                         ('g', str(self.stats['g'])),
                         ('f', str(self.stats['f'])),
                         ('a', str(self.stats['a']))]:
                self.stat_labels[k].config(text=v)

            if self.stats['t']:
                up = datetime.now() - self.stats['t']
                h, r = divmod(int(up.total_seconds()), 3600)
                m, s = divmod(r, 60)
                self.stat_labels['up'].config(text=f"{h:02d}:{m:02d}:{s:02d}")
            
            self.actualizar_total()
            
        except:
            pass
        
        self.root.after(150, self.tick)


# ========================
# PUNTO DE ENTRADA
# ========================

def main():
    root = tk.Tk()
    
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - 1100) // 2
    y = (sh - 780) // 2
    
    root.geometry(f"1100x780+{x}+{y}")
    
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
