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
domain_expert = None  # New: Domain Expert for conceptual understanding

def init_components():
    """Initialize RAG components"""
    global vector_store, ingestion_pipeline, search_engine, job_manager, test_generator, script_generator, framework_loader, framework_expert, domain_expert
    try:
        vector_store = VectorStore()
        ingestion_pipeline = IngestionPipeline()
        search_engine = HybridSearchEngine(vector_store)
        job_manager = JobManager()
        framework_loader = FrameworkLoader()

        # Initialize Framework Expert and Domain Expert with Azure OpenAI client
        from openai import AzureOpenAI
        from src.domain_expert import DomainExpert

        azure_client = AzureOpenAI(
            api_version=config.AZURE_OPENAI_API_VERSION,
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_API_KEY
        )
        framework_expert = FrameworkExpert(azure_client, framework_loader)

        # Initialize Domain Expert for documentation understanding
        domain_expert = DomainExpert(azure_client)
        logger.info("Domain Expert initialized")

        # Initialize generators with domain expert integration
        test_generator = SimpleTestGenerator(domain_expert=domain_expert)
        script_generator = ScriptGenerator(rag_system=search_engine)

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

@app.route('/training/domain-knowledge')
def domain_knowledge_page():
    """Domain knowledge building page"""
    return render_template('training/domain_knowledge.html')

@app.route('/training/pkg-extraction')
def pkg_extraction_page():
    """PKG extraction page"""
    # Get list of available documents
    docs = []
    if vector_store and vector_store.doc_registry:
        for doc_id, doc_info in vector_store.doc_registry.items():
            docs.append({
                'doc_id': doc_id,
                'name': doc_info.filename,
                'path': doc_info.file_path,
                'pages': getattr(doc_info, 'total_pages', 'N/A'),
                'uploaded_at': doc_info.ingested_at
            })
    return render_template('training/pkg_extraction.html', documents=docs)

@app.route('/api/extract-pkg', methods=['POST'])
def extract_pkg():
    """Extract PKG from document"""
    try:
        data = request.get_json()
        doc_id = data.get('doc_id')
        document_name = data.get('document_name', 'untitled')
        start_page = data.get('start_page', 1)
        end_page = data.get('end_page')

        if not doc_id:
            return jsonify({'success': False, 'error': 'No document selected'}), 400

        # Get document metadata
        if not vector_store or doc_id not in vector_store.doc_registry:
            return jsonify({'success': False, 'error': 'Document not found'}), 404

        doc_info = vector_store.doc_registry[doc_id]
        pdf_path = doc_info.file_path

        if not pdf_path or not Path(pdf_path).exists():
            return jsonify({'success': False, 'error': 'Document file not found'}), 404

        # Set end_page to total pages if not specified
        if not end_page:
            end_page = getattr(doc_info, 'total_pages', 100)

        # Import PKG extraction functions
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from extract_pkg_enhanced import (
            extract_pdf_pages,
            discover_features_with_page_locations,
            extract_images_from_pdf,
            extract_pkg_from_scattered_pages
        )

        # Setup output directory
        output_dir = Path(config.DATA_DIR) / "pkg" / document_name
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting PKG extraction for {doc_id} (pages {start_page}-{end_page})")

        # Step 1: Extract PDF content
        pdf_content = extract_pdf_pages(pdf_path, start_page, end_page)

        # Step 2: Discover features
        feature_discovery = discover_features_with_page_locations(pdf_content)
        features = feature_discovery.get('features', [])

        # Save feature understanding
        feature_file = output_dir / "feature_understanding.json"
        with open(feature_file, 'w', encoding='utf-8') as f:
            json.dump(feature_discovery, f, indent=2, ensure_ascii=False)

        # Step 3: Extract images
        all_page_numbers = list(range(start_page, end_page + 1))
        images = extract_images_from_pdf(pdf_path, all_page_numbers)

        # Step 4: Extract PKG for each feature
        pkg_files = []
        for feature in features:
            feature_name = feature['feature_name']
            feature_id = feature_name.lower().replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')
            page_locations = feature.get('page_locations', [])

            pkg = extract_pkg_from_scattered_pages(
                pdf_path,
                feature_name,
                page_locations,
                images
            )

            # Save PKG
            pkg_file = output_dir / f"pkg_{feature_id}.json"
            with open(pkg_file, 'w', encoding='utf-8') as f:
                json.dump(pkg, f, indent=2, ensure_ascii=False)

            pkg_files.append({
                'feature_name': feature_name,
                'feature_id': feature_id,
                'inputs': len(pkg.get('inputs', [])),
                'constraints': len(pkg.get('constraints', [])),
                'workflows': len(pkg.get('workflows', []))
            })

        return jsonify({
            'success': True,
            'message': f'PKG extraction complete for {len(features)} features',
            'features_count': len(features),
            'images_analyzed': len(images),
            'output_dir': str(output_dir),
            'pkg_files': pkg_files
        })

    except Exception as e:
        logger.error(f"PKG extraction error: {e}", exc_info=True)
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
        'domain_expert': domain_expert is not None,
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

