from datetime import date
from app.core.database import Base, SessionLocal, engine
from app.core.entity_registry import Company, Department, Employee, JobPosting, QuarterlyPerformance, User

Base.metadata.create_all(engine)
db = SessionLocal()
try:
    user = db.query(User).filter_by(email="temporary@careerfit.local").first() or User(email="temporary@careerfit.local", name="임시 사용자")
    db.add(user); db.flush()
    companies = [("자룡종합상사","종합물류, 해운, 국제무역, 물류 IT"),("한빛테크","AI 플랫폼과 클라우드 서비스"),("그린에너지","친환경 에너지 솔루션")]
    for index,(name,industry) in enumerate(companies):
        company = db.query(Company).filter_by(name=name).first()
        if not company:
            company=Company(name=name,industry=industry,description=f"가상 기업 {name}",talent_profile="문제 해결, 협업, 데이터 기반 의사결정",core_values="고객 중심, 도전, 신뢰"); db.add(company); db.flush()
        if not db.query(Department).filter_by(company_id=company.id).first():
            departments=[]
            for n in range(10 if index==0 else 3):
                dep=Department(company_id=company.id,name=f"{['데이터전략','IT개발','영업','국제물류','경영기획'][n%5]}팀{n+1}",main_tasks="사업 데이터 분석 및 서비스 운영",required_competencies="Python, SQL, 협업"); db.add(dep); departments.append(dep)
            db.flush()
            for n in range(100 if index==0 else 30):
                dep=departments[n % len(departments)]; db.add(Employee(company_id=company.id,department_id=dep.id,name=f"직원{index+1}-{n+1}",hire_date=date(2010+n%15,1,1),position="사원",main_responsibilities="데이터 분석과 물류 운영"))
            for n in range(4): db.add(JobPosting(company_id=company.id,department_id=departments[n%len(departments)].id,title=f"{name} 백엔드 개발자 {n+1}",position_name="백엔드 개발자",required_skills="Python, FastAPI, PostgreSQL",qualifications="협업과 문제 해결 역량"))
            for year in range(2020,2027):
                for quarter in range(1,5): db.add(QuarterlyPerformance(company_id=company.id,year=year,quarter=quarter,revenue=1000000000+year*1000000+quarter*10000000,operating_profit=100000000,net_profit=70000000,highlights="안정적 성장"))
    db.commit()
    print("Seed completed")
finally:
    db.close()
