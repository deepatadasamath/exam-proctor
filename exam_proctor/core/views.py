"""
Views for ExamProctor Application
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import timedelta, datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

from .models import (
    UserProfile,
    Subject,
    Exam,
    Question,
    StudentExamAttempt,
    StudentAnswer,
    ProctoringLog,
    ExamSettings,
)


# ============================================
# Helper Functions
# ============================================


def get_user_profile(user):
    """
    Safely get or create user profile to avoid AttributeError
    """
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": "student", "phone": "", "institution": ""}
    )
    return profile


# ============================================
# Authentication & User Management Views
# ============================================


def home(request):
    """
    Landing page
    """
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    return render(request, "core/home.html")


def custom_login(request):
    """
    Custom login view
    """
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    if request.method == "POST":
        from django.contrib.auth import authenticate

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            # Ensure UserProfile exists (create if not found)
            get_user_profile(user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect("core:dashboard")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "core/login.html")


def custom_register(request):
    """
    User registration with role selection
    """
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            role = request.POST.get("role", "student")
            phone = request.POST.get("phone", "")
            institution = request.POST.get("institution", "")

            UserProfile.objects.create(
                user=user, role=role, phone=phone, institution=institution
            )

            messages.success(request, "Registration successful! Please login.")
            return redirect("core:login")
    else:
        form = UserCreationForm()

    return render(request, "core/register.html", {"form": form})


def custom_logout(request):
    """
    Logout view
    """
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("core:home")


# ============================================
# Dashboard Views
# ============================================


@login_required
def dashboard(request):
    """
    Main dashboard - redirects based on user role
    """
    # Ensure UserProfile exists
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={"role": "student", "phone": "", "institution": ""}
    )
    
    if profile.role == "teacher":
        return redirect("core:teacher_dashboard")
    else:
        return redirect("core:student_dashboard")


@login_required
def teacher_dashboard(request):
    """
    Teacher Dashboard - Overview of created exams and results
    """
    # Get or create teacher's profile
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={"role": "teacher", "phone": "", "institution": ""}
    )
    
    # If user doesn't have teacher role, redirect to dashboard
    if profile.role != "teacher":
        messages.error(request, "Access denied. Teachers only.")
        return redirect("core:dashboard")

    # Get statistics
    my_exams = (
        Exam.objects.filter(created_by=request.user)
        .select_related("subject")
        .order_by("-created_at")
    )
    published_exams = my_exams.filter(status="published").count()
    total_attempts = StudentExamAttempt.objects.filter(exam__in=my_exams).count()
    recent_attempts = (
        StudentExamAttempt.objects.filter(exam__in=my_exams)
        .select_related("student", "exam")
        .order_by("-start_time")[:10]
    )

    # Get attempt counts for each exam
    for exam in my_exams:
        exam.attempt_count = exam.attempts.count()
        exam.pending_questions = exam.questions.count()

    context = {
        "my_exams": my_exams,
        "my_exams_count": my_exams.count(),
        "published_exams": published_exams,
        "total_attempts": total_attempts,
        "recent_attempts": recent_attempts,
        "page_title": "Teacher Dashboard",
    }
    return render(request, "core/teacher_dashboard.html", context)


@login_required
def student_dashboard(request):
    """
    Student Dashboard - Available exams and past attempts
    """
    # Get or create student's profile
    profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={"role": "student", "phone": "", "institution": ""}
    )

    if profile.role != "student":
        messages.error(request, "Access denied. Students only.")
        return redirect("core:dashboard")

    now = timezone.now()

    # Get exams this student has already attempted with their attempt IDs
    attempts = StudentExamAttempt.objects.filter(student=request.user).values(
        "exam_id", "id"
    )

    # Create a mapping of exam_id to attempt_id
    exam_to_attempt = {attempt["exam_id"]: attempt["id"] for attempt in attempts}
    attempted_exam_ids = list(exam_to_attempt.keys())

    # Get all published exams (for better UX - show all with status)
    all_published_exams = (
        Exam.objects.filter(status="published")
        .select_related("subject")
        .order_by("start_time")
    )

    # Add availability status to each exam
    for exam in all_published_exams:
        exam.is_attempted = exam.id in attempted_exam_ids
        exam.is_not_started = exam.start_time > now
        exam.is_expired = exam.end_time < now
        # Available if within time window (even if attempted, to allow retry)
        exam.is_available = not exam.is_not_started and not exam.is_expired
        exam.question_count = exam.questions.count()
        # Add attempt_id if exam was attempted (get most recent attempt)
        exam.attempt_id = exam_to_attempt.get(exam.id)

    # Past attempts
    my_attempts = (
        StudentExamAttempt.objects.filter(student=request.user)
        .select_related("exam", "exam__subject")
        .order_by("-start_time")
    )

    context = {
        "all_exams": all_published_exams,
        "my_attempts": my_attempts,
        "page_title": "Student Dashboard",
    }
    return render(request, "core/student_dashboard.html", context)


# ============================================
# Teacher Views - Exam Management
# ============================================


@login_required
def create_exam(request):
    """
    Create a new exam
    """
    profile = get_user_profile(request.user)
    if profile.role != "teacher":
        messages.error(request, "Access denied.")
        return redirect("core:dashboard")

    if request.method == "POST":
        title = request.POST.get("title")
        subject_id = request.POST.get("subject")
        duration = request.POST.get("duration")
        total_marks = request.POST.get("total_marks", 100)
        passing_marks = request.POST.get("passing_marks")
        start_time = request.POST.get("start_time")
        end_time = request.POST.get("end_time")
        description = request.POST.get("description", "")
        instructions = request.POST.get("instructions", "")
        is_practice = request.POST.get("is_practice_mode") == "on"

        try:
            subject = Subject.objects.get(id=subject_id)

            # Validate duration
            duration = int(duration)
            if duration < 5 or duration > 300:
                messages.error(request, "Duration must be between 5 and 300 minutes.")
                return redirect("core:create_exam")

            # Create exam
            exam = Exam.objects.create(
                title=title,
                subject=subject,
                description=description,
                duration=duration,
                total_marks=int(total_marks),
                passing_marks=int(passing_marks),
                start_time=start_time,
                end_time=end_time,
                instructions=instructions,
                is_practice_mode=is_practice,
                created_by=request.user,
                status="draft",
            )
            messages.success(request, f'Exam "{title}" created successfully!')
            return redirect("core:add_questions", exam_id=exam.id)

        except Subject.DoesNotExist:
            messages.error(request, "Invalid subject.")
        except Exception as e:
            messages.error(request, f"Error creating exam: {str(e)}")

    subjects = Subject.objects.all()
    context = {"subjects": subjects, "page_title": "Create Exam"}
    return render(request, "core/create_exam.html", context)


@login_required
def add_questions(request, exam_id):
    """
    Add questions to an exam
    """
    profile = get_user_profile(request.user)
    if profile.role != "teacher":
        messages.error(request, "Access denied.")
        return redirect("core:dashboard")

    exam = get_object_or_404(Exam, id=exam_id)

    if exam.created_by != request.user:
        messages.error(request, "You can only edit your own exams.")
        return redirect("core:teacher_dashboard")

    if request.method == "POST":
        # Bulk add questions from JSON
        questions_data = json.loads(request.POST.get("questions_data"))

        for q_data in questions_data:
            Question.objects.create(
                exam=exam,
                question_text=q_data["question_text"],
                option_a=q_data["option_a"],
                option_b=q_data["option_b"],
                option_c=q_data["option_c"],
                option_d=q_data["option_d"],
                correct_option=q_data["correct_option"],
                marks=q_data.get("marks", 1),
                order=q_data.get("order", 0),
            )

        messages.success(
            request, f"{len(questions_data)} questions added successfully!"
        )
        return redirect("core:exam_detail", exam_id=exam.id)

    context = {
        "exam": exam,
        "existing_questions": exam.questions.all(),
        "page_title": f"Add Questions - {exam.title}",
    }
    return render(request, "core/add_questions.html", context)


@login_required
def exam_detail(request, exam_id):
    """
    View exam details and questions
    """
    exam = get_object_or_404(Exam, id=exam_id)
    profile = get_user_profile(request.user)

    if profile.role == "teacher":
        if exam.created_by != request.user:
            messages.error(request, "Access denied.")
            return redirect("core:teacher_dashboard")

        attempts = exam.attempts.select_related("student").order_by("-start_time")
        questions = Question.objects.filter(exam=exam).order_by("order")

        context = {
            "exam": exam,
            "questions": questions,
            "attempts": attempts,
            "page_title": exam.title,
        }
        return render(request, "core/exam_detail_teacher.html", context)
    else:
        context = {"exam": exam, "page_title": exam.title}
        return render(request, "core/exam_detail.html", context)


@login_required
def publish_exam(request, exam_id):
    """
    Publish an exam (make it available to students)
    """
    profile = get_user_profile(request.user)
    if profile.role != "teacher":
        return JsonResponse({"error": "Access denied"}, status=403)

    exam = get_object_or_404(Exam, id=exam_id)

    if exam.created_by != request.user:
        return JsonResponse(
            {"error": "You can only publish your own exams"}, status=403
        )

    if exam.questions.count() == 0:
        return JsonResponse(
            {
                "error": "Cannot publish exam with 0 questions. Please add at least one question first.",
                "success": False
            }, 
            status=400
        )

    exam.status = "published"
    exam.save()

    return JsonResponse({
        "success": True, 
        "message": "Exam published successfully! Students can now see and take this exam."
    })


@login_required
def make_exam_available_now(request, exam_id):
    """
    Make exam available now by updating start and end times
    """
    profile = get_user_profile(request.user)
    if profile.role != "teacher":
        return JsonResponse({"error": "Access denied"}, status=403)

    exam = get_object_or_404(Exam, id=exam_id)

    if exam.created_by != request.user:
        return JsonResponse({"error": "You can only modify your own exams"}, status=403)

    # Set start time to now and end time to 7 days from now
    from datetime import timedelta

    now = timezone.now()
    exam.start_time = now - timedelta(minutes=5)  # Start 5 minutes ago
    exam.end_time = now + timedelta(days=7)  # End 7 days from now
    exam.save()

    return JsonResponse(
        {
            "success": True,
            "message": f'Exam is now available until {exam.end_time.strftime("%b %d, %Y %H:%M")}',
        }
    )


@login_required
def edit_exam(request, exam_id):
    """
    Edit an existing exam
    """
    profile = get_user_profile(request.user)
    if profile.role != "teacher":
        messages.error(request, "Access denied.")
        return redirect("core:dashboard")

    exam = get_object_or_404(Exam, id=exam_id)

    if exam.created_by != request.user:
        messages.error(request, "You can only edit your own exams.")
        return redirect("core:teacher_dashboard")

    if request.method == "POST":
        title = request.POST.get("title")
        subject_id = request.POST.get("subject")
        duration = request.POST.get("duration")
        total_marks = request.POST.get("total_marks", 100)
        passing_marks = request.POST.get("passing_marks")
        start_time = request.POST.get("start_time")
        end_time = request.POST.get("end_time")
        description = request.POST.get("description", "")
        instructions = request.POST.get("instructions", "")
        is_practice = request.POST.get("is_practice_mode") == "on"

        try:
            subject = Subject.objects.get(id=subject_id)

            # Validate duration
            duration = int(duration)
            if duration < 5 or duration > 300:
                messages.error(request, "Duration must be between 5 and 300 minutes.")
                return redirect("core:edit_exam", exam_id=exam.id)

            # Update exam
            exam.title = title
            exam.subject = subject
            exam.description = description
            exam.duration = duration
            exam.total_marks = int(total_marks)
            exam.passing_marks = int(passing_marks)
            exam.start_time = start_time
            exam.end_time = end_time
            exam.instructions = instructions
            exam.is_practice_mode = is_practice
            exam.save()

            messages.success(request, f'Exam "{title}" updated successfully!')
            return redirect("core:exam_detail_teacher", exam_id=exam.id)

        except Subject.DoesNotExist:
            messages.error(request, "Invalid subject.")
        except Exception as e:
            messages.error(request, f"Error updating exam: {str(e)}")

    subjects = Subject.objects.all()
    context = {
        "exam": exam,
        "subjects": subjects,
        "page_title": f"Edit Exam - {exam.title}",
    }
    return render(request, "core/edit_exam.html", context)


@require_http_methods(["DELETE"])
@login_required
def delete_exam(request, exam_id):
    """
    Delete an exam
    """
    profile = get_user_profile(request.user)
    if profile.role != "teacher":
        return JsonResponse({"error": "Access denied"}, status=403)

    exam = get_object_or_404(Exam, id=exam_id)

    if exam.created_by != request.user:
        return JsonResponse({"error": "You can only delete your own exams"}, status=403)

    try:
        exam_title = exam.title
        exam.delete()
        return JsonResponse(
            {"success": True, "message": f'Exam "{exam_title}" deleted successfully'}
        )
    except Exception as e:
        return JsonResponse({"error": f"Error deleting exam: {str(e)}"}, status=500)


@login_required
def edit_question(request, question_id):
    """
    Edit an individual question
    """
    profile = get_user_profile(request.user)
    if profile.role != "teacher":
        messages.error(request, "Access denied.")
        return redirect("core:dashboard")

    question = get_object_or_404(Question, id=question_id)

    # Check if user owns the exam
    if question.exam.created_by != request.user:
        messages.error(request, "You can only edit questions in your own exams.")
        return redirect("core:teacher_dashboard")

    if request.method == "POST":
        question.question_text = request.POST.get("question_text")
        question.option_a = request.POST.get("option_a")
        question.option_b = request.POST.get("option_b")
        question.option_c = request.POST.get("option_c")
        question.option_d = request.POST.get("option_d")
        question.correct_option = request.POST.get("correct_option")
        question.marks = int(request.POST.get("marks", 1))
        question.order = int(request.POST.get("order", question.order))
        question.save()

        messages.success(request, "Question updated successfully!")
        return redirect("core:exam_detail_teacher", exam_id=question.exam.id)

    context = {
        "question": question,
        "exam": question.exam,
        "page_title": f"Edit Question {question.order}",
    }
    return render(request, "core/edit_question.html", context)


@require_http_methods(["DELETE"])
@login_required
def delete_question(request, question_id):
    """
    Delete an individual question
    """
    profile = get_user_profile(request.user)
    if profile.role != "teacher":
        return JsonResponse({"error": "Access denied"}, status=403)

    question = get_object_or_404(Question, id=question_id)

    # Check if user owns the exam
    if question.exam.created_by != request.user:
        return JsonResponse(
            {"error": "You can only delete questions from your own exams"}, status=403
        )

    try:
        exam_id = question.exam.id
        question_order = question.order
        question.delete()

        # Reorder remaining questions
        remaining_questions = Question.objects.filter(exam_id=exam_id).order_by("order")
        for idx, q in enumerate(remaining_questions, start=1):
            q.order = idx
            q.save()

        return JsonResponse(
            {
                "success": True,
                "message": f"Question {question_order} deleted successfully",
            }
        )
    except Exception as e:
        return JsonResponse({"error": f"Error deleting question: {str(e)}"}, status=500)


@login_required
def create_subject(request):
    """
    Create a new subject
    """
    profile = get_user_profile(request.user)
    if profile.role != "teacher":
        messages.error(request, "Access denied.")
        return redirect("core:dashboard")

    if request.method == "POST":
        name = request.POST.get("name")
        code = request.POST.get("code")
        description = request.POST.get("description", "")

        if Subject.objects.filter(code=code).exists():
            messages.error(request, "Subject with this code already exists.")
        else:
            Subject.objects.create(
                name=name, code=code, description=description, created_by=request.user
            )
            messages.success(request, f'Subject "{name}" created successfully!')
            return redirect("core:create_exam")

    return render(request, "core/create_subject.html")


# ============================================
# Student Views - Exam Taking
# ============================================


@login_required
def exam_instructions(request, exam_id):
    """
    Show exam instructions before starting
    """
    profile = get_user_profile(request.user)
    if profile.role != "student":
        messages.error(request, "Access denied.")
        return redirect("core:dashboard")

    exam = get_object_or_404(Exam, id=exam_id)

    # Check if exam is published
    if exam.status != "published":
        messages.error(request, "This exam is not yet published.")
        return redirect("core:student_dashboard")

    # Check if this is a retry (already attempted before)
    previous_attempts = StudentExamAttempt.objects.filter(
        student=request.user, exam=exam
    ).count()
    is_retry = previous_attempts > 0

    now = timezone.now()
    is_active = exam.is_active()
    is_not_started = exam.start_time > now
    is_expired = exam.end_time < now

    context = {
        "exam": exam,
        "is_active": is_active,
        "is_not_started": is_not_started,
        "is_expired": is_expired,
        "is_retry": is_retry,
        "previous_attempts": previous_attempts,
        "page_title": f"Instructions - {exam.title}",
    }
    return render(request, "core/exam_instructions.html", context)


@login_required
def start_exam(request, exam_id):
    """
    Start exam - Create attempt and redirect to exam interface
    Allows multiple attempts (retry functionality)
    """
    profile = get_user_profile(request.user)
    if profile.role != "student":
        return JsonResponse({"error": "Access denied"}, status=403)

    exam = get_object_or_404(Exam, id=exam_id)

    # Check if exam is published
    if exam.status != "published":
        return JsonResponse({"error": "Exam is not published"}, status=400)

    # Check if exam is active (within time window)
    if not exam.is_active():
        now = timezone.now()
        if exam.start_time > now:
            return JsonResponse({"error": "Exam has not started yet"}, status=400)
        else:
            return JsonResponse({"error": "Exam has ended"}, status=400)

    # Note: Removed check for already attempted to allow retries
    # Students can now take the exam multiple times

    # Create new attempt (even if previous attempts exist)
    attempt = StudentExamAttempt.objects.create(
        student=request.user,
        exam=exam,
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    return JsonResponse(
        {
            "success": True,
            "attempt_id": attempt.id,
            "exam_duration": exam.duration * 60,  # Convert to seconds
            "redirect_url": f"/exam/{exam_id}/take/",
        }
    )


@login_required
def take_exam(request, exam_id):
    """
    Main exam interface with proctoring
    """
    profile = get_user_profile(request.user)
    if profile.role != "student":
        messages.error(request, "Access denied.")
        return redirect("core:dashboard")

    exam = get_object_or_404(Exam, id=exam_id)

    # Get or create attempt
    attempt = StudentExamAttempt.objects.filter(
        student=request.user, exam=exam, status="in_progress"
    ).first()

    if not attempt:
        messages.error(request, "No active exam attempt found.")
        return redirect("core:student_dashboard")

    # Check if time is up
    time_elapsed = (timezone.now() - attempt.start_time).total_seconds()
    exam_duration_seconds = exam.duration * 60

    if time_elapsed >= exam_duration_seconds:
        attempt.status = "auto_submitted"
        attempt.end_time = timezone.now()
        attempt.time_taken = int(time_elapsed)
        attempt.save()
        messages.warning(request, "Time is up! Your exam has been auto-submitted.")
        return redirect("core:exam_result", attempt_id=attempt.id)

    questions = exam.questions.all()
    answers = {a.question_id: a.selected_option for a in attempt.answers.all()}

    # Get exam settings
    settings = ExamSettings.objects.first()
    if not settings:
        settings = ExamSettings.objects.create()

    # Prepare settings dictionary for JavaScript (proper JSON serialization)
    settings_dict = {
        "max_warnings": settings.max_warnings,
        "face_detection_interval": settings.face_detection_interval,
        "enable_gaze_tracking": settings.enable_gaze_tracking,
        "enable_tab_detection": settings.enable_tab_detection,
        "warning_cooldown": settings.warning_cooldown,
    }

    context = {
        "exam": exam,
        "attempt": attempt,
        "questions": questions,
        "answers": answers,
        "time_remaining": int(exam_duration_seconds - time_elapsed),
        "is_practice": exam.is_practice_mode,
        "settings": json.dumps(settings_dict),  # Properly serialize to JSON
        "page_title": f"Taking Exam - {exam.title}",
    }
    return render(request, "core/take_exam.html", context)


@login_required
def save_answer(request):
    """
    Save student's answer via AJAX
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    attempt_id = request.POST.get("attempt_id")
    question_id = request.POST.get("question_id")
    selected_option = request.POST.get("selected_option")

    attempt = get_object_or_404(StudentExamAttempt, id=attempt_id)

    if attempt.student != request.user:
        return JsonResponse({"error": "Access denied"}, status=403)

    if attempt.status != "in_progress":
        return JsonResponse({"error": "Exam is not active"}, status=400)

    question = get_object_or_404(Question, id=question_id)

    # Check if question belongs to this exam
    if question.exam != attempt.exam:
        return JsonResponse({"error": "Invalid question"}, status=400)

    # Create or update answer
    answer, created = StudentAnswer.objects.get_or_create(
        attempt=attempt,
        question=question,
        defaults={
            "selected_option": selected_option,
            "is_correct": selected_option == question.correct_option,
        },
    )

    if not created:
        answer.selected_option = selected_option
        answer.is_correct = selected_option == question.correct_option
        answer.save()

    return JsonResponse({"success": True, "is_correct": answer.is_correct})


