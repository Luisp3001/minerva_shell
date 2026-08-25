#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Herramienta de memoria a largo plazo para Minerva.
Actualiza secciones específicas en user_profile.md y preferences.md.
"""
from ..core.memory import update_memory_section


def tool_update_memory(file_key: str, section: str, content: str) -> str:
    """Actualiza una sección de la memoria permanente de Minerva.

    Args:
        file_key: Archivo de destino: 'profile' (datos del usuario) o 'preferences' (preferencias).
        section:  Nombre de la sección a crear o actualizar (ej: 'Lenguajes de Programación').
        content:  Información a guardar en esa sección. Puede ser texto libre o una lista con guiones.
    """
    return update_memory_section(file_key, section, content)
