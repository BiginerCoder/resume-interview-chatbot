from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from bot import InterviewBot
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
app.secret_key = os.getenv('SECRET_KEY', 'dev-key-12345')

# Initialize bot
bot = InterviewBot(
    groq_api_key=os.getenv('GROQ_API_KEY'),
    deepgram_api_key=os.getenv('DEEPGRAM_API_KEY')
)

# Session storage
sessions = {}

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/api/upload-resume', methods=['POST'])
def upload_resume():
    try:
        if 'resume' not in request.files:
            return jsonify({'error': 'No resume file'}), 400
        
        file = request.files['resume']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        file_content = file.read()
        filename = file.filename
        
        resume_text = bot.parse_resume(file_content, filename)
        
        if not resume_text or len(resume_text) < 50:
            return jsonify({'error': 'Resume is empty or too short'}), 400
        
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            'resume': resume_text,
            'current_question_idx': 0,
            'questions': [],
            'answers': [],
            'scores': [],
            'status': 'resume_uploaded',
            'created_at': datetime.now().isoformat()
        }
        
        preview = resume_text[:300] + '...' if len(resume_text) > 300 else resume_text
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'resume_preview': preview,
            'resume_length': len(resume_text),
            'message': 'Resume uploaded successfully!'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-questions', methods=['POST'])
def generate_questions():
    try:
        data = request.json
        session_id = data.get('session_id')
        num_questions = data.get('num_questions', 5)
        
        if session_id not in sessions:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        resume_text = sessions[session_id]['resume']
        
        questions = bot.generate_questions(resume_text, num_questions=num_questions)
        
        if not questions:
            return jsonify({'error': 'Failed to generate questions'}), 500
        
        sessions[session_id]['questions'] = questions
        sessions[session_id]['status'] = 'questions_generated'
        
        return jsonify({
            'success': True,
            'questions': questions,
            'total_questions': len(questions),
            'message': f'Generated {len(questions)} interview questions!'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-question/<session_id>', methods=['GET'])
def get_question(session_id):
    try:
        if session_id not in sessions:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        current_idx = sessions[session_id]['current_question_idx']
        questions = sessions[session_id]['questions']
        
        if not questions:
            return jsonify({'error': 'No questions generated'}), 400
        
        if current_idx >= len(questions):
            return jsonify({
                'success': True,
                'question': None,
                'message': 'All questions completed!',
                'is_complete': True
            }), 200
        
        question = questions[current_idx]
        
        return jsonify({
            'success': True,
            'question': question,
            'question_number': current_idx + 1,
            'total_questions': len(questions),
            'is_last': (current_idx + 1) >= len(questions),
            'progress': ((current_idx + 1) / len(questions)) * 100
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/submit-answer', methods=['POST'])
def submit_answer():
    try:
        data = request.json
        session_id = data.get('session_id')
        answer = data.get('answer', '').strip()
        
        if session_id not in sessions:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        if not answer:
            return jsonify({'error': 'Answer cannot be empty'}), 400
        
        current_idx = sessions[session_id]['current_question_idx']
        questions = sessions[session_id]['questions']
        
        if current_idx >= len(questions):
            return jsonify({'error': 'All questions answered'}), 400
        
        question = questions[current_idx]
        resume = sessions[session_id]['resume']
        
        evaluation = bot.evaluate_answer(question, answer, resume)
        
        sessions[session_id]['answers'].append(answer)
        sessions[session_id]['scores'].append(evaluation['score'])
        sessions[session_id]['current_question_idx'] += 1
        
        return jsonify({
            'success': True,
            'score': evaluation['score'],
            'feedback': evaluation['feedback'],
            'strengths': evaluation.get('strengths', []),
            'improvements': evaluation.get('improvements', []),
            'questions_remaining': len(questions) - sessions[session_id]['current_question_idx']
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/end-interview', methods=['POST'])
def end_interview():
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if session_id not in sessions:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        current_session = sessions[session_id]
        
        if not current_session['answers']:
            return jsonify({'error': 'No answers to evaluate'}), 400
        
        summary = bot.generate_summary(
            current_session['resume'],
            current_session['questions'],
            current_session['answers'],
            current_session['scores']
        )
        
        avg_score = sum(current_session['scores']) / len(current_session['scores']) if current_session['scores'] else 0
        
        sessions[session_id]['status'] = 'completed'
        
        return jsonify({
            'success': True,
            'summary': summary,
            'average_score': round(avg_score, 1),
            'total_questions': len(current_session['questions']),
            'completed_questions': len(current_session['answers']),
            'scores': current_session['scores']
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/session/<session_id>', methods=['GET'])
def get_session(session_id):
    try:
        if session_id not in sessions:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        session = sessions[session_id]
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'status': session['status'],
            'current_question': session['current_question_idx'],
            'total_questions': len(session['questions']),
            'answered_questions': len(session['answers']),
            'average_score': round(sum(session['scores']) / len(session['scores']), 1) if session['scores'] else 0
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return send_file('index.html')

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🎤 RESUME INTERVIEW CHATBOT - SERVER STARTING")
    print("="*60)
    print("\n📍 Open your browser and go to:")
    print("   👉 http://localhost:5000")
    print("\n🔧 API Endpoints:")
    print("   POST /api/upload-resume")
    print("   POST /api/generate-questions")
    print("   GET  /api/get-question/<session_id>")
    print("   POST /api/submit-answer")
    print("   POST /api/end-interview")
    print("\n⚡ Powered by Groq AI (Mixtral-8x7b)")
    print("="*60 + "\n")
    
    app.run(
        debug=True,
        host=os.getenv('HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', 5000))
    )
