<div align="center">
  <h1>🌌 Quickshell Dynamic Island</h1>
  <p><i>Una experiencia de escritorio hiper-modular impulsada por IA.</i></p>
</div>

Una experiencia de escritorio de próxima generación construida sobre [Quickshell](https://github.com/quickshell-mirror/quickshell). Diseñada íntegramente en QML (Qt Quick), esta shell introduce una **Isla Dinámica** fluida e interactiva en el centro de tu flujo de trabajo, diseñada con un solo propósito: ser el hogar perfecto para nuestra protagonista.

---

## 🌟 Protagonista: Minerva AI

**Minerva** no es un simple script de chat; es la diosa romana de la sabiduría reencarnada como el núcleo inteligente y agentizado de tu escritorio. Es un asistente multimodal, proactivo y profundamente integrado al sistema que vive en el corazón de la Isla Dinámica.

### 🔮 Sus Superpoderes
- **Dual Engine & Agentic Loop**: Desarrollada para funcionar tanto localmente (Ollama) como en la nube (Gemini). Posee un motor lógico que le permite razonar iterativamente y usar herramientas de sistema para resolver problemas complejos de forma autónoma.
- **Interacción Natural por Voz**: Habla con ella. Gracias a su detección de *Wake Word* ("Minerva", potenciado por Vosk), transcripción fluida (Whisper STT) y voz neuronal (Piper TTS), la conversación es orgánica y sin manos libres.
- **SiriOrb Reactivo (GPU)**: Cuando Minerva te escucha o te habla, la Isla Dinámica cobra vida desplegando un orbe animado. Escrito en un fragment shader de GLSL a ~60fps, reacciona matemáticamente en tiempo real al RMS y a las 4 bandas FFT de la voz.
- **Memoria a Largo Plazo (ChromaDB)**: Minerva no sufre de amnesia. Posee una base de datos vectorial que guarda proactivamente tus preferencias y hechos pasados, inyectando ese contexto en cada charla de forma invisible.
- **Visión y Ejecución**: Puede tomar "fotos" de tu pantalla para entender tu contexto visual, buscar en internet de forma silenciosa, controlar tu Spotify, y ejecutar comandos Bash asíncronos (con un sistema de seguridad riguroso que te pide autorización para comandos destructivos o `sudo`).
- **Asistente Proactivo (PostgreSQL)**: Minerva maneja tus fechas límite y tareas recurrentes. Si algo es urgente, su orbe parpadeará sutilmente en rojo en la isla para llamar tu atención, e inyectará automáticamente tu lista de pendientes en su conciencia para recordártelo si le preguntas qué debes hacer.

---

## 🧩 La Isla Dinámica & Sistema de Plugins

El shell está diseñado bajo una estricta filosofía de **hiper-modularidad**. La Isla Dinámica (`Bar.qml` + `CenterSection.qml`) transiciona con físicas suaves desde una "píldora" compacta a un panel de control interactivo gigante, alojando distintos módulos sin mezclar el código.

### Un Ecosistema 100% Extensible
No toques el código fuente (a menos que quieras). Puedes inyectar y retirar funcionalidades con facilidad:

- **Detección Dinámica**: El motor interno (`PluginManager`) escanea la carpeta `optional/` en tiempo real buscando manifiestos `plugin.json`.
- **Inyección Visual Inmediata**: Los plugins se instancian al vuelo. Si tu módulo define un componente central, se añadirá automáticamente a la lista de pestañas de la Isla Dinámica.
- **Menús de Ajustes Auto-Generados**: Si un plugin exporta una matriz de configuraciones, el shell creará instantáneamente una interfaz gráfica de _switches_ e _inputs_ en el panel de configuración global, guardando las preferencias del usuario de forma persistente y limpia.

> 🛠️ **¿Quieres crear tu propio plugin en 3 minutos?** Revisa la guía técnica completa en [Doc.md](./Doc.md).

---

## 🚀 Instalación "Plug & Play"

Hemos simplificado al máximo el despliegue del ecosistema y de Minerva para que no tengas que pelear con configuraciones tediosas.

```bash
# 1. Clona el repositorio (si aún no lo tienes)
git clone https://github.com/Luisp3001/minerva_shell.git ~/.config/minerva_shell

# 2. Navega al directorio del plugin estrella
cd ~/.config/minerva_shell/optional/Minerva

# 3. Deja que la magia suceda
./install.sh
```

El script de instalación se encargará de purgar viejos entornos, instalar exactamente el ecosistema minimalista de dependencias, descargar y ubicar los modelos pesados de IA (Vosk y Piper), y generar las plantillas para tu conexión con bases de datos y Spotify.

*Simplemente recarga Quickshell y Minerva despertará.*
