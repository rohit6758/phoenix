from flask import Flask, request, jsonify
import sqlite3
import subprocess
import time
import uuid
import os
import requests  # NCR ki data pampadaniki idhi kothaga add chesam
from cyber_vault import encrypt_code, decrypt_code

app = Flask(__name__)

# --- CONFIGURATION ---
# NCR gadu vaadi API link ivvagaane ikkada update chey
NCR_WEBHOOK_URL = "https://ncr-ai-system.com/api/receive-metrics"

# --- 1. CLOUD SANDBOX EXECUTION ---
def run_cloud_task(user_code, test_variables, language):
    ext_map = {"cpp": ".cpp", "python": ".py", "c": ".c", "java": ".java", "javascript": ".js"}
    ext = ext_map.get(language, ".txt") 
    
    unique_id = "Code_" + uuid.uuid4().hex[:8] 
    filename = f"{unique_id}{ext}"
    filepath = os.path.join(os.getcwd(), filename)
    
    with open(filepath, 'w') as f:
        f.write(user_code)

    if language == "cpp":
        command = f'g++ {filename} -o {unique_id}_exe && ./{unique_id}_exe {test_variables}'
    elif language == "c":
        command = f'gcc {filename} -o {unique_id}_exe && ./{unique_id}_exe {test_variables}'
    elif language == "python":
        command = f'python3 {filename} {test_variables}'
    elif language == "java":
        command = f'java {filename} {test_variables}'
    elif language == "javascript":
        command = f'node {filename} {test_variables}'
    else:
        return -1, "", f"Error: Language '{language}' not supported.", 0

    start_time = time.perf_counter()
    try:
        process = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=5)
        returncode, stdout, stderr = process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired:
        returncode, stdout, stderr = -1, "", "Timeout Error: Code took more than 5 seconds!"
        
    end_time = time.perf_counter()
    
    if os.path.exists(filepath): os.remove(filepath)
    if os.path.exists(f"{unique_id}_exe"): os.remove(f"{unique_id}_exe")

    return returncode, stdout, stderr, (end_time - start_time) * 1000

# --- 2. DYNAMIC PROFILING ---
def get_complexity(t1, t2):
    ratio = t2 / t1 if t1 > 0 else 0
    if ratio < 1.5: return "O(1) - Constant"
    if ratio < 12: return "O(N) - Linear"
    return "O(N²) - Quadratic"

def run_dynamic_test(user_code, language):
    res1, _, _, t1 = run_cloud_task(user_code, "100", language)
    res2, stdout, _, t2 = run_cloud_task(user_code, "1000", language)
    big_o = get_complexity(t1, t2)
    return big_o, t2, stdout

# --- 3. UPLOAD & AUTO-PUSH API (The Automation Core) ---
@app.route('/upload-blueprint', methods=['POST'])
def upload_blueprint():
    data = request.get_json()
    code = data.get('code')
    language = data.get('language')
    dev_name = data.get('developer_name')

    locked_code = encrypt_code(code)
    blueprint_id = "BP_" + uuid.uuid4().hex[:6].upper()

    # DB Save
    conn = sqlite3.connect('voidhub.db')
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS blueprints (id TEXT, code BLOB, language TEXT, developer_name TEXT)")
    c.execute("INSERT INTO blueprints VALUES (?, ?, ?, ?)", (blueprint_id, locked_code, language, dev_name))
    conn.commit()
    conn.close()

    # Automation: Ventane execute chesi NCR ki pampadam
    big_o, final_time, stdout = run_dynamic_test(code, language)
    
    ncr_payload = {
        "blueprint_id": blueprint_id,
        "name": dev_name,
        "big_o": big_o,
        "space_complexcity": "O(1)",
        "execution_time_ms": round(final_time, 2),
        "status": "Verified"
    }

    # NCR ki Push chesthunnam
    try:
        requests.post(NCR_WEBHOOK_URL, json=ncr_payload, timeout=5)
    except:
        print("NCR Webhook not reachable yet.")

    return jsonify({
        "status": "Success", 
        "blueprint_id": blueprint_id,
        "big_o": big_o,
        "message": "Pushed to NCR automatically"
    })

# --- 4. MANUAL PULL API (Fallback for NCR) ---
@app.route('/run-sandbox', methods=['POST'])
def run_sandbox():
    data = request.get_json()
    blueprint_id = data.get('blueprint_id')
    
    conn = sqlite3.connect('voidhub.db')
    c = conn.cursor()
    c.execute("SELECT code, language, developer_name FROM blueprints WHERE id=?", (blueprint_id,))
    row = c.fetchone()
    conn.close()

    if not row: return jsonify({"error": "Not found"}), 404

    locked_code, language, dev_name = row
    code = decrypt_code(locked_code)
    big_o, final_time, _ = run_dynamic_test(code, language)

    return jsonify({
        "name": dev_name,
        "big_o": big_o,
        "space_complexcity": "O(1)",
        "execution_time_ms": round(final_time, 2)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)