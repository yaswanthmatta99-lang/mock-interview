from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAI
import os
import tempfile
import shutil
from datetime import datetime
from typing import List, Dict, Optional
import json
import uuid

# Configuration
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = FastAPI()

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# In-memory storage (replace with database in production)
interviews = {}

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("AIzaSyAlPtTvQXMwIIZOSAW7Aq6Ae4kHylhT4sQ"))

def extract_skills(text: str) -> List[str]:
    """Extract skills from resume text."""
    skills = []
    common_skills = [
        # Programming Languages
        "Python", "JavaScript", "Java", "C++", "C#", "PHP", "Ruby", "Swift", "Kotlin", "Go", "Rust", "TypeScript",
        # Web Technologies
        "HTML", "CSS", "React", "Angular", "Vue.js", "Node.js", "Django", "Flask", "Spring", "ASP.NET", "Express.js",
        # Databases
        "SQL", "MySQL", "PostgreSQL", "MongoDB", "Oracle", "SQLite", "Redis", "Cassandra",
        # Cloud & DevOps
        "AWS", "Azure", "Google Cloud", "Docker", "Kubernetes", "Terraform", "Ansible", "Jenkins", "Git", "CI/CD",
        # Data Science
        "Machine Learning", "Deep Learning", "Data Analysis", "Pandas", "NumPy", "TensorFlow", "PyTorch", "scikit-learn",
        # Other
        "REST API", "GraphQL", "Microservices", "Agile", "Scrum", "TDD", "OOP", "Functional Programming"
    ]
    
    for skill in common_skills:
        if skill.lower() in text.lower():
            skills.append(skill)
    
    return list(dict.fromkeys(skills))[:8]  # Remove duplicates and limit to 8 skills

def extract_experiences(text: str) -> List[Dict]:
    """Extract work experiences from resume text."""
    experiences = []
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(role in line_lower for role in ['developer', 'engineer', 'analyst', 'specialist', 'manager', 'designer', 'researcher']):
            exp = {
                "title": line,
                "company": lines[i+1] if i+1 < len(lines) and len(lines[i+1]) < 50 else "a company"
            }
            # Avoid adding duplicate experiences
            if not any(e['title'] == exp['title'] and e['company'] == exp['company'] for e in experiences):
                experiences.append(exp)
                if len(experiences) >= 3:  # Limit to 3 experiences
                    break
    
    return experiences

def extract_projects(text: str) -> List[Dict]:
    """Extract projects from resume text."""
    projects = []
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if ("project" in line_lower or "portfolio" in line_lower) and len(line.split()) < 5:
            project = {
                "name": line.replace("Project:", "").replace("project:", "").strip(),
                "description": lines[i+1] if i+1 < len(lines) and 10 < len(lines[i+1]) < 200 else ""
            }
            # Avoid adding duplicate projects
            if not any(p['name'] == project['name'] for p in projects):
                projects.append(project)
                if len(projects) >= 3:  # Limit to 3 projects
                    break
    
    return projects

def generate_resume_questions(resume_text: str) -> List[Dict[str, str]]:
    """Generate interview questions based on resume content in a structured order."""
    print("Generating structured resume-specific questions...")
    
    # Extract key information from resume
    skills = extract_skills(resume_text)
    experiences = extract_experiences(resume_text)
    projects = extract_projects(resume_text)
    
    questions = []
    
    # 1. Self Introduction
    questions.append({
        "id": len(questions) + 1,
        "question": "Can you please introduce yourself and tell us about your background?",
        "difficulty": "Easy",
        "type": "Introduction",
        "category": "Basic"
    })
    
    # 2. Basic Information
    questions.append({
        "id": len(questions) + 1,
        "question": "What motivated you to pursue a career in this field?",
        "difficulty": "Easy",
        "type": "Background",
        "category": "Basic"
    })
    
    # 3. Technical Skills
    if skills:
        # Add a general technical question
        questions.append({
            "id": len(questions) + 1,
            "question": "Can you walk us through your technical skills and how you've applied them in your projects?",
            "difficulty": "Medium",
            "type": "Technical",
            "category": "Skills"
        })
        
        # Add specific skill questions
        for skill in skills[:3]:  # Top 3 skills
            questions.append({
                "id": len(questions) + 1,
                "question": f"Can you describe a specific project where you used {skill} and what challenges you faced?",
                "difficulty": "Medium",
                "type": "Technical",
                "category": "Skills"
            })
    
    # 4. Work Experience
    if experiences:
        # General experience question
        questions.append({
            "id": len(questions) + 1,
            "question": "Can you give us an overview of your professional experience and how it's prepared you for this role?",
            "difficulty": "Medium",
            "type": "Experience",
            "category": "Work"
        })
        
        # Specific experience questions
        for exp in experiences[:2]:  # Top 2 experiences
            questions.append({
                "id": len(questions) + 1,
                "question": f"Tell us about your role at {exp.get('company', 'your previous company')}. What were your key responsibilities and achievements?",
                "difficulty": "Medium",
                "type": "Experience",
                "category": "Work"
            })
    
    # 5. Projects
    if projects:
        # General project question
        questions.append({
            "id": len(questions) + 1,
            "question": "Can you tell us about a project you're particularly proud of and what you learned from it?",
            "difficulty": "Hard",
            "type": "Project",
            "category": "Projects"
        })
        
        # Specific project questions
        for project in projects[:2]:  # Top 2 projects
            questions.append({
                "id": len(questions) + 1,
                "question": f"For your project '{project.get('name', 'this project')}', what was your role, what technologies did you use, and what were the outcomes?",
                "difficulty": "Hard",
                "type": "Project",
                "category": "Projects"
            })
    
    # 6. Behavioral Questions
    behavioral_questions = [
        {
            "id": len(questions) + 1,
            "question": "Can you describe a time when you faced a significant challenge in a project and how you overcame it?",
            "difficulty": "Hard",
            "type": "Behavioral",
            "category": "Behavioral"
        },
        {
            "id": len(questions) + 2,
            "question": "How do you approach learning new technologies or skills? Can you give an example?",
            "difficulty": "Medium",
            "type": "Behavioral",
            "category": "Behavioral"
        },
        {
            "id": len(questions) + 3,
            "question": "Where do you see yourself in your career in the next 3-5 years?",
            "difficulty": "Easy",
            "type": "Behavioral",
            "category": "Behavioral"
        }
    ]
    
    questions.extend(behavioral_questions)
    return questions

