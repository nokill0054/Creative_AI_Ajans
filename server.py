import sys
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# Add creative-engine-template to path to import tools
sys.path.insert(0, '.')
from tools import config, airtable, image_gen, video_gen, kie_upload, prompt_gen

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)


# ============================================================================
#  Airtable Poller — Background Thread
# ============================================================================

class AirtablePoller:
    """Monitors Airtable for Pending records and auto-triggers generation."""

    def __init__(self, interval=30):
        self.interval = interval
        self.running = False
        self.thread = None
        self.last_scan = None
        self.total_processed = 0
        self._stop_event = threading.Event()

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print(f"[POLLER] Started — scanning every {self.interval}s")

    def stop(self):
        self.running = False
        self._stop_event.set()
        print("[POLLER] Stopped")

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def status(self):
        return {
            "running": self.running,
            "interval": self.interval,
            "last_scan": self.last_scan,
            "total_processed": self.total_processed,
        }

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._scan()
            except Exception as e:
                print(f"[POLLER] Scan error: {e}")
            self._stop_event.wait(self.interval)

    def _scan(self):
        self.last_scan = datetime.now().strftime("%H:%M:%S")

        # --- Process Pending Images ---
        try:
            pending_images = airtable.get_pending_images()
            if pending_images:
                print(f"[POLLER] Found {len(pending_images)} pending image(s)")
                for record in pending_images:
                    self._process_image(record)
        except Exception as e:
            print(f"[POLLER] Image scan error: {e}")

        # --- Process Pending Videos ---
        try:
            pending_videos = airtable.get_pending_videos()
            if pending_videos:
                print(f"[POLLER] Found {len(pending_videos)} pending video(s)")
                for record in pending_videos:
                    self._process_video(record)
        except Exception as e:
            print(f"[POLLER] Video scan error: {e}")

    def _process_image(self, record):
        """Process a single pending image record in background."""
        record_id = record["id"]
        fields = record.get("fields", {})
        ad_name = fields.get("Ad Name", "untitled")
        
        if not fields.get("Image Prompt"):
            return  # Skip records without prompt

        print(f"[POLLER] Processing image: {ad_name}")
        
        def run():
            try:
                airtable.update_record(record_id, {"Image Status": "Processing"})
                
                # Resolve model from Airtable field
                model_field = fields.get("Image Model", "")
                model_map = {
                    "Nano Banana": "nano-banana",
                    "Nano Banana Pro": "nano-banana-pro",
                    "GPT Image 1.5": "gpt-image-1.5",
                    "Flux 1.1 Pro": "flux-1.1-pro",
                    "Flux Dev": "flux-dev",
                    "Midjourney v6.1": "midjourney-v6.1",
                    "Recraft V3": "recraft-v3",
                    "DALL-E 3": "dalle-3",
                    "Ideogram v2": "ideogram-v2",
                }
                model = model_map.get(model_field, config.DEFAULT_IMAGE_MODEL)
                
                image_gen.generate_batch([record], model=model, num_variations=1)
                self.total_processed += 1
            except Exception as e:
                print(f"[POLLER] Image gen error for {ad_name}: {e}")
                error_msg = str(e).lower()
                final_status = "Failed - Quota" if ("429" in error_msg or "quota" in error_msg) else "Failed"
                try:
                    airtable.update_record(record_id, {"Image Status": final_status})
                except:
                    pass

        threading.Thread(target=run, daemon=True).start()

    def _process_video(self, record):
        """Process a single pending video record in background."""
        record_id = record["id"]
        fields = record.get("fields", {})
        ad_name = fields.get("Ad Name", "untitled")
        
        if not fields.get("Video Prompt"):
            return
        
        # Video needs a source image
        has_image = fields.get("Generated Image 1") or fields.get("Generated Image 2")
        if not has_image:
            print(f"[POLLER] Skipping video for {ad_name} — no generated image yet")
            return

        print(f"[POLLER] Processing video: {ad_name}")
        
        def run():
            try:
                airtable.update_record(record_id, {"Video Status": "Processing"})
                
                model_field = fields.get("Video Model", "")
                model_map = {
                    "Kling 3.0": "kling-3.0",
                    "Sora 2 Pro": "sora-2-pro",
                    "Sora 2": "sora-2",
                    "Veo 3.1": "veo-3.1",
                }
                model = model_map.get(model_field, config.DEFAULT_VIDEO_MODEL)
                
                video_gen.generate_for_record(record, model=model, num_variations=1)
                self.total_processed += 1
            except Exception as e:
                print(f"[POLLER] Video gen error for {ad_name}: {e}")
                error_msg = str(e).lower()
                final_status = "Failed - Quota" if ("429" in error_msg or "quota" in error_msg) else "Failed"
                try:
                    airtable.update_record(record_id, {"Video Status": final_status})
                except:
                    pass

        threading.Thread(target=run, daemon=True).start()


