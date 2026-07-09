import os
import time
import threading
from datetime import datetime
from app.extensions import db
from app.models import ScraperTask, DataRecord
from app.services.scraper.static_scraper import StaticScraper
from app.services.scraper.dynamic_scraper import DynamicScraper

class ScrapingTaskManager:
    """Manages background thread execution of scraping tasks."""
    
    def __init__(self):
        # Maps task_id -> { "event": threading.Event, "status": str, "logs": list }
        self._active_jobs = {}
        self._lock = threading.Lock()

    def start_task(self, app, task_id):
        """Launches a scraper task in a background thread."""
        with self._lock:
            # Create a cancellation/stop event
            stop_event = threading.Event()
            self._active_jobs[task_id] = {
                "event": stop_event,
                "status": "RUNNING",
                "logs": ["Task initialized."]
            }
            
        thread = threading.Thread(
            target=self._run_worker,
            args=(app, task_id, stop_event),
            daemon=True
        )
        thread.start()
        return True

    def cancel_task(self, task_id):
        """Signals a task to cancel execution."""
        with self._lock:
            if task_id in self._active_jobs:
                self._active_jobs[task_id]["event"].set()
                self._active_jobs[task_id]["status"] = "CANCELLED"
                self._active_jobs[task_id]["logs"].append("Cancellation requested.")
                return True
        return False

    def get_task_logs(self, task_id):
        """Fetches active in-memory log list for a task."""
        with self._lock:
            if task_id in self._active_jobs:
                return self._active_jobs[task_id]["logs"]
        
        # If not active, read from file if log_file_path is set in DB
        return None

    def _log(self, task_id, message, level="INFO"):
        """Logs a message with timestamp to memory and appends to file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        with self._lock:
            if task_id in self._active_jobs:
                self._active_jobs[task_id]["logs"].append(log_entry)
                
        # Write to log file on disk
        log_dir = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'exports', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"task_{task_id}.log")
        
        try:
            with open(log_file, "a") as f:
                f.write(log_entry + "\n")
        except Exception:
            pass

    def _run_worker(self, app, task_id, stop_event):
        """Worker thread entrypoint."""
        # Database operations require application context
        with app.app_context():
            self._log(task_id, f"Worker thread started for Task ID: {task_id}")
            
            task = ScraperTask.query.get(task_id)
            if not task:
                self._log(task_id, "Error: Task not found in database.", "ERROR")
                return

            task.status = "RUNNING"
            task.started_at = datetime.utcnow()
            
            # Setup log path in DB
            log_dir = os.path.join('exports', 'logs')
            task.log_file_path = os.path.join(log_dir, f"task_{task_id}.log")
            db.session.commit()

            try:
                config = task.configuration or {}
                url = task.url
                
                # Check for dynamic rendering flag
                is_dynamic = config.get('dynamic', False)
                self._log(task_id, f"Initializing scraper. Mode: {'Dynamic (Playwright)' if is_dynamic else 'Static (Requests)'}")
                
                # Instantiate scraper
                if is_dynamic:
                    scraper = DynamicScraper(config)
                else:
                    scraper = StaticScraper(config)
                
                # Check cancellation before starting fetch
                if stop_event.is_set():
                    self._finalize_task(task_id, "CANCELLED", "Task cancelled by user.")
                    return
                
                self._log(task_id, f"Scraping URL: {url}")
                
                # Execute Scrape
                success, data, error = scraper.scrape(url)
                
                if stop_event.is_set():
                    self._finalize_task(task_id, "CANCELLED", "Task cancelled by user.")
                    return
                
                if not success:
                    raise Exception(error)
                
                # Save scraped data records
                self._log(task_id, "Scrape successful. Processing results...")
                
                # Create a list of structured records to save
                # We can save separate components or the entire JSON payload
                records_saved = 0
                
                # Extract page records (e.g. products or articles)
                custom_fields = data.get('custom_fields', {})
                
                # Structure: We write a single record containing the parsed payload
                record = DataRecord(
                    task_id=task.id,
                    project_id=task.project_id,
                    url=url,
                    data_content=data
                )
                db.session.add(record)
                records_saved += 1
                
                # Save details log
                self._log(task_id, f"Extracted Headings: {len(data.get('headings', {}).get('h1', []))} h1 tags.")
                self._log(task_id, f"Extracted Paragraphs: {len(data.get('paragraphs', []))}")
                self._log(task_id, f"Extracted Links: {len(data.get('links', []))}")
                self._log(task_id, f"Extracted Table Rows: {sum(len(t['rows']) for t in data.get('tables', []))} rows.")
                self._log(task_id, f"Extracted Images: {len(data.get('media', {}).get('images', []))} images.")
                self._log(task_id, f"Extracted Contact Emails: {len(data.get('contacts', {}).get('emails', []))}")
                
                db.session.commit()
                
                self._finalize_task(task_id, "COMPLETED", total_extracted=records_saved)
                
            except Exception as e:
                self._log(task_id, f"Execution failed: {str(e)}", "ERROR")
                self._finalize_task(task_id, "FAILED", error_message=str(e))

    def _finalize_task(self, task_id, status, error_message=None, total_extracted=0):
        """Updates task state in database and cleans up memory registries."""
        task = ScraperTask.query.get(task_id)
        if task:
            task.status = status
            task.completed_at = datetime.utcnow()
            if error_message:
                task.error_message = error_message
            if total_extracted > 0:
                task.total_extracted = total_extracted
            db.session.commit()
            
        self._log(task_id, f"Task finalized with status: {status}")
        
        # Clean up active cache after brief delay to allow final log fetches
        def cleanup():
            time.sleep(10)
            with self._lock:
                if task_id in self._active_jobs:
                    del self._active_jobs[task_id]
                    
        threading.Thread(target=cleanup, daemon=True).start()

# Global Singleton Manager
task_manager = ScrapingTaskManager()
