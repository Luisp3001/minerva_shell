#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paquete tools de Minerva.

Expone:
  - OLLAMA_TOOLS            → lista de esquemas JSON de herramientas
  - SYSTEM_PROMPT           → prompt del sistema
  - get_relevant_tools()    → RAG sobre ChromaDB efímero para seleccionar tools relevantes
  - dispatch_tool()         → despachador centralizado (elimina la duplicación entre engines)
"""
import re
import sys

from .definitions   import OLLAMA_TOOLS, SYSTEM_PROMPT, FISH_AUDIO_EMOTION_PROMPT  # noqa: F401
from .filesystem    import (
    tool_list_dir, tool_read_file, tool_read_pdf, tool_read_docx,
    tool_read_pptx, tool_read_excel, tool_file_info, tool_write_file,
    tool_replace_lines, tool_create_docx, tool_modify_docx, tool_query_document
)
from .system        import tool_web_search, tool_launch_app, tool_hyprland_control, tool_check_job_status
from .spotify       import tool_spotify_music
from .memory_tool   import tool_update_memory
from .screen        import tool_capture_screen, ScreenCapture
from .tasks         import tool_manage_tasks
from ..core.io      import classify_cmd, emit
from ..core.config  import HOME
from ..core.job_manager import job_mgr, CommandJob  # noqa: F401

# ─────────────────────────────────────────────────────────────────────────────
# Colección ChromaDB efímera para RAG de tools (seleccionar herramientas relevantes por prompt)
# Usa EphemeralClient para NO necesitar el ChromaDB persistente de la memoria anterior.
# ─────────────────────────────────────────────────────────────────────────────
_tool_collection = None
try:
    import chromadb as _chromadb
    _ephemeral_client = _chromadb.EphemeralClient()
    _tool_collection  = _ephemeral_client.get_or_create_collection(name="minerva_tools")
    _tool_docs = [t["function"]["description"] for t in OLLAMA_TOOLS]
    _tool_ids  = [t["function"]["name"]        for t in OLLAMA_TOOLS]
    _tool_collection.upsert(documents=_tool_docs, ids=_tool_ids)
except Exception as e:
    print(f"Error sincronizando tools en ChromaDB efímero: {e}", file=sys.stderr)


def get_relevant_tools(prompt: str, top_k: int = 10) -> list:
    """
    Selecciona las herramientas más relevantes para el prompt usando ChromaDB.
    Si ChromaDB no está disponible, devuelve todas las tools.

    manage_tasks siempre se incluye — es una tool crítica que debe estar disponible
    para cualquier pregunta sobre tareas, fechas o recordatorios.
    """
    # Tools que siempre deben estar disponibles independientemente del RAG
    _ALWAYS_INCLUDE = {"manage_tasks", "read_pdf", "read_docx", "read_pptx", "read_excel", "create_docx", "modify_docx", "query_document", "run_command", "check_job_status"}

    if not _tool_collection or not prompt.strip():
        return OLLAMA_TOOLS
    try:
        results = _tool_collection.query(
            query_texts=[prompt],
            n_results=min(top_k, len(OLLAMA_TOOLS))
        )
        if not results["ids"] or not results["ids"][0]:
            return OLLAMA_TOOLS
        relevant_names = set(results["ids"][0]) | _ALWAYS_INCLUDE
        return [t for t in OLLAMA_TOOLS if t["function"]["name"] in relevant_names]
    except Exception as e:
        print(f"Error consultando ChromaDB: {e}", file=sys.stderr)
        return OLLAMA_TOOLS


# RUN_COMMAND_PENDING conservado por compatibilidad — ya no se usa internamente.
# Los engines ahora detectan CommandJob por isinstance().
class _RunCommandPending:
    pass

RUN_COMMAND_PENDING = _RunCommandPending()


# ─────────────────────────────────────────────────────────────────────────────
# Despachador centralizado
# ─────────────────────────────────────────────────────────────────────────────
def dispatch_tool(tool_name: str, args: dict, tool_call_id: str = "") -> "str | CommandJob | ScreenCapture":
    """
    Ejecuta la herramienta indicada con los argumentos dados.

    Retorna:
      - str         → resultado listo para agregar al historial como rol 'tool'
      - CommandJob  → la herramienta es run_command; el job fue registrado y el
                      engine debe acumular todos los jobs del turno antes de retornar.
      - ScreenCapture → captura de pantalla; el engine la inyecta como imagen.
    """
    if tool_name == "list_dir":
        return tool_list_dir(args.get("path", HOME))

    elif tool_name == "read_file":
        return tool_read_file(
            args.get("path", ""),
            start_line=args.get("start_line", 1),
            end_line=args.get("end_line", None),
        )

    elif tool_name == "file_info":
        return tool_file_info(args.get("path", ""))

    elif tool_name == "write_file":
        return tool_write_file(
            path      = args.get("path", ""),
            content   = args.get("content", ""),
            overwrite = bool(args.get("overwrite", False)),
        )

    elif tool_name == "replace_lines":
        return tool_replace_lines(
            path        = args.get("path", ""),
            start_line  = args.get("start_line", 1),
            end_line    = args.get("end_line", 1),
            new_content = args.get("new_content", ""),
        )

    elif tool_name == "read_pdf":
        return tool_read_pdf(args.get("path", ""))

    elif tool_name == "read_docx":
        return tool_read_docx(args.get("path", ""))

    elif tool_name == "read_pptx":
        return tool_read_pptx(args.get("path", ""))

    elif tool_name == "read_excel":
        return tool_read_excel(args.get("path", ""))

    elif tool_name == "create_docx":
        return tool_create_docx(args.get("path", ""), args.get("markdown_content", ""))

    elif tool_name == "modify_docx":
        return tool_modify_docx(args.get("path", ""), args.get("instruction", ""))

    elif tool_name == "query_document":
        try:
            top_k = int(args.get("top_k", 5))
        except (ValueError, TypeError):
            top_k = 5
        return tool_query_document(
            path  = args.get("path", ""),
            query = args.get("query", ""),
            top_k = top_k,
        )


    elif tool_name == "web_search":
        try:
            max_res = int(args.get("max_results", 5))
        except (ValueError, TypeError):
            max_res = 5
        return tool_web_search(args.get("query", ""), max_res)

    elif tool_name == "update_memory":
        return tool_update_memory(
            file_key = args.get("file_key", "profile"),
            section  = args.get("section",  ""),
            content  = args.get("content",  ""),
        )

    elif tool_name == "launch_app":
        return tool_launch_app(args.get("query", ""))

    elif tool_name == "spotify_music":
        try:
            vol = int(args.get("volume", 50))
        except (ValueError, TypeError):
            vol = 50
        return tool_spotify_music(
            action      = args.get("action",      ""),
            query       = args.get("query",       ""),
            uri         = args.get("uri",         ""),
            search_type = args.get("search_type", "track"),
            volume      = vol
        )

    elif tool_name == "run_command":
        cmd = args.get("command", "").strip()
        cls = classify_cmd(cmd)
        if cls == "sudo":
            clean      = re.sub(r"^\s*sudo\s+", "", cmd)
            display    = f"sudo {clean}"
            job        = job_mgr.create(tool_call_id, display, is_sudo=True)
            emit({"type": "sudo_required", "job_id": job.job_id, "command": clean})
            return job
        elif cls == "destructive":
            job = job_mgr.create(tool_call_id, cmd, is_sudo=False)
            emit({
                "type":    "confirm_required",
                "job_id":  job.job_id,
                "command": cmd,
                "reason":  "Este comando puede eliminar o modificar datos de forma irreversible"
            })
            return job
        else:
            # Comandos safe: el QML hace auto-confirm vía confirmRun
            job = job_mgr.create(tool_call_id, cmd, is_sudo=False)
            emit({"type": "run_command", "job_id": job.job_id, "command": cmd})
            return job

    elif tool_name == "manage_tasks":
        try:
            task_id = int(args["task_id"]) if args.get("task_id") is not None else None
        except (ValueError, TypeError):
            task_id = None
        try:
            recurrence_day = int(args["recurrence_day"]) if args.get("recurrence_day") is not None else None
        except (ValueError, TypeError):
            recurrence_day = None
        try:
            recurrence_month = int(args["recurrence_month"]) if args.get("recurrence_month") is not None else None
        except (ValueError, TypeError):
            recurrence_month = None
        return tool_manage_tasks(
            action         = args.get("action", ""),
            description    = args.get("description", ""),
            task_id        = task_id,
            due_date       = args.get("due_date"),
            recurrence     = args.get("recurrence"),
            recurrence_day = recurrence_day,
            recurrence_month = recurrence_month,
        )

    elif tool_name == "capture_screen":
        result = tool_capture_screen(output=args.get("output", ""))
        if isinstance(result, ScreenCapture):
            # Inyectar la imagen en el historial del motor (campo image_b64)
            # Los engines (ollama_engine, gemini_engine) ya saben manejar este campo.
            # Retornamos un dict especial que los engines detectan para hacer el inject.
            return result
        # Si hubo error, result es un str con el mensaje
        return result

    elif tool_name == "hyprland_control":
        try:
            ws = int(args["workspace"]) if args.get("workspace") is not None else None
        except (ValueError, TypeError):
            ws = None
        return tool_hyprland_control(
            action       = args.get("action", ""),
            workspace    = ws,
            window_query = args.get("window_query", "") or None,
        )

    elif tool_name == "check_job_status":
        return tool_check_job_status(job_id=args.get("job_id", ""))

    else:
        return "Herramienta desconocida"
