from groq import Groq
from PyPDF2 import PdfReader
import re
import os
from io import BytesIO

class InterviewBot:
    def __init__(self, groq_api_key, deepgram_api_key=None):
        self.client = Groq(api_key=groq_api_key)
        self.deepgram_key = deepgram_api_key
        self.model = "mixtral-8x7b-32768"

    def parse_resume(self, file_content, filename):
        """Parse resume from PDF or TXT format"""
        try:
            if filename.lower().endswith('.pdf'):
                pdf_file = BytesIO(file_content)
                pdf_reader = PdfReader(pdf_file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
                return text.strip()
            elif filename.lower().endswith('.txt'):
                return file_content.decode('utf-8', errors='ignore').strip()
            else:
                raise ValueError("Unsupported file format. Please use PDF or TXT.")
        except Exception as e:
            raise Exception(f"Error parsing resume: {str(e)}")

    def generate_questions(self, resume_text, num_questions=5):\n        """Generate interview questions based on resume content"""\n        try:
            prompt = f"""Based on this resume, generate exactly {num_questions} professional interview questions.

Resume:
{resume_text[:2000]}

Generate questions that:
1. Test specific skills mentioned in the resume
2. Explore their past projects and achievements
3. Ask about problem-solving approaches
4. Include behavioral questions
5. Challenge their technical knowledge

Format each question on a new line starting with "Q#: "

Provide exactly {num_questions} questions:"""

            message = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500
            )

            response_text = message.choices[0].message.content
            
            # Extract questions
            questions = []
            lines = response_text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('Q') and ':' in line:
                    question = re.sub(r'^Q\d+:\s*', '', line)
                    if question:
                        questions.append(question)
            
            return questions[:num_questions]
        except Exception as e:
            raise Exception(f"Error generating questions: {str(e)}")

    def evaluate_answer(self, question, answer, resume_text):
        """Evaluate candidate's answer to a question"""
        try:
            prompt = f"""As an expert interview evaluator, score this answer from 1-10.

Question: {question}

Answer: {answer}

Resume context:
{resume_text[:500]}

Provide:
1. Score out of 10
2. Strengths (2-3 bullet points)
3. Areas for Improvement (2-3 bullet points)
4. Brief Feedback

Format as:
SCORE: [number]
STRENGTHS:
- [point]
IMPROVEMENTS:
- [point]
FEEDBACK: [text]"""

            message = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=800
            )

            response_text = message.choices[0].message.content
            
            # Parse response
            evaluation = {
                'score': 5,
                'strengths': [],
                'improvements': [],
                'feedback': response_text
            }
            
            score_match = re.search(r'SCORE:\s*(\d+)', response_text)
            if score_match:
                evaluation['score'] = int(score_match.group(1))
            
            strengths_match = re.search(r'STRENGTHS:\s*([\s\S]*?)(?=IMPROVEMENTS:|$)', response_text)
            if strengths_match:
                strengths_text = strengths_match.group(1)
                evaluation['strengths'] = [s.strip('- ').strip() for s in strengths_text.split('\n') if s.strip().startswith('-')]
            
            improvements_match = re.search(r'IMPROVEMENTS:\s*([\s\S]*?)(?=FEEDBACK:|$)', response_text)
            if improvements_match:
                improvements_text = improvements_match.group(1)
                evaluation['improvements'] = [i.strip('- ').strip() for i in improvements_text.split('\n') if i.strip().startswith('-')]
            
            return evaluation
        except Exception as e:
            raise Exception(f"Error evaluating answer: {str(e)}")

    def generate_summary(self, resume_text, questions, answers, scores):
        """Generate comprehensive interview summary"""
        try:
            avg_score = sum(scores) / len(scores) if scores else 0
            
            interview_transcript = "\n\n".join([
                f"Q{i+1}: {q}\nA{i+1}: {a}\nScore: {s}/10"
                for i, (q, a, s) in enumerate(zip(questions, answers, scores))
            ])
            
            prompt = f"""Provide a comprehensive interview evaluation.

Average Score: {avg_score:.1f}/10
Questions: {len(questions)}

Interview:
{interview_transcript}

Resume:
{resume_text[:500]}

Provide:
1. Overall Assessment
2. Key Strengths (3 points)
3. Areas for Development (3 points)
4. Technical Proficiency (1-10)
5. Communication Skills (1-10)
6. Hiring Recommendation: STRONG YES / YES / MAYBE / NO
7. Next Steps

Be professional and constructive."""

            message = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=2000
            )

            return message.choices[0].message.content
        except Exception as e:
            raise Exception(f"Error generating summary: {str(e)}")

    def get_response(self, user_message, context=""):
        """General conversational response"""
        try:
            prompt = f"""You are a friendly interview coach AI.

User: {user_message}
Context: {context[:200] if context else 'General chat'}

Provide a helpful, encouraging response."""

            message = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500
            )

            return message.choices[0].message.content
        except Exception as e:
            raise Exception(f"Error: {str(e)}")
