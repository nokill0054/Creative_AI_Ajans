"""
Expert Prompt Generator for Creative Content Engine.
Uses Gemini LLM to expand simple user input into professional cinematic prompts.
"""

import google.generativeai as genai
from google.api_core import exceptions
from . import config

# Configure Gemini
genai.configure(api_key=config.GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

def enhance_prompt(data):
    """
    Takes base prompt and technical parameters to generate a hyper-descriptive cinematic prompt.
    """
    base_prompt = data.get('prompt', '')
    if not base_prompt:
        return "Please enter a base description first."

    # Technical params for context
    params = {
        "gear": data.get('camera_gear', 'None'),
        "lighting": data.get('lighting_dynamics', 'None'),
        "weather": data.get('weather_atmosphere', 'None'),
        "grading": data.get('color_grading', 'None'),
        "angle": data.get('camera_angle', 'None'),
        "lens": data.get('lens_type', 'None'),
        "comp": data.get('composition', 'None'),
        "motion": data.get('camera_motion', 'None'),
        "intensity": data.get('motion_intensity', 'None'),
        "action": data.get('actor_action', 'None'),
        "phys_tex": data.get('physical_textures', 'None'),
        "resonance": data.get('material_resonance', 'None'),
        "post": data.get('post_processing', 'None')
    }

    # Build the Art Director instructions
    instructions = f"""
    You are a world-class AI Prompt Engineer and Cinematic Art Director. 
    Your mission is to take a simple 'Base Idea' and transform it into a hyper-descriptive, 
    professional cinematic prompt for high-end AI image and video generation (Higgsfield-style).

    Base Idea: "{base_prompt}"

    Technical Requirements to incorporate naturally:
    - Cinematography: {params['gear']}, {params['angle']}, {params['lens']}
    - Motion Profile: {params['motion']} ({params['intensity']})
    - Subject/Actor: {params['action']}
    - Environmental Detail: {params['lighting']}, {params['weather']}
    - Aesthetic & Textures: {params['phys_tex']}, {params['resonance']}, {params['comp']}
    - Post-Processing: {params['grading']}, {params['post']}

    Guidelines:
    1. Focus on sensory micro-details, hyper-realistic textures (pores, individual fabric threads, refractive light), and high-fidelity lighting.
    2. Use professional cinematography and VFX terminology (e.g., subsurface scattering, chromatic aberration, volumetric dust motes).
    3. Ensure the camera movement and subject motion are central to the descriptive flow.
    4. The tone should be sophisticated, evocative, and technically precise (~75-125 words).
    5. OUTPUT ONLY the final enhanced prompt text. Do not include any intro or outro.
    """

    try:
        response = model.generate_content(instructions)
        return {"status": "success", "prompt": response.text.strip()}
    except exceptions.ResourceExhausted:
        return {"status": "error", "type": "quota", "message": "Gemini quota exceeded. Using fallback."}
    except Exception as e:
        return {"status": "error", "type": "general", "message": str(e)}