@login_required
def submit_exam(request, attempt_id):
    """
    Submit exam and calculate results
    """
    attempt = get_object_or_404(StudentExamAttempt, id=attempt_id)

    if attempt.student != request.user:
        messages.error(request, "Access denied.")
        return redirect("core:dashboard")

    if attempt.status != "in_progress":
        messages.warning(request, "This exam has already been submitted.")
        return redirect("core:exam_result", attempt_id=attempt_id)

    # Calculate score
    result = attempt.calculate_score()

    # Update attempt
    attempt.end_time = timezone.now()
    attempt.time_taken = int((attempt.end_time - attempt.start_time).total_seconds())
    attempt.status = "completed"
    attempt.save()

    messages.success(
        request,
        f'Exam submitted successfully! Your score: {result["score"]}/{result["total_marks"]}',
    )
    return redirect("core:exam_result", attempt_id=attempt_id)


@login_required
def exam_result(request, attempt_id):
    """
    Display exam results with detailed analysis
    """
    attempt = get_object_or_404(StudentExamAttempt, id=attempt_id)
    
    profile = get_user_profile(request.user)
    if attempt.student != request.user and profile.role != "teacher":
        messages.error(request, "Access denied.")
        return redirect("core:dashboard")

    # Calculate score if not already calculated
    if not attempt.score:
        attempt.calculate_score()

    answers = attempt.answers.select_related("question")
    proctoring_logs = attempt.proctoring_logs.all()

    is_passed = attempt.is_passed()

    context = {
        "attempt": attempt,
        "answers": answers,
        "proctoring_logs": proctoring_logs,
        "is_passed": is_passed,
        "page_title": f"Results - {attempt.exam.title}",
    }
    return render(request, "core/exam_result.html", context)


