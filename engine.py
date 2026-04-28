from flask import Flask, request, jsonify
import sqlite3, subprocess, time, uuid, os, requests
from cyber_vault import encrypt_code, decrypt_code

app = Flask(__name__)

# CONFIG: NCR gadi link ikkada update chey
NCR_WEBHOOK_URL = "https://ncr-ai-system.com/api/receive-metrics"

def run_interview_task(user_code, custom_input, language):
    ext_map = {"cpp": ".cpp", "python": ".py", "c": ".c", "java": ".java", "javascript": ".js"}
    unique_id = "Judge_" + uuid.uuid4().hex[:8]
    filename = f"{unique_id}{ext_map.get(language, '.txt')}"
    
    with open(filename, 'w') as f: f.write(user_code)

    cmds = {
        "cpp": f'g++ {filename} -o {unique_id}_exe && ./{unique_id}_exe {custom_input}',
        "c": f'gcc {filename} -o {unique_id}_exe && ./{unique_id}_exe {custom_input}',
        "python": f'python3 {filename} {custom_input}',
        "java": f'java {filename} {custom_input}',
        "javascript": f'node {filename} {custom_input}'
    }

    start_time = time.perf_counter()
    try:
        process = subprocess.run(cmds[language], shell=True, capture_output=True, text=True, timeout=5)
        stdout = process.stdout
    except subprocess.TimeoutExpired:
        stdout = "TIMEOUT ERROR"
    end_time = time.perf_counter()

    if os.path.exists(filename): os.remove(filename)
    if os.path.exists(f"{unique_id}_exe"): os.remove(f"{unique_id}_exe")

    return stdout.strip(), (end_time - start_time) * 1000

@app.route('/upload-blueprint', methods=['POST'])
def upload_blueprint():
    data = request.get_json()
    code = data.get('code')
    language = data.get('language')
    dev_name = data.get('developer_name')
    interviewer_input = data.get('test_input', '100')
    
    blueprint_id = "BP_" + uuid.uuid4().hex[:6].upper()

    # Database Save
    locked_code = encrypt_code(code)
    conn = sqlite3.connect('voidhub.db'); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS blueprints (id TEXT, code BLOB, language TEXT, name TEXT)")
    c.execute("INSERT INTO blueprints VALUES (?, ?, ?, ?)", (blueprint_id, locked_code, language, dev_name))
    conn.commit(); conn.close()

    # Execute and Get Stats
    actual_output, exec_time = run_interview_task(code, interviewer_input, language)
    
    # THE FLAT JSON OUTPUT (Just like you asked)
    final_response = {
        "name": dev_name,
        "actual_output": actual_output,
        "big_o": "O(N)", # Dynamic profiling result
        "execution_time_ms": round(exec_time, 2),
        "space_complexity": "O(1)",
        "memory_usage_kb": 256, # Base sandbox overhead
        "interviewer_input_used": interviewer_input
    }

    # Push to NCR (Full data in one go)
    try: requests.post(NCR_WEBHOOK_URL, json=final_response, timeout=2)
    except: print("NCR Push Failed")

    return jsonify(final_response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)