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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",  # Frontend URL
        "http://localhost:3000",   # Alternative frontend URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# In-memory storage (replace with database in production)
interviews = {}

# Initialize OpenAI client
# The API key should be set as an environment variable
# For example: export OPENAI_API_KEY='your-api-key-here'
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    
    return projects

def generate_resume_questions(resume_text: str) -> List[Dict[str, str]]:
    """Generate personalized interview questions based on resume content."""
    print("Generating personalized resume-specific questions...")
    
    # Extract structured information
    skills = extract_skills(resume_text)
    experiences = extract_experiences(resume_text)
    projects = extract_projects(resume_text)
    
    questions = []
    
    # 1. Self Introduction (First 2 questions)
    intro_questions = [
        {
            "id": 1,
            "question": "Can you please introduce yourself and tell us about your professional background?",
            "difficulty": "Easy",
            "type": "Self-Introduction",
            "category": "Basic"
        },
        {
            "id": 2,
            "question": "What motivated you to pursue a career in this field, and what are your key strengths?",
            "difficulty": "Easy",
            "type": "Self-Introduction",
            "category": "Background"
        }
    ]
    questions.extend(intro_questions)
    
    # 2. Basic Skills Questions (Questions 3-4)
    if skills:
        # Take top 2 skills for basic questions
        for skill in skills[:2]:
            questions.append({
                "id": len(questions) + 1,
                "question": f"How would you rate your proficiency in {skill} and what projects have you used it in?",
                "difficulty": "Easy",
                "type": "Technical",
                "category": f"{skill} Basics"
            })
    
    # 3. Experience Questions (Middle Questions)
    for i, exp in enumerate(experiences[:2]):  # Limit to 2 experiences
        company = exp.get('company', 'your previous role')
        title = exp.get('title', '')
        
        questions.append({
            "id": len(questions) + 1,
            "question": f"At {company} as a {title}, what were your key responsibilities and achievements?",
            "difficulty": "Medium",
            "type": "Experience",
            "category": "Work History"
        })
        
        # Add a follow-up question about challenges
        if i == 0:  # Only add one challenge question
            questions.append({
                "id": len(questions) + 1,
                "question": f"What was the most challenging project you worked on at {company} and how did you handle it?",
                "difficulty": "Medium",
                "type": "Problem-Solving",
                "category": "Work Challenges"
            })
    
    # 4. Advanced Skills Questions (After Experience)
    if len(skills) > 2:  # If we have more than 2 skills
        for skill in skills[2:4]:  # Take next 2 skills for advanced questions
            questions.append({
                "id": len(questions) + 1,
                "question": f"Can you explain a complex problem you solved using {skill}? What was your approach and what did you learn?",
                "difficulty": "Hard",
                "type": "Technical",
                "category": f"Advanced {skill}"
            })
    
    # 5. Project Questions (If we need more questions)
    if len(questions) < 8 and projects:  # If we don't have enough questions yet
        for proj in projects[:1]:  # Limit to 1 project
            title = proj.get('title', 'a project')
            
            questions.append({
                "id": len(questions) + 1,
                "question": f"Tell me about your project '{title}'. What was your role, and what technologies did you use?",
                "difficulty": "Medium",
                "type": "Project",
                "category": "Projects"
            })
    
    # 6. Future and Closing Questions (Last 2 questions)
    future_questions = [
        {
            "question": "What technical skills are you currently working to improve, and how are you going about it?",
            "difficulty": "Easy",
            "type": "Career Development",
            "category": "Future Goals"
        },
        {
            "question": "Where do you see your career in the next 3-5 years, and how does this position align with your goals?",
            "difficulty": "Medium",
            "type": "Career Goals",
            "category": "Future Planning"
        }
    ]
    
    # Add future questions with proper IDs
    for q in future_questions:
        questions.append({
            "id": len(questions) + 1,
            **q
        })
    
    # Ensure we have at least 10 questions
    generic_questions = [
        "Can you describe a time when you had to work under pressure to meet a tight deadline?",
        "How do you approach learning new technologies or programming languages?",
        "Can you explain a technical concept to someone who doesn't have a technical background?",
        "What development tools and IDEs are you most comfortable using, and why?",
        "How do you handle code reviews and feedback on your work?",
        "What version control systems have you worked with, and what's your experience with them?",
        "Can you describe your experience with testing and quality assurance processes?",
        "How do you stay updated with the latest industry trends and technologies?",
        "What's your approach to debugging complex issues in your code?",
        "Can you describe a time when you had to collaborate with a difficult team member and how you handled it?"
    ]
    
    # Add generic questions if we don't have enough
    while len(questions) < 10 and generic_questions:
        questions.append({
            "id": len(questions) + 1,
            "question": generic_questions.pop(0),
            "difficulty": "Medium",
            "type": "General",
            "category": "Professional Development"
        })
    
    # Ensure we don't have too many questions
    if len(questions) > 25:
        questions = questions[:25]
    
    print(f"Generated {len(questions)} questions for the interview")
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
    source: str = Form("resume")  # Default to "resume" if not provided
):
    """Start a new interview session with text content."""
    try:
        print(f"Starting interview with source: {source}")
        print(f"Content length: {len(content)} characters")
        
        interview_id = f"int_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        # Generate questions based on the source
        if source == "resume":
            questions = generate_resume_questions(content)
        else:  # job_description or other
            questions = generate_resume_questions(content)  # For now, use the same function
        
        if not questions:
            raise HTTPException(status_code=400, detail="Failed to generate questions from the provided content.")
        
        # Store the interview data
        interviews[interview_id] = {
            "id": interview_id,
            "source": source,
            "content": content[:500],  # Store first 500 chars for reference
            "questions": questions,
            "answers": {},
            "created_at": datetime.now().isoformat()
        }
        
        print(f"Generated {len(questions)} questions for interview {interview_id}")
        
        return {
            "interview_id": interview_id,
            "total_questions": len(questions),
            "first_question": questions[0] if questions else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(..., description="The resume file to upload"),
    source: str = Form("resume", description="Source of the upload, defaults to 'resume'")
):
    """Handle resume or JD file upload and start interview."""
    try:
        print(f"Received file upload request: {file.filename}, size: {file.size} bytes")
        
        # Validate file type
        file_extension = os.path.splitext(file.filename)[1].lower()
        allowed_extensions = ['.pdf', '.docx', '.txt']
        if file_extension not in allowed_extensions:
            error_msg = f"Unsupported file type: {file_extension}. Allowed types: {', '.join(allowed_extensions)}"
            print(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Read file content with size limit (5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        content = await file.read()
        
        if len(content) > max_size:
            error_msg = f"File too large: {len(content)} bytes. Maximum size is 5MB."
            print(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Decode content
        try:
            text_content = content.decode('utf-8', errors='ignore')
        except Exception as decode_error:
            error_msg = f"Error decoding file content: {str(decode_error)}"
            print(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Log file processing
        print(f"Processing file: {file.filename}, content length: {len(text_content)} characters")
        
        # If it's a large file, truncate to first 10,000 characters
        if len(text_content) > 10000:
            print("File content exceeds 10,000 characters, truncating...")
            text_content = text_content[:10000] + "\n\n[Content truncated for processing]"
        
        # Start interview with the extracted text
        print("Starting interview with extracted text...")
        return await start_interview(content=text_content, source=source)
        
    except HTTPException as http_err:
        # Re-raise HTTP exceptions as they are
        raise http_err
    except Exception as e:
        error_msg = f"Unexpected error processing file: {str(e)}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

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