# ============================================
# Proctoring API Views
# ============================================


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def log_proctoring_alert(request):
    """
    API endpoint to log proctoring alerts from frontend
    """
    data = json.loads(request.body)
    attempt_id = data.get("attempt_id")
    alert_type = data.get("alert_type")
    description = data.get("description", "")
    severity = data.get("severity", "medium")

    attempt = get_object_or_404(StudentExamAttempt, id=attempt_id)

    if attempt.student != request.user:
        return JsonResponse({"error": "Access denied"}, status=403)

    # Check if exam is still active
    if attempt.status != "in_progress":
        return JsonResponse({"error": "Exam is not active"}, status=400)

    # Check cooldown (prevent spam)
    last_log = (
        ProctoringLog.objects.filter(attempt=attempt, alert_type=alert_type)
        .order_by("-timestamp")
        .first()
    )

    settings = ExamSettings.objects.first()
    if settings and last_log:
        cooldown_seconds = settings.warning_cooldown
        time_since_last = (timezone.now() - last_log.timestamp).total_seconds()
        if time_since_last < cooldown_seconds:
            return JsonResponse({"success": True, "cooldown": True})

    # Create log
    log = ProctoringLog.objects.create(
        attempt=attempt,
        alert_type=alert_type,
        severity=severity,
        description=description,
        ip_address=get_client_ip(request),
    )

    # Update warning count
    attempt.total_warnings = attempt.proctoring_logs.count()
    attempt.save()

    response_data = {
        "success": True,
        "log_id": log.id,
        "total_warnings": attempt.total_warnings,
        "auto_submit": False,
    }

    # Check if max warnings reached
    if settings and attempt.total_warnings >= settings.max_warnings:
        if settings.auto_submit_on_violation:
            attempt.status = "flagged"
            attempt.end_time = timezone.now()
            attempt.time_taken = int(
                (attempt.end_time - attempt.start_time).total_seconds()
            )
            attempt.save()

            # Calculate score
            attempt.calculate_score()

            response_data["auto_submit"] = True
            response_data["redirect_url"] = f"/result/{attempt.id}/"

    return JsonResponse(response_data)


@login_required
def get_proctoring_logs(request, attempt_id):
    """
    Get proctoring logs for an attempt
    """
    attempt = get_object_or_404(StudentExamAttempt, id=attempt_id)

    profile = get_user_profile(request.user)
    if attempt.student != request.user and profile.role != "teacher":
        return JsonResponse({"error": "Access denied"}, status=403)

    logs = attempt.proctoring_logs.values(
        "alert_type", "severity", "timestamp", "description"
    ).order_by("-timestamp")

    return JsonResponse({"logs": list(logs)})


# ============================================
# Utility Functions
# ============================================


def get_client_ip(request):
    """
    Get client IP address
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip
