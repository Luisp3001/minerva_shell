#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR"

echo "======================================"
echo "    Instalación rápida de Minerva"
echo "======================================"
echo ""

echo "==> 1. Compilando librerías base del Shell (Caelestia)..."
echo "    Dependencias del sistema sugeridas: cmake, make, gcc, qt6, libqalculate, pipewire, aubio, cava"
CAELESTIA_DIR="$DIR/../../shell/plugin"
if [ -d "$CAELESTIA_DIR" ]; then
    mkdir -p "$CAELESTIA_DIR/build"
    cd "$CAELESTIA_DIR/build"
    cmake ..
    make -j$(nproc)
    cd "$DIR"
    echo "    Librerías compiladas con éxito."
else
    echo "    Advertencia: No se encontró el directorio de Caelestia en $CAELESTIA_DIR"
fi

echo ""
echo "==> 2. Limpiando el entorno virtual de Python si existe..."
rm -rf .venv

echo "==> 3. Creando nuevo entorno virtual..."
python3 -m venv .venv

echo "==> 4. Activando entorno e instalando dependencias de IA..."
source .venv/bin/activate
pip install --quiet -U pip
pip install --quiet -r requirements.txt

echo ""
echo "==> 5. Verificando e instalando modelos de voz..."
mkdir -p voice
cd voice

# Modelo Vosk (Wake word)
if [ ! -d "vosk-model-es" ]; then
    echo "    Descargando modelo Vosk para español (STT / Wake word)..."
    if command -v wget >/dev/null 2>&1; then
        wget -q --show-progress https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
    else
        curl -# -LO https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
    fi
    unzip -q vosk-model-small-es-0.42.zip
    mv vosk-model-small-es-0.42 vosk-model-es
    rm vosk-model-small-es-0.42.zip
else
    echo "    Modelo Vosk ya está instalado."
fi

# Modelo Piper TTS
if [ ! -f "es_MX-claude-high.onnx" ] || [ ! -f "es_MX-claude-high.onnx.json" ]; then
    echo "    Descargando modelo de voz Piper (TTS)..."
    if command -v wget >/dev/null 2>&1; then
        wget -q --show-progress https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx
        wget -q --show-progress https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx.json
    else
        curl -# -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx
        curl -# -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx.json
    fi
else
    echo "    Modelo Piper TTS ya está instalado."
fi

cd ..

echo ""
echo "==> 6. Comprobando configuración de .env (Tareas)..."
if [ ! -f "backend/.env" ]; then
    echo "    Creando backend/.env por defecto..."
    cat > backend/.env << 'EOF'
# Configuración de base de datos para tareas
# DB_HOST=localhost
# DB_PORT=5432
# DB_NAME=minerva
# DB_USER=postgres
# DB_PASS=postgres
EOF
    echo "    -> Por favor, edita backend/.env con tus credenciales de PostgreSQL si usas las Tareas."
else
    echo "    El archivo .env ya existe."
fi

echo ""
echo "==> 7. Comprobando configuración de Spotify..."
SPOTIFY_DIR="$HOME/.config/spotify_minerva"
SPOTIFY_CREDS="$SPOTIFY_DIR/credentials.json"
mkdir -p "$SPOTIFY_DIR"

if [ ! -f "$SPOTIFY_CREDS" ]; then
    echo "    Creando plantilla de credenciales en $SPOTIFY_CREDS..."
    cat > "$SPOTIFY_CREDS" << 'EOF'
{
    "client_id": "TU_CLIENT_ID_AQUI",
    "client_secret": "TU_CLIENT_SECRET_AQUI",
    "redirect_uri": "http://localhost:8888/callback"
}
EOF
    echo "    -> (Opcional) Para poder controlar Spotify, necesitas ir a https://developer.spotify.com/dashboard"
    echo "       crear una App y colocar tu Client ID y Client Secret en ese archivo JSON."
else
    echo "    Las credenciales de Spotify ya existen."
fi

echo ""
echo "=========================================================="
echo " ¡Instalación completada! Minerva está lista para usarse."
echo " Recuerda revisar los pasos opcionales (Base de datos y Spotify)."
echo " Luego, reinicia Quickshell para cargar el ecosistema."
echo "=========================================================="
