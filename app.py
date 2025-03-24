import os
import random
from datetime import datetime, timedelta
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

class FakeDataGenerator:
    @staticmethod
    def generate_confluence_results(query):
        """Generate realistic fake Confluence pages"""
        return [
            {
                "title": f"{query.capitalize()} Installation Guide",
                "content": f"""# {query.capitalize()} Installation
                ## Prerequisites
                - Windows 10/11
                - Admin rights
                ## Steps
                1. Download package
                2. Run installer
                3. Verify installation"""
            },
            {
                "title": f"Enterprise {query.capitalize()} Config",
                "content": f"""# Enterprise Setup
                **Security Notes:**
                - Requires ports 443/8080
                - Approved version: 2.4.1"""
            }
        ]

    @staticmethod
    def generate_remedy_results(query):
        """Generate realistic fake Remedy tickets"""
        return [
            {
                "ticket_id": "INC12345",
                "solution": f"""**Solution for {query} issues:**
                1. Found antivirus blocking
                2. Added exception
                3. Verified install"""
            }
        ]

class ITHelpChatbot:
    def __init__(self):
        self.fake = FakeDataGenerator()

    def generate_response(self, user_query):
        """Get fake data, send to Gemini for summarization"""
        # Get fake data
        confluence_data = self.fake.generate_confluence_results(user_query)
        remedy_data = self.fake.generate_remedy_results(user_query)

        # Prepare Gemini prompt
        prompt = f"""
        You are an IT support assistant. Summarize and structure this information:

        USER QUESTION: {user_query}

        CONFLUENCE DOCUMENTS:
        {confluence_data}

        REMEDY TICKETS:
        {remedy_data}

        Provide response with:
        1. Brief introduction
        2. Prerequisites (bold warnings)
        3. Step-by-step instructions
        4. Troubleshooting (from Remedy)
        5. Format in clean markdown
        """

        # Call Gemini API
        headers = {'Content-Type': 'application/json'}
        params = {'key': GEMINI_API_KEY}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

        try:
            response = requests.post(
                GEMINI_API_URL,
                headers=headers,
                params=params,
                json=payload
            )
            response.raise_for_status()
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            return f"Error generating response: {str(e)}"

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_query = data.get('query', '')
    
    if not user_query:
        return jsonify({'error': 'No query provided'}), 400
    
    chatbot = ITHelpChatbot()
    try:
        response = chatbot.generate_response(user_query)
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
