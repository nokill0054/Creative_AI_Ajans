import sys
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# Add creative-engine-template to path to import tools
sys.path.insert(0, '.')
from tools import config, airtable, image_gen, video_gen, kie_upload

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)  # Enable CORS for Next.js frontend

@app.route('/')
def index():
    """Main Dashboard UI."""
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "message": "Creative Engine Backend is running"})

@app.route('/api/config', methods=['GET'])
def get_engine_config():
    """Returns available models, styles, and detailed prompt controls."""
    return jsonify({
        "image_models": [
            {"id": "nano-banana-pro", "name": "Nano Banana Pro", "cost": 0.09},
            {"id": "nano-banana", "name": "Nano Banana", "cost": 0.09},
            {"id": "gpt-image-1.5", "name": "GPT Image 1.5", "cost": 0.13}
        ],
        "video_models": ["Veo 3.1", "Kling 3.0", "Sora 2 Pro"],
        "styles": [
            {"id": "photorealistic", "name": "Photorealistic", "desc": "Real-world photography with natural lighting", "prompt": "A photorealistic..."},
            {"id": "cinematic", "name": "Cinematic", "desc": "Movie-quality dramatic scenes", "prompt": "A cinematic film still of..."},
            {"id": "product-shot", "name": "Product Shot", "desc": "Studio quality commercial photography", "prompt": "A high-end product shot..."},
            {"id": "illustration", "name": "Illustration", "desc": "Clean digital art and vector styles", "prompt": "A clean digital illustration..."},
            {"id": "3d-render", "name": "3D Render", "desc": "Octane render, Unreal Engine 5 aesthetic", "prompt": "A highly detailed 3D render..."},
            {"id": "anime", "name": "Anime", "desc": "Studio Ghibli or modern Shonen style", "prompt": "A beautiful anime scene..."},
            {"id": "watercolor", "name": "Watercolor", "desc": "Soft hand-painted artistic style", "prompt": "A delicate watercolor painting..."},
            {"id": "oil-painting", "name": "Oil Painting", "desc": "Rich textures and classical brushwork", "prompt": "A classical oil painting..."}
        ],
        "advanced_controls": {
            "lighting": ["None", "Golden Hour", "Neon-Lit", "Rembrandt", "Soft Box", "Dramatic Chiaroscuro"],
            "camera_angle": ["None", "Eye Level", "Low-Angle Hero", "Bird's Eye", "Dutch Angle", "Over-the-Shoulder", "Top-Down", "Macro Close-up"],
            "lens_type": ["None", "85mm Portrait", "24mm Wide-Angle", "50mm Standard", "135mm Telephoto", "Macro", "Tilt Shift", "Vintage Anamorphic"],
            "composition": ["None", "Rule of Thirds", "Centered Symmetry", "Leading Lines", "Golden Ratio"],
            "atmosphere": ["None", "Moody", "Bright & Cheerful", "Dark & Mysterious", "Ethereal", "Gritty Urban", "Dreamy", "Energetic"],
            "color_palette": ["None", "Earth Tones", "Vibrant Neon", "Monochrome Blue", "Warm Autumn", "Pastel", "Teal & Orange", "B&W High Contrast"],
            "material_texture": ["None", "Glass", "Linen", "Brushed Metal", "Velvet", "Weathered Wood", "Marble", "Crystal", "Silk", "Concrete"]
        },
        "presets": [
            {"id": "desktop-wallpaper", "name": "Desktop Wallpaper"},
            {"id": "phone-wallpaper", "name": "Phone Wallpaper"},
            {"id": "product-photo", "name": "Product Photo"},
            {"id": "logo", "name": "Logo"},
            {"id": "youtube-thumbnail", "name": "YouTube Thumbnail"},
            {"id": "social-media-post", "name": "Social Media Post"},
            {"id": "concept-art", "name": "Concept Art"}
        ]
    })

@app.route('/api/generate-image', methods=['POST'])
def generate_image_endpoint():
    """Creates an Airtable record and triggers image generation with advanced prompt merging."""
    data = request.json
    try:
        product = data.get('product', 'New Product')
        base_prompt = data.get('prompt', '')
        negative_prompt = data.get('negative_prompt', 'blurry, watermark, low quality, deformed')
        model = data.get('model', 'nano-banana-pro')
        
        # Merge advanced parameters into prompt
        lighting = data.get('lighting', 'None')
        camera = data.get('camera_angle', 'None')
        lens = data.get('lens_type', 'None')
        atmosphere = data.get('atmosphere', 'None')
        color_palette = data.get('color_palette', 'None')
        material = data.get('material_texture', 'None')
        
        rich_parts = [base_prompt]
        if lighting != "None": rich_parts.append(f"{lighting} lighting")
        if camera != "None": rich_parts.append(f"{camera} camera angle")
        if lens != "None": rich_parts.append(f"{lens} lens")
        if atmosphere != "None": rich_parts.append(f"{atmosphere} atmosphere")
        if color_palette != "None": rich_parts.append(f"color palette: {color_palette}")
        if material != "None": rich_parts.append(f"material texture: {material}")
        
        final_prompt = ", ".join(rich_parts)
        
        # 1. Get next index
        next_idx = airtable.get_next_index()
        
        # 2. Create the record in Airtable
        record_fields = {
            "Index": next_idx,
            "Ad Name": f"{product} - {final_prompt[:30]}...",
            "Product": product,
            "Image Prompt": final_prompt,
            "Image Model": "Nano Banana Pro" if "nano-banana" in model else "GPT Image 1.5",
            "Image Status": "Pending"
        }
        record = airtable.create_record(record_fields)
        
        # 3. Trigger generation
        results = image_gen.generate_batch([record], model=model)
        
        return jsonify({"status": "success", "results": results, "final_prompt": final_prompt})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Run on port 5052 to avoid conflicts
    app.run(debug=True, port=5052)
