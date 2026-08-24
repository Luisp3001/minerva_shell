#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Herramientas de sistema para Minerva: búsqueda web, lanzamiento de apps y control de Hyprland."""
import os
import re
import subprocess
import pathlib

from ..core.config import HOME, WEB_SEARCH_AVAILABLE


def tool_web_search(query: str, max_results: int = 5) -> str:
    """Busca en internet usando DuckDuckGo (sin API key)."""
    if not WEB_SEARCH_AVAILABLE:
        return "Error: el módulo 'ddgs' no está instalado en el entorno del plugin."
    max_results = max(1, min(10, int(max_results)))
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(r)
        if not results:
            return f"No se encontraron resultados para: {query}"
        lines = [f"Resultados de búsqueda para: '{query}'\n"]
        for i, r in enumerate(results, 1):
            title   = r.get("title",  "Sin título")
            href    = r.get("href",   "")
            snippet = r.get("body",   r.get("description", "Sin descripción"))
            lines.append(f"[{i}] {title}")
            lines.append(f"    URL: {href}")
            lines.append(f"    {snippet}")
            lines.append("")
        return "\n".join(lines).strip()
    except Exception as e:
        return f"Error al realizar la búsqueda web: {e}"


def tool_launch_app(query: str) -> str:
    """Busca una aplicación por nombre, palabra clave o sinónimo y la abre en segundo plano."""
    query = query.lower().strip()
    synonyms = {
        "navegador": ["firefox", "brave", "chrome", "chromium", "browser", "thorium"],
        "musica":    ["spotify", "youtube", "music"],
        "discord":   ["vesktop", "discord", "webcord", "armcord"],
        "archivos":  ["dolphin", "nautilus", "thunar", "files", "explorador"],
        "terminal":  ["kitty", "alacritty", "konsole", "wezterm"]
    }

    search_terms = [query]
    for key, vals in synonyms.items():
        if key in query:
            search_terms.extend(vals)

    desktop_dirs = [
        "/usr/share/applications",
        os.path.expanduser("~/.local/share/applications"),
        "/var/lib/flatpak/exports/share/applications"
    ]

    best_match = None
    best_score = 0
    best_exec  = None
    best_name  = None

    for d in desktop_dirs:
        if not os.path.isdir(d):
            continue
        for path in pathlib.Path(d).rglob("*.desktop"):
            try:
                content = path.read_text(encoding='utf-8')
                if "NoDisplay=true" in content:
                    continue

                name, exec_cmd, keywords, generic_name = "", "", "", ""
                in_desktop_entry = False
                for line in content.splitlines():
                    line = line.strip()
                    if line == "[Desktop Entry]":
                        in_desktop_entry = True
                        continue
                    elif line.startswith("[") and in_desktop_entry:
                        in_desktop_entry = False

                    if in_desktop_entry:
                        if line.startswith("Name=") and not name:
                            name = line[5:]
                        elif line.startswith("Exec=") and not exec_cmd:
                            exec_cmd = line[5:]
                        elif line.startswith("Keywords="):
                            keywords = line[9:].lower()
                        elif line.startswith("GenericName="):
                            generic_name = line[12:].lower()

                if not exec_cmd or not name:
                    continue

                score        = 0
                name_lower   = name.lower()
                generic_lower = generic_name.lower()

                for term in search_terms:
                    term = term.lower()
                    if not term:
                        continue
                    if term == name_lower:
                        score += 100
                    elif term in name_lower:
                        score += 50
                    elif term in generic_lower:
                        score += 30
                    elif term in keywords:
                        score += 20
                    elif term in path.name.lower():
                        score += 10

                if score > best_score:
                    best_score = score
                    best_match = path
                    best_exec  = exec_cmd
                    best_name  = name

            except Exception:
                continue

    if best_score > 0 and best_exec:
        clean_exec = re.sub(r'%[uUfFdDnNvmick]', '', best_exec).strip()
        try:
            subprocess.Popen(
                ["hyprctl", "dispatch", f"hl.dsp.exec_cmd([[{clean_exec}]])"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return f"Aplicación abierta: {best_name}. IMPORTANTE: Responde brevemente al usuario confirmando que has abierto la aplicación."
        except Exception as e:
            return f"Error abriendo aplicación: {e}. IMPORTANTE: Informa al usuario del error."

    return f"No se encontró ninguna aplicación gráfica para: {query}. IMPORTANTE: Informa al usuario que no la encontraste."


def tool_hyprland_control(action: str, workspace: int | None = None, window_query: str | None = None) -> str:
    """
    Controla Hyprland: navega a un workspace o mueve una ventana entre workspaces.
    Usa la API Lua de Hyprland 0.56 (hyprctl eval / hyprctl dispatch).

    Parámetros:
      action        : 'switch_workspace'  → ir al workspace indicado
                    | 'move_window'       → mover una ventana al workspace indicado
                    | 'list_windows'      → listar ventanas abiertas con su workspace
      workspace     : número de workspace destino (requerido para switch/move)
      window_query  : nombre de clase o título de la ventana a mover (solo para 'move_window')
                      Ejemplos: 'Spotify', 'firefox', 'kitty'
    """
    action = action.strip().lower()

    # ── list_windows ────────────────────────────────────────────────────────
    if action == "list_windows":
        try:
            result = subprocess.run(
                ["hyprctl", "clients", "-j"],
                capture_output=True, text=True, timeout=5
            )
            import json
            clients = json.loads(result.stdout)
            if not clients:
                return "No hay ventanas abiertas en este momento."
            lines = ["Ventanas abiertas:"]
            for c in clients:
                cls   = c.get("class", "desconocida")
                title = c.get("title", "")[:50]
                ws_id = c.get("workspace", {}).get("id", "?")
                lines.append(f"  - {cls} | '{title}' | workspace {ws_id}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error listando ventanas: {e}"

    # ── switch_workspace ────────────────────────────────────────────────────
    if action == "switch_workspace":
        if workspace is None:
            return "Error: debes indicar el número de workspace al que quieres ir."
        try:
            subprocess.run(
                ["hyprctl", "dispatch", f'hl.dsp.focus({{ workspace = "{workspace}" }})'],
                capture_output=True, text=True, timeout=5
            )
            return f"Me moví al workspace {workspace}. IMPORTANTE: Confirma brevemente al usuario."
        except Exception as e:
            return f"Error al cambiar de workspace: {e}"

    # ── move_window ─────────────────────────────────────────────────────────
    if action == "move_window":
        if workspace is None:
            return "Error: debes indicar el workspace de destino."
        if not window_query:
            return "Error: debes indicar el nombre de la ventana (clase o título) que quieres mover."

        # Buscar la ventana en la lista de clientes para encontrar la mejor coincidencia
        try:
            result = subprocess.run(
                ["hyprctl", "clients", "-j"],
                capture_output=True, text=True, timeout=5
            )
            import json
            clients = json.loads(result.stdout)
        except Exception as e:
            return f"Error obteniendo lista de ventanas: {e}"

        query_lower = window_query.lower()
        matched = None
        match_type = None

        for c in clients:
            cls   = c.get("class", "").lower()
            title = c.get("title", "").lower()
            if query_lower in cls:
                matched    = c
                match_type = "class"
                break
            if query_lower in title:
                matched    = c
                match_type = "title"

        if not matched:
            return (
                f"No encontré ninguna ventana que coincida con '{window_query}'.\n"
                "Usa la acción 'list_windows' para ver las ventanas abiertas."
            )

        matched_class = matched.get("class", "")
        matched_title = matched.get("title", "")
        current_ws    = matched.get("workspace", {}).get("id", "?")

        # Construir el identificador para Hyprland
        if match_type == "class":
            window_id = f"class:{matched_class}"
        else:
            window_id = f"title:{matched_title}"

        # Dispatch usando la nueva API Lua 0.56
        dispatch_cmd = f'hl.dsp.window.move({{ workspace = {workspace}, window = "{window_id}" }})'
        try:
            subprocess.run(
                ["hyprctl", "dispatch", dispatch_cmd],
                capture_output=True, text=True, timeout=5
            )
            display_name = matched_class or matched_title
            return (
                f"Moví '{display_name}' del workspace {current_ws} al workspace {workspace}. "
                "IMPORTANTE: Confirma brevemente al usuario."
            )
        except Exception as e:
            return f"Error moviendo la ventana: {e}"

    return f"Acción desconocida: '{action}'. Usa 'switch_workspace', 'move_window' o 'list_windows'."
