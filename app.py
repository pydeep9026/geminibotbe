import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from difflib import SequenceMatcher

load_dotenv()
app = Flask(__name__)
CORS(app)

def load_data(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except:
        return []

def is_query_relevant(query, data):
    query_lower = query.lower()
    for item in data:
        title_match = SequenceMatcher(None, query_lower, item.get("title", "").lower()).ratio()
        content_match = SequenceMatcher(None, query_lower, item.get("content", "").lower()).ratio()
        if title_match > 0.6 or content_match > 0.6:
            return True
    return False

def filter_data(data, query):
    query_lower = query.lower()
    return [item for item in data if SequenceMatcher(None, query_lower, item.get("title", "").lower()).ratio() > 0.6 or SequenceMatcher(None, query_lower, item.get("content", "").lower()).ratio() > 0.6]

def filter_remedy(data, query):
    query_lower = query.lower()
    return [item for item in data if SequenceMatcher(None, query_lower, item.get("solution", "").lower()).ratio() > 0.6]

def generate_prompt(query, confluence, remedy):
    prompt = "You are an IT support assistant. Reformat the provided content without adding extra details. Use only the given information to structure the answer in clean markdown. Do not generate additional content.\n"
    prompt += f"USER QUESTION: {query}\n"
    prompt += f"CONFLUENCE DOCUMENTS: {json.dumps(confluence)}\n"
    prompt += f"REMEDY TICKETS: {json.dumps(remedy)}\n"
    prompt += "The response should include:\n1. Introduction\n2. Prerequisites (include **bold warnings** if applicable)\n3. Step-by-step instructions\n4. Troubleshooting\n"
    return prompt

def call_gemini_api(prompt):
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    headers = {"Content-Type": "application/json"}
    params = {"key": GEMINI_API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=payload)
        response.raise_for_status()
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"Error generating response: {str(e)}"

def generate_response(query):
    confluence_data = load_data("confluence_data.txt")
    remedy_data = load_data("remedy_data.txt")

    if not is_query_relevant(query, confluence_data):
        return "Data not found"

    filtered_confluence = filter_data(confluence_data, query)
    filtered_remedy = filter_remedy(remedy_data, query)
    
    prompt = generate_prompt(query, filtered_confluence, filtered_remedy)
    return call_gemini_api(prompt)

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    query = data.get("query", "")
    if not query:
        return jsonify({"error": "No query provided"}), 400
    try:
        response = generate_response(query)
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
