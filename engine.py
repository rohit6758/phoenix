from flask import Flask, request, jsonify, render_template_string, redirect
import time
import json
from cyber_vault import encrypt_code # Ensuring security for reports

app = Flask(__name__)

# Mock Database for Void Hub Analysis History
analysis_history = []


# --- MODULAR ANALYSIS FUNCTIONS ---

def auto_tag(data):
    """Auto-tags the asset dynamically based on the inputs found in the blueprint."""
    tags = []
    if 'base_damage' in data or 'fire_rate' in data:
        tags.append('Weapon')
    if 'max_speed' in data or 'speed' in data or 'boat' in str(data.get('asset_name', '')).lower():
        tags.append('Vehicle')
    if 'animation_count' in data:
        tags.append('Character/Animal')
    if 'poly_count' in data:
        tags.append('3D Model')
    if data.get('is_vr_ready'):
        tags.append('VR Ready')
    return tags if tags else ['Generic Asset']

def analyze_geometry(data, context):
    poly_count = data.get('poly_count')
    if poly_count is not None and isinstance(poly_count, (int, float)):
        # Weighted scoring: vehicles and characters tolerate higher polycounts than static models
        weight = 0.5 if 'Vehicle' in context['tags'] or 'Character/Animal' in context['tags'] else 1.0
        
        if poly_count > 50000:
            context['score'] -= (20 * weight)
            context['alerts'].append(f"Very high poly count ({poly_count}). Consider heavy LOD optimization.")
        elif poly_count > 15000:
            context['score'] -= (10 * weight)
            context['alerts'].append(f"Moderate poly count ({poly_count}). LODs recommended for scalability.")
        else:
            context['recommendations'].append("✔ Low poly count, highly optimized for all devices.")

def analyze_combat(data, context):
    base_damage = data.get('base_damage')
    fire_rate = data.get('fire_rate')
    if base_damage is not None and fire_rate is not None:
        try:
            dps = round(float(base_damage) * float(fire_rate), 1)
            context['stats']['Calculated DPS'] = dps # Auto-inject computed stat
            weight = 1.5 if 'Weapon' in context['tags'] else 1.0 # Extra penalty weight for dedicated weapons
            
            if dps > 300:
                context['score'] -= (15 * weight)
                context['alerts'].append(f"High DPS ({dps}) might unbalance standard gameplay. Test thoroughly.")
            elif dps < 50:
                context['recommendations'].append(f"Low DPS ({dps}). Great fit for utility or starter gear.")
        except ValueError:
            pass

def analyze_physics(data, context):
    speed = data.get('max_speed') or data.get('speed')
    if speed is not None and isinstance(speed, (int, float)):
        weight = 1.2 if 'Vehicle' in context['tags'] else 1.0
        if speed > 250:
            context['score'] -= (10 * weight)
            context['alerts'].append(f"High speed ({speed}) may cause collision/physics clipping in engine. Enable sub-stepping.")
        else:
            context['recommendations'].append(f"✔ Speed ({speed}) is well within stable physics bounds.")

def analyze_performance(data, context):
    texture_mem = data.get('texture_memory_mb')
    if texture_mem is not None and isinstance(texture_mem, (int, float)):
        if texture_mem > 1024:
            context['score'] -= 15
            context['alerts'].append(f"High texture memory footprint ({texture_mem}MB). Evaluate texture streaming and compression.")
        else:
            context['recommendations'].append("✔ Texture memory is well optimized.")
            
    is_vr_ready = data.get('is_vr_ready')
    if is_vr_ready is False:
        context['alerts'].append("VR Unsafe: Asset is not flagged as VR ready. May cause performance drops or frame-pacing issues.")
        
    node_count = data.get('blueprint_nodes_count')
    if node_count is not None and isinstance(node_count, int) and node_count > 500:
        context['score'] -= 10
        context['alerts'].append(f"Heavy blueprint logic detected ({node_count} nodes). Consider moving heavy ticks to C++.")

def analyze_compatibility(data, context):
    ue_version = data.get('ue_version')
    if ue_version:
        if not str(ue_version).startswith('5.'):
            context['alerts'].append(f"Legacy Unreal Engine version detected ({ue_version}). Recommend updating to UE5 format.")
        else:
            context['recommendations'].append(f"✔ Native UE5 Compatibility verified ({ue_version}).")
            
    plugins = data.get('required_plugins', [])
    if plugins:
        context['alerts'].append(f"Requires external plugins: {', '.join(plugins)}. Ensure dependencies are documented.")

def analyze_packaging(data, context):
    missing_files = data.get('missing_files', [])
    if missing_files:
        context['score'] -= 30
        context['alerts'].append(f"CRITICAL: {len(missing_files)} broken references or missing files detected. Asset may fail to load.")