@app.route('/api/domain/analyze', methods=['POST'])
def api_domain_analyze():
    """Trigger domain knowledge building from documentation"""
    try:
        if not domain_expert:
            return jsonify({'success': False, 'error': 'Domain Expert not initialized'}), 500

        data = request.get_json()
        doc_path = data.get('doc_path', '').strip()
        force_rebuild = data.get('force_rebuild', False)

        if not doc_path:
            return jsonify({'success': False, 'error': 'Document path is required'}), 400

        # Check if file exists
        if not Path(doc_path).exists():
            return jsonify({'success': False, 'error': f'Document not found: {doc_path}'}), 404

        logger.info(f"Starting domain analysis for: {doc_path}")

        # Analyze and build concept graph
        # Convert string path to Path object
        from pathlib import Path as PathLib
        doc_path_obj = PathLib(doc_path)

        result = domain_expert.analyze_and_build_concept_graph(
            doc_path=doc_path_obj,
            force_rebuild=force_rebuild
        )

        # Check for both 'success' (new build) and 'ready' (existing knowledge)
        if result.get('status') in ['success', 'ready']:
            return jsonify({
                'success': True,
                'message': 'Domain knowledge built successfully' if result.get('status') == 'success' else 'Domain knowledge already exists',
                'statistics': {
                    'total_concepts': result.get('total_concepts', 0),
                    'total_sub_concepts': sum(
                        len(concept.get('sub_concepts', []))
                        for concept in domain_expert.concept_graph.values()
                    ) if domain_expert.concept_graph else 0,
                    'total_indexed_terms': result.get('total_indexed_terms', 0),
                    'concept_names': list(domain_expert.concept_graph.keys()) if domain_expert.concept_graph else []
                }
            })
        else:
            error_msg = result.get('error', 'Failed to build domain knowledge')
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

    except Exception as e:
        logger.error(f"Error analyzing domain: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/domain/status')
def api_domain_status():
    """Get status of domain knowledge base"""
    try:
        if not domain_expert:
            return jsonify({'success': False, 'error': 'Domain Expert not initialized'}), 500

        # Check if knowledge base exists
        if not domain_expert.knowledge_file.exists():
            return jsonify({
                'success': True,
                'status': 'empty',
                'message': 'No domain knowledge built yet',
                'statistics': {
                    'total_concepts': 0,
                    'total_sub_concepts': 0,
                    'total_relationships': 0
                }
            })

        # Get statistics from concept graph
        total_concepts = len(domain_expert.concept_graph)
        total_sub_concepts = sum(
            len(concept.get('sub_concepts', []))
            for concept in domain_expert.concept_graph.values()
        )
        total_relationships = sum(
            len(concept.get('relationships', []))
            for concept in domain_expert.concept_graph.values()
        )

        return jsonify({
            'success': True,
            'status': 'ready',
            'statistics': {
                'total_concepts': total_concepts,
                'total_sub_concepts': total_sub_concepts,
                'total_relationships': total_relationships,
                'concept_names': list(domain_expert.concept_graph.keys())
            }
        })

    except Exception as e:
        logger.error(f"Error getting domain status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
    """Generate test files using selected framework (PSTAFF or Client) with framework-aware AI generation"""
    try:
        data = request.get_json()
        description = data.get('description')
        test_name = data.get('test_name')
        framework_type = data.get('framework_type', 'pstaff')  # Default to PSTAFF

        if not description or not test_name:
            return jsonify({'success': False, 'error': 'Description and test name are required'}), 400

        logger.info(f"Generating test script with {framework_type} framework")

        # Create framework-specific loader and expert
        from src.framework_loader import FrameworkLoader
        from src.framework_expert import FrameworkExpert
        from src.demo_suite_loader import load_demo_suite
        from openai import AzureOpenAI

        # Initialize framework loader for the selected framework
        temp_framework_loader = FrameworkLoader(framework_type=framework_type)

        # Initialize Azure client
        azure_client = AzureOpenAI(
            api_version=config.AZURE_OPENAI_API_VERSION,
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_API_KEY
        )

        # Initialize framework expert with the specific loader
        temp_framework_expert = FrameworkExpert(azure_client, temp_framework_loader)

        # Get framework-specific context
        logger.info(f"Getting optimized context for {framework_type} framework: {description}")
        framework_context = temp_framework_expert.get_relevant_context(description)

        if not framework_context:
            return jsonify({
                'success': False,
                'error': f'Could not generate {framework_type} framework context. Please check framework files.'
            }), 400

        logger.info(f"Context size: {len(framework_context)} chars (~{len(framework_context)//4} tokens)")

        # Load framework-specific demo suite
        demo_suite = load_demo_suite(framework_type)
        logger.info(f"Loaded {framework_type} demo suite ({len(demo_suite)} chars)")

        # Generate files with framework-specific context and demo
        logger.info("Phase 1: Generating test files with feedback...")
        files = _generate_framework_aware_script(
            description,
            test_name,
            framework_context,
            framework_type=framework_type,
            demo_suite=demo_suite
        )

        # Phase 2: Review generated code for quality assurance
        logger.info("Phase 2: Reviewing generated code...")
        review = _review_generated_code(files, description, framework_type=framework_type)

        return jsonify({
            'success': True,
            'files': {
                'robot_file': files['robot_file'],
                'python_file': files['python_file'],
                'data_file': files['data_file'],
                'feature_name': files['feature_name']
            },
            'generation_feedback': files.get('generation_feedback', {}),
            'review': review,
            'feature_name': files['feature_name'],
            'framework_type': framework_type
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


def _generate_framework_aware_script(description: str, test_name: str, framework_context: str,
                                      framework_type: str = 'pstaff', demo_suite: str = '') -> dict:
    """Generate framework-specific test files (PSTAFF or Client framework)

    Args:
        description: Test case description
        test_name: Test method name
        framework_context: Framework code patterns and examples
        framework_type: 'pstaff' or 'client'
        demo_suite: Framework-specific demo test suite

    Returns:
        dict with keys: 'robot_file', 'python_file', 'data_file', 'feature_name', 'generation_feedback'
    """
    from openai import AzureOpenAI

    client = AzureOpenAI(
        api_version=config.AZURE_OPENAI_API_VERSION,
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_API_KEY
    )

    # Extract feature name from test_name for file naming
    # e.g., test_admin_login_functionality -> Admin_Login_Functionality
    feature_name = '_'.join(word.capitalize() for word in test_name.replace('test_', '').split('_'))

    # Generate framework-specific prompt
    if framework_type == 'client':
        # Client framework (aut-pypdc) prompt - pytest with PPS modules
        prompt = f"""You are an expert pytest test automation engineer working with the aut-pypdc client framework. Generate THREE complete, production-ready files for a pytest test suite following PPS (Profiler) patterns.

DEMO SUITE REFERENCE:
{demo_suite}

FRAMEWORK CONTEXT:
{framework_context}

IMPORTANT: Study the patterns from the demo suite above, then generate NEW code for the specific test case below.

OUTPUT FORMAT - You must respond with exactly this structure:
=== FILE 1: DATA FILE ===
[data file content here]

=== FILE 2: TEST SUITE FILE ===
[test suite content here]

=== FILE 3: TEST RUNNER FILE ===
[test runner content here]

TEST CASE TO IMPLEMENT:
Feature Name: {feature_name}
Test Method Name: {test_name}
Description: {description}

FILE 1: {feature_name}_Data.py
Contains test data using FWUtils pattern from aut-pypdc/Generic/Framework.

CRITICAL REQUIREMENTS:
1. Import FWUtils:
   from FWUtils import FWUtils

2. Initialize FWUtils object:
   objFWUtils = FWUtils()

3. Get configuration data:
   pps_ip = objFWUtils.get_config('DEVICE')['HOSTNAME']

4. Define data constants (use CAPITAL_LETTERS):
   PPS_ADMIN_USERNAME = "admin"
   PPS_ADMIN_PASSWORD = "admin123"

5. Include Profiler-specific URIs if needed:
   PROFILER_CONFIG_URI = "/api/v1/configuration/profiler/..."

FILE 2: {feature_name}_TestSuite.py
Contains test functions using PpsRestClient and admin_pps modules.

CRITICAL REQUIREMENTS:
1. Imports:
   import sys
   import logging as log
   from admin_pps.PpsRestUtils import PpsRestClient
   from {feature_name}_Data import *

2. Initialize PPS REST client:
   ppsAdmin = PpsRestClient(pps_ip, PPS_ADMIN_USERNAME, PPS_ADMIN_PASSWORD)

3. Test function naming: TC_<ID>_PPS_<DESCRIPTION>()
   Example: def TC_001_PPS_CONFIGURE_WMI_PROFILING():

4. Test function structure:
   def TC_001_PPS_{test_name.upper()}():
       tc_id = sys._getframe().f_code.co_name
       log.info('-' * 50)
       log.info(tc_id + ' [START]')

       try:
           step_text = "Step description"
           log.info(step_text)

           # Use PpsRestClient methods
           return_dict = ppsAdmin.loginSA()
           assert return_dict['status'] == 1, "Failed to login"

           # API calls using URIs from Data file
           response = ppsAdmin.put(PROFILER_CONFIG_URI, payload)
           assert response.status_code == 200, "API call failed"

           log.info(tc_id + ' [PASSED]')
           eresult = True
       except AssertionError as e:
           log.error(e)
           log.info(tc_id + ' [FAILED]')
           eresult = False

       log.info(tc_id + ' [END]')
       return eresult

5. Use try/except with AssertionError
6. Return eresult (True/False)
7. Use logging statements for test steps

FILE 3: {feature_name}_Test.py
pytest test runner that calls test suite functions.

CRITICAL REQUIREMENTS:
1. Imports:
   import pytest
   from {feature_name}_TestSuite import *

2. pytest test functions:
   def test_{test_name.lower()}():
       assert TC_001_PPS_{test_name.upper()}(), "Test failed"

3. Follow pytest naming conventions (test_* functions)
4. Assert the result from TestSuite functions

IMPORTANT GENERATION RULES:
1. Generate ALL THREE files in the format shown above
2. Follow aut-pypdc/PPS patterns exactly
3. Use PpsRestClient for API calls, not generic REST client
4. Import from admin_pps modules for PPS-specific operations
5. Use FWUtils for configuration management
6. Test functions must return boolean (True/False)
7. Do NOT generate markdown code blocks - just plain text content
8. Clearly separate files with === FILE N: === headers

ADDITIONALLY - PROVIDE GENERATION FEEDBACK:
After generating all three files, add a feedback section:

=== GENERATION FEEDBACK ===
{{
  "overall_confidence": 85,
  "assumptions": [
    {{
      "description": "What you assumed",
      "reason": "Why",
      "confidence": 90
    }}
  ],
  "uncertainties": ["List any uncertain decisions"],
  "framework_coverage": "How well framework examples covered this test case"
}}

Generate all three files now with feedback:"""
    else:
        # PSTAFF framework (aut-pstaf) prompt - Robot Framework
        prompt = f"""You are an expert Robot Framework test automation engineer. Generate THREE complete, production-ready files for a Robot Framework test suite.

IMPORTANT: You must generate EXACTLY THREE files in this specific format:

OUTPUT FORMAT - You must respond with exactly this structure:
=== FILE 1: ROBOT FILE ===
[robot file content here]

=== FILE 2: PYTHON LIBRARY FILE ===
[python library content here]

=== FILE 3: DATA FILE ===
[data file content here]

FRAMEWORK CONTEXT TO FOLLOW:
{framework_context}

IMPORTANT INSTRUCTIONS ABOUT FRAMEWORK EXAMPLES:
The framework context above includes Robot Framework examples (.robot files, _Data.py files, and DemoTestSuite.py).
These are PROVIDED AS EXAMPLES TO LEARN PATTERNS FROM - NOT as templates to copy verbatim!

YOU MUST:
1. Study the STRUCTURE and PATTERNS from the examples (*** Settings ***, test case format, data dictionary structure)
2. Generate NEW, UNIQUE code tailored to the specific test case below
3. DO NOT copy specific test method names, data values, or logic from the examples
4. DO apply the same coding style, conventions, and structural patterns

Think of the examples like a style guide - learn the pattern, then create something new following that pattern.

TEST CASE TO IMPLEMENT:
Feature Name: {feature_name}
Test Method Name: {test_name}
Description: {description}

FILE 1: {feature_name}.robot
This is the Robot Framework test file that declares test cases and calls the Python library methods.

*** Settings ***
Documentation     Robot test file for {feature_name} feature
Library           {feature_name}

*** Variables ***

*** Test Cases ***
INITIALIZE
    [Documentation]    INITIALIZE
    {feature_name}.INITIALIZE

{test_name.upper()}
    [Documentation]    {test_name.upper()}
    {feature_name}.{test_name}

CLEANUP
    [Documentation]    CLEANUP
    {feature_name}.SuiteCleanup


FILE 2: {feature_name}.py
This is the Python library file with actual test implementation following framework patterns.

CRITICAL REQUIREMENTS:
1. Standard framework imports (from DemoTestSuite):
   from REST.REST import RestClient
   from Initialize import *
   from AppAccess import *
   from BrowserActions import *
   from Utils import *
   from Log import *
   from PSRSClient import *
   from ConfigUtils import ConfigUtils
   import sys, time, inspect, logging

2. Import the data file:
   from {feature_name}_Data import *

3. GLOBAL object initialization (module level):
   restObj = None
   token = None
   log = Log()
   initObj = Initialize()
   util = Utils()
   appaccess = AppAccess()
   browser = BrowserActions()
   browseractions = BrowserActions()
   restObj = RestClient()

4. Class structure:
   class {feature_name}(object):
       ROBOT_LIBRARY_SCOPE = 'GLOBAL'

       def __init__(self):
           pass

       def INITIALIZE(self):
           # Framework initialization pattern
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
           # Actual test implementation
           # Use data from {feature_name}_Data.py via the imported dictionaries
           # Follow patterns from DemoTestSuite examples
           pass

       def SuiteCleanup(self):
           # Cleanup pattern
           pass

5. Test method patterns to follow:
   - Browser tests: Use appaccess.login(), appaccess.logout(), browseractions.close_browser_window()
   - REST tests: Use restObj.rest_login(), restObj.get/post/put/delete()
   - Use global objects (appaccess, browser, browseractions, restObj, util, etc.) - NEVER create new instances
   - Use dict-based parameters (login_dict, return_dict, etc.)
   - Assert return_dict['status'] == 1 after operations
   - Use data from {feature_name}_Data.py

FILE 3: {feature_name}_Data.py
This file contains test data in Python dictionary format.

Example structure:
# Test data for {feature_name}

# Admin credentials
delegated_admin_dict = {{
    "username": "delegatedadmin",
    "password": "delegatedadminpassword123"
}}

# System admin credentials
system_admin_dict = {{
    "username": "systemadmin",
    "password": "systemadmin123"
}}

# AAA Delegated Admin Realm
aaa_delegated_admin_realm_dict = {{
    "username": "aaadelegatedadmin",
    "password": "aaadelegatedadmin123",
    "realm": "AAA Delegated Admin Realm"
}}

# Add more data dictionaries as needed for the test case

IMPORTANT GENERATION RULES:
1. Generate ALL THREE files in the format shown above
2. The Python library MUST follow the exact framework patterns from DemoTestSuite
3. Use data from the Data file in test methods (import at top of Python file)
4. Keep test logic SIMPLE and follow existing patterns
5. Use EXACT imports and global object patterns as shown
6. Do NOT generate markdown code blocks - just plain text content for each file
7. Clearly separate the three files with the === FILE N: === headers
8. Make sure all method names match between robot file and python library

ADDITIONALLY - PROVIDE GENERATION FEEDBACK:
After generating all three files, add a feedback section explaining your decisions:

=== GENERATION FEEDBACK ===
{{
  "overall_confidence": 85,
  "assumptions": [
    {{
      "description": "What you assumed",
      "reason": "Why you made this assumption",
      "confidence": 90
    }}
  ],
  "uncertainties": ["List any uncertain decisions"],
  "framework_coverage": "How well framework examples covered this test case"
}}

Generate all three files now with feedback:"""

    try:
        # Framework-specific system message
        if framework_type == 'client':
            system_message = "You are an expert pytest test automation engineer working with the aut-pypdc client framework. Generate clean, production-ready pytest test files following PPS module patterns exactly."
        else:
            system_message = "You are an expert Robot Framework test automation engineer. Generate clean, production-ready Robot Framework test files following framework patterns exactly."

        response = client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=8000,
            temperature=0.3
        )

        content = response.choices[0].message.content
        logger.info(f"LLM Response length: {len(content)} chars")

        # Parse the three files and feedback from the response
        robot_file = ""
        python_file = ""
        data_file = ""
        generation_feedback = {}

        # Framework-specific parsing
        if framework_type == 'client':
            # Client framework: DATA FILE, TEST SUITE FILE, TEST RUNNER FILE
            if "=== FILE 1: DATA FILE ===" in content:
                parts = content.split("=== FILE 1: DATA FILE ===")[1]
                if "=== FILE 2: TEST SUITE FILE ===" in parts:
                    data_file = parts.split("=== FILE 2: TEST SUITE FILE ===")[0].strip()

                    parts2 = parts.split("=== FILE 2: TEST SUITE FILE ===")[1]
                    if "=== FILE 3: TEST RUNNER FILE ===" in parts2:
                        python_file = parts2.split("=== FILE 3: TEST RUNNER FILE ===")[0].strip()  # TestSuite goes to python_file

                        parts3 = parts2.split("=== FILE 3: TEST RUNNER FILE ===")[1]
                        if "=== GENERATION FEEDBACK ===" in parts3:
                            robot_file = parts3.split("=== GENERATION FEEDBACK ===")[0].strip()  # Test runner goes to robot_file
                            feedback_text = parts3.split("=== GENERATION FEEDBACK ===")[1].strip()
                            try:
                                if '```json' in feedback_text:
                                    feedback_text = feedback_text.split('```json')[1].split('```')[0].strip()
                                elif '```' in feedback_text:
                                    feedback_text = feedback_text.split('```')[1].split('```')[0].strip()
                                generation_feedback = json.loads(feedback_text)
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse generation feedback: {e}")
                                generation_feedback = {"overall_confidence": 75, "assumptions": [], "uncertainties": []}
                        else:
                            robot_file = parts3.strip()
            else:
                logger.warning("Client framework separators not found in response")
                logger.debug(f"Response content: {content[:500]}...")
        else:
            # PSTAFF framework: ROBOT FILE, PYTHON LIBRARY FILE, DATA FILE
            if "=== FILE 1: ROBOT FILE ===" in content:
                parts = content.split("=== FILE 1: ROBOT FILE ===")[1]
                if "=== FILE 2: PYTHON LIBRARY FILE ===" in parts:
                    robot_file = parts.split("=== FILE 2: PYTHON LIBRARY FILE ===")[0].strip()

                    parts2 = parts.split("=== FILE 2: PYTHON LIBRARY FILE ===")[1]
                    if "=== FILE 3: DATA FILE ===" in parts2:
                        python_file = parts2.split("=== FILE 3: DATA FILE ===")[0].strip()

                        parts3 = parts2.split("=== FILE 3: DATA FILE ===")[1]
                        if "=== GENERATION FEEDBACK ===" in parts3:
                            data_file = parts3.split("=== GENERATION FEEDBACK ===")[0].strip()
                            feedback_text = parts3.split("=== GENERATION FEEDBACK ===")[1].strip()
                            try:
                                if '```json' in feedback_text:
                                    feedback_text = feedback_text.split('```json')[1].split('```')[0].strip()
                                elif '```' in feedback_text:
                                    feedback_text = feedback_text.split('```')[1].split('```')[0].strip()
                                generation_feedback = json.loads(feedback_text)
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse generation feedback: {e}")
                                generation_feedback = {"overall_confidence": 75, "assumptions": [], "uncertainties": []}
                        else:
                            data_file = parts3.strip()

        # Clean up any markdown code blocks if present
        def clean_code_block(code):
            if '```robot' in code:
                code = code.split('```robot')[1].split('```')[0].strip()
            elif '```python' in code:
                code = code.split('```python')[1].split('```')[0].strip()
            elif '```' in code:
                # Remove first and last code blocks
                if code.count('```') >= 2:
                    code = code.split('```')[1].split('```')[0].strip()
            return code

        robot_file = clean_code_block(robot_file)
        python_file = clean_code_block(python_file)
        data_file = clean_code_block(data_file)

        # Return all three files with generation feedback
        return {
            'robot_file': robot_file,
            'python_file': python_file,
            'data_file': data_file,
            'feature_name': feature_name,
            'generation_feedback': generation_feedback
        }

    except Exception as e:
        logger.error(f"Error calling Azure OpenAI: {e}")
        raise


def _review_generated_code(files: dict, test_description: str, framework_type: str = 'pstaff') -> dict:
    """
    Review generated code for quality, potential issues, and provide ratings

    Args:
        files: Dictionary containing robot_file, python_file, data_file
        test_description: Original test case description
        framework_type: 'pstaff' or 'client'

    Returns:
        Dictionary with review results, ratings, issues, and recommendations
    """
    from openai import AzureOpenAI

    client = AzureOpenAI(
        api_version=config.AZURE_OPENAI_API_VERSION,
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_API_KEY
    )

    # Framework-specific review prompts
    framework_specifics = ""
    if framework_type == 'client':
        framework_specifics = """
FRAMEWORK-SPECIFIC VALIDATION (Client Framework - aut-pypdc):
- Does this follow aut-pypdc pytest patterns and PPS module conventions?
- Are PpsRestClient methods (loginSA, put, get, post, delete) used correctly?
- Is FWUtils used properly for configuration management?
- Do test functions follow TC_<ID>_PPS_<NAME>() naming pattern?
- Does the test runner use pytest conventions (test_* functions)?
- Are admin_pps modules (PpsRestUtils, authentication, etc.) imported correctly?
- Is logging done correctly with log.info() for test steps?
"""
    else:
        framework_specifics = """
FRAMEWORK-SPECIFIC VALIDATION (PSTAFF - aut-pstaf):
- Does this follow PSTAF naming conventions and patterns?
- Are Robot Framework keyword names descriptive and follow library conventions?
- Are PSTAF utility methods (ConfigUtils, AppAccess, BrowserActions) used correctly?
- Are dependencies used as documented in framework examples?
"""

    review_prompt = f"""You are a senior code reviewer specializing in test automation quality assurance.

Review the following generated test files for quality, correctness, and potential issues.

Framework: {framework_type.upper()}

ORIGINAL TEST REQUIREMENT:
{test_description}

GENERATED FILES:

=== {files['feature_name']}.robot ===
{files['robot_file']}

=== {files['feature_name']}.py ===
{files['python_file']}

=== {files['feature_name']}_Data.py ===
{files['data_file']}

REVIEW CRITERIA:
1. **Correctness**: Does the code correctly implement the test requirement? What percentage of requirements are covered?
2. **Framework Compliance**: Does it follow Robot Framework and PSTAF framework best practices and naming conventions?
3. **Code Quality**: Is the code clean, maintainable, well-structured, and free of code smells?
4. **Error Handling**: Are errors properly handled with appropriate fallbacks and logging?
5. **Data Management**: Is test data properly separated, validated, and managed?
6. **Best Practices**: Does it follow testing best practices including proper assertions and cleanup?
7. **Test Coverage**: What scenarios are NOT covered? What edge cases, negative paths, and error conditions are missing?
8. **Security**: Are there any security vulnerabilities (credential exposure, injection risks, etc.)?

SEVERITY LEVEL GUIDELINES - BE PRECISE:
- **critical**: Security vulnerabilities (exposed credentials, SQL injection, XSS), data corruption, system crashes, infinite loops, authentication bypasses
- **high**: Race conditions, memory leaks, incorrect core logic, missing critical error handling, data loss risks
- **medium**: Hardcoded values that should be configurable, poor error messages, missing input validation, code that works but is fragile
- **low**: Code style issues, unused variables, minor redundancy, missing comments
- **info**: Suggestions for future enhancements, alternative approaches

{framework_specifics}

Provide a comprehensive review in the following JSON format:

{{
  "overall_rating": "B+",
  "confidence_score": 87,
  "rating_explanation": "Overall B+ because Python file (50% weight) has 2 medium-severity issues affecting robustness. Robot file is excellent (A-) and data file is clean (A-). No critical or high-severity issues found.",
  "what_would_make_it_A": "Fix the 2 MEDIUM issues: (1) Add config fallbacks for missing values, (2) Replace bare except clauses with specific exception handling. Estimated total effort: 20 minutes.",

  "file_ratings": {{
    "robot_file": "A-",
    "python_file": "B+",
    "data_file": "A-"
  }},

  "test_coverage_gaps": {{
    "missing_scenarios": [
      "Negative test: Invalid credentials",
      "Edge case: Network timeout during login",
      "Error case: Landing page text missing or changed"
    ],
    "untested_conditions": [
      "Browser crash during session",
      "ConfigUtils missing required keys",
      "Logout failure handling"
    ],
    "requirement_coverage_percent": 85,
    "what_is_missing": "Error handling paths and negative test cases"
  }},

  "top_3_priorities": [
    {{
      "issue": "Add config fallbacks using default_profiler_config",
      "why": "Test will fail in environments where ConfigUtils is incomplete",
      "impact_if_not_fixed": "Test becomes environment-dependent and brittle",
      "estimated_effort": "10 minutes",
      "how_to_fix": "Add helper function: get_config(key, fallback) that checks ConfigUtils then default_profiler_config"
    }},
    {{
      "issue": "Replace bare except clauses with specific exception handling",
      "why": "Bare except catches SystemExit and KeyboardInterrupt, masks real errors",
      "impact_if_not_fixed": "Debugging becomes difficult, may hide critical failures",
      "estimated_effort": "5 minutes",
      "how_to_fix": "Change 'except:' to 'except Exception as e:' and re-raise with context"
    }},
    {{
      "issue": "Use Robot Framework BuiltIn assertions instead of Python assert",
      "why": "Python asserts can be disabled with -O flag and provide poor Robot reports",
      "impact_if_not_fixed": "Tests may pass when they should fail in optimized mode",
      "estimated_effort": "5 minutes",
      "how_to_fix": "Import BuiltIn library and use should_be_equal() or should_be_true()"
    }}
  ],

  "strengths": [
    "Follows PSTAF three-file structure (Robot, Python, Data) correctly",
    "Clean separation of test logic and test data",
    "Proper use of INITIALIZE and SuiteCleanup keywords",
    "Consistent logging with utility wrappers",
    "Good defensive cleanup on failure"
  ],

  "potential_issues": [
    {{
      "severity": "medium",
      "file": "python_file",
      "location": "test_admin_login_functionality method",
      "issue": "No fallback when ConfigUtils is missing HOSTNAME, PROTOCOL, or PORT keys",
      "suggestion": "Add helper to read from ConfigUtils with fallback to default_profiler_config",
      "estimated_effort": "10 minutes",
      "impact_if_not_fixed": "Test fails with KeyError in some environments"
    }},
    {{
      "severity": "medium",
      "file": "python_file",
      "location": "INITIALIZE and SuiteCleanup methods",
      "issue": "Bare except clauses catch all exceptions including SystemExit",
      "suggestion": "Use 'except Exception as e:' and re-raise to preserve traceback",
      "estimated_effort": "5 minutes",
      "impact_if_not_fixed": "Debugging becomes difficult, may mask critical errors"
    }},
    {{
      "severity": "low",
      "file": "python_file",
      "location": "Module-level globals",
      "issue": "Unused globals (restObj, token) and duplicate BrowserActions instances",
      "suggestion": "Remove unused variables and consolidate to single browseractions instance",
      "estimated_effort": "3 minutes",
      "impact_if_not_fixed": "Code clutter, potential confusion for maintainers"
    }}
  ],

  "recommendations": [
    "Add configuration fallbacks to make tests portable across environments",
    "Replace Python assertions with Robot Framework BuiltIn library for better reporting",
    "Implement negative test cases (invalid credentials, timeouts, missing config)",
    "Externalize hardcoded timeout (60 seconds) to configuration for environment-specific tuning",
    "Add edge case handling for missing or changed landing page text"
  ],

  "correctness_analysis": {{
    "meets_requirements": true,
    "requirement_coverage_percent": 85,
    "what_works": "Implements core login, landing page verification, and logout flow correctly",
    "what_is_missing": "Error handling, negative test cases, edge case coverage",
    "assumptions_that_may_break": [
      "ConfigUtils has HOSTNAME, PROTOCOL, PORT, ADMIN_LANDING_TEXT keys",
      "AppAccess.login returns dict with 'status' key where 1 = success",
      "BrowserActions.verify_text_on_page and close_browser_window methods exist"
    ],
    "production_readiness": "Ready for happy-path testing, needs error handling for production"
  }},

  "security_concerns": [
    "Credentials passed in plain dict - ensure not logged in plain text",
    "Landing page text verification could fail if text contains HTML/scripts"
  ]
}}

IMPORTANT RULES:
1. Limit recommendations to 5 maximum (consolidate related items)
2. Every potential_issue MUST have estimated_effort and impact_if_not_fixed
3. top_3_priorities MUST be the most impactful fixes, ordered by priority
4. Be specific with line numbers and file names
5. rating_explanation must justify the overall rating clearly
6. what_would_make_it_A must be actionable and specific

RATING SCALE:
- A+/A/A-: Excellent, production-ready with comprehensive coverage
- B+/B/B-: Good, functional but needs minor improvements
- C+/C/C-: Acceptable, works but needs moderate improvements
- D+/D/D-: Needs significant work before production use
- F: Not functional, severely flawed, or dangerous

Generate the review now as valid JSON:"""

    try:
        response = client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are an expert code reviewer. Provide thorough, constructive reviews in valid JSON format. Follow the schema exactly."},
                {"role": "user", "content": review_prompt}
            ],
            max_completion_tokens=6000,  # Increased for comprehensive review with all new fields
            temperature=0.2  # Lower temperature for consistent reviews
        )

        review_content = response.choices[0].message.content

        # Parse JSON from response
        try:
            if '```json' in review_content:
                review_content = review_content.split('```json')[1].split('```')[0].strip()
            elif '```' in review_content:
                review_content = review_content.split('```')[1].split('```')[0].strip()

            review = json.loads(review_content)
            return review

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse review JSON: {e}")
            # Return default review structure
            return {
                "overall_rating": "B",
                "confidence_score": 75,
                "file_ratings": {"robot_file": "B", "python_file": "B", "data_file": "B"},
                "strengths": ["Code generated successfully"],
                "potential_issues": [],
                "recommendations": ["Manual review recommended"],
                "correctness_analysis": "Review parsing failed - manual review needed"
            }

    except Exception as e:
        logger.error(f"Error during code review: {e}")
        return {
            "overall_rating": "Unknown",
            "confidence_score": 0,
            "file_ratings": {},
            "strengths": [],
            "potential_issues": [],
            "recommendations": ["Review failed - manual inspection required"],
            "correctness_analysis": str(e)
        }


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

    # Initialize components BEFORE starting Flask
    init_components()

    # Run Flask app
    logger.info("Flask app starting on http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
