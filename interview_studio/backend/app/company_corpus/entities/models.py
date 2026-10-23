from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.entities.base import Timestamped


class Company(Timestamped):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    slogan: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    founded_date: Mapped[date | None] = mapped_column(Date)
    founder: Mapped[str | None] = mapped_column(String(100))
    ceo: Mapped[str | None] = mapped_column(String(100))
    headquarters: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(255))
    employee_count: Mapped[int | None] = mapped_column(Integer)
    vision: Mapped[str | None] = mapped_column(Text)
    core_values: Mapped[str | None] = mapped_column(Text)
    talent_profile: Mapped[str | None] = mapped_column(Text)
    culture: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(String(500))


class Department(Timestamped):
    __tablename__ = "departments"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    main_tasks: Mapped[str | None] = mapped_column(Text)
    goals: Mapped[str | None] = mapped_column(Text)
    required_competencies: Mapped[str | None] = mapped_column(Text)


class Employee(Timestamped):
    __tablename__ = "employees"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    hire_date: Mapped[date | None] = mapped_column(Date)
    position: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str | None] = mapped_column(String(100))
    school: Mapped[str | None] = mapped_column(String(200))
    major: Mapped[str | None] = mapped_column(String(200))
    salary: Mapped[float | None] = mapped_column(Float)
    employment_status: Mapped[str] = mapped_column(String(50), default="ACTIVE")
    main_responsibilities: Mapped[str | None] = mapped_column(Text)


class JobPosting(Timestamped):
    __tablename__ = "job_postings"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    title: Mapped[str] = mapped_column(String(255))
    position_name: Mapped[str | None] = mapped_column(String(255))
    responsibilities: Mapped[str | None] = mapped_column(Text)
    qualifications: Mapped[str | None] = mapped_column(Text)
    preferred_qualifications: Mapped[str | None] = mapped_column(Text)
    required_skills: Mapped[str | None] = mapped_column(Text)
    preferred_skills: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="OPEN")


class QuarterlyPerformance(Timestamped):
    __tablename__ = "quarterly_performance"
    __table_args__ = (UniqueConstraint("company_id", "year", "quarter", name="uq_company_performance_period"),)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    quarter: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[float] = mapped_column(Float)
    operating_profit: Mapped[float | None] = mapped_column(Float)
    net_profit: Mapped[float | None] = mapped_column(Float)
    highlights: Mapped[str | None] = mapped_column(Text)
    risks: Mapped[str | None] = mapped_column(Text)


class Client(Timestamped):
    __tablename__ = "clients"
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    name: Mapped[str] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    contract_amount: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE")
    risk_level: Mapped[str | None] = mapped_column(String(50))
