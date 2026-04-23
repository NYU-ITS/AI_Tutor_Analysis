"""PDF report generation for student analysis."""

from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY


def generate_analysis_pdf(analysis_data: dict, homework_name: str = "Homework", creator_email: str = "", model_name: str = "") -> BytesIO:
    """Generate a formatted PDF report from student analysis data.

    Args:
        analysis_data: Dict with student analysis including metrics, evaluations, and topic performances
        homework_name: Name/number of the homework (e.g., "Homework 8", "Assignment 3")
        creator_email: Email of the student/creator
        model_name: Name of the AI model/tutor

    Returns:
        BytesIO object containing the PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)

    # Define styles
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#663399'),  # Purple
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#663399'),  # Purple
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )

    subheader_style = ParagraphStyle(
        'CustomSubHeader',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.black,
        spaceAfter=6,
        spaceBefore=6,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=6
    )

    # Build story
    story = []

    # Header with student info
    student_email = analysis_data.get('student_email', 'Unknown')

    story.append(Paragraph(f"<b>{student_email}</b>", normal_style))
    story.append(Paragraph(homework_name, normal_style))
    story.append(Spacer(1, 0.2*inch))

    # Title
    story.append(Paragraph("Homework Analysis for MathAlly", title_style))

    # Disclaimer
    story.append(Paragraph(
        "<i>Disclaimer : All graphical questions are excluded from this analysis</i>",
        normal_style
    ))
    story.append(Spacer(1, 0.2*inch))

    # Section A: Metrics
    story.append(Paragraph(f"A. Metrics ({homework_name})", header_style))

    # Quantitative metrics
    story.append(Paragraph("1. Quantitative Metrics", subheader_style))

    metrics_data = [
        [f"Total Number of Questions in the {homework_name}", str(analysis_data.get('total_question', 0))],
        ["Total Number of Problems Attempted", str(analysis_data.get('total_attempted', 0))],
        ["Total Number of Problems Solved", str(analysis_data.get('total_solved', 0))],
        ["Total Number of Problems with Errors", str(analysis_data.get('total_errors', 0))],
    ]

    for label, value in metrics_data:
        story.append(Paragraph(f"<b>{label}</b>", normal_style))
        story.append(Paragraph(value, normal_style))

    story.append(Spacer(1, 0.15*inch))

    # Qualitative metrics
    story.append(Paragraph("2. Qualitative Metrics", subheader_style))

    topic_performances = analysis_data.get('topic_performances', [])
    mastered_topics = [tp for tp in topic_performances if tp.get('status') == 'mastered']
    needs_practice_topics = [tp for tp in topic_performances if tp.get('status') == 'needs_practice']

    # Mastered topics
    story.append(Paragraph("<b>Mastered Topics</b>", normal_style))
    story.append(Paragraph(
        "The student has mastered the following topics (all attempted questions for the topic were solved correctly):",
        normal_style
    ))

    if mastered_topics:
        for topic in mastered_topics:
            story.append(Paragraph(f"● {topic['topic_name']}", normal_style))
    else:
        story.append(Paragraph("● None", normal_style))

    story.append(Spacer(1, 0.15*inch))

    # Need more practice topics
    story.append(Paragraph("<b>&quot;Need More Practice&quot; Topics</b>", normal_style))

    if needs_practice_topics:
        for topic in needs_practice_topics:
            story.append(Paragraph(f"● {topic['topic_name']}", normal_style))
    else:
        story.append(Paragraph("● None", normal_style))

    story.append(PageBreak())

    # Section B: Topic-Level Summary
    story.append(Paragraph(f"B. Topic-Level Summary ({homework_name})", header_style))

    if mastered_topics:
        story.append(Paragraph("1. Topics Mastered by Student", subheader_style))
        for topic in mastered_topics:
            story.append(Paragraph(f"<b>{topic['topic_name']}</b>", normal_style))
            story.append(Paragraph(f"Questions Tested: {topic['details']}", normal_style))
            story.append(Paragraph(
                f"Performance: {topic['questions_solved']}/{topic['question_tested']} solved",
                normal_style
            ))
            story.append(Paragraph(f"Details: {topic['details']}", normal_style))
            story.append(Paragraph(f"Reason: {topic['reason']}", normal_style))
            story.append(Spacer(1, 0.1*inch))

    if needs_practice_topics:
        story.append(Paragraph('2. "Need More Practice" Topics', subheader_style))
        for topic in needs_practice_topics:
            story.append(Paragraph(f"<b>{topic['topic_name']}</b>", normal_style))
            story.append(Paragraph(f"Questions Tested: {topic['details']}", normal_style))
            story.append(Paragraph(
                f"Performance: {topic['questions_solved']}/{topic['question_tested']} solved",
                normal_style
            ))
            story.append(Paragraph(f"Details: {topic['details']}", normal_style))
            story.append(Paragraph(f"Reason: {topic['reason']}", normal_style))
            story.append(Spacer(1, 0.1*inch))

    # Footer
    story.append(Spacer(1, 0.2*inch))
    footer_text = (
        "This report was generated from <b>NYU PilotGenAI Application</b> based on chat "
        "interactions with <b>AI Tutor</b> created by <b>{}</b> for "
        "<b>{}</b><br/>"
        "<i>Disclaimer : All graphical questions are excluded from this analysis</i>"
    ).format(creator_email, model_name)
    story.append(Paragraph(footer_text, ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#663399')
    )))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer
