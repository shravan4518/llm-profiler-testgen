"""
Flask Web Application for RAG Test Case Generation System

Features:
- Model Training: Document ingestion, framework ingestion, view data, DB status
- Inference: Test case generation and script generation
"""
import sys
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import config
from src.vector_db.vector_store import VectorStore
from src.vector_db.ingestion_pipeline import IngestionPipeline
from src.vector_db.search_engine import HybridSearchEngine
from src.document_processing.loaders import DocumentLoaderFactory
from src.document_processing.code_loader import load_framework_repository
from src.utils.logger import setup_logger
from src.utils.job_manager import JobManager
from src.simple_testgen import SimpleTestGenerator
from src.script_generator import ScriptGenerator
from src.framework_loader import FrameworkLoader
from src.framework_expert import FrameworkExpert

logger = setup_logger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = str(config.DATA_DIR / 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Ensure upload folder exists
Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)

# Initialize components
vector_store = None
ingestion_pipeline = None
search_engine = None
job_manager = None
test_generator = None
script_generator = None
framework_loader = None
framework_expert = None

def init_components():
    """Initialize RAG components"""
    global vector_store, ingestion_pipeline, search_engine, job_manager, test_generator, script_generator, framework_loader, framework_expert
    try:
        vector_store = VectorStore()
        ingestion_pipeline = IngestionPipeline()
        search_engine = HybridSearchEngine(vector_store)
        job_manager = JobManager()
        test_generator = SimpleTestGenerator()
        script_generator = ScriptGenerator(rag_system=search_engine)
        framework_loader = FrameworkLoader()

        # Initialize Framework Expert with Azure OpenAI client
        from openai import AzureOpenAI
        azure_client = AzureOpenAI(
            api_version=config.AZURE_OPENAI_API_VERSION,
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_API_KEY
        )
        framework_expert = FrameworkExpert(azure_client, framework_loader)

        logger.info("Flask app components initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing components: {e}")

# ============================================================================
# HOME ROUTES
# ============================================================================

@app.route('/')
def index():
    """Landing page with two main options"""
    return render_template('index.html')

# ============================================================================
# TRAINING ROUTES (Data Management)
# ============================================================================

@app.route('/training')
def training_dashboard():
    """Training dashboard with all data management features"""
    return render_template('training/dashboard.html')

@app.route('/training/ingest-docs')
def ingest_docs_page():
    """Document ingestion page"""
    supported_formats = config.SUPPORTED_FORMATS
    return render_template('training/ingest_docs.html', supported_formats=supported_formats)

@app.route('/training/upload-document', methods=['POST'])
def upload_document():
    """Handle document upload and ingestion"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in config.SUPPORTED_FORMATS:
            return jsonify({
                'success': False,
                'error': f'Unsupported format. Supported: {", ".join(config.SUPPORTED_FORMATS)}'
            }), 400

        # Save file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        filepath = Path(app.config['UPLOAD_FOLDER']) / unique_filename
        file.save(str(filepath))

        logger.info(f"File saved: {filepath}")

        # Ingest into vector database
        result = ingestion_pipeline.ingest_file(str(filepath))

        # Handle different return types from ingest_file
        if isinstance(result, dict):
            # New ingestion with metadata
            return jsonify({
                'success': True,
                'message': f'Successfully ingested {filename}',
                'filename': filename,
                'chunks': result.get('num_chunks', 0),
                'doc_id': result.get('doc_id', '')
            })
        elif result is True:
            # Document already up-to-date
            return jsonify({
                'success': True,
                'message': f'Document {filename} already up-to-date',
                'filename': filename,
                'skipped': True
            })
        else:
            # Failed ingestion
            return jsonify({
                'success': False,
                'error': 'Failed to ingest document into vector database'
            }), 500

    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/training/ingest-framework')
def ingest_framework_page():
    """Framework code ingestion page"""
    return render_template('training/ingest_framework.html')

@app.route('/training/ingest-framework-path', methods=['POST'])
def ingest_framework_path():
    """Handle framework directory ingestion"""
    try:
        data = request.get_json()
        framework_path = data.get('framework_path')

        if not framework_path:
            return jsonify({'success': False, 'error': 'No path provided'}), 400

        if not Path(framework_path).exists():
            return jsonify({'success': False, 'error': 'Path does not exist'}), 400

        # Load framework files
        documents = load_framework_repository(
            framework_path=framework_path,
            include_patterns=['**/*.py']
        )

        if not documents:
            return jsonify({
                'success': False,
                'error': 'No Python files found in the specified path'
            }), 400

        # Ingest each file
        ingested = []
        failed = []
        skipped = []

        for doc in documents:
            try:
                result = ingestion_pipeline.ingest_file(doc.file_path)

                # Handle different return types from ingest_file
                if isinstance(result, dict):
                    # New ingestion with metadata
                    ingested.append({
                        'filename': doc.filename,
                        'chunks': result.get('num_chunks', 0)
                    })
                elif result is True:
                    # Document already up-to-date (skipped)
                    skipped.append(doc.filename)
                else:
                    # Failed ingestion (result is False or None)
                    failed.append(doc.filename)
            except Exception as e:
                logger.error(f"Error ingesting {doc.filename}: {e}")
                failed.append(doc.filename)

        return jsonify({
            'success': True,
            'ingested': len(ingested),
            'skipped': len(skipped),
            'failed': len(failed),
            'total': len(documents),
            'files': ingested
        })

    except Exception as e:
        logger.error(f"Error ingesting framework: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/training/view-documents')
def view_documents():
    """View all ingested documents"""
    try:
        # Get document registry
        documents = []
        if vector_store and vector_store.doc_registry:
            for doc_id, doc_info in vector_store.doc_registry.items():
                documents.append({
                    'doc_id': doc_id,
                    'filename': doc_info.filename,
                    'file_path': doc_info.file_path,
                    'num_chunks': doc_info.num_chunks,
                    'ingested_at': doc_info.ingested_at,
                    'last_updated': doc_info.last_updated
                })

        # Sort by ingestion date (newest first)
        documents.sort(key=lambda x: x['ingested_at'], reverse=True)

        return render_template('training/view_documents.html', documents=documents)

    except Exception as e:
        logger.error(f"Error viewing documents: {e}")
        return render_template('training/view_documents.html', documents=[], error=str(e))

@app.route('/training/delete-document/<doc_id>', methods=['POST'])
def delete_document(doc_id):
    """Delete a document from vector database"""
    try:
        if vector_store:
            success = vector_store.delete_document(doc_id)
            if success:
                return jsonify({'success': True, 'message': 'Document deleted successfully'})
            else:
                return jsonify({'success': False, 'error': 'Failed to delete document'}), 500
        else:
            return jsonify({'success': False, 'error': 'Vector store not initialized'}), 500
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/training/status')
def vector_db_status():
    """View vector database status and statistics"""
    try:
        stats = {
            'total_documents': 0,
            'total_chunks': 0,
            'index_size': 0,
            'embedding_model': config.EMBED_MODEL_NAME,
            'embedding_dim': config.EMBED_DIM,
            'chunk_size': config.CHUNK_SIZE,
            'supported_formats': config.SUPPORTED_FORMATS
        }

        if vector_store:
            stats['total_documents'] = len(vector_store.doc_registry)
            stats['total_chunks'] = len(vector_store.chunk_metadata)
            stats['index_size'] = vector_store.index.ntotal if vector_store.index else 0

        return render_template('training/status.html', stats=stats)

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return render_template('training/status.html', stats={}, error=str(e))

@app.route('/training/clear-database', methods=['POST'])
def clear_database():
    """Clear all data from vector database"""
    try:
        if vector_store:
            vector_store.clear()
            return jsonify({'success': True, 'message': 'Database cleared successfully'})
        else:
            return jsonify({'success': False, 'error': 'Vector store not initialized'}), 500
    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/training/test-retrieval')
def test_retrieval_page():
    """RAG retrieval testing page"""
    return render_template('training/test_retrieval.html')

@app.route('/api/search', methods=['POST'])
def search():
    """Perform RAG search with different modes"""
    try:
        if not search_engine:
            return jsonify({'error': 'Search engine not initialized'}), 500

        data = request.get_json()
        query = data.get('query', '').strip()
        search_mode = data.get('search_mode', 'hybrid')
        k = data.get('k', config.DEFAULT_TOP_K)
        context_window = data.get('context_window', 1)

        if not query:
            return jsonify({'error': 'Query cannot be empty'}), 400

        logger.info(f"Search request: query='{query}', mode={search_mode}, k={k}")

        # Perform search based on mode
        if search_mode == 'context':
            results = search_engine.search_with_context(
                query=query,
                k=k,
                context_window=context_window
            )
            # Format context results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'doc_id': result['doc_id'],
                    'doc_name': result['doc_name'],
                    'text': result['text'],
                    'chunk_index': result.get('chunk_index', 0),
                    'page_number': result.get('page_number'),
                    'hybrid_score': result['hybrid_score'],
                    'context': result.get('context', [])
                })
        else:
            results = search_engine.search(
                query=query,
                k=k,
                search_mode=search_mode
            )
            # Format standard results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'doc_id': result.chunk_metadata.doc_id,
                    'doc_name': result.chunk_metadata.doc_name,
                    'text': result.chunk_metadata.text,
                    'chunk_index': result.chunk_metadata.chunk_index,
                    'page_number': result.chunk_metadata.page_number,
                    'semantic_score': float(result.semantic_score),
                    'keyword_score': float(result.keyword_score),
                    'hybrid_score': float(result.hybrid_score)
                })

        return jsonify({
            'success': True,
            'query': query,
            'search_mode': search_mode,
            'results': formatted_results,
            'total': len(formatted_results)
        })

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ============================================================================
# INFERENCE ROUTES (Test Case & Script Generation)
# ============================================================================

@app.route('/inference')
def inference_page():
    """Inference page for test case and script generation"""
    return render_template('inference/generate.html')

@app.route('/inference/generate', methods=['POST'])
def generate_test_cases():
    """Generate test cases (placeholder for now)"""
    try:
        data = request.get_json()
        user_prompt = data.get('prompt', '')

        if not user_prompt:
            return jsonify({'success': False, 'error': 'No prompt provided'}), 400

        # TODO: Implement test case generation
        # For now, return placeholder response
        return jsonify({
            'success': True,
            'message': 'Test case generation coming soon!',
            'prompt': user_prompt
        })

    except Exception as e:
        logger.error(f"Error generating test cases: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/api/health')
def health_check():
    """Health check endpoint with system stats"""
    stats = {
        'status': 'healthy',
        'vector_store': vector_store is not None,
        'ingestion_pipeline': ingestion_pipeline is not None,
        'total_documents': 0,
        'total_chunks': 0,
        'index_size': 0,
        'model': config.AZURE_OPENAI_DEPLOYMENT  # Add model name
    }

    if vector_store:
        stats['total_documents'] = len(vector_store.doc_registry)
        stats['total_chunks'] = len(vector_store.chunk_metadata)
        stats['index_size'] = vector_store.index.ntotal if vector_store.index else 0

    return jsonify(stats)

@app.route('/api/generate', methods=['POST'])
def api_generate_test_cases():
    """Generate test cases and create a job"""
    try:
        if not test_generator or not job_manager:
            return jsonify({'success': False, 'error': 'Test generator not initialized'}), 500

        data = request.get_json()
        user_prompt = data.get('user_prompt', '').strip()
        model = data.get('model', 'gpt-4.1-nano')
        output_formats = data.get('output_formats', ['json', 'markdown'])
        use_iteration = data.get('use_iteration', False)
        target_config = data.get('target_config', {})

        if not user_prompt:
            return jsonify({'success': False, 'error': 'User prompt is required'}), 400

        # Create job
        job_id = job_manager.create_job(
            user_prompt=user_prompt,
            model=model,
            parameters={
                'output_formats': output_formats,
                'use_iteration': use_iteration
            },
            target_config=target_config
        )

        logger.info(f"Created job {job_id} for prompt: {user_prompt[:50]}...")

        # Update job status to running
        job_manager.update_job(job_id, status='running')

        # Generate test cases
        try:
            result = test_generator.generate(
                user_prompt=user_prompt,
                output_formats=output_formats
            )

            if result.get('status') == 'success':
                # Update job with results
                job_manager.update_job(
                    job_id=job_id,
                    status='completed',
                    test_cases=result.get('test_cases', ''),
                    test_plan=result.get('test_plan', ''),
                    validation_report=result.get('validation_report', ''),
                    metadata=result.get('metadata', {}),
                    output_files=result.get('output_files', {})
                )

                return jsonify({
                    'success': True,
                    'job_id': job_id,
                    'message': 'Test cases generated successfully',
                    'status': 'completed'
                })
            else:
                # Generation failed
                error_msg = result.get('error', 'Unknown error during generation')
                job_manager.update_job(
                    job_id=job_id,
                    status='failed',
                    error=error_msg
                )

                return jsonify({
                    'success': False,
                    'job_id': job_id,
                    'error': error_msg
                }), 500

        except Exception as e:
            logger.error(f"Error generating test cases for job {job_id}: {e}", exc_info=True)
            job_manager.update_job(
                job_id=job_id,
                status='failed',
                error=str(e)
            )

            return jsonify({
                'success': False,
                'job_id': job_id,
                'error': str(e)
            }), 500

    except Exception as e:
        logger.error(f"Error in generate_test_cases: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/jobs')
def list_jobs():
    """List all jobs"""
    try:
        if not job_manager:
            return jsonify({'success': False, 'error': 'Job manager not initialized'}), 500

        jobs = job_manager.list_jobs(limit=50)
        stats = job_manager.get_stats()

        return jsonify({
            'success': True,
            'jobs': jobs,
            'stats': stats
        })

    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/jobs/<job_id>')
def get_job_details(job_id):
    """Get job details"""
    try:
        if not job_manager:
            return jsonify({'success': False, 'error': 'Job manager not initialized'}), 500

        job = job_manager.get_job(job_id)

        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404

        return jsonify({
            'success': True,
            'job': job
        })

    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/jobs/<job_id>/generate-script', methods=['POST'])
def generate_script_endpoint(job_id):
    """Generate automated test scripts for a job"""
    try:
        if not job_manager or not script_generator:
            return jsonify({'success': False, 'error': 'Services not initialized'}), 500

        job = job_manager.get_job(job_id)

        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404

        if job.get('status') != 'completed':
            return jsonify({'success': False, 'error': 'Job must be completed before generating scripts'}), 400

        if not job.get('test_cases'):
            return jsonify({'success': False, 'error': 'No test cases found in job'}), 400

        # Update script status to generating
        job_manager.update_script_status(job_id, 'generating')

        logger.info(f"Starting script generation for job {job_id}")

        # Generate scripts
        result = script_generator.generate_scripts(
            job_id=job_id,
            test_cases=job.get('test_cases', ''),
            target_config=job.get('target_config', {}),
            user_prompt=job.get('user_prompt', '')
        )

        if result.get('status') == 'success':
            # Update job with script information
            job_manager.update_script_status(
                job_id,
                'generated',
                script_file=result.get('scripts_dir')
            )

            return jsonify({
                'success': True,
                'message': 'Scripts generated successfully',
                'scripts_dir': result.get('scripts_dir'),
                'test_count': result.get('test_count')
            })
        else:
            # Generation failed
            error_msg = result.get('error', 'Unknown error during script generation')
            job_manager.update_script_status(
                job_id,
                'failed',
                error=error_msg
            )

            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    except Exception as e:
        logger.error(f"Error generating script for job {job_id}: {e}")
        job_manager.update_script_status(job_id, 'failed', error=str(e))
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/jobs/<job_id>/script')
def get_script(job_id):
    """Get generated scripts for a job"""
    try:
        if not job_manager:
            return jsonify({'success': False, 'error': 'Job manager not initialized'}), 500

        job = job_manager.get_job(job_id)

        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404

        if job.get('script_status') != 'generated':
            return jsonify({'success': False, 'error': 'Script not generated yet'}), 404

        script_file = job.get('script_file')
        if not script_file or not Path(script_file).exists():
            return jsonify({'success': False, 'error': 'Script files not found'}), 404

        # Check if it's a directory (scripts folder)
        scripts_path = Path(script_file)
        if scripts_path.is_dir():
            # List all Python script files
            script_files = {}
            for file_path in scripts_path.glob('*.py'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    script_files[file_path.name] = f.read()

            # Also include README and requirements
            readme_path = scripts_path / 'README.md'
            if readme_path.exists():
                with open(readme_path, 'r', encoding='utf-8') as f:
                    script_files['README.md'] = f.read()

            requirements_path = scripts_path / 'requirements.txt'
            if requirements_path.exists():
                with open(requirements_path, 'r', encoding='utf-8') as f:
                    script_files['requirements.txt'] = f.read()

            return jsonify({
                'success': True,
                'scripts': script_files,
                'scripts_dir': str(scripts_path),
                'file_count': len(script_files)
            })
        else:
            # Single file (legacy support)
            with open(scripts_path, 'r', encoding='utf-8') as f:
                script_content = f.read()

            return jsonify({
                'success': True,
                'script': script_content,
                'script_file': script_file
            })

    except Exception as e:
        logger.error(f"Error getting script for job {job_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# FRAMEWORK API ROUTES
# ============================================================================

@app.route('/api/framework/files')
def get_framework_files():
    """List all uploaded framework files"""
    try:
        if not framework_loader:
            return jsonify({'success': False, 'error': 'Framework loader not initialized'}), 500

        files = framework_loader.list_uploaded_files()
        return jsonify({
            'success': True,
            'files': files
        })

    except Exception as e:
        logger.error(f"Error listing framework files: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500




@app.route('/api/framework/generate-script', methods=['POST'])
def generate_custom_script():
    """Generate a custom test script using framework context (LLM Expert optimized)"""
    try:
        if not framework_expert:
            return jsonify({'success': False, 'error': 'Framework expert not initialized'}), 500

        data = request.get_json()
        description = data.get('description')
        test_name = data.get('test_name')

        if not description or not test_name:
            return jsonify({'success': False, 'error': 'Description and test name are required'}), 400

        # Use LLM Expert to get optimized, relevant context
        logger.info(f"Getting optimized context for: {description}")
        framework_context = framework_expert.get_relevant_context(description)

        if not framework_context:
            return jsonify({
                'success': False,
                'error': 'Could not generate framework context. Please check framework files.'
            }), 400

        logger.info(f"Context size: {len(framework_context)} chars (~{len(framework_context)//4} tokens)")

        # Generate the script using GPT with optimized framework context
        script = _generate_framework_aware_script(description, test_name, framework_context)

        return jsonify({
            'success': True,
            'script': script
        })

    except Exception as e:
        logger.error(f"Error generating custom script: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/framework/analyze', methods=['POST'])
def analyze_framework():
    """Trigger framework analysis (or re-analysis)"""
    try:
        if not framework_expert:
            return jsonify({'success': False, 'error': 'Framework expert not initialized'}), 500

        data = request.get_json() or {}
        force_reanalysis = data.get('force', False)

        logger.info(f"Starting framework analysis (force={force_reanalysis})...")

        # Run analysis
        knowledge_base = framework_expert.analyze_framework(force_reanalysis=force_reanalysis)

        return jsonify({
            'success': True,
            'message': 'Framework analysis complete',
            'stats': {
                'classes_count': len(knowledge_base.get('classes', {})),
                'patterns_count': len(knowledge_base.get('test_patterns', {})),
                'knowledge_file': str(framework_expert.knowledge_file)
            }
        })

    except Exception as e:
        logger.error(f"Error analyzing framework: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/framework/knowledge-stats')
def get_knowledge_stats():
    """Get statistics about framework knowledge base"""
    try:
        if not framework_expert:
            return jsonify({'success': False, 'error': 'Framework expert not initialized'}), 500

        stats = framework_expert.get_knowledge_stats()

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        logger.error(f"Error getting knowledge stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _generate_framework_aware_script(description: str, test_name: str, framework_context: str) -> str:
    """Generate a test script using framework patterns"""
    from openai import AzureOpenAI

    client = AzureOpenAI(
        api_version=config.AZURE_OPENAI_API_VERSION,
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_API_KEY
    )

    prompt = f"""You are an expert test automation engineer. Generate a complete, production-ready Python test script based on the test case description provided.

IMPORTANT FRAMEWORK CONTEXT:
Below is the framework code and patterns you MUST follow. Study the example test suite (DemoTestSuite) carefully and use the EXACT same patterns, imports, and structure.

{framework_context}

=== TEST CASE TO IMPLEMENT ===
Test Method Name: {test_name}

Test Case Description:
{description}

=== CRITICAL REQUIREMENTS ===

1. IMPORTS - Use the EXACT same imports as shown in DemoTestSuite:
   from REST.REST import RestClient
   from Initialize import *
   from AppAccess import *
   from BrowserActions import *
   from Utils import *
   from Log import *
   from PSRSClient import *
   from ConfigUtils import ConfigUtils
   import sys, time, inspect

2. GLOBAL OBJECT INITIALIZATION (at module level, before the class):
   restObj = None
   token = None
   log = Log()
   initObj = Initialize()
   util = Utils()
   appaccess = AppAccess()
   browser = BrowserActions()
   restObj = RestClient()

3. CLASS STRUCTURE WITH INITIALIZE AND CLEANUP (MANDATORY):
   class <TestClassName>(object):
       ROBOT_LIBRARY_SCOPE = 'GLOBAL'

       def __init__(self):
           pass

       def INITIALIZE(self):
           '''MANDATORY FIRST METHOD - Initialize framework'''
           tc_name = inspect.stack()[0][3]
           try:
               initObj.initialize()
               util.TC_HEADER_FOOTER('Start', tc_name)

               logging.info("Inside Initialize........")
               config = ConfigUtils.getInstance()
               logging.info("ConfigUtils - Value of HOSTNAME..............." + str(config.getConfig('HOSTNAME')))

               util.TC_HEADER_FOOTER('End', tc_name)
           except:
               e = sys.exc_info()[1]
               logging.error("Exception in " + tc_name + "(): " + str(e))
               util.TC_HEADER_FOOTER('End', tc_name)
               raise Exception(e)

       def {test_name}(self):
           # Your test method implementation here
           pass

       def SuiteCleanup(self):
           '''MANDATORY LAST METHOD - Cleanup'''
           tc_name = inspect.stack()[0][3]
           input_dict = {{'filename': tc_name}}
           return_dict = {{'status': 1}}

           try:
               log.setloggingconf()
               util.TC_HEADER_FOOTER('Start', tc_name)
               logging.info("Close All Browsers.... ")
               # Cleanup code if needed
               logging.info("Response = " + str(return_dict))
               assert return_dict['status'] == 1, return_dict['value']
           except:
               e = sys.exc_info()[1]
               logging.error("Exception in " + tc_name + "(): " + str(e))
               util.TC_HEADER_FOOTER('End', tc_name)
               raise Exception(e)

           util.TC_HEADER_FOOTER('End', tc_name)

4. TEST METHOD STRUCTURE (MANDATORY):
   def {test_name}(self):
       tc_name = inspect.stack()[0][3]
       input_dict = {{'filename': tc_name}}  # For screenshot on error

       try:
           log.setloggingconf()  # MANDATORY as first line in try block
           util.TC_HEADER_FOOTER('Start', tc_name)

           config = ConfigUtils.getInstance()
           host = str(config.getConfig('HOSTNAME'))

           # Your SIMPLE test logic here
           # Use dict-based parameters (login_dict, return_dict, etc.)
           # Assert return_dict['status'] == 1 after each operation
           # ALWAYS use global objects (appaccess, browser, etc.) - NEVER create new instances

           util.TC_HEADER_FOOTER('End', tc_name)
       except:
           e = sys.exc_info()[1]
           logging.error("Exception in " + tc_name + "(): " + str(e))
           logging.info("Taking screenshot.............")
           browser.capture_webpage_screenshot(input_dict)
           return_dict = browseractions.close_browser_window()  # Use global browseractions
           util.TC_HEADER_FOOTER('End', tc_name)
           raise Exception(e)

5. KEEP IT SIMPLE - Follow DemoTestSuite Examples EXACTLY:
   - For admin login test: Use GEN_002_FUNC_BROWSER_ADMIN_LOGIN pattern
   - For user login test: Use GEN_003_FUNC_BROWSER_USER_LOGIN pattern
   - For REST API test: Use GEN_002_FUNC_GET_ACTIVE_USERS_VIA_REST pattern
   - DO NOT make up complex xpaths or workflows
   - DO NOT create overly complex tests
   - Keep it simple like the examples

