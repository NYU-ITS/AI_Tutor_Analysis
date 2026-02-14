from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ── Prompt Tables ──

class GeneralPrompt(Base):
    __tablename__ = "general_prompt"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)  # e.g. "pdf_to_markdown", "topic_mapping"
    prompt = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TutorPrompt(Base):
    __tablename__ = "tutor_prompt"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)      # same names as general_prompt
    group_id = Column(String, nullable=False)  # references group.id in OpenWebUI DB
    prompt = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Homework Pipeline Tables ──

class TutorHomework(Base):
    __tablename__ = "tutor_homework"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(String, nullable=True)   # references group.id in OpenWebUI DB
    model_id = Column(String, nullable=True)   # references model.id in OpenWebUI DB
    question_data = Column(Text, nullable=True)
    answer_data = Column(Text, nullable=True)
    topic_mapping = Column(JSON, nullable=True)
    question_uploaded_at = Column(DateTime, nullable=True)
    answer_uploaded_at = Column(DateTime, nullable=True)
    topic_mapped_at = Column(DateTime, nullable=True)


# ── Student Analysis Tables ──

class StudentAnalysis(Base):
    __tablename__ = "student_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, nullable=True)  # references user.id in OpenWebUI DB
    student_email = Column(String, nullable=True)
    homework_id = Column(Integer, ForeignKey("tutor_homework.id"), nullable=True)
    total_question = Column(Integer, default=0)
    total_attempted = Column(Integer, default=0)
    total_solved = Column(Integer, default=0)
    total_errors = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    topic_performances = relationship("StudentTopicPerformance", back_populates="student_analysis")
    question_evaluations = relationship("StudentQuestionEvaluation", back_populates="student_analysis")


class StudentTopicPerformance(Base):
    __tablename__ = "student_topic_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_analysis_id = Column(Integer, ForeignKey("student_analysis.id"), nullable=False)
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

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_analysis_id = Column(Integer, ForeignKey("student_analysis.id"), nullable=False)
    question_number = Column(Integer, nullable=False)
    attempted = Column(Boolean, default=False)
    solved = Column(Boolean, default=False)
    error_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    student_analysis = relationship("StudentAnalysis", back_populates="question_evaluations")


# ── Other Tables ──

class TutorErrorType(Base):
    __tablename__ = "tutor_error_type"

    id = Column(Integer, primary_key=True, autoincrement=True)
    homework_id = Column(Integer, ForeignKey("tutor_homework.id"), nullable=False)
    data = Column(JSON, nullable=True)


class TutorPracticeProblem(Base):
    __tablename__ = "tutor_practice_problem"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=True)  # references user.id in OpenWebUI DB
    homework_id = Column(Integer, ForeignKey("tutor_homework.id"), nullable=True)
    source = Column(String, nullable=True)  # ai_generated / user_uploaded
    status = Column(String, nullable=True)  # pending / approved
    version_number = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
