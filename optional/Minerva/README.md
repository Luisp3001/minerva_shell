# Minerva

Minerva es una asistente de inteligencia artificial integrada en el escritorio, construida como un plugin de [Quickshell](https://github.com/quickshell-mirror/quickshell). Combina un frontend en QML (interfaz gráfica nativa Wayland) con un backend en Python que conecta modelos de lenguaje (Ollama local o Gemini en la nube) con herramientas del sistema operativo: ejecución de comandos asíncronos, sistema de archivos, búsqueda web, generación de imágenes, control de Hyprland, control de Spotify, captura de pantalla, gestión proactiva de tareas y memoria persistente a largo plazo.

El nombre viene de la diosa romana de la sabiduría.

---

## Características principales

- **Dual engine:** Ollama (local, offline) y Gemini (API de Google Cloud) con streaming de tokens.
- **Agentic loop:** La IA puede invocar herramientas de forma iterativa (hasta 6 turnos) para completar tareas complejas.
- **Ejecución de comandos asíncrona:** Coordinada vía `JobManager` thread-safe con rastreo por `job_id`, turnos multi-comando, streaming de salida en tiempo real e inspección de estado con `check_job_status` — no se congela mientras espera.
- **Sistema de voz completo:** Wake word ("Minerva"), STT (Whisper), TTS triple (**Piper** local, **Fish Audio** en la nube con **Emotion Tags** y **Google Gemini TTS** con ~30 voces) y detección de silencio.
- **Generación de imágenes:** Integración nativa con Gemini (`gemini-3.1-flash-image`) para generar imágenes a partir de descripciones de texto en resoluciones 1K (previsualizable en el chat) y 2K (guardado directo en disco en `~/Pictures/minerva`).
- **Control de entorno de escritorio (Hyprland):** Navegación entre workspaces (1-10), reubicación de ventanas entre workspaces por clase o título y listado de ventanas activas vía `hyprctl`.
- **Herramientas de documentos y RAG Efímero:** Creación de documentos Word (`.docx`) formateados desde Markdown con `pypandoc`, edición quirúrgica de Word con `python-docx` y consulta semántica puntual (`query_document`) en PDF, DOCX y PPTX con `MarkItDown` + `ChromaDB` sin necesidad de leer todo el archivo.
- **SiriOrb:** Visualización animada por GPU (fragment shader) que reacciona al audio en tiempo real con RMS y 4 bandas FFT.
- **Memoria a largo plazo:** Archivos Markdown (`user_profile.md` y `preferences.md`) para almacenar el perfil del usuario y sus preferencias entre sesiones, actualizables proactivamente con `update_memory`.
- **Proactividad (Tareas):** Conexión a PostgreSQL para gestionar tareas con alertas visuales sutiles en el SiriOrb. Soporta **tareas recurrentes** (diaria, semanal, mensual, anual con `recurrence_month`) con auto-renovación en segundo plano.
- **Herramientas de archivos avanzadas:** Lectura inteligente por rangos de líneas (`read_file`), metadatos (`file_info`), creación directa (`write_file`), edición quirúrgica (`replace_lines`) y conversión a Markdown para PDF, Word (`.docx`), PowerPoint (`.pptx`) y Excel/CSV (`.xlsx`/`.csv`).
- **Tool RAG:** Selección inteligente de herramientas relevantes vía embedding semántico para no saturar el contexto.
- **Seguridad:** Clasificación automática de comandos (safe / destructive / sudo) con confirmación en la UI.
- **Captura de pantalla:** Visión multimodal — Minerva puede ver tu pantalla y analizarla.
- **Spotify:** Control completo de reproducción vía OAuth2 (buscar, reproducir, pausar, cola, volumen).
- **Directorio de configuración unificado:** Centralización de variables de entorno (`.env`), credenciales y tokens de caché en `~/.config/minerva/`.

---

## Estructura del proyecto

```text
optional/Minerva/
│
│  ── Frontend (QML) ──────────────────────────────────────────────────
│
├── plugin.json                  # Manifiesto del plugin (id, nombre, versión, autor)
├── qmldir                       # Registro de componentes QML (ChatWidget, SiriOrb)
├── Main.qml                     # Punto de entrada del plugin:
│                                #   - Inicia el proceso Python como subproceso
│                                #   - Servidor HTTP local (POST → backend)
│                                #   - Lee stdout del backend (JSON Lines → QML)
│                                #   - Estado global: configuración IA, grabación, transcripción
│                                #   - Expone barIcon, centerWidget y expandedPanel
├── ChatWidget.qml               # Interfaz de chat completa:
│                                #   - Burbujas de usuario e IA con streaming de tokens
│                                #   - Tarjetas de comando (pending / running / success / error)
│                                #   - Streaming de salida de comandos en tiempo real
│                                #   - Previsualización de imágenes generadas por IA
│                                #   - Diálogo de confirmación para comandos destructivos/sudo
│                                #   - Input con micrófono, adjuntar imagen, placeholder dinámico
├── SiriOrb.qml                  # Orbe animado tipo Siri (GPU ShaderEffect):
│                                #   - Estados: idle, recording, transcribing, thinking, speaking
│                                #   - Recibe audioRms + 4 bandas FFT como uniforms
│                                #   - Acumulador de fase continuo (~60fps) para evitar saltos
│
├── shaders/
│   ├── siri_orb.frag            # Fragment shader GLSL: Simplex Noise + 4 ondas de color
│   └── siri_orb.frag.qsb       # Shader precompilado (Qt Shader Baker)
│
├── voice/                       # Modelos locales de voz
│   ├── es_MX-claude-high.onnx   # Modelo Piper TTS (español México, calidad alta)
│   ├── es_MX-claude-high.onnx.json
│   └── vosk-model-es/           # Modelo Vosk STT para wake word
│
│  ── Backend (Python) ────────────────────────────────────────────────
│
├── main.py                      # Punto de entrada del backend:
│                                #   - Servidor HTTP en 127.0.0.1:11435
│                                #   - Bucle principal: despacha mensajes (chat, run_confirmed,
│                                #     run_sudo, toggle_voice, cancel, ping, stop_tts)
│                                #   - Ejecución asíncrona de comandos (Popen + hilo)
│                                #   - Transcripción de voz (Whisper)
├── requirements.txt             # Dependencias pip del entorno virtual
├── .venv/                       # Entorno virtual de Python
│
└── backend/
    ├── __init__.py
    ├── README.md                # Documentación del backend (cómo agregar tools, etc.)
    │
    ├── core/                    # Lógica central y motores de IA
    │   ├── config.py            # Constantes globales y directorio ~/.config/minerva/:
    │   │                        #   - MODEL, HOME, MAX_FILE, MAX_DIR
    │   │                        #   - Paths de Spotify, voz y .env unificado
    │   │                        #   - Flags de disponibilidad (VOICE_AVAILABLE, FISH_AUDIO_AVAILABLE, GEMINI_TTS_AVAILABLE, etc.)
    │   ├── io.py                # Comunicación con QML:
    │   │                        #   - emit() / emit_error() → JSON Lines a stdout
    │   │                        #   - is_safe_path() → verificación $HOME
    │   │                        #   - classify_cmd() → safe / destructive / sudo
    │   ├── job_manager.py       # JobManager (singleton job_mgr):
    │   │                        #   - CommandJob: representa comandos asíncronos con job_id
    │   │                        #   - Gestión de turnos multi-comando y estados (queued/running/completed/failed/cancelled)
    │   ├── ollama_engine.py     # Engine de chat con Ollama (API REST local):
    │   │                        #   - Streaming de tokens, tool calls nativas, thinking mode
    │   │                        #   - Agentic loop con re-invocación iterativa coordinada por turnos
    │   ├── gemini_engine.py     # Engine de chat con Gemini (API OpenAI-compatible / GenAI):
    │   │                        #   - SSE streaming, tool calls incrementales (delta chunks)
    │   │                        #   - Soporte multimodal (imágenes en base64) y desconcatenación de calls
    │   ├── voice.py             # VoiceManager (singleton voice_mgr):
    │   │                        #   - TTS triple: Piper (local ONNX), Fish Audio (nube con Emotion Tags)
    │   │                        #     o Google Gemini TTS (~30 voces neurales)
    │   │                        #   - STT: Whisper (pywhispercpp)
    │   │                        #   - Wake word: Vosk con stream de audio continuo
    │   │                        #   - StreamEmotionStripper para limpiar tags en tiempo real
    │   ├── audio_analyzer.py    # AudioAnalyzer: RMS + FFT de 4 bandas
    │   │                        #   - Suavizado exponencial
    │   │                        #   - Ventana Hann para reducir spectral leakage
    │   │                        #   - Alimenta los uniforms del shader SiriOrb
    │   ├── memory.py            # Lectura y actualización de archivos Markdown (user_profile.md / preferences.md)
    │   │                        #   - get_memory_context() para inyección en el system prompt
    │   │                        #   - update_memory_section() para guardado quirúrgico de secciones
    │   └── tasks_db.py          # Conexión a PostgreSQL (CRUD de tareas + recurrencia):
    │                            #   - init_db(): crea tabla y columnas de recurrencia
    │                            #   - renew_recurring_tasks(): renueva tareas vencidas en segundo plano
    │
    └── tools/                   # Herramientas que la IA puede invocar
        ├── __init__.py          # Exporta dispatch_tool() (despachador centralizado),
        │                        # OLLAMA_TOOLS, SYSTEM_PROMPT, get_relevant_tools() (RAG)
        ├── definitions.py       # SYSTEM_PROMPT (personalidad, reglas, contexto, FISH_AUDIO_EMOTION_PROMPT)
        │                        # OLLAMA_TOOLS (esquemas JSON de todas las herramientas)
        ├── filesystem.py        # list_dir, file_info, read_file, write_file, replace_lines,
        │                        # read_pdf, read_docx, read_pptx, read_excel (vía MarkItDown),
        │                        # create_docx, modify_docx, query_document (RAG efímero)
        ├── system.py            # web_search (DuckDuckGo), launch_app (busca .desktop),
        │                        # hyprland_control (workspaces/ventanas), check_job_status
        ├── imagen.py            # tool_generate_image: Gemini 3.1 Flash Image (1K/2K) en ~/Pictures/minerva
        ├── spotify.py           # spotify_music: OAuth2 completo, control de reproducción
        ├── screen.py            # capture_screen: grim → base64 → visión multimodal
        ├── memory_tool.py       # update_memory: modifica secciones en user_profile.md y preferences.md
        └── tasks.py             # manage_tasks: Gestiona tareas en PostgreSQL (add, complete, list)
                                 #   - Soporte de recurrence ('daily','weekly','monthly','yearly'),
                                 #     recurrence_day y recurrence_month
```

---

## Flujo de comunicación

El frontend y el backend se comunican mediante dos canales distintos:

```
┌──────────────────────┐          HTTP POST           ┌──────────────────────┐
│                      │  ──────────────────────────▶  │                      │
│      QML (Main.qml)  │    127.0.0.1:11435           │   Python (main.py)   │
│                      │                              │                      │
│                      │  ◀──────────────────────────  │                      │
│                      │     stdout (JSON Lines)       │                      │
└──────────────────────┘                              └──────────────────────┘
```

**QML → Python (peticiones):** La interfaz envía objetos JSON via HTTP POST al servidor local del backend. Los tipos de mensaje incluyen:

| Tipo              | Descripción                                          |
|-------------------|------------------------------------------------------|
| `chat`            | Mensaje del usuario con historial, imagen y settings |
| `run_confirmed`   | Confirmación para ejecutar un comando normal (pasa `job_id`) |
| `run_sudo`        | Confirmación para ejecutar un comando con pkexec (pasa `job_id`) |
| `job_cancelled`   | Notifica que un comando fue cancelado por el usuario (pasa `job_id`) |
| `toggle_voice`    | Iniciar/detener grabación de voz                     |
| `cancel`          | Cancelar operación en curso                          |
| `stop_tts`        | Detener la síntesis de voz                           |
| `ping`            | Health check (retorna `ready`)                       |

**Python → QML (eventos):** El backend escribe una línea JSON por evento a stdout, que QML lee vía `SplitParser`. Los tipos de evento incluyen:

| Tipo                     | Descripción                                            |
|--------------------------|--------------------------------------------------------|
| `tasks_pending`          | Señal silenciosa: hay tareas pendientes (incluye `urgent: bool`, `urgency: string`) |
| `tasks_cleared`          | Señal silenciosa: no hay tareas pendientes             |
| `ready`                  | Backend inicializado, modelo y home disponibles        |
| `token`                  | Token de texto generado por la IA (streaming)          |
| `done`                   | Respuesta completa de la IA                            |
| `tool_start`             | La IA comienza a usar una herramienta                  |
| `tool_result`            | Resultado de la herramienta (interno)                  |
| `run_command`            | Comando seguro auto-ejecutable (incluye `job_id`)      |
| `command_start`          | Inicio de ejecución asíncrona de un comando (`job_id`) |
| `command_output`         | Línea de salida parcial del comando en ejecución (`job_id`) |
| `command_result`         | Resultado final del comando (`job_id`, output, returncode) |
| `confirm_required`       | Comando destructivo que necesita confirmación (`job_id`) |
| `sudo_required`          | Comando que necesita privilegios elevados (`job_id`)   |
| `voice_recording_started`| Grabación de micrófono iniciada                        |
| `voice_recording_stopped`| Grabación detenida                                     |
| `voice_transcribing`     | Transcribiendo audio con Whisper                       |
| `voice_recognized`       | Texto transcrito listo                                 |
| `wake_word_detected`     | Se detectó "Minerva" via Vosk                          |
| `silence_detected`       | Silencio detectado, fin de dictado                     |
| `voice_speaking_started` | TTS comienza a hablar                                  |
| `voice_speaking_stopped` | TTS terminó de hablar                                  |
| `audio_data`             | Métricas de audio en tiempo real (rms + 4 bandas FFT)  |
| `error`                  | Error genérico                                         |

---

## Flujo de un mensaje de chat

```
Usuario escribe → QML envía POST {"type":"chat"} → main.py recibe
    │
    ├── Inyecta fecha al SYSTEM_PROMPT
    ├── Inyecta memoria (user_profile.md y preferences.md) al prompt
    ├── Inyecta tareas pendientes proactivamente (si aplican)
    ├── Construye historial [system, ...history, user]
    │
    └── _dispatch_chat() → elige engine según provider
            │
            ├── Ollama: do_chat() → API REST local, streaming (soporta thinking mode)
            └── Gemini: do_chat_gemini() → API SSE, streaming (soporta desconcatenación de calls)
                    │
                    ├── Emite tokens → QML los muestra en la burbuja de IA
                    │
                    ├── Si la IA decide usar tool_calls:
                    │       ├── dispatch_tool() ejecuta la herramienta
                    │       ├── Si es run_command:
                    │       │       ├── Crea CommandJob y registra en JobManager
                    │       │       ├── safe → emite "run_command" → QML auto-confirma
                    │       │       ├── destructive → emite "confirm_required"
                    │       │       └── sudo → emite "sudo_required"
                    │       │       └── Se inicia turno (job_mgr.start_turn); retoma chat cuando TODOS completan
                    │       ├── Si es otra tool → ejecuta, inyecta resultado, reitera
                    │       └── Máximo 6 iteraciones
                    │
                    └── Sin tool calls → emite "done" → fin del turno
```

---

## Sistema de voz

Minerva tiene un pipeline de voz completo con tres subsistemas independientes:

**Wake word (siempre activo):** Un hilo dedicado escucha el micrófono continuamente usando Vosk con un modelo de español. Cuando detecta la palabra "minerva" en el flujo de audio, emite `wake_word_detected` y la UI activa la grabación automáticamente.

**STT (Speech-to-Text):** Al activar la grabación (botón de micrófono o wake word), el audio del micrófono se acumula en un búfer. Cuando se detiene la grabación (manual o por detección de silencio), el audio se transcribe con Whisper (pywhispercpp, modelo small) y el texto resultante se envía como si el usuario lo hubiera escrito.

**TTS (Text-to-Speech):** Motor triple configurable desde la UI:
- **Piper (local ONNX):** Síntesis offline rápida con modelo ONNX en español (`es_MX-claude-high`).
- **Fish Audio (API en la nube):** Síntesis neural de alta calidad con soporte de **Emotion Tags** (`[happy]`, `[sad]`, `[excited]`, `[confident]`, `[neutral]`, etc.). Un procesador en streaming (`StreamEmotionStripper`) limpia los tags en tiempo real antes de emitir los tokens a la UI, asegurando que la voz exprese entonación sin mostrar símbolos en el chat.
- **Google Gemini TTS (API en la nube):** Síntesis neural multilingüe con la API oficial de Google (`google-genai`). Admite modelos `gemini-2.5-flash-tts` y `gemini-2.5-pro-tts` con ~30 voces preconstruidas (ej: `Kore`, `Aoede`, `Puck`, `Charon`, `Zephyr`, etc.) convertidas directamente a audio PCM 24kHz.

Durante la reproducción de cualquier motor, un `AudioAnalyzer` calcula métricas (RMS + FFT) que se envían al frontend para animar el SiriOrb en sincronía con la voz.

---

## Herramientas disponibles para la IA

| Herramienta       | Archivo                | Descripción                                                      |
|-------------------|------------------------|------------------------------------------------------------------|
| `list_dir`        | `tools/filesystem.py`  | Lista el contenido de un directorio (dentro de $HOME)            |
| `file_info`       | `tools/filesystem.py`  | Devuelve metadatos del archivo (total de líneas y tamaño)        |
| `read_file`       | `tools/filesystem.py`  | Lee un archivo por rangos de líneas (`start_line`, `end_line`)   |
| `write_file`      | `tools/filesystem.py`  | Crea o sobreescribe un archivo de forma directa (`overwrite`)    |
| `replace_lines`   | `tools/filesystem.py`  | Reemplazo quirúrgico de líneas específicas en un archivo         |
| `read_pdf`        | `tools/filesystem.py`  | Extrae texto de un PDF a Markdown (vía MarkItDown)              |
| `read_docx`       | `tools/filesystem.py`  | Extrae contenido de un archivo Word (.docx) a Markdown           |
| `read_pptx`       | `tools/filesystem.py`  | Extrae texto de presentaciones PowerPoint (.pptx) a Markdown     |
| `read_excel`      | `tools/filesystem.py`  | Extrae contenido de hojas Excel (.xlsx) y CSV a Markdown         |
| `create_docx`     | `tools/filesystem.py`  | Crea un archivo Word (.docx) formateado desde Markdown (pypandoc)|
| `modify_docx`     | `tools/filesystem.py`  | Añade párrafos de texto al final de un archivo Word (.docx)      |
| `query_document`  | `tools/filesystem.py`  | Búsqueda semántica (RAG efímero) en PDF, DOCX, PPTX con ChromaDB |
| `run_command`     | `tools/__init__.py`    | Ejecuta un comando bash (asíncrono, rastreado por `job_id`)      |
| `check_job_status`| `tools/system.py`      | Consulta el estado y salida de comandos en segundo plano         |
| `web_search`      | `tools/system.py`      | Busca en internet via DuckDuckGo (ddgs)                          |
| `launch_app`      | `tools/system.py`      | Busca y abre una app gráfica por nombre o sinónimo               |
| `hyprland_control`| `tools/system.py`      | Controla workspaces y mueve ventanas en Hyprland vía `hyprctl`   |
| `generate_image`  | `tools/imagen.py`      | Genera imágenes con Gemini 3.1 Flash Image (1K/2K) en ~/Pictures |
| `spotify_music`   | `tools/spotify.py`     | Control de Spotify (play, pause, search, queue, volume, etc.)    |
| `capture_screen`  | `tools/screen.py`      | Captura la pantalla con grim → base64 → visión multimodal       |
| `update_memory`   | `tools/memory_tool.py` | Modifica quirúrgicamente `user_profile.md` o `preferences.md`    |
| `manage_tasks`    | `tools/tasks.py`       | Gestiona tareas en PostgreSQL (`add`, `complete`, `list`) con soporte de recurrencia (`recurrence`, `recurrence_day`, `recurrence_month`) |

---

## Proactividad y Tareas (PostgreSQL)

Minerva puede gestionar tus pendientes usando una base de datos PostgreSQL remota o local (configurada en `~/.config/minerva/.env`). Esto le permite funcionar como un asistente proactivo real:

1. **Inyección de Contexto**: Al chatear, Minerva lee tus tareas pendientes y las inyecta en su `SYSTEM_PROMPT` para conocerlas y recordártelas de forma natural.
2. **Worker en Segundo Plano**: Un hilo en `main.py` sondea la BD cada 10 minutos. Antes de consultar pendientes, llama a `renew_recurring_tasks()` para renovar automáticamente cualquier tarea recurrente vencida.
3. **Indicador Visual Silencioso**: QML captura el evento y muestra el SiriOrb en el centro de tu pantalla por 20 segundos y deja un aviso en el widget. El orbe reacciona visualmente según el nivel de urgencia máximo con tinte de color en GPU y una animación de respiración/pulso: **Verde esmeralda** (baja urgencia, > 3 días), **Amarillo/Ámbar** (media urgencia, 1 a 3 días) o **Rojo vibrante parpadeante** (alta urgencia / vencida, < 24 horas).
4. **Herramienta IA**: Minerva tiene la tool `manage_tasks` para añadir nuevas tareas, ponerles fecha de vencimiento (`due_date`) o marcarlas como completadas. `manage_tasks` está **siempre disponible** en el Tool RAG para garantizar que la IA la use ante cualquier pregunta sobre fechas o cobros.

### Tareas recurrentes

Las tareas pueden repetirse automáticamente configurando campos adicionales:

| Campo            | Tipo        | Descripción                                                                                  |
|------------------|-------------|----------------------------------------------------------------------------------------------|
| `recurrence`     | `VARCHAR(10)` | Frecuencia: `'daily'`, `'weekly'`, `'monthly'`, `'yearly'`. `NULL` = tarea única.          |
| `recurrence_day` | `INTEGER`   | Día de anclaje. Para `monthly`/`yearly`: día del mes (1-31). Para `weekly`: día de semana (0=lun…6=dom). |
| `recurrence_month` | `INTEGER` | Mes de anclaje (1-12). Solo usado para recurrencia `'yearly'` (ej. cumpleaños). |

---

## Seguridad de comandos y JobManager

El módulo `io.py` clasifica cada comando en tres categorías usando expresiones regulares:

- **safe**: Se ejecuta de forma asíncrona tras autoconfirmación. El resultado se transmite en streaming.
- **destructive** (rm, dd, mkfs, shred, etc.): Requiere confirmación explícita del usuario en la UI.
- **sudo** (sudo, pkexec, pacman -S, systemctl start/stop, etc.): Se ejecuta via `pkexec` (polkit) tras confirmación.

Cada comando emitido se registra en el singleton **`JobManager`** (`job_mgr`) como un **`CommandJob`** con un `job_id` único (hex corto de UUID).
- **Estados del job:** `queued` → `running` → `completed` / `failed` / `cancelled` (si el usuario cancela en la UI).
- **Gestión por turnos:** Cuando la IA emite uno o varios comandos en la misma respuesta, `job_mgr.start_turn()` registra el grupo. El backend espera a que todos los jobs del turno alcancen un estado terminal antes de reanudar el chat (`_dispatch_chat`) con los resultados acumulados.

---

## Memoria y RAG

Minerva usa almacenamiento estructurado y ChromaDB para dos propósitos:

1. **Memoria a largo plazo** (`user_profile.md` y `preferences.md`): Almacena hechos, datos personales y preferencias del usuario. Al inicio de cada chat, se inyectan en el system prompt. La IA usa `update_memory` para guardar o actualizar secciones proactivamente.

2. **Tool RAG** (colección efímera `minerva_tools`): Evita enviar todas las definiciones de herramientas en cada request. Usa embeddings para seleccionar las herramientas más relevantes al mensaje del usuario (top-k configurable). Herramientas críticas como `manage_tasks`, `run_command` y de lectura/edición de documentos se inyectan siempre en el resultado.

3. **RAG Efímero de Documentos** (`query_document`): Permite consultar información puntual en PDF, DOCX y PPTX dividiendo el texto en chunks y creando una colección ChromaDB temporal en memoria.

Directorio de configuración e historias: `~/.config/minerva/`

---

## Dependencias opcionales

El backend detecta automáticamente qué dependencias están instaladas y desactiva funcionalidades que no estén disponibles:

| Flag                     | Dependencias requeridas                  | Funcionalidad             |
|--------------------------|------------------------------------------|---------------------------|
| `VOICE_AVAILABLE`        | sounddevice, soundfile, pywhispercpp     | Grabación y transcripción (STT) |
| `VOSK_AVAILABLE`         | vosk                                     | Wake word ("Minerva")     |
| `FISH_AUDIO_AVAILABLE`   | fish_audio_sdk                           | TTS en la nube con Emotion Tags |
| `GEMINI_TTS_AVAILABLE`   | google-genai                             | TTS en la nube con Google Gemini (~30 voces) |
| `WEB_SEARCH_AVAILABLE`   | ddgs                                     | Búsqueda web              |
| `CHROMADB_AVAILABLE`     | chromadb                                 | RAG efímero y Tool RAG    |
| *(Google GenAI)*         | google-genai                             | Generación de imágenes (`generate_image`) y Gemini TTS |
| *(Documentos Word)*      | pypandoc + pandoc (sistema), python-docx | Creación (`create_docx`) y edición (`modify_docx`) de Word |
| *(MarkItDown opcional)*  | markitdown                               | Extracción de texto de PDF, DOCX, PPTX y Excel/CSV |

Piper TTS se carga bajo demanda (lazy-load) al primer uso de voz local.

---

## Configuración

Los ajustes de la IA, voz e imágenes se gestionan desde la UI de Quickshell y se pasan al backend en cada petición de chat (con variables persistidas en `~/.config/minerva/.env`):

| Ajuste            | Propiedad QML   | Descripción                                     |
|-------------------|-----------------|--------------------------------------------------|
| Proveedor IA      | `aiProvider`    | `"Ollama"` o `"Gemini"`                          |
| API Key Gemini    | `geminiApiKey`  | Clave de API para Google Generative AI (Chat, Visión, Imágenes y TTS) |
| Modelo Gemini     | `geminiModel`   | Ej: `gemini-2.5-flash`                           |
| Modelo Ollama     | `aiModel`       | Ej: `qwen3.5:9b` o `gemma4:e4b`                  |
| Temperatura       | `aiTemperature` | Creatividad del modelo (0.0 – 1.0)              |
| Contexto          | `aiNumCtx`      | Ventana de contexto para Ollama (tokens)         |
| Thinking          | `aiThinking`    | Activar razonamiento extendido (Ollama)          |
| Proveedor TTS     | `ttsProvider`   | `"piper"` (local), `"fish"` (Fish Audio) o `"gemini"` (Google Gemini TTS) |
| Voz Gemini TTS    | `geminiTtsVoice`| Voz preconstruida de Google (ej: `Kore`, `Aoede`, `Puck`, `Charon`) |
| Modelo Gemini TTS | `geminiTtsModel`| Modelo de TTS (ej: `gemini-2.5-flash-tts`, `gemini-2.5-pro-tts`) |
| API Key Fish      | `fishApiKey`    | API Key de Fish Audio                            |
| Voice ID Fish     | `fishVoiceId`   | ID de voz de referencia en Fish Audio            |
| Modelo Fish       | `fishModel`     | Ej: `s2-pro`, `speech-1.6`, etc.                 |
