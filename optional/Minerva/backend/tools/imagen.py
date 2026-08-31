import os
import re
import datetime

def tool_generate_image(prompt: str, resolution: str = "1K", api_key: str = "") -> str:
    HOME = os.path.expanduser("~")
    
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return "Error: la librería 'google-genai' no está instalada. Ejecuta 'pip install google-genai'."
        
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        
    if not api_key:
        return "Error: no hay API Key de Gemini configurada. Por favor configúrala en los ajustes."
        
    client = genai.Client(api_key=api_key)
    
    try:
        interaction = client.interactions.create(
            model="gemini-3.1-flash-image",
            input=prompt,
            response_format={
                "type": "image",
                "mime_type": "image/jpeg",
                "aspect_ratio": "1:1",
                "image_size": resolution
            },
        )
    except Exception as e:
        return f"Error al generar la imagen con interactions.create: {e}"
            
    image_bytes = None
    
    try:
        import base64
        if hasattr(interaction, 'output_image') and hasattr(interaction.output_image, 'data'):
            image_bytes = base64.b64decode(interaction.output_image.data)
        else:
            return "Error: el objeto de respuesta no contiene 'output_image.data'."
    except Exception as e:
        return f"Error al decodificar la imagen: {e}"
                
    if not image_bytes:
        return f"Error: la imagen devuelta está vacía."
    
    pic_dir = os.path.join(HOME, "Pictures", "minerva")
    os.makedirs(pic_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"gen_{timestamp}.jpg"
    filepath = os.path.join(pic_dir, filename)
    
    try:
        with open(filepath, "wb") as f:
            f.write(image_bytes)
    except Exception as e:
        return f"Error al guardar la imagen en disco: {e}"
        
    if resolution == "2K":
        # 2K is just saved directly without displaying, per the user's earlier requirement.
        return f"Imagen 2K generada exitosamente y guardada en {filepath}"
    else:
        return f"![Imagen Generada]({filepath})"