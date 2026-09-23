from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
from groq import Groq
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv()

# --- Config ---
my_api_key = os.getenv("GROQ_API_KEY")
model = "openai/gpt-oss-120b"

# --- Resume Schema (mirrors backend/main.py Pydantic models) ---
resume_schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"},
        "phone": {"type": "string"},
        "total_experience_years": {"type": "number"},
        "skills": {"type": "array", "items": {"type": "string"}},
        "experiences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "role": {"type": "string"},
                    "duration": {"type": "string"},
                    "description": {"type": "string"},
                    "skills_used": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "education": {"type": "array", "items": {"type": "string"}},
        "projects": {"type": "array", "items": {"type": "string"}},
        "certifications": {"type": "array", "items": {"type": "string"}},
    },
}


# --- Helpers ---

def read_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def parse_resume(resume_text):
    client = Groq(api_key=my_api_key)
    system_prompt = f"""
    You are an expert resume parser.

    Extract information from the resume based on its meaning,
    not only based on exact section headings.

    Different resumes may use different headings.

    For example:
    - Experience
    - Professional Experience
    - Work History
    - Employment
    - Internships

    These may all contain relevant experience.

    Skills may also appear in the skills section, work experience,
    internships or projects.

    Return ONLY valid JSON matching this schema:

    {json.dumps(resume_schema)}

    Important rules:

    1. Do not invent information.
    2. If a value is not available, return null.
    3. If a list has no information, return an empty list.
    4. Include internships inside experiences.
    5. Extract skills mentioned across the entire resume.
    """
    user_prompt = f"""
    Parse the following resume:

    {resume_text}
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )
    raw_output = response.choices[0].message.content
    data = json.loads(raw_output)
    return data


def ask_chat(question, resume_data):
    client = Groq(api_key=my_api_key)
    system_prompt = f"""
    You are an AI assistant representing a job candidate.

    Below is everything you know about the candidate.

    {json.dumps(resume_data, indent=2)}

    Rules:

    1. Answer only using this information.
    2. Never hallucinate.
    3. If information is unavailable, say:
    "I don't have enough information to answer that."
    4. Be professional.
    5. Answer as if HR is interviewing this candidate.
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        stream=True,
    )
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            yield content


# --- Vercel Serverless Handler ---

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
            question = data.get("question", "").strip()
        except (json.JSONDecodeError, AttributeError):
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON body"}).encode())
            return

        if not question:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Question is required"}).encode())
            return

        if not my_api_key:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "GROQ_API_KEY not configured"}).encode())
            return

        try:
            # Resolve PDF path relative to project root
            pdf_path = Path(__file__).resolve().parent.parent / "backend" / "subhanker_resume.pdf"
            resume_text = read_pdf(pdf_path)
            resume_data = parse_resume(resume_text)

            # Stream the response
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            for text_chunk in ask_chat(question, resume_data):
                self.wfile.write(text_chunk.encode("utf-8"))
                self.wfile.flush()

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
