#!/usr/bin/env python
"""
create_test_fixtures.py — Generate test_resume.pdf for CareerCraft AI E2E tests.

Run once before the E2E test suite:
    python tests/fixtures/create_test_fixtures.py

Creates tests/fixtures/test_resume.pdf with realistic candidate data.
"""
from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH = FIXTURES_DIR / "test_resume.pdf"

CANDIDATE = {
    "name": "Preetham Raj",
    "email": "preetham.raj@email.com",
    "phone": "+91 98765 43210",
    "location": "Bengaluru, India",
    "linkedin": "linkedin.com/in/preethamraj",
    "github": "github.com/preethamraj",
    "summary": (
        "AI/ML Engineer with 5+ years of experience building production-grade "
        "machine learning systems and NLP pipelines. Expert in Python, FastAPI, "
        "LangChain, and cloud infrastructure (AWS/GCP). Delivered 3 enterprise "
        "chatbot systems serving 50k+ daily users. Strong background in "
        "distributed systems, PostgreSQL, Redis, and Docker/Kubernetes."
    ),
    "skills": [
        "Python", "FastAPI", "LangChain", "LangGraph", "PostgreSQL",
        "Redis", "Docker", "Kubernetes", "AWS (ECS, S3, Lambda, Bedrock)",
        "GCP", "PyTorch", "TensorFlow", "scikit-learn", "pandas", "NumPy",
        "REST APIs", "GraphQL", "gRPC", "CI/CD (GitHub Actions)",
        "Vector Databases (pgvector, Pinecone)", "RAG Systems",
        "LLMOps", "Prompt Engineering", "Agents (LangGraph/CrewAI)",
    ],
    "experience": [
        {
            "title": "Senior AI/ML Engineer",
            "company": "TechCorp Innovations",
            "location": "Bengaluru, India",
            "dates": "Jan 2023 – Present",
            "bullets": [
                "Architected and deployed a multi-agent RAG system using LangGraph "
                "and FastAPI, handling 50k+ daily queries with sub-500ms latency.",
                "Built an AI-powered job search platform with 15 LangGraph agents — "
                "resume optimization, cover letter generation, interview coaching, "
                "email outreach, and salary intelligence.",
                "Designed pgvector-based semantic search pipeline indexing 100k+ documents "
                "with HNSW indexing, achieving 95%+ recall@10.",
                "Led migration from monolithic Django to microservices architecture "
                "using FastAPI, reducing deployment time from 45min to 3min.",
                "Implemented comprehensive observability with OpenTelemetry, Grafana, "
                "and structured logging — reduced MTTR by 60%.",
            ],
        },
        {
            "title": "ML Engineer",
            "company": "DataFlow Systems",
            "location": "Hyderabad, India",
            "dates": "Jun 2021 – Dec 2022",
            "bullets": [
                "Developed NLP pipeline for document classification and entity extraction "
                "using transformer models (BERT, RoBERTa), achieving 92% F1 score.",
                "Built REST API microservices with FastAPI serving ML models at 10k RPM, "
                "with Redis caching reducing inference latency by 40%.",
                "Implemented CI/CD pipeline with GitHub Actions and Docker, automating "
                "model training, evaluation, and deployment to AWS ECS.",
                "Created real-time anomaly detection system processing 1M+ events/day "
                "with sub-second alerting using Redis Streams.",
            ],
        },
        {
            "title": "Junior Data Scientist",
            "company": "StartupML",
            "location": "Remote, India",
            "dates": "Jul 2019 – May 2021",
            "bullets": [
                "Built customer churn prediction model using XGBoost and feature engineering, "
                "improving retention by 18% and saving $2M annually.",
                "Developed interactive dashboards with Streamlit for stakeholder visualization "
                "of ML model performance metrics and business KPIs.",
                "Automated ETL pipelines processing 500GB+ daily using Python, Apache Airflow, "
                "and PostgreSQL — reduced manual data processing by 85%.",
            ],
        },
    ],
    "education": [
        {
            "degree": "B.Tech in Computer Science & Engineering",
            "school": "Indian Institute of Technology (IIT), Madras",
            "year": "2019",
            "gpa": "8.7/10",
        },
    ],
    "certifications": [
        "AWS Solutions Architect Associate",
        "Google Cloud Professional ML Engineer",
        "Deep Learning Specialization — deeplearning.ai (Coursera)",
    ],
    "projects": [
        {
            "name": "CareerCraft AI Platform",
            "tech": "Python, FastAPI, LangGraph, pgvector, Supabase",
            "description": (
                "End-to-end job search automation platform with 15 AI agents. "
                "Features: resume optimization, cover letter generation, interview "
                "coaching, Gmail integration, company research, salary intelligence, "
                "and one-click job application via browser automation."
            ),
        },
        {
            "name": "Multi-Agent Customer Support Bot",
            "tech": "LangChain, LangGraph, FastAPI, PostgreSQL, Redis",
            "description": (
                "Designed a supervisor-worker agent system with 8 specialized agents "
                "handling billing, technical support, and account management. "
                "Reduced support ticket resolution time by 65%."
            ),
        },
    ],
}


def create_resume_pdf(output_path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        HRFlowable,
        ListFlowable,
        ListItem,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=4,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#16213e"),
        spaceBefore=12,
        spaceAfter=4,
        borderPadding=(0, 0, 1, 0),
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#0f3460"),
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        spaceAfter=3,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=body_style,
        leftIndent=18,
        bulletIndent=6,
        spaceBefore=1,
        spaceAfter=1,
    )

    story = []

    # Header
    story.append(Paragraph(CANDIDATE["name"], title_style))
    contact = (
        f"{CANDIDATE['email']} | {CANDIDATE['phone']} | {CANDIDATE['location']}<br/>"
        f"{CANDIDATE['linkedin']} | {CANDIDATE['github']}"
    )
    story.append(Paragraph(contact, body_style))
    story.append(Spacer(1, 6))

    # Summary
    story.append(Paragraph("Professional Summary", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#16213e")))
    story.append(Paragraph(CANDIDATE["summary"], body_style))

    # Skills
    story.append(Paragraph("Technical Skills", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#16213e")))
    story.append(Paragraph(" | ".join(CANDIDATE["skills"]), body_style))

    # Experience
    story.append(Paragraph("Professional Experience", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#16213e")))
    for exp in CANDIDATE["experience"]:
        header = (
            f"<b>{exp['title']}</b> — {exp['company']}, {exp['location']}"
            f"<br/><i>{exp['dates']}</i>"
        )
        story.append(Paragraph(header, subtitle_style))
        for bullet in exp["bullets"]:
            story.append(Paragraph(f"• {bullet}", bullet_style))

    # Education
    story.append(Paragraph("Education", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#16213e")))
    for edu in CANDIDATE["education"]:
        story.append(Paragraph(
            f"<b>{edu['degree']}</b> — {edu['school']}<br/>"
            f"<i>{edu['year']}</i> | GPA: {edu['gpa']}",
            body_style,
        ))

    # Certifications
    story.append(Paragraph("Certifications", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#16213e")))
    for cert in CANDIDATE["certifications"]:
        story.append(Paragraph(f"• {cert}", bullet_style))

    # Projects
    story.append(Paragraph("Projects", section_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#16213e")))
    for proj in CANDIDATE["projects"]:
        story.append(Paragraph(
            f"<b>{proj['name']}</b> ({proj['tech']})",
            subtitle_style,
        ))
        story.append(Paragraph(proj["description"], body_style))

    doc.build(story)
    print(f"Test resume PDF created: {output_path}")
    print(f"   Candidate: {CANDIDATE['name']}")
    print(f"   Size: {output_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    create_resume_pdf(OUTPUT_PATH)
