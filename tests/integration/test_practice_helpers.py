import pytest

from app.models import StudentAnalysis, StudentTopicPerformance, TutorHomework
from app.routers.practice import _aggregate_class_weakness


pytestmark = pytest.mark.integration


def test_aggregate_class_weakness_filters_and_sorts(db_session):
    hw = TutorHomework(id="hw1", group_id="g1", model_id="m1")
    db_session.add(hw)
    db_session.flush()

    a1 = StudentAnalysis(student_id="s1", homework_id="hw1")
    a2 = StudentAnalysis(student_id="s2", homework_id="hw1")
    db_session.add_all([a1, a2])
    db_session.flush()

    db_session.add_all(
        [
            StudentTopicPerformance(student_analysis_id=a1.id, topic_name="Derivatives", status="needs_practice"),
            StudentTopicPerformance(student_analysis_id=a2.id, topic_name="Derivatives", status="needs_practice"),
            StudentTopicPerformance(student_analysis_id=a1.id, topic_name="Limits", status="mastered"),
            StudentTopicPerformance(student_analysis_id=a2.id, topic_name="Limits", status="needs_practice"),
        ]
    )
    db_session.commit()

    weak_topics = _aggregate_class_weakness(db_session, homework_id="hw1", weakness_threshold=0.6)

    assert len(weak_topics) == 1
    assert weak_topics[0]["topic_name"] == "Derivatives"
    assert weak_topics[0]["weakness_rate"] == 1.0


def test_aggregate_class_weakness_returns_empty_when_no_analyses(db_session):
    weak_topics = _aggregate_class_weakness(db_session, homework_id="missing", weakness_threshold=0.5)
    assert weak_topics == []


def test_aggregate_class_weakness_respects_threshold(db_session):
    hw = TutorHomework(id="hw2", group_id="g1", model_id="m1")
    db_session.add(hw)
    db_session.flush()

    a1 = StudentAnalysis(student_id="s1", homework_id="hw2")
    a2 = StudentAnalysis(student_id="s2", homework_id="hw2")
    db_session.add_all([a1, a2])
    db_session.flush()
    db_session.add_all(
        [
            StudentTopicPerformance(student_analysis_id=a1.id, topic_name="Limits", status="needs_practice"),
            StudentTopicPerformance(student_analysis_id=a2.id, topic_name="Limits", status="mastered"),
        ]
    )
    db_session.commit()

    weak_topics = _aggregate_class_weakness(db_session, homework_id="hw2", weakness_threshold=0.8)
    assert weak_topics == []


def test_aggregate_class_weakness_counts_unknown_statuses_toward_total_but_not_weakness(db_session):
    """Topic-performance rows with a status other than 'needs_practice' or
    'mastered' must still count toward the 'total students tested' denominator
    but never toward needs_practice / mastered buckets. This guards against
    regressions if new statuses are introduced upstream."""
    hw = TutorHomework(id="hw-unk", group_id="g1", model_id="m1")
    db_session.add(hw)
    db_session.flush()

    a1 = StudentAnalysis(student_id="s1", homework_id="hw-unk")
    a2 = StudentAnalysis(student_id="s2", homework_id="hw-unk")
    a3 = StudentAnalysis(student_id="s3", homework_id="hw-unk")
    db_session.add_all([a1, a2, a3])
    db_session.flush()

    db_session.add_all([
        StudentTopicPerformance(student_analysis_id=a1.id, topic_name="Limits", status="needs_practice"),
        StudentTopicPerformance(student_analysis_id=a2.id, topic_name="Limits", status="needs_practice"),
        # Unknown/novel status — shouldn't be counted as weak or mastered.
        StudentTopicPerformance(student_analysis_id=a3.id, topic_name="Limits", status="pending_review"),
    ])
    db_session.commit()

    # 2 weak / 3 total = 0.666... (threshold 0.5 → included).
    weak_topics = _aggregate_class_weakness(db_session, homework_id="hw-unk", weakness_threshold=0.5)
    assert len(weak_topics) == 1
    row = weak_topics[0]
    assert row["topic_name"] == "Limits"
    assert row["students_tested"] == 3
    assert row["students_weak"] == 2
    assert row["students_mastered"] == 0
    assert row["weakness_rate"] == round(2 / 3, 3)