6. BROWSER TEST PATTERN (from GEN_002_FUNC_BROWSER_ADMIN_LOGIN):
   login_dict = {{
       "type": "admin",
       "url": "https://" + host + "/admin",
       "username": "admindb",
       "password": "dana123",
   }}
   return_dict = appaccess.login(login_dict)
   assert return_dict['status'] == 1, return_dict['value']

   time.sleep(15)  # Wait for page load

   return_dict = appaccess.logout()
   assert return_dict['status'] == 1, return_dict['value']

   return_dict = browseractions.close_browser_window()
   assert return_dict['status'] == 1, return_dict['value']

7. REST API PATTERN (from GEN_002_FUNC_GET_ACTIVE_USERS_VIA_REST):
   data = {{"username": "admindb", "password": "dana123"}}
   response_details = restObj.rest_login(host, data)
   if response_details["ResponseCode"] == 200:
       token = response_details["ResponseContent"]
   else:
       raise Exception("Rest Login Failed")

   response_details = restObj.get(rest_uri, token)
   if response_details["ResponseCode"] == 200:
       # process response
   else:
       raise Exception("API call failed")

8. IMPORTANT - USE GLOBAL OBJECTS:
   - NEVER write: browseractions = BrowserActions()
   - ALWAYS use the global objects directly: browseractions, browser, appaccess, util, etc.

9. Generate ONLY the Python code, no markdown formatting
10. Include proper comments explaining each step
11. Follow the DemoTestSuite examples as closely as possible - don't reinvent patterns

Generate the complete test script now with INITIALIZE, {test_name}, and SuiteCleanup methods:"""

    try:
        response = client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are an expert test automation engineer specializing in Python test frameworks. Generate clean, production-ready code following framework patterns exactly."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=4000,
            temperature=0.3
        )

        script = response.choices[0].message.content

        # Extract code from markdown if present
        if '```python' in script:
            script = script.split('```python')[1].split('```')[0].strip()
        elif '```' in script:
            script = script.split('```')[1].split('```')[0].strip()

        return script

    except Exception as e:
        logger.error(f"Error calling Azure OpenAI: {e}")
        raise

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("Starting Profiler Agentic Automation Web Application")
    logger.info("=" * 80)

    # Initialize components
    init_components()

    # Run Flask app
    logger.info("Flask app starting on http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
