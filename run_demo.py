import os
import time
from app import create_app, db
from app.models import User, Project, ScraperTask, DataRecord, ExportRecord
from app.services.task_manager import task_manager
from app.services.exporter import Exporter

def run_demo():
    print("=== WebScrape Pro - Programmatic Verification Demo ===")
    
    # 1. Initialize Flask Application Context
    app = create_app('development')
    
    with app.app_context():
        # 2. Retrieve seeded Admin User
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("[Error] Admin user not found. Run run.py first to seed database.")
            return
            
        print(f"[*] Authenticated as system administrator: '{admin.username}'")
        
        # 3. Create a Sandbox Demo Project
        project_name = "Automated Demo Project"
        project = Project.query.filter_by(name=project_name, user_id=admin.id).first()
        if not project:
            project = Project(
                name=project_name,
                description="Demo container built to verify scraping engines and export integrations.",
                user_id=admin.id
            )
            db.session.add(project)
            db.session.commit()
            print(f"[+] Created project container: '{project.name}' (ID: {project.id})")
        else:
            print(f"[*] Using existing project container: '{project.name}' (ID: {project.id})")
            
        # 4. Create and register a Scraper Task
        target_url = "https://quotes.toscrape.com/"
        config = {
            "depth": 1,
            "dynamic": False,  # Using static BeautifulSoup parser for speed and offline stability
            "timeout": 15,
            "rate_limit": 0.5,
            "ignore_robots_txt": True
        }
        
        task = ScraperTask(
            project_id=project.id,
            url=target_url,
            configuration=config,
            status='PENDING'
        )
        db.session.add(task)
        db.session.commit()
        print(f"[+] Scheduled scraper task ID: #{task.id} targeting: {target_url}")
        
        # 5. Launch task via the background Task Manager
        task_manager.start_task(app, task.id)
        print("[*] Task launched in background thread. Monitoring logs...")
        
        # 6. Monitor progress in loop
        last_log_idx = 0
        while True:
            # Reload task state
            db.session.refresh(task)
            
            # Fetch in-memory logs
            logs = task_manager.get_task_logs(task.id)
            if logs:
                if len(logs) > last_log_idx:
                    for line in logs[last_log_idx:]:
                        print(f"   > {line}")
                    last_log_idx = len(logs)
                    
            if task.status in ['COMPLETED', 'FAILED', 'CANCELLED']:
                print(f"[*] Task terminated with status: {task.status}")
                break
                
            time.sleep(1)
            
        # 7. Check if scraped data records were stored
        if task.status == 'COMPLETED':
            records = DataRecord.query.filter_by(task_id=task.id).all()
            print(f"[+] Successfully extracted {len(records)} page dataset.")
            
            # 8. Export dataset to Excel spreadsheet
            export_dir = app.config['EXPORT_DIR']
            export_path = os.path.join(export_dir, f"demo_export_task_{task.id}.xlsx")
            
            print(f"[*] Compiling multi-tab Excel spreadsheet at: {export_path}")
            Exporter.export_to_excel(records, export_path)
            
            # Save export record to DB
            file_size = os.path.getsize(export_path)
            export_rec = ExportRecord(
                project_id=project.id,
                task_id=task.id,
                file_name=f"demo_export_task_{task.id}.xlsx",
                file_path=export_path,
                file_format="EXCEL",
                file_size=file_size
            )
            db.session.add(export_rec)
            db.session.commit()
            
            print(f"[Success] Excel export saved successfully! File size: {round(file_size / 1024, 2)} KB")
        else:
            print(f"[Error] Scraper task failed. Message: {task.error_message}")

if __name__ == '__main__':
    run_demo()