def analyze_blueprint(data):
    """
    Phoenix Logic: Modular backend analyzing blueprint data automatically via inputs.
    """
    asset_name = data.get('asset_name', 'Unnamed Asset')
    
    # 1. Auto-tagging (Analyzer behavior)
    tags = auto_tag(data)
    
    context = {
        'tags': tags,
        'score': 100.0,
        'alerts': [],
        'recommendations': [],
        'stats': {}
    }

    # Clean up display stats
    for key, value in data.items():
        if key not in ['asset_name', 'asset_type']:
            display_key = key.replace('_', ' ').title()
            context['stats'][display_key] = value
            
    # 2. Modular Analysis Routing
    analyze_geometry(data, context)
    analyze_combat(data, context)
    analyze_physics(data, context)
    analyze_performance(data, context)
    analyze_compatibility(data, context)
    analyze_packaging(data, context)

    animations = data.get('animation_count')
    if animations is not None and isinstance(animations, int):
        if animations < 5:
            context['alerts'].append(f"Low animation count ({animations}). Movement and transitions may feel rigid.")
        else:
            context['recommendations'].append(f"✔ Generous animation pool ({animations}) for smooth blending.")

    # 3. Dynamic Skill Level Check
    skill_level = "Beginner Friendly"
    if len(context['alerts']) >= 2 or context['score'] <= 80:
        skill_level = "Intermediate Setup"
    if len(context['alerts']) >= 4 or context['score'] <= 50:
        skill_level = "Advanced Integration"
        
    # 4. Void Hub Security Validation
    secure_signature = "Encryption Disabled"
    try:
        stat_string = json.dumps(context['stats'], sort_keys=True)
        secure_signature = encrypt_code(stat_string)
    except Exception:
        pass

    report = {
        "asset_name": asset_name,
        "asset_type": ", ".join(tags),
        "stats": context['stats'],
        "optimization_score": max(0, int(context['score'])),
        "alerts": context['alerts'],
        "recommendations": context['recommendations'],
        "skill_level": skill_level,
        "secure_signature": secure_signature
    }
    return report

