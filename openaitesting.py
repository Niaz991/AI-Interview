from fastapi import FastAPI,Depends, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from pydantic import BaseModel
from typing import List, Dict
import PyPDF2
from docx import Document
import json
import io
import fitz
from datetime import datetime
from openai import OpenAI
import os
import re

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "put your key"))


app = FastAPI()

# Add CORS middleware with allow_origins set to ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

generated_questions=[]
generated_answers = []


qa_from_text = None  # Initialize to None outside of the endpoints
qa_from_file = None  # Initialize to None outside of the endpoints
last_generate_text_time = None  # Initialize to None
last_generate_file_time = None  # Initialize to None



def extract_job_title(job_description_text):
    # Use regex to extract the job title from the job description text
    # Adjust the regex pattern based on the format of your job titles
    match = re.search(r'Job\s*Title:\s*(.+)', job_description_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    else:
        return None

"""
                                    TEXT OF JOB DESCRIPTION
"""   

@app.post("/generate_question_answer_from_text")
def generate_questions(job_description: str = Form(...)):
    global qa_from_text, last_generate_text_time


    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        response_format={ "type": "json_object" },
        messages=[
            {
            "role": "system",
            "content": "You are a technical interviewer evaluating a candidate for the job position. Your job is to ask technical and conceptual questions. Do not repeat the question. For each question, also provide a short insightful answer.Output should be a json."
            },
            {
            "role": "user",
            "content": f"""Generate a json with the title "INTERVIEW QUESTIONS & ANSWERS" containing the Questions and Answers. The overall format should be:\n
            {{
            "INTERVIEW QUESTIONS & ANSWERS": [
                {{
                "Question 1": "model generated question",
                Answer 1: "model generated answer"
                }},
                {{
                "Question 2": "model generated question",
                "Answer 2": "model generated answer"
                }}
            ]
            }}\n
            Generate 4 technical interview questions based on the provided job description information.Each time generate different questions from the provided job description.\n
            Job_description: {job_description}"""
            }
        ],
        temperature=0.2,
        max_tokens=2048,
        top_p=1
        )


    qa_from_text = json.loads(response.choices[0].message.content)
    
    questions = [f"{key}: {value}" for i, qa in enumerate(qa_from_text.get("INTERVIEW QUESTIONS & ANSWERS", []), 1) for key, value in qa.items() if "Question" in key]
    generated_questions.append(questions)

    answers = [f"{key}: {value}" for i, qa in enumerate(qa_from_text.get("INTERVIEW QUESTIONS & ANSWERS", []), 1) for key, value in qa.items() if "Answer" in key]
    generated_answers.append(answers)
    last_generate_text_time = datetime.now()
    
    return qa_from_text



"""
                                    FILE OF JOB DESCRIPTION
"""

def extract_text_from_pdf(file_content):
    text = ""
    try:
        # Open the PDF from file content
        pdf_document = fitz.open(stream=io.BytesIO(file_content), filetype="pdf")

        # Iterate over each page
        for page_number in range(pdf_document.page_count):
            page = pdf_document[page_number]

            # Extract text from the page
            text += page.get_text()

        # Close the PDF file
        pdf_document.close()
    except Exception as e:
        print(f"Error extracting text: {e}")

    return text

def extract_text_from_docx(file_content):
    doc = Document(io.BytesIO(file_content))
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

def extract_text_from_doc(file_content):
    text = ""
    try:
        # Open the document from file content
        # Extracting text from DOC files using PyMuPDF
        doc = fitz.open(stream=io.BytesIO(file_content), filetype="doc")
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        print(f"Error extracting text from DOC: {e}")

    return text

