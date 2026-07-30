#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Herramientas de sistema de archivos para Minerva.

Todas las funciones reciben rutas y retornan strings (resultado o error).
La validación de seguridad (is_safe_path) se aplica en todas las operaciones.
"""
import pathlib
import shutil
import subprocess

from ..core.config import HOME, MAX_FILE, MAX_DIR
from ..core.io import is_safe_path


def tool_list_dir(path: str) -> str:
    exp = str(pathlib.Path(path).expanduser())
    if not is_safe_path(exp):
        return f"Acceso denegado: solo se permite dentro de {HOME}"
    try:
        r = subprocess.run(
            ["ls", "-la", "--color=never", exp],
            capture_output=True, text=True, timeout=5
        )
        return (r.stdout if r.returncode == 0 else r.stderr)[:MAX_DIR]
    except Exception as e:
        return f"Error al listar directorio: {e}"


def tool_file_info(path: str) -> str:
    """Devuelve metadatos del archivo: total de líneas y tamaño.
    Usar antes de read_file para decidir qué rango de líneas pedir."""
    exp = str(pathlib.Path(path).expanduser())
    if not is_safe_path(exp):
        return f"Acceso denegado: solo se permite dentro de {HOME}"
    try:
        p = pathlib.Path(exp)
        if not p.exists():
            return f"No existe: {exp}"
        if p.is_dir():
            return "Es un directorio, no un archivo"
        if not p.is_file():
            return "No es un archivo regular"
        size_bytes = p.stat().st_size
        if size_bytes >= 1_048_576:
            size_str = f"{size_bytes / 1_048_576:.1f} MB"
        elif size_bytes >= 1_024:
            size_str = f"{size_bytes / 1_024:.1f} KB"
        else:
            size_str = f"{size_bytes} B"
        with open(exp, "r", encoding="utf-8", errors="replace") as f:
            total_lines = sum(1 for _ in f)
        return (
            f"Archivo: {exp}\n"
            f"Líneas totales: {total_lines}\n"
            f"Tamaño: {size_str}\n"
            f"Sugerencia: usa read_file con start_line y end_line para leer en bloques de hasta 200 líneas."
        )
    except Exception as e:
        return f"Error obteniendo info del archivo: {e}"


def tool_read_file(path: str, start_line: int = 1, end_line: int = None) -> str:
    """Lee un archivo de texto en un rango de líneas específico.

    Args:
        path:       Ruta absoluta del archivo.
        start_line: Primera línea a leer (1-indexado). Por defecto 1.
        end_line:   Última línea a leer (1-indexado, inclusivo).
                    Por defecto start_line + 199 (chunk de 200 líneas).
    """
    import itertools

    exp = str(pathlib.Path(path).expanduser())
    if not is_safe_path(exp):
        return f"Acceso denegado: solo se permite dentro de {HOME}"
    try:
        p = pathlib.Path(exp)
        if not p.exists():
            return f"No existe: {exp}"
        if p.is_dir():
            return "Es un directorio; usa list_dir en su lugar"
        if not p.is_file():
            return "No es un archivo regular"

        # Normalizar parámetros
        start_line = max(1, int(start_line))
        if end_line is None:
            end_line = start_line + 199  # chunk por defecto: 200 líneas
        else:
            end_line = max(start_line, int(end_line))

        lines_out = []
        eof_reached = False
        total_lines = 0

        with open(exp, "r", encoding="utf-8", errors="replace") as f:
            for lineno, line in enumerate(f, start=1):
                total_lines = lineno
                if lineno < start_line:
                    continue
                if lineno > end_line:
                    # Contamos el resto sin almacenar
                    for _ in f:
                        total_lines += 1
                    break
                lines_out.append(f"{lineno}: {line.rstrip()}")
            else:
                # El bucle terminó sin break → llegamos al EOF dentro del rango
                eof_reached = True

        # EOF: start_line supera el total del archivo
        if start_line > total_lines:
            return (
                f"[EOF] El archivo tiene {total_lines} líneas. "
                f"start_line={start_line} supera el total."
            )

        # Encabezado con metadatos
        shown_end = min(end_line, total_lines)
        header = (
            f"Archivo: {exp} | Total líneas: {total_lines} | "
            f"Mostrando líneas {start_line}–{shown_end}\n"
            f"{'─' * 60}"
        )

        body = "\n".join(lines_out)

        # Nota de EOF si end_line pedido superaba el final real
        footer = ""
        if eof_reached and end_line > total_lines:
            footer = f"\n[EOF alcanzado en línea {total_lines}]"

        return f"{header}\n{body}{footer}"

    except Exception as e:
        return f"Error leyendo archivo: {e}"


def tool_read_pdf(path: str) -> str:
    exp = str(pathlib.Path(path).expanduser())
    if not is_safe_path(exp):
        return f"Acceso denegado: solo se permite dentro de {HOME}"
    try:
        p = pathlib.Path(exp)
        if not p.exists() or not p.is_file():
            return f"Archivo inválido o no existe: {exp}"
        r = subprocess.run(["pdftotext", exp, "-"], capture_output=True, text=True, timeout=10)
        text = r.stdout
        if r.returncode != 0:
            return f"Error extrayendo PDF: {r.stderr}"
        if len(text) > MAX_FILE:
            text = text[:MAX_FILE] + f"\n\n[... truncado: mostrando {MAX_FILE} de {len(text)} bytes ...]"
        return text
    except Exception as e:
        return f"Error leyendo PDF: {e}"


def tool_read_docx(path: str) -> str:
    exp = str(pathlib.Path(path).expanduser())
    if not is_safe_path(exp):
        return f"Acceso denegado: solo se permite dentro de {HOME}"
    try:
        p = pathlib.Path(exp)
        if not p.exists() or not p.is_file():
            return f"Archivo inválido o no existe: {exp}"
        r = subprocess.run(["pandoc", "-f", "docx", "-t", "markdown", exp], capture_output=True, text=True, timeout=10)
        text = r.stdout
        if r.returncode != 0:
            return f"Error extrayendo DOCX: {r.stderr}"
        if len(text) > MAX_FILE:
            text = text[:MAX_FILE] + f"\n\n[... truncado: mostrando {MAX_FILE} de {len(text)} bytes ...]"
        return text
    except Exception as e:
        return f"Error leyendo DOCX: {e}"


def tool_write_file(path: str, content: str, overwrite: bool = False) -> str:
    """Crea o sobreescribe un archivo con el contenido dado.

    Args:
        path:      Ruta absoluta del archivo a crear/sobreescribir.
        content:   Contenido completo a escribir.
        overwrite: Si False (defecto) y el archivo ya existe, retorna error.
                   Pasar True para sobreescribir intencionalmente.
    """
    exp = str(pathlib.Path(path).expanduser())
    if not is_safe_path(exp):
        return f"Acceso denegado: solo se permite dentro de {HOME}"
    try:
        p = pathlib.Path(exp)
        if p.exists() and not overwrite:
            return (
                f"Error: el archivo ya existe en {exp}. "
                f"Usa overwrite=true para sobreescribirlo intencionalmente."
            )
        # Crear directorios padre si no existen
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(exp, "w", encoding="utf-8") as f:
            f.write(content)
        total_lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        action = "sobreescrito" if p.exists() else "creado"
        return f"Archivo {action}: {exp} ({total_lines} líneas escritas)"
    except Exception as e:
        return f"Error escribiendo archivo: {e}"


def tool_replace_lines(path: str, start_line: int, end_line: int, new_content: str) -> str:
    """Reemplaza un rango de líneas en un archivo existente.

    Equivalente a un patch quirúrgico: sustituye las líneas [start_line, end_line]
    (1-indexado, inclusivo) por new_content, sin tocar el resto del archivo.

    Args:
        path:        Ruta absoluta del archivo a modificar.
        start_line:  Primera línea a reemplazar (1-indexado).
        end_line:    Última línea a reemplazar (1-indexado, inclusivo).
        new_content: Texto de reemplazo. Puede ser una o varias líneas.
                     No necesita terminar con \\n; se añade automáticamente.
    """
    exp = str(pathlib.Path(path).expanduser())
    if not is_safe_path(exp):
        return f"Acceso denegado: solo se permite dentro de {HOME}"
    try:
        p = pathlib.Path(exp)
        if not p.exists():
            return f"No existe: {exp}"
        if not p.is_file():
            return "No es un archivo regular"

        start_line = max(1, int(start_line))
        end_line   = max(start_line, int(end_line))

        with open(exp, "r", encoding="utf-8", errors="replace") as f:
            original_lines = f.readlines()

        total_original = len(original_lines)

        if start_line > total_original:
            return (
                f"[EOF] El archivo tiene {total_original} líneas. "
                f"start_line={start_line} supera el total."
            )

        # Asegurar que el nuevo contenido termina con \n
        replacement = new_content if new_content.endswith("\n") else new_content + "\n"
        replacement_lines = replacement.splitlines(keepends=True)

        # Splice: antes del rango + reemplazo + después del rango
        new_lines = (
            original_lines[:start_line - 1]
            + replacement_lines
            + original_lines[end_line:]
        )

        with open(exp, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        removed  = end_line - start_line + 1
        added    = len(replacement_lines)
        total_new = len(new_lines)

        return (
            f"Reemplazo exitoso en {exp}\n"
            f"Líneas {start_line}–{end_line} reemplazadas "
            f"(-{removed} línea(s) → +{added} línea(s))\n"
            f"Total líneas: {total_original} → {total_new}"
        )
    except Exception as e:
        return f"Error reemplazando líneas: {e}"
