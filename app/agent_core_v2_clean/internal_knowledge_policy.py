from __future__ import annotations
PROMPT_POLICY_VERSION='internal_applicability_v1'
CONTEXT_APPLICABILITY_POLICY='''Incluye únicamente mecanismos directamente relacionados con la tarea consultada y sustentados por el contexto operativo. Considera administración local, directorios corporativos, sincronización de atributos, autoservicio o autenticación en dispositivo solo si la pregunta trata sobre identidad, acceso, usuarios, credenciales o autenticación. Para firmware, red, colas, monitoreo, instalación u otras tareas, usa controles y verificaciones propios de esa operación. No rellenes la respuesta con mecanismos ajenos al objetivo.'''

def apply_context_policy(system_prompt:str)->str:
    value=str(system_prompt or '').rstrip()
    return f'{value}\n\nPOLITICA DE APLICABILIDAD CONTEXTUAL:\n{CONTEXT_APPLICABILITY_POLICY}'
