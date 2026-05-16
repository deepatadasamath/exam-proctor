"""
Admin Configuration for ExamProctor Application
"""

from django.contrib import admin
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


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "phone", "institution", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["user__username", "user__email", "institution"]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "created_by", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "code", "description"]


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ["order", "question_text", "correct_option", "marks"]
    ordering = ["order"]


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "subject",
        "duration",
        "total_marks",
        "passing_marks",
        "status",
        "is_practice_mode",
        "created_by",
        "start_time",
    ]
    list_filter = ["status", "is_practice_mode", "subject", "created_at"]
    search_fields = ["title", "description"]
    inlines = [QuestionInline]
    readonly_fields = ["created_at", "updated_at"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["__str__", "exam", "correct_option", "marks", "order"]
    list_filter = ["exam", "marks"]
    search_fields = ["question_text"]


class StudentAnswerInline(admin.TabularInline):
    model = StudentAnswer
    extra = 0
    readonly_fields = ["question", "selected_option", "is_correct", "time_spent"]
    can_delete = False


class ProctoringLogInline(admin.TabularInline):
    model = ProctoringLog
    extra = 0
    readonly_fields = ["alert_type", "severity", "timestamp", "description"]
    can_delete = False


@admin.register(StudentExamAttempt)
class StudentExamAttemptAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "exam",
        "status",
        "score",
        "percentage",
        "total_warnings",
        "start_time",
        "end_time",
    ]
    list_filter = ["status", "start_time"]
    search_fields = ["student__username", "exam__title"]
    readonly_fields = ["start_time", "created_at"]
    inlines = [StudentAnswerInline, ProctoringLogInline]

    def is_passed(self, obj):
        return obj.is_passed()

    is_passed.boolean = True
    is_passed.short_description = "Passed"


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = [
        "attempt",
        "question",
        "selected_option",
        "is_correct",
        "answered_at",
    ]
    list_filter = ["is_correct", "answered_at"]
    readonly_fields = ["answered_at"]


@admin.register(ProctoringLog)
class ProctoringLogAdmin(admin.ModelAdmin):
    list_display = ["attempt", "alert_type", "severity", "timestamp", "is_reviewed"]
    list_filter = ["alert_type", "severity", "is_reviewed", "timestamp"]
    search_fields = ["attempt__student__username", "description"]
    readonly_fields = ["timestamp"]


@admin.register(ExamSettings)
class ExamSettingsAdmin(admin.ModelAdmin):
    list_display = [
        "max_warnings",
        "face_detection_interval",
        "enable_gaze_tracking",
        "enable_tab_detection",
        "auto_submit_on_violation",
    ]