@app.route('/analyze-asset', methods=['POST'])
def analyze_asset():
    data = None
    is_ui_upload = False

    # Route 1: File Validation (Blueprint scan directly from the web panel)
    if 'file' in request.files:
        is_ui_upload = True
        file = request.files['file']
        if file.filename == '' or not file.filename.endswith('.json'):
            return jsonify({"error": "Invalid file type. Please upload a .json blueprint."}), 400
        try:
            data = json.load(file)
        except Exception as e:
            return jsonify({"error": f"Failed to parse JSON file: {str(e)}"}), 400
            
    # Route 2: Raw JSON API body
    elif request.is_json:
        data = request.get_json()
        
    if not data:
        return jsonify({"error": "No valid blueprint data provided."}), 400
    
    report = analyze_blueprint(data)
    
    entry = {
        "id": len(analysis_history),
        "asset": report['asset_name'],
        "report": report,
        "raw_data": data,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    analysis_history.append(entry)
    
    # If imported from the panel UI, redirect smoothly back rather than raw text dump
    if is_ui_upload:
        return redirect('/')
    
    return jsonify({
        "status": "Phoenix Analysis Complete",
        "void_hub_report": report
    })

@app.route('/api/simulate', methods=['POST'])
def api_simulate():
    """Real-time simulation endpoint that recalculates stats based on user overrides."""
    req = request.get_json()
    asset_id = req.get('id')
    overrides = req.get('overrides', {})
    
    if asset_id is None or asset_id >= len(analysis_history):
        return jsonify({"error": "Asset not found"}), 404
        
    # Start with the original blueprint data
    simulated_data = analysis_history[asset_id]['raw_data'].copy()
    
    # Apply user tweaks dynamically
    for key, value in overrides.items():
        if key in simulated_data:
            simulated_data[key] = type(simulated_data[key])(value) if value != "" else 0
            
    new_report = analyze_blueprint(simulated_data)
    return jsonify(new_report)

# --- DASHBOARD UI TEMPLATE ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phoenix Analysis Panel</title>
    <style>
        body { background: #0D1117; color: #C9D1D9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; margin: 0; }
        h1 { color: #58A6FF; text-align: center; border-bottom: 1px solid #30363D; padding-bottom: 20px; }
        .container { max-width: 900px; margin: auto; }
        .upload-panel { background: #161B22; border: 1px dashed #30363D; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 30px; }
        .upload-panel input[type="file"] { margin-bottom: 15px; color: #C9D1D9; }
        .btn { background: #238636; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; }
        .btn:hover { background: #2EA043; }
        .card { border: 1px solid #30363D; padding: 20px; margin-bottom: 20px; border-radius: 8px; background: #161B22; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .card-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #21262D; padding-bottom: 10px; margin-bottom: 15px; }
        .card-header h2 { margin: 0; color: #E6EDF3; }
        .score { font-size: 1.5em; font-weight: bold; }
        .score.excellent { color: #3FB950; }
        .score.warning { color: #D2A8FF; }
        .score.danger { color: #F85149; }
        .tags { background: #1F6FEB; color: #FFF; padding: 3px 10px; border-radius: 12px; font-size: 0.85em; margin-right: 5px; display: inline-block; margin-bottom: 10px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .list-group { list-style: none; padding: 0; margin: 0; font-size: 0.95em; }
        .list-group li { padding: 6px 0; border-bottom: 1px solid #21262D; }
        .list-group li:last-child { border-bottom: none; }
        .rec { color: #3FB950; }
        .alert { color: #F85149; }
        .signature { margin-top: 15px; padding-top: 10px; border-top: 1px dashed #30363D; font-family: monospace; font-size: 0.8em; color: #484F58; word-wrap: break-word; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔥 Phoenix Analysis Panel</h1>
        
        <div class="upload-panel">
            <h3 style="margin-top: 0;">Scan Asset Blueprint</h3>
            <form action="/analyze-asset" method="post" enctype="multipart/form-data">
                <input type="file" name="file" accept=".json" required><br>
                <button type="submit" class="btn">Analyze JSON</button>
            </form>
        </div>

        {% if not history %}
            <p style="text-align: center; color: #8B949E;">No blueprints scanned yet. Upload a JSON file above.</p>
        {% else %}
            {% for entry in history %}
            <div class="card">
                <div class="card-header">
                    <h2>{{ entry.asset }} <span style="font-size: 0.6em; color: #8B949E; font-weight: normal;">({{ entry.timestamp }})</span></h2>
                    {% set score = entry.report.optimization_score %}
                    <div class="score {% if score >= 80 %}excellent{% elif score >= 50 %}warning{% else %}danger{% endif %}">
                        {{ score }}%
                        <a href="/simulate/{{ entry.id }}" class="btn" style="background: #1F6FEB; font-size: 0.6em; margin-left: 15px; text-decoration: none;">Launch Interactive Sim 🚀</a>
                    </div>
                </div>
                
                <div>
                    {% for tag in entry.report.asset_type.split(', ') %}
                        <span class="tags">{{ tag }}</span>
                    {% endfor %}
                    <span style="color:#58A6FF; font-weight:bold; margin-left: 10px; font-size: 0.9em;">Skill Level: {{ entry.report.skill_level }}</span>
                </div>

                <div class="grid">
                    <div>
                        <h3 style="color: #8B949E; margin-top: 10px;">Detected Stats</h3>
                        <ul class="list-group">
                            {% for k, v in entry.report.stats.items() %}
                                <li>✔ <strong>{{ k }}:</strong> {{ v }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                    <div>
                        <h3 style="color: #8B949E; margin-top: 10px;">Phoenix Output</h3>
                        <ul class="list-group">
                            {% for rec in entry.report.recommendations %}
                                <li class="rec">✔ {{ rec }}</li>
                            {% endfor %}
                            {% for alert in entry.report.alerts %}
                                <li class="alert">⚠ {{ alert }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                </div>
                <div class="signature">
                    <strong>Vault Signature:</strong> {{ entry.report.secure_signature }}
                </div>
            </div>
            {% endfor %}
        {% endif %}
    </div>
</body>
</html>
"""

# --- INTERACTIVE SIMULATOR TEMPLATE ---
SIMULATOR_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phoenix Live Simulator - {{ entry.asset }}</title>
    <style>
        body { background: #0D1117; color: #C9D1D9; font-family: 'Segoe UI', sans-serif; margin: 0; display: flex; height: 100vh; overflow: hidden; }
        .store-side { flex: 6; padding: 40px; overflow-y: auto; border-right: 1px solid #30363D; display: flex; flex-direction: column; }
        .phoenix-side { flex: 4; padding: 40px; background: #161B22; overflow-y: auto; display: flex; flex-direction: column; }
        .video-placeholder { background: #000; height: 400px; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #8B949E; border: 1px dashed #30363D; margin-bottom: 20px; font-size: 1.2em; }
        .buy-box { background: #21262D; padding: 20px; border-radius: 8px; margin-top: 20px; }
        .btn-buy { background: #238636; color: white; border: none; padding: 15px 30px; border-radius: 5px; cursor: pointer; font-size: 1.1em; font-weight: bold; width: 100%; }
        h1 { color: #58A6FF; margin-top: 0; }
        h2 { color: #E6EDF3; border-bottom: 1px solid #30363D; padding-bottom: 10px; margin-top: 0; }
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; font-size: 0.9em; color: #8B949E; margin-bottom: 5px; text-transform: capitalize; }
        .input-group input { width: 100%; padding: 8px; border-radius: 4px; border: 1px solid #30363D; background: #0D1117; color: #C9D1D9; box-sizing: border-box; }
        .live-results { margin-top: 30px; padding: 20px; background: #0D1117; border-radius: 8px; border: 1px solid #30363D; }
        .score-display { font-size: 2em; font-weight: bold; color: #3FB950; margin-bottom: 15px; }
        .alert { color: #F85149; font-size: 0.9em; margin-bottom: 5px; }
        .rec { color: #3FB950; font-size: 0.9em; margin-bottom: 5px; }
        .live-tag { background: #F85149; color: white; font-size: 0.7em; padding: 2px 6px; border-radius: 10px; vertical-align: middle; margin-left: 10px; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
</head>
<body>
    <!-- LEFT SIDE: Clean Store / Video Interface -->
    <div class="store-side">
        <a href="/" style="color: #58A6FF; text-decoration: none; margin-bottom: 20px;">&larr; Back to Dashboard</a>
        <div class="video-placeholder">
            ▶ [ Asset Showcase Video Area ]
        </div>
        <h1>{{ entry.asset }}</h1>
        <p style="color: #8B949E; line-height: 1.6;">
            High-quality marketplace asset ready for integration. Adjust the parameters on the right to see how this asset scales within your specific game environment before purchasing.
        </p>
        <div class="buy-box">
            <h2 style="border:none;">$24.99</h2>
            <button class="btn-buy">Add to Cart</button>
        </div>
    </div>

    <!-- RIGHT SIDE: Phoenix Live Interactive Sim -->
    <div class="phoenix-side">
        <h2>Phoenix Engine <span class="live-tag">LIVE SIMULATION</span></h2>
        <p style="font-size: 0.85em; color: #8B949E;">Tweak blueprint parameters below to instantly recalculate performance and gameplay alerts.</p>
        
        <form id="sim-form">
            {% for key, val in editable_params.items() %}
            <div class="input-group">
                <label>{{ key.replace('_', ' ') }}</label>
                <input type="number" step="any" class="sim-input" data-key="{{ key }}" value="{{ val }}">
            </div>
            {% endfor %}
        </form>

        <div class="live-results" id="results-pane">
            <div class="score-display" id="sim-score">Score: {{ entry.report.optimization_score }}%</div>
            <div id="sim-stats" style="color: #58A6FF; font-weight: bold; margin-bottom: 15px;"></div>
            <div id="sim-alerts">
                {% for rec in entry.report.recommendations %}<div class="rec">✔ {{ rec }}</div>{% endfor %}
                {% for alert in entry.report.alerts %}<div class="alert">⚠ {{ alert }}</div>{% endfor %}
            </div>
        </div>
    </div>

    <script>
        const inputs = document.querySelectorAll('.sim-input');
        
        inputs.forEach(input => {
            input.addEventListener('input', () => {
                const overrides = {};
                inputs.forEach(inp => {
                    overrides[inp.getAttribute('data-key')] = inp.value;
                });
                
                fetch('/api/simulate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: {{ asset_id }}, overrides: overrides })
                })
                .then(response => response.json())
                .then(data => {
                    // Update Score
                    const scoreEl = document.getElementById('sim-score');
                    scoreEl.innerText = `Score: ${data.optimization_score}%`;
                    scoreEl.style.color = data.optimization_score >= 80 ? '#3FB950' : (data.optimization_score >= 50 ? '#D2A8FF' : '#F85149');
                    
                    // Update Computed Stats (like DPS)
                    const statsEl = document.getElementById('sim-stats');
                    statsEl.innerHTML = '';
                    if(data.stats['Calculated Dps']) {
                        statsEl.innerHTML = `🔥 Live DPS: ${data.stats['Calculated Dps']}`;
                    }

                    // Update Alerts & Recs
                    const alertsEl = document.getElementById('sim-alerts');
                    alertsEl.innerHTML = '';
                    data.recommendations.forEach(r => alertsEl.innerHTML += `<div class="rec">✔ ${r}</div>`);
                    data.alerts.forEach(a => alertsEl.innerHTML += `<div class="alert">⚠ ${a}</div>`);
                });
            });
        });
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Visual Analysis Panel for Void Hub"""
    return render_template_string(DASHBOARD_HTML, history=reversed(analysis_history))

@app.route('/simulate/<int:asset_id>')
def simulate_page(asset_id):
    """Renders the separated Interactive Preview side-by-side view."""
    if asset_id >= len(analysis_history):
        return redirect('/')
        
    entry = analysis_history[asset_id]
    
    # Extract only editable numeric/boolean parameters dynamically
    editable_params = {k: v for k, v in entry['raw_data'].items() 
                       if isinstance(v, (int, float, bool)) and k not in ['is_vr_ready']}
                       
    return render_template_string(SIMULATOR_HTML, entry=entry, asset_id=asset_id, editable_params=editable_params)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)