# Global poller instance
poller = AirtablePoller(interval=30)


# ============================================================================
#  Routes
# ============================================================================

@app.route('/')
def index():
    """Main Dashboard UI."""
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "message": "Creative Engine Backend is running"})


# --- Config ---

@app.route('/api/config', methods=['GET'])
def get_engine_config():
    """Returns available models, styles, and detailed prompt controls."""
    return jsonify({
        "image_models": [
            {"id": "flux-1.1-pro", "name": "Flux 1.1 Pro (Kie)", "cost": 0.05},
            {"id": "flux-dev", "name": "Flux Dev (Kie)", "cost": 0.03},
            {"id": "midjourney-v6.1", "name": "Midjourney v6.1 (Kie)", "cost": 0.15},
            {"id": "recraft-v3", "name": "Recraft V3 (Kie)", "cost": 0.08},
            {"id": "dalle-3", "name": "DALL-E 3 (Kie)", "cost": 0.12},
            {"id": "ideogram-v2", "name": "Ideogram v2 (Kie)", "cost": 0.10},
            {"id": "nano-banana-pro", "name": "Nano Banana Pro (Google)", "cost": 0.09},
            {"id": "nano-banana", "name": "Nano Banana (Google)", "cost": 0.09},
            {"id": "gpt-image-1.5", "name": "GPT Image 1.5 (OpenAI)", "cost": 0.13}
        ],
        "video_models": ["Veo 3.1", "Kling 3.0", "Sora 2 Pro"],
        "video_models_detail": [
            {"id": "veo-3.1", "name": "Veo 3.1 (Google)", "cost": 0.50},
            {"id": "kling-3.0", "name": "Kling 3.0 (WaveSpeed)", "cost": 0.30},
            {"id": "sora-2-pro", "name": "Sora 2 Pro (WaveSpeed)", "cost": 0.30},
        ],
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
        "advanced_controls_groups": [
            {
                "title": "Cinematography (Camera)",
                "icon": "video",
                "controls": {
                    "camera_gear": ["None", "Arri Alexa LF", "Red V-Raptor XL", "Sony A7S III", "GoPro Hero 12 (Action)", "iPhone 15 Pro Max (Log)"],
                    "camera_angle": ["None", "Eye Level", "Low-Angle Hero", "Bird's Eye", "Dutch Angle", "Over-the-Shoulder", "Macro Close-up"],
                    "lens_type": ["None", "85mm Portrait", "24mm Wide-Angle", "50mm Standard", "135mm Telephoto", "Tilt Shift", "Vintage Anamorphic"],
                    "camera_motion": ["None", "Static", "Dolly In", "Dolly Out", "Pan Left", "Pan Right", "Tilt Up", "Tilt Down", "Orbital 360", "Crane Shot", "Bullet Time", "Handheld Realism", "FPV Drone", "Crash Zoom"]
                }
            },
            {
                "title": "Production (Motion & Directing)",
                "icon": "clapperboard",
                "controls": {
                    "motion_intensity": ["Steady", "Cinematic Slow", "Rapid Kinetic", "High-Energy Chaotic", "Still Life"],
                    "actor_action": ["None", "Looking at Camera", "Walking towards lens", "Holding product with both hands", "Smiling naturally", "Genuine surprise", "Professional presentation"],
                    "post_processing": ["None", "Film Grain (Heavy)", "Anamorphic Lens Flare", "8k Resolution Enhancement", "Motion Blur", "Light Leaks", "Chromatic Aberration"]
                }
            },
            {
                "title": "Atmosphere (Vibe)",
                "icon": "cloud-sun",
                "controls": {
                    "lighting_dynamics": ["None", "Volumetric Fog", "God Rays", "Global Illumination", "Ray-Traced Shadows", "Rim Lighting (Magenta)", "Neon Glow", "Studio Soft-Box"],
                    "weather_atmosphere": ["None", "Heavy Mist", "Thunderstorm", "Golden Dusk", "Studio High-Key", "Cyberpunk Rain", "Snow Dust", "Windy Particles"],
                    "color_grading": ["None", "Kodak Portra 400", "Teal & Orange", "Fujifilm Velvia", "High Contrast B&W", "Agfa Vista 200", "Vintage 70s Film", "Bleach Bypass"]
                }
            },
            {
                "title": "Aesthetics (Detail)",
                "icon": "layers",
                "controls": {
                    "composition": ["None", "Rule of Thirds", "Centered Symmetry", "Leading Lines", "Golden Ratio", "Minimalist Empty Space"],
                    "physical_textures": ["None", "Micro-Pores & Skin Details", "Fine-Woven Fabric", "Brushed Metal", "Reflective Mirror Chrome", "Weathered Wood", "Translucent Marble", "High-Consistency Glass"],
                    "material_resonance": ["None", "Matte", "Glossy", "Metallic", "Subsurface Scattering", "Fluorescent Glow", "Organic Growth"]
                }
            }
        ],
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


# --- Prompt Enhancement ---

@app.route('/api/enhance-prompt', methods=['POST'])
def enhance_prompt_endpoint():
    """Takes base prompt + sidebar params and returns a cinematic expansion."""
    data = request.json
    try:
        result = prompt_gen.enhance_prompt(data)
        if result["status"] == "success":
            return jsonify({"enhanced_prompt": result["prompt"]})
        else:
            return jsonify({
                "enhanced_prompt": data.get('prompt', 'Product Shot'),
                "error": result["message"],
                "is_fallback": True,
                "error_type": result.get("type", "general")
            })
    except Exception as e:
        return jsonify({
            "error": str(e), 
            "enhanced_prompt": data.get('prompt', 'Product Shot'),
            "is_fallback": True
        })


# --- Unified Production Endpoint ---

MODEL_DISPLAY_NAMES = {
    "nano-banana": "Nano Banana",
    "nano-banana-pro": "Nano Banana Pro",
    "gpt-image-1.5": "GPT Image 1.5",
    "flux-1.1-pro": "Flux 1.1 Pro",
    "flux-dev": "Flux Dev",
    "midjourney-v6.1": "Midjourney v6.1",
    "recraft-v3": "Recraft V3",
    "dalle-3": "DALL-E 3",
    "ideogram-v2": "Ideogram v2",
}

VIDEO_MODEL_DISPLAY_NAMES = {
    "veo-3.1": "Veo 3.1",
    "kling-3.0": "Kling 3.0",
    "sora-2-pro": "Sora 2 Pro",
    "sora-2": "Sora 2",
}


def _build_rich_prompt(base_prompt, data):
    """Merge base prompt with advanced parameters."""
    params = {
        "gear": data.get('camera_gear', 'None'),
        "lighting": data.get('lighting_dynamics', 'None'),
        "weather": data.get('weather_atmosphere', 'None'),
        "grading": data.get('color_grading', 'None'),
        "post": data.get('post_processing', 'None'),
        "angle": data.get('camera_angle', 'None'),
        "lens": data.get('lens_type', 'None'),
        "comp": data.get('composition', 'None'),
        "motion": data.get('camera_motion', 'None'),
        "intensity": data.get('motion_intensity', 'None'),
        "action": data.get('actor_action', 'None'),
        "phys_tex": data.get('physical_textures', 'None'),
        "resonance": data.get('material_resonance', 'None')
    }
    
    rich_parts = [base_prompt]
    for key, val in params.items():
        if val and val != "None":
            if key == "gear": rich_parts.append(f"shot on {val}")
            elif key == "grading": rich_parts.append(f"color graded with {val}")
            elif key == "phys_tex": rich_parts.append(f"texture: {val}")
            elif key == "motion": rich_parts.append(f"camera motion: {val}")
            elif key == "action": rich_parts.append(f"subject: {val}")
            else: rich_parts.append(val)
    
    return ", ".join(rich_parts)


@app.route('/api/produce', methods=['POST'])
def produce_endpoint():
    """
    Unified production endpoint.
    mode: "image" | "video" | "image+video"
    """
    is_form = request.content_type and request.content_type.startswith('multipart/form-data')
    if is_form:
        data = request.form.to_dict()
    else:
        data = request.json or {}
        
    mode = data.get('mode', 'image')  # image | video | image+video
    
    try:
        product = data.get('product', 'New Product')
        base_prompt = data.get('prompt', '')
        video_prompt = data.get('video_prompt', '')
        model = data.get('model', 'nano-banana-pro')
        video_model = data.get('video_model', 'veo-3.1')
        provider = data.get('provider', None)
        video_duration = data.get('video_duration', '5')
        video_quality = data.get('video_quality', 'pro')
        
        # Build enriched prompt
        final_prompt = _build_rich_prompt(base_prompt, data) if base_prompt else ''
        
        # Get next index
        next_idx = airtable.get_next_index()
        
        # Build Airtable record fields
        record_fields = {
            "Index": next_idx,
            "Ad Name": f"{product} - {mode.replace('+', ' + ').title()} Production",
            "Product": product,
        }
        
        # Image fields
        if mode in ('image', 'image+video'):
            record_fields["Image Prompt"] = final_prompt
            record_fields["Image Model"] = MODEL_DISPLAY_NAMES.get(model, model)
            record_fields["Image Status"] = "Pending"
        
        # Video fields
        if mode in ('video', 'image+video'):
            record_fields["Video Prompt"] = video_prompt or final_prompt
            record_fields["Video Model"] = VIDEO_MODEL_DISPLAY_NAMES.get(video_model, video_model)
            record_fields["Video Status"] = "Pending"
        
        # Create the Airtable record
        record = airtable.create_record(record_fields)
        record_id = record["id"]
        
        # Handle uploaded files
        local_paths = None
        source_image_url = None
        if is_form and request.files:
            file_list = request.files.getlist('reference_files')
            if file_list:
                import os
                from pathlib import Path
                from werkzeug.utils import secure_filename
                
                temp_dir = Path('/tmp/creative_engine_uploads')
                temp_dir.mkdir(parents=True, exist_ok=True)
                local_paths = []
                for f in file_list:
                    if f.filename:
                        p = temp_dir / secure_filename(f.filename)
                        f.save(str(p))
                        local_paths.append(str(p))
                
                if local_paths and mode in ('video', 'image+video'):
                    try:
                        # Upload to Kie AI to get public URLs for the video generator as reference
                        uploaded_urls = kie_upload.upload_references(local_paths)
                        if uploaded_urls:
                            source_image_url = uploaded_urls[0]
                    except Exception as e:
                        print(f"File upload error: {e}")
        
        # --- Background Generation ---
        def run_production():
            try:
                if mode == 'image':
                    _run_image_gen(record, model, provider, reference_paths=local_paths)
                    
                elif mode == 'video':
                    _run_video_gen(record, video_model, provider, video_duration, video_quality, source_image_url=source_image_url)
                    
                elif mode == 'image+video':
                    # Step 1: Generate image
                    _run_image_gen(record, model, provider, reference_paths=local_paths)
                    
                    # Step 2: Re-fetch record to get generated image URL
                    time.sleep(2)
                    updated_records = airtable.get_records(f'RECORD_ID() = "{record_id}"')
                    if updated_records:
                        updated_record = updated_records[0]
                        img_status = updated_record.get("fields", {}).get("Image Status", "")
                        if img_status == "Generated":
                            _run_video_gen(updated_record, video_model, provider, video_duration, video_quality)
                        else:
                            # Image failed, mark video as failed too
                            airtable.update_record(record_id, {"Video Status": "Failed"})
                    else:
                        airtable.update_record(record_id, {"Video Status": "Failed"})
                        
            except Exception as e:
                print(f"Production error: {e}")
        
        threading.Thread(target=run_production, daemon=True).start()
        
        return jsonify({
            "status": "success",
            "record_id": record_id,
            "mode": mode,
            "final_prompt": final_prompt,
            "message": f"{mode} production started in cloud."
        })
        
    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({"error": str(e)}), 500


def _run_image_gen(record, model, provider, reference_paths=None):
    """Run image generation for a record."""
    record_id = record["id"]
    try:
        airtable.update_record(record_id, {"Image Status": "Processing"})
        image_gen.generate_batch([record], model=model, provider=provider, num_variations=1, reference_paths=reference_paths)
    except Exception as e:
        print(f"Image generation error: {e}")
        error_msg = str(e).lower()
        final_status = "Failed - Quota" if ("429" in error_msg or "quota" in error_msg) else "Failed"
        airtable.update_record(record_id, {"Image Status": final_status})


def _run_video_gen(record, video_model, provider, duration="5", quality="pro", source_image_url=None):
    """Run video generation for a record."""
    record_id = record["id"]
    try:
        airtable.update_record(record_id, {"Video Status": "Processing"})
        video_gen.generate_for_record(
            record, model=video_model, duration=duration,
            num_variations=1, mode=quality, source_image_url=source_image_url,
            provider=provider
        )
    except Exception as e:
        print(f"Video generation error: {e}")
        error_msg = str(e).lower()
        final_status = "Failed - Quota" if ("429" in error_msg or "quota" in error_msg) else "Failed"
        airtable.update_record(record_id, {"Video Status": final_status})


# --- Record Status (for UI polling) ---

@app.route('/api/record-status/<record_id>', methods=['GET'])
def record_status(record_id):
    """Get current status and generated URLs for a record."""
    try:
        url = f"{airtable._table_url()}/{record_id}"
        import requests as req
        resp = req.get(url, headers=airtable._headers())
        if resp.status_code != 200:
            return jsonify({"error": "Record not found"}), 404
        
        fields = resp.json().get("fields", {})
        
        result = {
            "image_status": fields.get("Image Status"),
            "video_status": fields.get("Video Status"),
            "image_url": None,
            "video_url": None,
        }
        
        # Get image URL
        img1 = fields.get("Generated Image 1", [])
        if img1:
            result["image_url"] = img1[0].get("url")
        
        # Get video URL
        vid1 = fields.get("Generated Video 1", [])
        if vid1:
            result["video_url"] = vid1[0].get("url")
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Legacy endpoint (backward compat) ---

@app.route('/api/generate-image', methods=['POST'])
def generate_image_endpoint():
    """Legacy endpoint — redirects to unified produce."""
    data = request.json
    data['mode'] = 'image'
    # Forward to produce
    with app.test_request_context('/api/produce', method='POST', json=data):
        return produce_endpoint()


# --- Poller Control ---

@app.route('/api/poller/status', methods=['GET'])
def poller_status():
    return jsonify(poller.status())

@app.route('/api/poller/toggle', methods=['POST'])
def poller_toggle():
    poller.toggle()
    return jsonify(poller.status())


# ============================================================================
#  Main
# ============================================================================

if __name__ == '__main__':
    # Poller starts PAUSED — activate via UI toggle or POST /api/poller/toggle
    # This prevents auto-processing all existing Pending records on server boot.
    print("[POLLER] Initialized — paused. Use UI toggle or /api/poller/toggle to start.")
    # Run on port 5056 to avoid conflicts
    app.run(debug=True, port=5056, use_reloader=False)
