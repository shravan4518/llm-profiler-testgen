"""
Job Manager for Test Case Generation
Tracks all test generation jobs with metadata and status
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import uuid

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class JobManager:
    """Manages test case generation jobs"""

    def __init__(self, jobs_dir: Path = None):
        """Initialize job manager"""
        if jobs_dir is None:
            from config import DATA_DIR
            jobs_dir = DATA_DIR / 'jobs'

        self.jobs_dir = Path(jobs_dir)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_file = self.jobs_dir / 'jobs_registry.json'

        # Initialize jobs registry
        if not self.jobs_file.exists():
            self._save_registry({})

    def create_job(
        self,
        user_prompt: str,
        model: str = 'gpt-4.1-nano',
        parameters: Dict = None,
        target_config: Dict = None
    ) -> str:
        """
        Create a new test case generation job

        Args:
            user_prompt: User's feature description
            model: AI model to use
            parameters: Additional parameters

        Returns:
            job_id: Unique job identifier
        """
        job_id = str(uuid.uuid4())[:8]  # Short UUID
        timestamp = datetime.now().isoformat()

        job_data = {
            'job_id': job_id,
            'user_prompt': user_prompt,
            'model': model,
            'parameters': parameters or {},
            'target_config': target_config or {},
            'status': 'pending',
            'created_at': timestamp,
            'updated_at': timestamp,
            'test_cases': None,
            'test_plan': None,
            'validation_report': None,
            'metadata': {},
            'output_files': {},
            'script_status': 'not_generated',  # not_generated, generating, generated, failed
            'script_file': None,
            'script_files': {},  # Will store multiple script files
            'error': None
        }

        # Save job
        job_file = self.jobs_dir / f'{job_id}.json'
        with open(job_file, 'w', encoding='utf-8') as f:
            json.dump(job_data, f, indent=2, ensure_ascii=False)

        # Update registry
        registry = self._load_registry()
        registry[job_id] = {
            'job_id': job_id,
            'user_prompt': user_prompt,
            'model': model,
            'status': 'pending',
            'created_at': timestamp,
            'script_status': 'not_generated'
        }
        self._save_registry(registry)

        logger.info(f"Created job: {job_id} - {user_prompt[:50]}...")
        return job_id

    def update_job(
        self,
        job_id: str,
        status: str = None,
        test_cases: str = None,
        test_plan: str = None,
        validation_report: str = None,
        metadata: Dict = None,
        output_files: Dict = None,
        error: str = None
    ):
        """Update job with generation results"""
        job_file = self.jobs_dir / f'{job_id}.json'

        if not job_file.exists():
            raise ValueError(f"Job not found: {job_id}")

        # Load current job data
        with open(job_file, 'r', encoding='utf-8') as f:
            job_data = json.load(f)

        # Update fields
        if status:
            job_data['status'] = status
        if test_cases:
            job_data['test_cases'] = test_cases
        if test_plan:
            job_data['test_plan'] = test_plan
        if validation_report:
            job_data['validation_report'] = validation_report
        if metadata:
            job_data['metadata'] = metadata
        if output_files:
            job_data['output_files'] = output_files
        if error:
            job_data['error'] = error

        job_data['updated_at'] = datetime.now().isoformat()

        # Save updated job
        with open(job_file, 'w', encoding='utf-8') as f:
            json.dump(job_data, f, indent=2, ensure_ascii=False)

        # Update registry
        registry = self._load_registry()
        if job_id in registry:
            if status:
                registry[job_id]['status'] = status
            registry[job_id]['updated_at'] = job_data['updated_at']
            self._save_registry(registry)

        logger.info(f"Updated job: {job_id} - Status: {status}")

    def update_script_status(
        self,
        job_id: str,
        script_status: str,
        script_file: str = None,
        error: str = None
    ):
        """Update job script generation status"""
        job_file = self.jobs_dir / f'{job_id}.json'

        if not job_file.exists():
            raise ValueError(f"Job not found: {job_id}")

        # Load current job data
        with open(job_file, 'r', encoding='utf-8') as f:
            job_data = json.load(f)

        # Update script fields
        job_data['script_status'] = script_status
        if script_file:
            job_data['script_file'] = script_file
        if error:
            job_data['error'] = error
        job_data['updated_at'] = datetime.now().isoformat()

        # Save updated job
        with open(job_file, 'w', encoding='utf-8') as f:
            json.dump(job_data, f, indent=2, ensure_ascii=False)

        # Update registry
        registry = self._load_registry()
        if job_id in registry:
            registry[job_id]['script_status'] = script_status
            self._save_registry(registry)

        logger.info(f"Updated script status for job {job_id}: {script_status}")

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job details by ID"""
        job_file = self.jobs_dir / f'{job_id}.json'

        if not job_file.exists():
            return None

        with open(job_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def list_jobs(self, limit: int = 50) -> List[Dict]:
        """List all jobs (most recent first)"""
        registry = self._load_registry()

        # Convert to list and sort by created_at (most recent first)
        jobs = list(registry.values())
        jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return jobs[:limit]

    def delete_job(self, job_id: str) -> bool:
        """Delete a job"""
        job_file = self.jobs_dir / f'{job_id}.json'

        if not job_file.exists():
            return False

        # Delete job file
        job_file.unlink()

        # Update registry
        registry = self._load_registry()
        if job_id in registry:
            del registry[job_id]
            self._save_registry(registry)

        logger.info(f"Deleted job: {job_id}")
        return True

    def get_stats(self) -> Dict:
        """Get job statistics"""
        registry = self._load_registry()

        stats = {
            'total_jobs': len(registry),
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
            'scripts_generated': 0
        }

        for job in registry.values():
            status = job.get('status', 'unknown')
            if status == 'pending':
                stats['pending'] += 1
            elif status == 'running':
                stats['running'] += 1
            elif status == 'completed':
                stats['completed'] += 1
            elif status == 'failed':
                stats['failed'] += 1

            if job.get('script_status') == 'generated':
                stats['scripts_generated'] += 1

        return stats

    def _load_registry(self) -> Dict:
        """Load jobs registry"""
        if not self.jobs_file.exists():
            return {}

        with open(self.jobs_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_registry(self, registry: Dict):
        """Save jobs registry"""
        with open(self.jobs_file, 'w', encoding='utf-8') as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
