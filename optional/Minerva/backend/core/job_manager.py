#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Job Manager para comandos asíncronos de Minerva.

Proporciona:
  - CommandJob  → representa un comando en ejecución con su estado y metadatos.
  - JobManager  → registro global thread-safe de jobs. Coordina la re-entrada
                  al LLM cuando todos los comandos de un turno han terminado.
  - job_mgr     → instancia singleton global.

Estados de un job:
  queued → running → completed
                   ╰→ failed
         ╰→ cancelled  (usuario rechazó antes de ejecutar)
"""
import threading
import uuid


class CommandJob:
    """Representa un comando único emitido por el LLM."""

    __slots__ = (
        "job_id",
        "tool_call_id",
        "command",
        "is_sudo",
        "status",
        "output",
        "returncode",
    )

    def __init__(self, job_id: str, tool_call_id: str, command: str, is_sudo: bool):
        self.job_id       = job_id        # ID único del job (UUID corto)
        self.tool_call_id = tool_call_id  # ID del tool_call del LLM (para el historial)
        self.command      = command       # display_cmd ("sudo pacman -Ss ...")
        self.is_sudo      = is_sudo
        self.status       = "queued"      # queued | running | completed | failed | cancelled
        self.output       = ""
        self.returncode   = -1

    @property
    def is_terminal(self) -> bool:
        """True si el job está en un estado final (no puede cambiar más)."""
        return self.status in ("completed", "failed", "cancelled")

    def __repr__(self) -> str:
        return f"<CommandJob {self.job_id} [{self.status}] cmd={self.command!r}>"


class JobManager:
    """
    Registro global thread-safe de CommandJobs.

    También gestiona el concepto de 'turno': el conjunto de jobs que el LLM
    emitió en una sola respuesta. Cuando todos terminan, el engine puede
    retomar el chat con todos los resultados.
    """

    def __init__(self) -> None:
        self._jobs: dict         = {}
        self._turn_job_ids: list = []
        self._lock               = threading.Lock()

    # ── Creación ─────────────────────────────────────────────────────────────

    def create(self, tool_call_id: str, command: str, is_sudo: bool) -> CommandJob:
        """Crea y registra un nuevo job. Retorna el objeto CommandJob."""
        job_id = uuid.uuid4().hex[:8]
        job    = CommandJob(job_id, tool_call_id, command, is_sudo)
        with self._lock:
            self._jobs[job_id] = job
        return job

    # ── Consulta ─────────────────────────────────────────────────────────────

    def get(self, job_id: str):
        with self._lock:
            return self._jobs.get(job_id)

    # ── Mutación de estado ───────────────────────────────────────────────────

    def update_status(self, job_id: str, status: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].status = status

    def append_output(self, job_id: str, text: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].output += text

    def set_result(self, job_id: str, output: str, returncode: int, success: bool) -> None:
        """Actualiza output, returncode y status al terminar la ejecución."""
        with self._lock:
            if job_id in self._jobs:
                job            = self._jobs[job_id]
                job.output     = output
                job.returncode = returncode
                job.status     = "completed" if success else "failed"

    def cancel(self, job_id: str) -> None:
        """Marca un job como cancelado por el usuario."""
        with self._lock:
            if job_id in self._jobs and not self._jobs[job_id].is_terminal:
                self._jobs[job_id].status = "cancelled"

    # ── Gestión de turno ─────────────────────────────────────────────────────

    def start_turn(self, job_ids: list) -> None:
        """
        Registra los job_ids del turno actual del LLM.
        Llamar desde el engine después de despachar todos los tool calls.
        """
        with self._lock:
            self._turn_job_ids = list(job_ids)

    def get_turn_job_ids(self) -> list:
        with self._lock:
            return list(self._turn_job_ids)

    def is_turn_job(self, job_id: str) -> bool:
        """True si job_id pertenece al turno activo actual."""
        with self._lock:
            return job_id in self._turn_job_ids

    def all_turn_finished(self) -> bool:
        """True cuando todos los jobs del turno actual están en estado terminal."""
        with self._lock:
            for jid in self._turn_job_ids:
                job = self._jobs.get(jid)
                if job and not job.is_terminal:
                    return False
        return True

    def clear_turn(self) -> None:
        """Limpia el turno actual y elimina sus jobs del registro (usar solo cuando ya completaron)."""
        with self._lock:
            for jid in self._turn_job_ids:
                self._jobs.pop(jid, None)
            self._turn_job_ids = []

    def detach_turn(self) -> None:
        """
        Desacopla el turno activo sin borrar los jobs del registro.

        Usar cuando el usuario empieza una nueva conversación mientras hay jobs
        pendientes: los jobs quedan vivos en _jobs (accesibles via check_job_status
        y _internal_cmd_done), pero ya no pertenecen al turno activo, por lo que
        no dispararán una re-invocación del LLM al completar.
        """
        with self._lock:
            self._turn_job_ids = []

    # ── Inspección ───────────────────────────────────────────────────────────

    def get_all_jobs(self) -> list:
        """
        Devuelve una lista de snapshots (dicts) de todos los jobs registrados.
        Útil para que la herramienta check_job_status muestre el estado al LLM.
        """
        with self._lock:
            return [
                {
                    "job_id":     job.job_id,
                    "command":    job.command,
                    "status":     job.status,
                    "returncode": job.returncode,
                    "output":     job.output[:1024] if job.output else "",  # truncar para el prompt
                    "in_turn":    job.job_id in self._turn_job_ids,
                }
                for job in self._jobs.values()
            ]


# ── Singleton global ──────────────────────────────────────────────────────────
job_mgr = JobManager()
