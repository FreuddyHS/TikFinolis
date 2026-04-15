#!/usr/bin/env python3
"""
Script para compilar TikTok TTS Bot a .exe portable
Requisitos: pip install pyinstaller
"""

import PyInstaller.__main__
import os
import sys

def check_ffmpeg():
    """Verifica que FFmpeg esté presente"""
    if not os.path.exists("ffmpeg.exe"):
        print("❌ ERROR: No se encuentra ffmpeg.exe")
        print("Descarga desde: https://www.gyan.dev/ffmpeg/builds/")
        print("Copia ffmpeg.exe y ffprobe.exe en esta carpeta")
        return False
    
    if not os.path.exists("ffprobe.exe"):
        print("❌ ERROR: No se encuentra ffprobe.exe")
        return False
    
    print("✓ FFmpeg encontrado")
    return True

def build():
    """Compila el ejecutable"""
    print("🚀 Iniciando compilación de TikTok TTS Bot...")
    
    if not check_ffmpeg():
        sys.exit(1)
    
    # Argumentos para PyInstaller
    args = [
        'bot.py',                              # Script principal
        '--onefile',                           # Un solo archivo .exe
        '--windowed',                          # Sin consola (solo GUI)
        '--name', 'TikTokTTSBot',              # Nombre del exe
        '--add-binary', 'ffmpeg.exe;.',        # Incluir FFmpeg
        '--add-binary', 'ffprobe.exe;.',       # Incluir FFprobe
        '--hidden-import', 'edge_tts',         # Dependencias ocultas
        '--hidden-import', 'TikTokLive',
        '--hidden-import', 'TikTokLive.events',
        '--hidden-import', 'pydub',
        '--hidden-import', 'asyncio',
        '--collect-all', 'edge_tts',           # Asegurar que se incluya todo edge_tts
        '--clean',                             # Limpiar caché
        '--noconfirm',                         # Sobrescibir sin preguntar
    ]
    
    print("⚙️  Compilando... (esto puede tardar 2-5 minutos)")
    
    try:
        PyInstaller.__main__.run(args)
        print("\n" + "="*50)
        print("✅ COMPILACIÓN EXITOSA")
        print("="*50)
        print(f"📦 Ejecutable creado en: dist/TikTokTTSBot.exe")
        print(f"📁 Tamaño aproximado: 80-150 MB")
        print("\nInstrucciones de uso:")
        print("1. Copia dist/TikTokTTSBot.exe a cualquier PC")
        print("2. Al ejecutar, creará automáticamente la carpeta 'audios/'")
        print("3. No necesita instalar nada adicional")
        print("="*50)
    except Exception as e:
        print(f"\n❌ Error durante compilación: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build()