@app.post("/generate-question-answer-from-file")
async def extract_text(file: List[UploadFile] = File(...)):
    global qa_from_file, last_generate_file_time
    files=file
    text = ""
    for file in files:
        file_content = await file.read()

        # Extract text based on file type
        if file.filename.endswith('.pdf'):
            text += extract_text_from_pdf(file_content)
        elif file.filename.endswith('.docx'):
            text += extract_text_from_docx(file_content)
        elif file.filename.endswith('.doc'):
            text += extract_text_from_doc(file_content)
        else:
            raise HTTPException(status_code=401, detail="Unsupported file format")
    
    print("Extracted Text:", text)
    if not text.strip():  # Improved check for empty text
        print('Empty file detected')
        raise HTTPException(status_code=400, detail="The attached file is empty. Please try another file.")
    # Extract the job title from the job description text
    job_title = extract_job_title(text)

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        response_format={ "type": "json_object" },
        messages=[
            {
            "role": "system",
            "content": "You are a interviewer evaluating a candidate for the job position. Your job is to ask technical and conceptual questions. Do not repeat the question. For each question, also provide a short insightful answer.Output should be a json."
            },
            {
            "role": "user",
            "content": f"""Generate a json with the title "INTERVIEW QUESTIONS & ANSWERS" containing the Questions and Answers. The overall format should be:\n
            {{
            "Job_Title": "{job_title}",
            "INTERVIEW QUESTIONS & ANSWERS": [
                {{
                "Question 1": "model generated question",
                Answer 1: "model generated answer"
                }},
                {{
                "Question 2": "model generated question",
                "Answer 2": "model generated answer"
                }}
            ]
            }}\n
            Generate 4 technical interview questions based on the provided job description information.Each time generate different questions from the provided job description\n
            Job_description: {text}"""
            }
        ],
        temperature=0.2,
        max_tokens=1024,
        top_p=1
        )


    
    qa_from_file =json.loads(response.choices[0].message.content)

    questions= [f"{key}: {value}" for i, qa in enumerate(qa_from_file["INTERVIEW QUESTIONS & ANSWERS"], 1) for key, value in qa.items() if "Question" in key]
    generated_questions.append(questions)

    answers= [f"{key}: {value}" for i, qa in enumerate(qa_from_file["INTERVIEW QUESTIONS & ANSWERS"], 1) for key, value in qa.items() if "Answer" in key]
    generated_answers.append(answers)
    
    last_generate_file_time = datetime.now()
    
    print(qa_from_file)
    return qa_from_file



"""
                           USER RESPONSE IMPROVEMENTS

"""

class QARequest(BaseModel):
    ai_qa_pairs: dict
    user_responses: dict

@app.post("/suggest-improvements-in-user's-response")
async def compare_and_suggest_improvements(request: QARequest):
    ai_qa_pairs = request.ai_qa_pairs
    user_responses = request.user_responses

    if not ai_qa_pairs or not user_responses:
        raise HTTPException(status_code=400, detail="Invalid input")

    ai_qa_pairs_filtered = {k: v for k, v in ai_qa_pairs.items() if v is not None}
    user_responses_filtered = {k: v for k, v in user_responses.items() if v is not None}
    
    # Prepare the messages for the API call
    messages = [
        {
            "role": "system",
            "content": '''You are a helpful technical assistant. You will be given a json file including answers written by the user, you have to compare it with the ai model generated answers and return the strengths and improvements.
            Strengths are the correct points found in user answer and improvements are the improvements required in user answer.'''
        },
        {
            "role": "user",
            "content": f"""
            Output should be a json. Generate a json with the title "Strengths_and_Improvements_in_user_response" containing the strengths and Improvements for each answers. The overall format should be:
            {{
            "Strengths_and_Improvements_in_user_response": [
                {{
                "Strengths_answer_1": "write the strengths you find in user answer_1",
                "Improvements_answer_1": "write the improvements required in user answer_1"
                }},
                {{
                "Strengths_answer_2": "write the strengths you find in user answer_2",
                "Improvements_answer_2": "write the improvements required in user answer_2"
                }},
                .
                .
                .
                {{
                "Strengths_answer_n": "write the strengths you find in user answer_n",
                "Improvements_answer_n": "write the improvements required in user answer_n"
                }}  
            ]
            }},
            "summary": "generate a generic summary of the user capabilities and strengths. Do not mention any correct or wrong answers, instead focus on life lon learning.",
            Model answers: {ai_qa_pairs_filtered}
            User answers: {user_responses_filtered}"""
        }
    ]

    # Debugging purposes
    print(ai_qa_pairs_filtered)
    print(user_responses_filtered)
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            response_format={ "type": "json_object" },
            messages=messages,
            temperature=0.2,
            max_tokens=2048,
            top_p=1
        )

        user_response_improvements = json.loads(response.choices[0].message.content)
        print(f"user_response_improvements = {user_response_improvements}")
        return user_response_improvements
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))






"""
                                      RESUME SUGGESTIONS

"""

def suggest_improvements_in_resume(resume_text,job_description):
  
    # Extract the job title from the job description text
    job_title = extract_job_title(job_description)

    # Set up the model
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        response_format={ "type": "json_object" },
        messages=[
            {
            "role": "system",
            "content": "Evaluate the user's resume based on the provided job description and suggest improvements to enhance the chances of receiving an interview invitation. Please carefully review the resume and provide tailored suggestions and feedback."
            },
            {
            "role": "user",
            "content": f"""Please carefully review the resume and job_description and provide tailored suggestions.\n  
            The output should be in JSON format, structured as follows:\n
            {{
            "Job_Title": "{job_title}",
            "Resume_Desc": "Model generated a 2 to 3 lines description. Highlighting their relevance between job description and resume, and suggesting areas for improvement."
            "Resume_Evaluation": [
            "Match_Percentage_Output": {{
                        "Percentage": "relevance percentage between job description and resume",
                        "key_factors": [
                            "Factor 1",
                            "Factor 2",
                            "Factor 3"
                        ]
                    }},
            "Strength_Weakness":{{
                        "Strength": [
                            "Point 1",
                            "Point 2"
                        ],
                        "Weakness": [
                            "Point 1",
                            "Point 2"
                        ]
                    }},
            "Improvement_Tips_Output": [
                        "Tip 1",
                        "Tip 2",
                        "Tip 3",
                        "Tip 4",
                        "Tip 5"
                    ]
            }}\n\n

            Please provide the necessary details for resume evaluation based on the job description provided.

            Match Percentage Output:
            - Percentage: [Enter the match percentage here, e.g., "50%"]
            - Key Factors: Please list at least 3 key factors supporting the match percentage.

            Strength & Weakness:
            - Strength: Please list at least 2 strengths.
            - Weakness: Please list at least 2 weaknesses.

            Improvement Tips Output: Please provide at least 4 improvement tips.

            Once you have provided all the details, we will generate a JSON structure based on your inputs for resume evaluation.

            Job_description: {job_description}\n\n
            Resume: {resume_text}

            """
            }
        ],
        temperature=0.2,
        max_tokens=1024,
        top_p=1
        )
 

    responses = response.choices[0].message.content
    resume_suggestions = json.loads(responses)
    return resume_suggestions

@app.post("/resume-improvement-suggestions")
async def extract_text(files: List[UploadFile] = File(...), job_description_file: List[UploadFile] = File(...)):
    # job description file and resume file
    
    
    resume_text = ""
    job_description_text= ""

    for file in files:
        file_content = await file.read()
        # Extract text based on file type
        if file.filename.endswith('.pdf'):
            resume_text += extract_text_from_pdf(file_content)
        elif file.filename.endswith('.docx'):
            resume_text += extract_text_from_docx(file_content)
        elif file.filename.endswith('.doc'):
            resume_text+= extract_text_from_doc(file_content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")   

    for file in job_description_file:
        file_content = await file.read()
        # Extract text based on file type
        if file.filename.endswith('.pdf'):
            job_description_text += extract_text_from_pdf(file_content)
        elif file.filename.endswith('.docx'):
            job_description_text += extract_text_from_docx(file_content)
        elif file.filename.endswith('.doc'):
            job_description_text += extract_text_from_doc(file_content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")     
        

    return suggest_improvements_in_resume(resume_text,job_description_text)







"""
                                      AVAILABLE QUESTIONS
"""

@app.get("/available_questions")
def available_questions():
    try:
        if not generated_questions:
            raise ValueError("Please upload the job description first.")
        
        q_str = json.dumps(generated_questions[-1], indent=2)
        q = json.loads(q_str)
        return {"Available Questions": q}
    except Exception as e:
        return {"error": str(e)}

"""
                                      AVAILABLE ANSWERS
"""

@app.get("/available_answers")
def available_answers():
    try:
        if not generated_answers:
            raise ValueError("Please upload the job description first.")
        
        a_str = json.dumps(generated_answers[-1], indent=2)
        a = json.loads(a_str)
        return {"Available Answers": a}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=7000)