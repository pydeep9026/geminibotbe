import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from difflib import SequenceMatcher
from bs4 import BeautifulSoup
import re

load_dotenv()
app = Flask(__name__)
CORS(app)

def load_data(file_path):
    try:
        with open(file_path, 'r') as f:
            if file_path == "confluence_data.txt":
                data = json.loads(f.read())
                return [{
                    "id": item.get("id", ""),
                    "title": item.get("title", ""),
                    "content": BeautifulSoup(item.get("body", {}).get("storage", {}).get("value", ""), "html.parser").get_text(),
                    "labels": [label["name"] for label in item.get("labels", {}).get("results", [])],
                    "status": item.get("status", "")
                } for item in data]
            elif file_path == "remedy_data.txt":
                data = json.loads(f.read())
                return [{
                    "ticketId": item.get("ticketId", ""),
                    "title": item.get("title", ""),
                    "solution": item.get("solution", {}).get("text", ""),
                    "workaround": item.get("solution", {}).get("workaround", ""),
                    "category": item.get("category", ""),
                    "status": item.get("status", "")
                } for item in data]
    except Exception as e:
        print(f"Error loading {file_path}: {str(e)}")
        return []
    

def is_id_match(query, item):
    # Check Confluence ID
    if "id" in item and query.lower() == item["id"].lower():
        return True
    # Check Remedy ticket ID
    if "ticketId" in item and query.lower() == item["ticketId"].lower():
        return True
    return False



def calculate_relevance_score(query, item):

    if is_id_match(query, item):
        return 1.0 

    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    
    # Title match (50% weight)
    title = item.get("title", "").lower()
    title_words = set(re.findall(r'\w+', title))
    title_score = SequenceMatcher(None, query_lower, title).ratio() * 0.5
    
    # Label match (30% weight)
    label_score = 0
    for label in item.get("labels", []):
        label_score += SequenceMatcher(None, query_lower, label.lower()).ratio()
    label_score = min(label_score * 0.3, 0.3)
    
    # Content match (20% weight)
    content = item.get("content", "").lower() if "content" in item else item.get("solution", "").lower()
    content_score = 0
    for word in query_words:
        content_score += content.count(word) * 0.01
    content_score = min(content_score, 0.2)
    
    return title_score + label_score + content_score

def filter_and_sort_data(data, query, threshold=0.5):
    if not data:
        return []
    
    scored_items = []
    for item in data:
        score = calculate_relevance_score(query, item)
        if score >= threshold:
            scored_items.append((item, score))
    
    scored_items.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in scored_items if item[1] >= threshold]

def generate_prompt(query, confluence_results, remedy_results):
    prompt = """You are an IT support assistant. Structure the answer using ONLY the provided reference materials.
Format the response in clean markdown without adding external information.

USER QUESTION: {query}

REFERENCE MATERIALS:
""".format(query=query)

    if confluence_results:
        prompt += "\nCONFLUENCE DOCUMENTS (Source IDs: {confluence_ids}):\n{confluence_data}\n".format(
            confluence_ids=", ".join([doc.get("id", "N/A") for doc in confluence_results]),
            confluence_data=json.dumps([{"title": doc.get("title"), "content": doc.get("content")} for doc in confluence_results], indent=2)
        )
    
    if remedy_results:
        prompt += "\nREMEDY TICKETS (Ticket IDs: {remedy_ids}):\n{remedy_data}\n".format(
            remedy_ids=", ".join([ticket.get("ticketId", "N/A") for ticket in remedy_results]),
            remedy_data=json.dumps([{"title": ticket.get("title"), "solution": ticket.get("solution")} for ticket in remedy_results], indent=2)
        )

    prompt += """
RESPONSE FORMAT:
1. **Introduction** (Briefly state what this covers)
2. **Prerequisites** (List requirements in bullet points)
3. **Steps** (Numbered instructions)
4. **Troubleshooting** (Common issues and fixes)
5. **Sources** (List document IDs used)

IMPORTANT: If no relevant information exists, respond only with: "No results found for this query."
"""
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
    
    filtered_confluence = filter_and_sort_data(confluence_data, query)
    filtered_remedy = filter_and_sort_data(remedy_data, query)
    
    if not filtered_confluence and not filtered_remedy:
        return "No results found for this query."
    
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