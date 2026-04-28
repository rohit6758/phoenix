from flask import Flask, request, jsonify
import subprocess, time, uuid, os

app = Flask(__name__)

# 1. DATABASE (Store chesthundi ikkade)
candidates_db = []

# --- CORE EXECUTION ENGINE ---
def run_interview_task(user_code, custom_input, language):
    ext_map = {"cpp": ".cpp", "python": ".py", "c": ".c", "java": ".java", "javascript": ".js"}
    unique_id = "Judge_" + uuid.uuid4().hex[:8]
    filename = f"{unique_id}{ext_map.get(language, '.txt')}"
    
    with open(filename, 'w') as f: f.write(user_code)

    cmds = {
        "python": f'python3 {filename} {custom_input}',
        "javascript": f'node {filename} {custom_input}',
        "cpp": f'g++ {filename} -o {unique_id}_exe && ./{unique_id}_exe {custom_input}'
    }

    start_time = time.perf_counter()
    try:
        process = subprocess.run(cmds.get(language, cmds["python"]), shell=True, capture_output=True, text=True, timeout=5)
        stdout = process.stdout
    except:
        stdout = "ERROR OR TIMEOUT"
    end_time = time.perf_counter()

    if os.path.exists(filename): os.remove(filename)
    if os.path.exists(f"{unique_id}_exe"): os.remove(f"{unique_id}_exe")

    return stdout.strip(), (end_time - start_time) * 1000

# --- API: UPLOAD & EVALUATE ---
@app.route('/upload-blueprint', methods=['POST'])
def upload_blueprint():
    data = request.get_json()
    code = data.get('code')
    language = data.get('language', 'python')
    dev_name = data.get('developer_name', 'Anonymous')
    interviewer_input = data.get('test_input', '50')
    
    # 1. Run the code
    actual_output, exec_time = run_interview_task(code, interviewer_input, language)
    
    # 2. Generate Metrics
    candidate_result = {
        "name": dev_name,
        "actual_output": actual_output,
        "big_o": "O(N)", # Dynamic assignment in real-world
        "execution_time_ms": round(exec_time, 2),
        "space_complexity": "O(1)",
        "memory_usage_estimate_kb": 256 # Base estimate
    }
    
    # 3. Save to Local Leaderboard
    candidates_db.append(candidate_result)
    
    return jsonify({"status": "Evaluated & Added to Leaderboard", "metrics": candidate_result})

# --- UI: THE LEADERBOARD DASHBOARD ---
@app.route('/')
def dashboard():
    if not candidates_db:
        return "<h2 style='color:white; background:#121212; padding:20px; font-family:sans-serif;'>🔥 Phoenix Engine LIVE: Waiting for candidates to submit code...</h2>"

    # Target Criteria
    TARGET_BIG_O = "O(N)"
    TARGET_MAX_TIME = 50.0  

    scored_candidates = []

    # AI Scoring Logic
    for c in candidates_db:
        score = 5000.0  
        score -= (c['execution_time_ms'] * 5)
        score -= (c['memory_usage_estimate_kb'] * 2)
        if c['big_o'] == TARGET_BIG_O: score += 1000.0
            
        c['score'] = round(score, 1)
        scored_candidates.append(c)

    # Sort ranks
    scored_candidates.sort(key=lambda x: x['score'], reverse=True)

    # Generate HTML
    html = """
    <body style="background-color:#0D1117; color:#C9D1D9; font-family:Arial; padding:40px;">
        <h1 style="color:#58A6FF;">🏆 Phoenix Hackathon Leaderboard</h1>
        <table style="width:100%; border-collapse: collapse; text-align: left;">
            <tr style="background-color:#161B22; border-bottom: 2px solid #30363D;">
                <th style="padding:15px;">Rank</th>
                <th style="padding:15px;">Candidate</th>
                <th style="padding:15px;">AI Score</th>
                <th style="padding:15px;">Big-O</th>
                <th style="padding:15px;">Exec Time (ms)</th>
                <th style="padding:15px;">Memory (KB)</th>
                <th style="padding:15px;">Output</th>
            </tr>
    """

    for index, c in enumerate(scored_candidates):
        # Highlighting logic
        big_o_color = "#00FF00" if c['big_o'] == TARGET_BIG_O else "#9B59B6" 
        time_color = "#00FF00" if c['execution_time_ms'] <= TARGET_MAX_TIME else "#9B59B6"

        html += f"""
            <tr style="border-bottom: 1px solid #30363D;">
                <td style="padding:15px; font-size:20px;"><b>#{index + 1}</b></td>
                <td style="padding:15px; color:white;">{c['name']}</td>
                <td style="padding:15px; color:#FFD700; font-weight:bold;">{c['score']}</td>
                <td style="padding:15px; color:{big_o_color}; font-weight:bold;">{c['big_o']}</td>
                <td style="padding:15px; color:{time_color}; font-weight:bold;">{c['execution_time_ms']}</td>
                <td style="padding:15px;">{c['memory_usage_estimate_kb']}</td>
                <td style="padding:15px; color:#8B949E;">{c['actual_output']}</td>
            </tr>
        """
    
    html += "</table></body>"
    return html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)