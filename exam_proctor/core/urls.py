"""
URL Configuration for Core App
"""

from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    # Authentication
    path("", views.home, name="home"),
    path("login/", views.custom_login, name="login"),
    path("register/", views.custom_register, name="register"),
    path("logout/", views.custom_logout, name="logout"),
    # Dashboard
    path("dashboard/", views.dashboard, name="dashboard"),
    path("teacher/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("student/dashboard/", views.student_dashboard, name="student_dashboard"),
    # Subject Management
    path("teacher/subject/create/", views.create_subject, name="create_subject"),
    # Exam Management (Teacher)
    path("teacher/exam/create/", views.create_exam, name="create_exam"),
    path("teacher/exam/<int:exam_id>/edit/", views.edit_exam, name="edit_exam"),
    path("teacher/exam/<int:exam_id>/delete/", views.delete_exam, name="delete_exam"),
    path(
        "teacher/exam/<int:exam_id>/questions/",
        views.add_questions,
        name="add_questions",
    ),
    path(
        "teacher/exam/<int:exam_id>/detail/",
        views.exam_detail,
        name="exam_detail_teacher",
    ),
    path(
        "teacher/exam/<int:exam_id>/publish/", views.publish_exam, name="publish_exam"
    ),
    path(
        "teacher/exam/<int:exam_id>/make-available/",
        views.make_exam_available_now,
        name="make_exam_available_now",
    ),
    # Question Management
    path(
        "teacher/question/<int:question_id>/edit/",
        views.edit_question,
        name="edit_question",
    ),
    path(
        "teacher/question/<int:question_id>/delete/",
        views.delete_question,
        name="delete_question",
    ),
    # Exam Viewing (Student)
    path("exam/<int:exam_id>/", views.exam_detail, name="exam_detail"),
    path(
        "exam/<int:exam_id>/instructions/",
        views.exam_instructions,
        name="exam_instructions",
    ),
    # Exam Taking
    path("exam/<int:exam_id>/start/", views.start_exam, name="start_exam"),
    path("exam/<int:exam_id>/take/", views.take_exam, name="take_exam"),
    path("exam/save-answer/", views.save_answer, name="save_answer"),
    path("exam/<int:attempt_id>/submit/", views.submit_exam, name="submit_exam"),
    # Results
    path("result/<int:attempt_id>/", views.exam_result, name="exam_result"),
    # Proctoring API
    path(
        "api/proctoring/log/", views.log_proctoring_alert, name="log_proctoring_alert"
    ),
    path(
        "api/proctoring/logs/<int:attempt_id>/",
        views.get_proctoring_logs,
        name="get_proctoring_logs",
    ),
]
