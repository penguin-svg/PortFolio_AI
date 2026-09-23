from fastapi import FastAPI
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, Field
from pypdf import PdfReader
import json
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import FileResponse, StreamingResponse

load_dotenv()
my_api_key=os.getenv("GROQ_API_KEY")

if not my_api_key:
    raise ValueError("API key kaha hai bhai")

client=Groq(api_key=my_api_key)
model = "openai/gpt-oss-120b"

# ---------------------------------------------------------------------------------------------------------------------------------------------------------




BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)

    

# classes # ------------------------------------------------------------------------------------------------------------------------------------------------------


class MatchResult(BaseModel):
    score: float
    details: dict
class Experience(BaseModel):
    company: str | None = None
    role: str | None = None
    duration: str | None = None
    description: str | None = None
    skills_used: list[str] = []

class Resume(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None

    total_experience_years: float | None = None

    skills: list[str] = []
    experiences: list[Experience] = []
    education: list[str] = []
    projects: list[str] = []
    certifications: list[str] = []


resume_schema = Resume.model_json_schema()

class ChatReq(BaseModel):
    question: str


# methods # ------------------------------------------------------------------------------------------------------------------------------------------------------

def AskChat(question: str, resume: Resume):

    system_prompt = f"""
    You are an AI assistant representing a job candidate.

    Below is everything you know about the candidate.

    {resume.model_dump_json(indent=2)}

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
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": question
            }
        ],
        stream=True
    )

    for chunk in response:
        content = chunk.choices[0].delta.content

        if content:
            yield content


#pdf extraction

def read_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

#resume parsing

def parse_resume(resume_text):
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

    {resume_schema}

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
    message_system={
        "role" : "system",
        "content" : system_prompt
    }
    message_user={
        "role" : "user",
        "content" : user_prompt
    }
    messages=[message_system, message_user]
    response_format={
        "type": "json_object"
    }
    response=client.chat.completions.create(model=model, messages=messages, response_format=response_format)
    raw_output = response.choices[0].message.content
    data = json.loads(raw_output)
    resume = Resume(**data)
    return resume

# main # ------------------------------------------------------------------------------------------------------------------------------------------------------
@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.post("/chat")

def chat(request: ChatReq):
    resume_text = read_pdf(Path("subhanker_resume.pdf"))
    resume=parse_resume(resume_text)
    return StreamingResponse(
        AskChat(request.question, resume),
        media_type="text/plain"
    )
    

