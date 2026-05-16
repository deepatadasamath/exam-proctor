"""
Database Models for ExamProctor Application
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    """
    Extended User Profile to differentiate between Teacher and Student
    """

    ROLE_CHOICES = [
        ("teacher", "Teacher"),
        ("student", "Student"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="student")
    phone = models.CharField(max_length=15, blank=True, null=True)
    institution = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


class Subject(models.Model):
    """
    Subject/Category for Exams
    """

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    code = models.CharField(max_length=20, unique=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="subjects_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"
        ordering = ["code"]


class Exam(models.Model):
    """
    Exam Model - Created by Teachers
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    title = models.CharField(max_length=300)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="exams")
    description = models.TextField(blank=True, null=True)
    duration = models.IntegerField(help_text="Duration in minutes")
    total_marks = models.IntegerField(default=100)
    passing_marks = models.IntegerField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    instructions = models.TextField(
        blank=True, null=True, help_text="Exam instructions for students"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    is_practice_mode = models.BooleanField(
        default=False, help_text="If True, no proctoring and timer"
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="exams_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Exam"
        verbose_name_plural = "Exams"
        ordering = ["-created_at"]

    def is_active(self):
        now = timezone.now()
        return self.status == "published" and self.start_time <= now <= self.end_time

    def question_count(self):
        return self.questions.count()


class Question(models.Model):
    """
    Multiple Choice Questions
    """

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_option = models.CharField(
        max_length=1,
        choices=[
            ("A", "Option A"),
            ("B", "Option B"),
            ("C", "Option C"),
            ("D", "Option D"),
        ],
    )
    marks = models.IntegerField(default=1)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."

    class Meta:
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        ordering = ["exam", "order"]


class StudentExamAttempt(models.Model):
    """
    Track Student Exam Attempts
    """

    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("flagged", "Flagged - Proctoring Violations"),
        ("auto_submitted", "Auto Submitted"),
        ("abandoned", "Abandoned"),
    ]

    student = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="exam_attempts"
    )
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="attempts")
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="in_progress"
    )
    total_warnings = models.IntegerField(default=0)
    time_taken = models.IntegerField(
        null=True, blank=True, help_text="Time taken in seconds"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} - {self.exam.title}"

    class Meta:
        verbose_name = "Student Exam Attempt"
        verbose_name_plural = "Student Exam Attempts"
        ordering = ["-start_time"]
        # unique_together removed to allow retry/re-attempt of exams

    def calculate_score(self):
        """
        Calculate score based on answers
        """
        answers = self.answers.all()
        total_marks = 0
        obtained_marks = 0

        for answer in answers:
            question = answer.question
            total_marks += question.marks
            if answer.selected_option == question.correct_option:
                obtained_marks += question.marks

        self.score = obtained_marks
        self.total_marks = total_marks
        self.percentage = (obtained_marks / total_marks * 100) if total_marks > 0 else 0
        self.save()

        return {
            "score": obtained_marks,
            "total_marks": total_marks,
            "percentage": self.percentage,
        }

    def is_passed(self):
        """
        Check if student passed the exam
        """
        if self.percentage is None:
            return False
        passing_percentage = (self.exam.passing_marks / self.exam.total_marks) * 100
        return self.percentage >= passing_percentage


class StudentAnswer(models.Model):
    """
    Store Student's Answers for Each Question
    """

    attempt = models.ForeignKey(
        StudentExamAttempt, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.CharField(
        max_length=1,
        choices=[
            ("A", "Option A"),
            ("B", "Option B"),
            ("C", "Option C"),
            ("D", "Option D"),
        ],
        blank=True,
        null=True,
    )
    is_correct = models.BooleanField(default=False)
    time_spent = models.IntegerField(
        default=0, help_text="Time spent on this question in seconds"
    )
    answered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.attempt.student.username} - Q{self.question.order}"

    class Meta:
        verbose_name = "Student Answer"
        verbose_name_plural = "Student Answers"
        unique_together = ["attempt", "question"]
        ordering = ["attempt", "question__order"]


class ProctoringLog(models.Model):
    """
    AI Proctoring Logs and Alerts
    """

    ALERT_TYPE_CHOICES = [
        ("no_face", "No Face Detected"),
        ("multiple_faces", "Multiple Faces Detected"),
        ("tab_switch", "Tab Switch Detected"),
        ("no_match", "Face Not Matching"),
        ("suspicious_activity", "Suspicious Activity"),
        ("camera_blocked", "Camera Blocked/ Covered"),
    ]

    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    attempt = models.ForeignKey(
        StudentExamAttempt, on_delete=models.CASCADE, related_name="proctoring_logs"
    )
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES, default="medium"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    snapshot_image = models.ImageField(
        upload_to="exam_snapshots/", blank=True, null=True
    )
    is_reviewed = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.attempt.student.username} - {self.alert_type} - {self.timestamp}"

    class Meta:
        verbose_name = "Proctoring Log"
        verbose_name_plural = "Proctoring Logs"
        ordering = ["-timestamp"]


class ExamSettings(models.Model):
    """
    Global Proctoring Settings
    """

    max_warnings = models.IntegerField(
        default=5, help_text="Maximum warnings before auto-submit"
    )
    face_detection_interval = models.IntegerField(
        default=2, help_text="Face check interval in seconds"
    )
    enable_gaze_tracking = models.BooleanField(default=True)
    enable_tab_detection = models.BooleanField(default=True)
    enable_face_matching = models.BooleanField(
        default=False, help_text="Match face with registration photo"
    )
    auto_submit_on_violation = models.BooleanField(default=True)
    warning_cooldown = models.IntegerField(
        default=10, help_text="Cooldown between warnings in seconds"
    )

    def __str__(self):
        return "Exam Settings"

    class Meta:
        verbose_name = "Exam Settings"
        verbose_name_plural = "Exam Settings"
