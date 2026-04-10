import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, JSON, Integer  # Integer kept for StudentAnalysis
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


# ── Prompt Tables ──

class GeneralPrompt(Base):
    __tablename__ = "general_prompt"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False, unique=True)  # e.g. "pdf_to_markdown", "topic_mapping"
    prompt = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TutorPrompt(Base):
    __tablename__ = "tutor_prompt"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)      # same names as general_prompt
    group_id = Column(String, nullable=False)  # references group.id in OpenWebUI DB
    prompt = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Homework Pipeline Tables ──

class TutorHomework(Base):
    __tablename__ = "tutor_homework"

    id = Column(String, primary_key=True, default=generate_uuid)
    group_id = Column(String, nullable=True)   # references group.id in OpenWebUI DB
    model_id = Column(String, nullable=True)   # references model.id in OpenWebUI DB
    question_data = Column(Text, nullable=True)
    answer_data = Column(Text, nullable=True)
    answer_source = Column(String, nullable=True)  # "uploaded" or "ai_generated"
    topic_mapping = Column(JSON, nullable=True)
    question_uploaded_at = Column(DateTime, nullable=True)
    answer_uploaded_at = Column(DateTime, nullable=True)
    topic_mapped_at = Column(DateTime, nullable=True)


# ── Student Conversation Table ──

class StudentConversation(Base):
    __tablename__ = "student_conversation"

    id = Column(String, primary_key=True, default=generate_uuid)
    student_id = Column(String, nullable=False)   # references user.id in OpenWebUI DB
    student_email = Column(String, nullable=True)
    homework_id = Column(String, ForeignKey("tutor_homework.id"), nullable=False)
    conversation_markdown = Column(Text, nullable=True)
    exported_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Student Analysis Tables ──

class StudentAnalysis(Base):
    __tablename__ = "student_analysis"

    id = Column(String, primary_key=True, default=generate_uuid)
    student_id = Column(String, nullable=True)  # references user.id in OpenWebUI DB
    student_email = Column(String, nullable=True)
    homework_id = Column(String, ForeignKey("tutor_homework.id"), nullable=True)
    total_question = Column(Integer, default=0)
    total_attempted = Column(Integer, default=0)
    total_solved = Column(Integer, default=0)
    total_errors = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    topic_performances = relationship("StudentTopicPerformance", back_populates="student_analysis")
    question_evaluations = relationship("StudentQuestionEvaluation", back_populates="student_analysis")


class StudentTopicPerformance(Base):
    __tablename__ = "student_topic_performance"

    id = Column(String, primary_key=True, default=generate_uuid)
    student_analysis_id = Column(String, ForeignKey("student_analysis.id"), nullable=False)
    topic_name = Column(String, nullable=False)
    status = Column(String, nullable=True)  # mastered / needs_practice
    question_tested = Column(Integer, default=0)
    questions_solved = Column(Integer, default=0)
    details = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    student_analysis = relationship("StudentAnalysis", back_populates="topic_performances")


class StudentQuestionEvaluation(Base):
    __tablename__ = "student_question_evaluations"

    id = Column(String, primary_key=True, default=generate_uuid)
    student_analysis_id = Column(String, ForeignKey("student_analysis.id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    attempted = Column(Boolean, default=False)
    solved = Column(Boolean, default=False)
    error_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    student_analysis = relationship("StudentAnalysis", back_populates="question_evaluations")


# ── Other Tables ──

class TutorErrorType(Base):
    """User-defined error types per group.

    data format: [{"name": "Conceptual", "description": "Wrong formula, misunderstood question"}, ...]
    """
    __tablename__ = "tutor_error_type"

    id = Column(String, primary_key=True, default=generate_uuid)
    group_id = Column(String, nullable=False, unique=True)
    data = Column(JSON, nullable=True)  # list of {name, description}
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PipelineJob(Base):
    """Tracks any background pipeline step so the frontend can poll for status."""
    __tablename__ = "pipeline_job"

    id = Column(String, primary_key=True, default=generate_uuid)
    step = Column(String, nullable=False)        # pdf_to_markdown / run_analysis / generate_practice
    homework_id = Column(String, nullable=True)  # may be set by the background worker after creation
    student_id = Column(String, nullable=True)   # run_analysis only: None = all students
    status = Column(String, default="queued")    # queued / running / done / failed
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)


class StudentPracticeAssignment(Base):
    __tablename__ = "student_practice_assignment"

    id = Column(String, primary_key=True, default=generate_uuid)
    student_id = Column(String, nullable=False)
    student_email = Column(String, nullable=True)
    homework_id = Column(String, nullable=False)
    practice_problem_id = Column(String, ForeignKey("tutor_practice_problem.id"), nullable=False)
    assigned_items = Column(JSON, nullable=True)  # subset of problem_items matched to student's weak topics
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TutorPracticeProblem(Base):
    __tablename__ = "tutor_practice_problem"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, nullable=True)  # references user.id in OpenWebUI DB
    homework_id = Column(String, ForeignKey("tutor_homework.id"), nullable=True)
    group_id = Column(String, nullable=True)  # references group.id in OpenWebUI DB
    source = Column(String, nullable=True)  # ai_generated / user_uploaded
    status = Column(String, nullable=True)  # pending / approved / rejected
    version_number = Column(Integer, default=1)
    problem_data = Column(Text, nullable=True)  # generated practice problems in markdown
    problem_items = Column(JSON, nullable=True)  # [{number, text, topics[], hint, answer}] from LLM
    weakness_summary = Column(JSON, nullable=True)  # class weakness snapshot that drove generation
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
