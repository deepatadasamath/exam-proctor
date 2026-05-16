# 📚 ExamPrep Proctor

An AI-powered online examination platform with real-time proctoring using **face-api.js** for browser-based face detection and monitoring.

## 🌟 Features

### For Teachers
- ✅ Create and manage exams with multiple subjects
- ✅ Add MCQ questions with multiple options
- ✅ Set exam duration, passing marks, and time windows
- ✅ View student results with detailed analytics
- ✅ Review proctoring logs and alerts
- ✅ Practice mode support (no proctoring)

### For Students
- ✅ Browse and take available exams
- ✅ Real-time AI proctoring during exams
- ✅ Instant results with detailed feedback
- ✅ View exam history and performance

### AI Proctoring Features
- 🤖 **Face Detection** - Monitors if student is present
- 👥 **Multiple Face Detection** - Alerts if multiple people detected
- 🔄 **Tab Switch Detection** - Logs when student leaves exam tab
- 📸 **Snapshot Logging** - (Optional) Saves snapshots during violations
- ⚠️ **Warning System** - configurable threshold before auto-submit
- 🎯 **Gaze Tracking** - (Optional) monitors if student looks away

## 🛠️ Tech Stack

- **Backend**: Django 5.0+ (Python)
- **Database**: SQLite (default, can use PostgreSQL/MySQL)
- **Frontend**: HTML, CSS (Bootstrap 5), JavaScript
- **AI/ML**: face-api.js (browser-based face detection)
- **Static Files**: Django's built-in static file handling

## 📋 Requirements

- Python 3.9+
- Django 5.0+
- Modern web browser with webcam support
- Internet connection (for loading face-api.js models from CDN)

## 🚀 Installation & Setup

### 1. Clone/Extract the Project

```bash
cd exam_proctor
```

### 2. Create Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Create Superuser (Optional - for admin access)

```bash
python manage.py createsuperuser
```

### 6. Run the Development Server

```bash
python manage.py runserver
```

### 7. Access the Application

Open your browser and navigate to:
- **Application**: http://127.0.0.1:8000/
- **Admin Panel**: http://127.0.0.1:8000/admin/

## 👥 User Roles

### Teacher Account
1. Register as a **Teacher**
2. Create Subjects (e.g., Mathematics, Physics)
3. Create Exams with questions
4. Publish exams for students
5. View results and proctoring logs

### Student Account
1. Register as a **Student**
2. Browse available exams
3. Read instructions and start exam
4. Complete exam with AI proctoring
5. View instant results

## 📖 Usage Guide

### Creating an Exam (Teacher)

1. Login as Teacher
2. Click "Create Exam"
3. Fill exam details:
   - Title, Subject, Duration
   - Total Marks, Passing Marks
   - Start/End Time
   - Instructions (optional)
4. Add questions:
   - Question text
   - 4 Options (A, B, C, D)
   - Correct option
   - Marks per question
5. Save and Publish

### Taking an Exam (Student)

1. Login as Student
2. Go to Dashboard
3. Click "Start Exam" on available exam
4. **Allow camera access** when prompted
5. Read instructions carefully
6. Click "Start Exam"
7. **Proctoring starts automatically**:
   - Face detected every 2 seconds
   - Tab switching monitored
   - Warnings logged
8. Answer questions
9. Submit exam or wait for timer

## ⚙️ Configuration

### Proctoring Settings

Access via Django Admin at `/admin/core/examsettings/`

| Setting | Default | Description |
|---------|---------|-------------|
| `max_warnings` | 5 | Warnings before auto-submit |
| `face_detection_interval` | 2 | Face check interval (seconds) |
| `enable_gaze_tracking` | True | Enable gaze detection |
| `enable_tab_detection` | True | Enable tab switch detection |
| `auto_submit_on_violation` | True | Auto-submit on max warnings |
| `warning_cooldown` | 10 | Seconds between same-type warnings |

## 🎯 Proctoring Logic

### Frontend (JavaScript)

1. **Camera Initialization**
   ```javascript
   navigator.mediaDevices.getUserMedia({ video: true })
   ```

2. **Face Detection Loop**
   ```javascript
   setInterval(async () => {
       const detections = await faceapi.detectAllFaces(video);
       if (detections.length === 0) {
           logAlert('no_face', 'No face detected');
       } else if (detections.length > 1) {
           logAlert('multiple_faces', 'Multiple faces detected');
       }
   }, 2000);
   ```

3. **Tab Switch Detection**
   ```javascript
   document.addEventListener('visibilitychange', () => {
       if (document.hidden) {
           logAlert('tab_switch', 'Tab switch detected');
       }
   });
   ```