def generate_mock_questions(text: str, source: str) -> List[Dict[str, str]]:
    """Generate mock interview questions without using the OpenAI API."""
    if "resume" in source.lower():
        return generate_resume_questions(text)
    else:  # job description
        return [
            {
                "id": 1, 
                "question": "What interests you about this position and how does it align with your career goals?", 
                "difficulty": "Easy",
                "type": "General"
            },
            {
                "id": 2, 
                "question": "How would your skills and experience help you succeed in this role?", 
                "difficulty": "Medium",
                "type": "Experience"
            },
            {
                "id": 3, 
                "question": "Can you describe a challenging project you worked on and how it demonstrates your ability to handle this position's responsibilities?", 
                "difficulty": "Hard",
                "type": "Project"
            }
        ]

@app.post("/start-interview")
@app.post("/start-interview/")
async def start_interview(
    content: str = Form(...),
    source: str = Form(...)  # "resume" or "job_description"
):
    """Start a new interview session with text content."""
    try:
        interview_id = f"int_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        questions = generate_mock_questions(content, source)
        
        # Store the interview data
        interviews[interview_id] = {
            "id": interview_id,
            "source": source,
            "content": content[:500],  # Store first 500 chars for reference
            "questions": questions,
            "answers": {},
            "created_at": datetime.now().isoformat()
        }
        
        return {
            "interview_id": interview_id,
            "total_questions": len(questions),
            "first_question": questions[0] if questions else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    source: str = Form("resume")  # Default to "resume" if not provided
):
    """Handle resume or JD file upload and start interview."""
    try:
        # Validate file type
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ['.pdf', '.docx', '.txt']:
            raise HTTPException(status_code=400, detail="Unsupported file type. Please upload PDF, DOCX, or TXT.")
        
        # Read file content
        content = await file.read()
        text_content = content.decode('utf-8', errors='ignore')
        
        # If it's a large file, truncate to first 10,000 characters
        if len(text_content) > 10000:
            text_content = text_content[:10000] + "\n\n[Content truncated for processing]"
        
        # Start interview with the extracted text
        return await start_interview(content=text_content, source=source)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.get("/interview/{interview_id}/question/{question_id}")
async def get_question(interview_id: str, question_id: int):
    """Get a specific question from an interview."""
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    interview = interviews[interview_id]
    question = next((q for q in interview["questions"] if q["id"] == question_id), None)
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
        
    return {
        "interview_id": interview_id,
        "current_question": question,
        "total_questions": len(interview["questions"]),
        "has_next": question_id < len(interview["questions"])
    }

@app.post("/upload-answer")
async def upload_answer(
    interview_id: str = Form(...),
    question_id: int = Form(...),
    video: UploadFile = File(...)
):
    """Upload a video answer for a specific question."""
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # Create directory for this interview if it doesn't exist
    interview_dir = os.path.join(UPLOAD_FOLDER, interview_id)
    os.makedirs(interview_dir, exist_ok=True)
    
    # Save the video file
    filename = f"q{question_id}_{int(datetime.now().timestamp())}.webm"
    file_path = os.path.join(interview_dir, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            # Read and save the file in chunks to handle large files
            while True:
                chunk = await video.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                buffer.write(chunk)
        
        # Update interview data
        interviews[interview_id]["answers"][question_id] = {
            "video_path": file_path,
            "uploaded_at": datetime.now().isoformat()
        }
        
        return {
            "status": "success",
            "interview_id": interview_id,
            "question_id": question_id,
            "saved_path": file_path
        }
    except Exception as e:
        # Clean up the file if there was an error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error saving video: {str(e)}")

@app.get("/interview/{interview_id}/summary")
async def get_interview_summary(interview_id: str):
    """Get a summary of the interview including all questions and answers."""
    if interview_id not in interviews:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    interview = interviews[interview_id]
    return {
        "interview_id": interview_id,
        "source": interview["source"],
        "created_at": interview["created_at"],
        "total_questions": len(interview["questions"]),
        "questions_answered": len(interview["answers"]),
        "questions": interview["questions"],
        "answers": interview["answers"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)