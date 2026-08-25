#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memoria a largo plazo de Minerva — basada en archivos Markdown.

Expone:
  - MEMORY_DIR              → ~/.config/minerva/memory/
  - USER_PROFILE_FILE       → user_profile.md  (datos estables del usuario)
  - PREFERENCES_FILE        → preferences.md   (preferencias configurables)
  - CHROMADB_AVAILABLE      → siempre False (mantenido por compatibilidad con __init__.py)
  - chroma_client           → siempre None  (mantenido por compatibilidad con __init__.py)
  - get_memory_context()    → str con el contenido de ambos archivos para inyectar en el system prompt
  - update_memory_section() → escribe/actualiza una sección en user_profile.md o preferences.md
"""
import os
import pathlib
import sys

from .config import HOME

# ─────────────────────────────────────────────────────────────────────────────
# Rutas de memoria
# ─────────────────────────────────────────────────────────────────────────────
MEMORY_DIR         = os.path.join(HOME, ".config", "minerva", "memory")
USER_PROFILE_FILE  = os.path.join(MEMORY_DIR, "user_profile.md")
PREFERENCES_FILE   = os.path.join(MEMORY_DIR, "preferences.md")

# Compatibilidad con código que todavía importa chroma_client / CHROMADB_AVAILABLE
chroma_client      = None
CHROMADB_AVAILABLE = False
MEMORY_AVAILABLE   = True  # La memoria markdown siempre está disponible

# ─────────────────────────────────────────────────────────────────────────────
# Plantillas base para los archivos de memoria
# ─────────────────────────────────────────────────────────────────────────────
_USER_PROFILE_TEMPLATE = """\
# Perfil del Usuario

## Información Personal
<!-- Nombre, alias, idioma preferido, zona horaria, etc. -->

## Entorno de Trabajo
<!-- Sistema operativo, shell, editor, hardware relevante, etc. -->

## Proyectos Activos
<!-- Proyectos en los que trabaja actualmente el usuario -->

## Contexto General
<!-- Cualquier otro dato estable del usuario que sea útil recordar -->
"""

_PREFERENCES_TEMPLATE = """\
# Preferencias del Usuario

## Lenguajes de Programación
<!-- Lenguajes favoritos, los que usa por defecto, etc. -->

## Herramientas y Software
<!-- Editores, terminales, apps preferidas, etc. -->

## Estilo de Comunicación
<!-- Cómo prefiere recibir las respuestas: concisas, detalladas, con ejemplos, etc. -->

## Otras Preferencias
<!-- Cualquier otra preferencia relevante: música, temas visuales, etc. -->
"""


def _ensure_memory_files() -> None:
    """Crea el directorio de memoria y los archivos base si no existen."""
    try:
        pathlib.Path(MEMORY_DIR).mkdir(parents=True, exist_ok=True)
        if not os.path.exists(USER_PROFILE_FILE):
            with open(USER_PROFILE_FILE, "w", encoding="utf-8") as f:
                f.write(_USER_PROFILE_TEMPLATE)
        if not os.path.exists(PREFERENCES_FILE):
            with open(PREFERENCES_FILE, "w", encoding="utf-8") as f:
                f.write(_PREFERENCES_TEMPLATE)
    except Exception as e:
        print(f"[Minerva/memory] Error creando archivos de memoria: {e}", file=sys.stderr)


def _read_file_safe(path: str) -> str:
    """Lee un archivo de texto de forma segura; retorna '' si falla."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def get_memory_context(_text: str = "") -> str:
    """
    Retorna el contenido combinado de user_profile.md y preferences.md
    listo para inyectar en el system prompt de Minerva.

    El parámetro _text ya no se usa (era para la búsqueda semántica en ChromaDB),
    se mantiene por compatibilidad con las llamadas existentes en main.py.
    """
    _ensure_memory_files()

    profile_content = _read_file_safe(USER_PROFILE_FILE)
    prefs_content   = _read_file_safe(PREFERENCES_FILE)

    parts = []
    if profile_content:
        parts.append(profile_content)
    if prefs_content:
        parts.append(prefs_content)

    return "\n\n---\n\n".join(parts) if parts else ""


def update_memory_section(file_key: str, section: str, content: str) -> str:
    """
    Escribe o actualiza una sección (cabecera ##) dentro de un archivo de memoria.

    Args:
        file_key: 'profile' para user_profile.md, 'preferences' para preferences.md.
        section:  El nombre de la cabecera ## (sin los símbolos, ej: 'Lenguajes de Programación').
        content:  El contenido a escribir bajo esa sección.

    Returns:
        Mensaje de éxito o error como string.
    """
    _ensure_memory_files()

    if file_key == "profile":
        target_path = USER_PROFILE_FILE
    elif file_key == "preferences":
        target_path = PREFERENCES_FILE
    else:
        return f"Error: file_key desconocido '{file_key}'. Usa 'profile' o 'preferences'."

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            current_text = f.read()

        heading = f"## {section}"
        content_clean = content.strip()

        if heading in current_text:
            # Reemplazar el contenido existente bajo esa sección.
            # Encontrar el inicio y el fin de la sección (hasta la próxima cabecera ## o ## o EOF)
            import re
            # Escapar el heading para usarlo en regex
            escaped_heading = re.escape(heading)
            # Patrón: desde la cabecera hasta la próxima cabecera de mismo o mayor nivel (## o #) o fin de archivo
            pattern = rf"({escaped_heading}\n)(.*?)(?=\n##|\n#|\Z)"
            replacement = f"{heading}\n{content_clean}\n"
            new_text, count = re.subn(pattern, replacement, current_text, flags=re.DOTALL)
            if count == 0:
                # Si el regex no coincidió por alguna razón, simplemente agregar al final
                new_text = current_text.rstrip() + f"\n\n{heading}\n{content_clean}\n"
        else:
            # La sección no existe: agregar al final del archivo
            new_text = current_text.rstrip() + f"\n\n{heading}\n{content_clean}\n"

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(new_text)

        fname = os.path.basename(target_path)
        return f"Memoria actualizada en '{fname}' → sección '{section}'."

    except Exception as e:
        return f"Error al actualizar memoria: {e}"