4. **Alert Logging to Server**
   ```javascript
   fetch('/api/proctoring/log/', {
       method: 'POST',
       body: JSON.stringify({
           attempt_id: attemptId,
           alert_type: 'no_face',
           description: 'No face detected'
       })
   });
   ```

### Backend (Django)

```python
@csrf_exempt
def log_proctoring_alert(request):
    data = json.loads(request.body)
    ProctoringLog.objects.create(
        attempt_id=data['attempt_id'],
        alert_type=data['alert_type'],
        description=data['description']
    )

    attempt.total_warnings = attempt.proctoring_logs.count()
    if attempt.total_warnings >= settings.max_warnings:
        attempt.status = 'flagged'
        attempt.save()

    return JsonResponse({'success': True})
```

## 📁 Project Structure

```
exam_proctor/
├── exam_proctor/          # Project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                  # Main application
│   ├── models.py          # Database models
│   ├── views.py           # View functions
│   ├── urls.py            # URL patterns
│   ├── admin.py           # Admin configuration
│   ├── migrations/        # Database migrations
│   ├── templates/core/    # HTML templates
│   │   ├── base.html
│   │   ├── home.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── teacher_dashboard.html
│   │   ├── student_dashboard.html
│   │   ├── create_exam.html
│   │   ├── add_questions.html
│   │   ├── exam_instructions.html
│   │   ├── take_exam.html       # Proctoring interface
│   │   └── exam_result.html
│   └── static/core/       # CSS, JS files
├── media/                 # User uploaded content
│   └── exam_snapshots/    # Proctoring snapshots
├── db.sqlite3            # SQLite database
├── manage.py
└── requirements.txt
```

## 🗄️ Database Models

### User Profile
- User authentication (Django's built-in)
- Role: Teacher/Student
- Phone, Institution

### Subject
- Name, Code, Description
- Created by (Teacher)

### Exam
- Title, Subject (FK)
- Duration, Total Marks, Passing Marks
- Start/End Time
- Status: Draft/Published/Archived
- Practice Mode flag

### Question
- Exam (FK)
- Question Text, Options A-D
- Correct Option
- Marks, Order

### StudentExamAttempt
- Student (FK), Exam (FK)
- Start/End Time
- Score, Percentage
- Status, Total Warnings
- IP Address, User Agent

### StudentAnswer
- Attempt (FK), Question (FK)
- Selected Option
- Is Correct flag

### ProctoringLog
- Attempt (FK)
- Alert Type (no_face, multiple_faces, tab_switch, etc.)
- Severity
- Timestamp, Description
- Snapshot Image (optional)

## 🔐 Security Considerations

1. **CSRF Protection**: All forms use Django's CSRF tokens
2. **Authentication**: Login required for all exam-related pages
3. **Authorization**: Role-based access control (Teacher/Student)
4. **IP Logging**: Student IP addresses logged
5. **Time Tracking**: Exam time tracked server-side
6. **One Attempt Per Exam**: Unique constraint on (student, exam)

## 🌐 Browser Compatibility

| Browser | Status | Notes |
|---------|--------|-------|
| Chrome 90+ | ✅ Full Support | Recommended |
| Firefox 88+ | ✅ Full Support | Good |
| Safari 14+ | ✅ Full Support | May require HTTPS |
| Edge 90+ | ✅ Full Support | Chromium-based |

**Note**: Webcam access requires HTTPS in production (except localhost).

## 🚨 Known Limitations

1. **Face Detection**: Requires good lighting and clear face visibility
2. **Camera Required**: Students must have a working webcam
3. **Internet Required**: face-api.js models loaded from CDN
4. **Browser Compatibility**: Modern browsers only (no IE)
5. **Mobile Support**: Limited (desktop recommended)

## 🔄 Deployment

### Production Checklist

1. **Set DEBUG = False** in `settings.py`
2. **Configure ALLOWED_HOSTS**
3. **Use PostgreSQL/MySQL** instead of SQLite
4. **Set up HTTPS** (required for webcam)
5. **Configure static/media files** (Whitenoise, AWS S3, etc.)
6. **Set up production server** (Gunicorn + Nginx)
7. **Environment variables** for sensitive data

### Static Files (Whitenoise)

```bash
pip install whitenoise
```

Add to `settings.py` MIDDLEWARE:
```python
MIDDLEWARE = [
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # ... other middleware
]
```

## 📝 License

This project is created for educational purposes.

## 👨‍💻 Author

Created as a secure online examination platform with AI-based proctoring.

## 🙏 Acknowledgments

- **face-api.js** - Face detection library
- **Django** - Web framework
- **Bootstrap 5** - UI framework

---

**Note**: This is a demonstration project. For production use, additional security hardening, scalability improvements, and legal compliance checks are recommended.
