"""
PKG Loader: Load and manage Product Knowledge Graph structures
Provides feature identification and PKG retrieval for test generation
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class PKGLoader:
    """
    Loads and manages Product Knowledge Graph (PKG) structures.

    PKG provides structured product knowledge:
    - UI surfaces (screens, navigation paths)
    - Input controls (fields, types, ranges, defaults)
    - Actions (buttons, operations)
    - Constraints (business rules, prerequisites)
    - Error conditions
    """

    def __init__(self, pkg_dir: Path, azure_client: Optional[AzureOpenAI] = None):
        self.pkg_dir = Path(pkg_dir)
        self.azure_client = azure_client

        # Load feature understanding layer from all subdirectories
        self.features = self._load_feature_understanding()

        # Cache for loaded PKGs
        self.pkg_cache = {}

        logger.info(f"PKG Loader initialized with {len(self.features)} features from {self._count_sources()} sources")

    def _load_feature_understanding(self) -> List[Dict]:
        """Load the feature understanding layer from multiple sources"""
        all_features = []
        sources_loaded = 0

        # Check for root-level feature understanding (backward compatibility)
        root_feature_file = self.pkg_dir / "feature_understanding.json"
        if root_feature_file.exists():
            try:
                with open(root_feature_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    features = data.get('features', [])
                    # Tag with source
                    for feat in features:
                        feat['_source'] = 'root'
                        feat['_source_path'] = str(self.pkg_dir)
                    all_features.extend(features)
                    sources_loaded += 1
                    logger.info(f"Loaded {len(features)} features from root")
            except Exception as e:
                logger.error(f"Error loading root feature understanding: {e}")

        # Check subdirectories for feature understanding files
        if self.pkg_dir.exists() and self.pkg_dir.is_dir():
            for subdir in self.pkg_dir.iterdir():
                if subdir.is_dir():
                    feature_file = subdir / "feature_understanding.json"
                    if feature_file.exists():
                        try:
                            with open(feature_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                features = data.get('features', [])
                                # Tag with source
                                for feat in features:
                                    feat['_source'] = subdir.name
                                    feat['_source_path'] = str(subdir)
                                all_features.extend(features)
                                sources_loaded += 1
                                logger.info(f"Loaded {len(features)} features from {subdir.name}")
                        except Exception as e:
                            logger.error(f"Error loading feature understanding from {subdir.name}: {e}")

        if not all_features:
            logger.warning(f"No feature understanding files found in {self.pkg_dir}")

        return all_features

    def _count_sources(self) -> int:
        """Count number of feature understanding sources loaded"""
        sources = set(f.get('_source', 'unknown') for f in self.features)
        return len(sources)

    def identify_features(self, user_query: str) -> List[Dict]:
        """
        Identify which features are relevant to the user query.

        Uses LLM to match query against available features.
        """
        if not self.features:
            logger.warning("No features available for identification")
            return []

        if not self.azure_client:
            # Fallback: Simple keyword matching
            return self._identify_features_fallback(user_query)

        # Use LLM for intelligent feature identification
        feature_list = "\n".join([
            f"- {f['feature_id']}: {f['feature_name']} - {f['description']}"
            for f in self.features
        ])

        prompt = f"""Given a user query, identify which features are relevant.

USER QUERY: {user_query}

AVAILABLE FEATURES:
{feature_list}

Return the relevant feature IDs as a JSON array. Include features that are:
1. Directly mentioned in the query
2. Related parent features (if a sub-feature is mentioned)
3. Related child features (if a parent is mentioned)

Return ONLY a JSON array of feature_ids:
["feature_id_1", "feature_id_2", ...]

If no features match, return an empty array: []
"""

        try:
            response = self.azure_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a feature identifier. Return ONLY valid JSON array."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_completion_tokens=500
            )

            result_text = response.choices[0].message.content.strip()

            # Extract JSON
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            feature_ids = json.loads(result_text)

            # Get full feature objects
            identified = [f for f in self.features if f['feature_id'] in feature_ids]

            logger.info(f"Identified {len(identified)} features from query: {[f['feature_name'] for f in identified]}")
            return identified

        except Exception as e:
            logger.error(f"Error identifying features with LLM: {e}. Falling back to keyword matching.")
            return self._identify_features_fallback(user_query)

    def _identify_features_fallback(self, user_query: str) -> List[Dict]:
        """Fallback: Simple keyword matching"""
        query_lower = user_query.lower()
        matched = []

        for feature in self.features:
            # Check if feature name or description matches query keywords
            feature_text = f"{feature['feature_name']} {feature['description']}".lower()

            # Simple word matching
            query_words = query_lower.split()
            if any(word in feature_text for word in query_words if len(word) > 3):
                matched.append(feature)

        logger.info(f"Fallback matching identified {len(matched)} features")
        return matched

    def load_pkg(self, feature_id: str, source_path: Optional[str] = None) -> Optional[Dict]:
        """
        Load PKG for a specific feature.

        Returns PKG structure with:
        - ui_surfaces
        - inputs
        - actions
        - constraints
        - errors
        """
        # Check cache first
        cache_key = f"{source_path}:{feature_id}" if source_path else feature_id
        if cache_key in self.pkg_cache:
            return self.pkg_cache[cache_key]

        # Try loading from specified source path first
        if source_path:
            pkg_file = Path(source_path) / f"pkg_{feature_id}.json"
            if pkg_file.exists():
                try:
                    with open(pkg_file, 'r', encoding='utf-8') as f:
                        pkg = json.load(f)
                        self.pkg_cache[cache_key] = pkg
                        logger.info(f"Loaded PKG for {feature_id} from {source_path}: {len(pkg.get('inputs', []))} inputs, {len(pkg.get('constraints', []))} constraints")
                        return pkg
                except Exception as e:
                    logger.error(f"Error loading PKG for {feature_id} from {source_path}: {e}")

        # Fallback: Search in root directory
        pkg_file = self.pkg_dir / f"pkg_{feature_id}.json"
        if pkg_file.exists():
            try:
                with open(pkg_file, 'r', encoding='utf-8') as f:
                    pkg = json.load(f)
                    self.pkg_cache[cache_key] = pkg
                    logger.info(f"Loaded PKG for {feature_id} from root: {len(pkg.get('inputs', []))} inputs, {len(pkg.get('constraints', []))} constraints")
                    return pkg
            except Exception as e:
                logger.error(f"Error loading PKG for {feature_id}: {e}")

        # Fallback: Search all subdirectories
        if self.pkg_dir.exists() and self.pkg_dir.is_dir():
            for subdir in self.pkg_dir.iterdir():
                if subdir.is_dir():
                    pkg_file = subdir / f"pkg_{feature_id}.json"
                    if pkg_file.exists():
                        try:
                            with open(pkg_file, 'r', encoding='utf-8') as f:
                                pkg = json.load(f)
                                self.pkg_cache[cache_key] = pkg
                                logger.info(f"Loaded PKG for {feature_id} from {subdir.name}: {len(pkg.get('inputs', []))} inputs, {len(pkg.get('constraints', []))} constraints")
                                return pkg
                        except Exception as e:
                            logger.error(f"Error loading PKG for {feature_id} from {subdir.name}: {e}")

        logger.warning(f"PKG file not found for feature: {feature_id}")
        return None

    def get_pkgs_for_query(self, user_query: str) -> Dict:
        """
        Get all relevant PKGs for a user query.

        Returns:
        {
            'features': [...],  # Identified features
            'pkgs': {...}       # feature_id -> PKG mapping
        }
        """
        # Identify features
        features = self.identify_features(user_query)

        # Load PKGs
        pkgs = {}
        for feature in features:
            feature_id = feature['feature_id']
            source_path = feature.get('_source_path')
            pkg = self.load_pkg(feature_id, source_path)
            if pkg:
                # Add source metadata to PKG
                pkg['_source'] = feature.get('_source', 'unknown')
                pkg['_source_path'] = source_path
                pkgs[feature_id] = pkg

        return {
            'features': features,
            'pkgs': pkgs
        }

    def format_pkg_for_prompt(self, feature_id: str) -> str:
        """
        Format PKG as a readable string for LLM prompts.
        """
        pkg = self.load_pkg(feature_id)
        if not pkg:
            return ""

        sections = []

        # Feature name
        sections.append(f"=== FEATURE: {pkg.get('feature_name', feature_id)} ===\n")

        # UI Surface
        ui_surfaces = pkg.get('ui_surfaces', [])
        if ui_surfaces:
            sections.append("UI NAVIGATION:")
            for ui in ui_surfaces:
                sections.append(f"  Screen: {ui.get('screen_name', 'N/A')}")
                sections.append(f"  Path: {ui.get('navigation_path', 'N/A')}")
            sections.append("")

        # Inputs
        inputs = pkg.get('inputs', [])
        if inputs:
            sections.append("INPUT CONTROLS:")
            for inp in inputs:
                inp_desc = f"  - {inp.get('name', 'N/A')} ({inp.get('control_type', 'unknown')})"

                if inp.get('data_type'):
                    inp_desc += f" [type: {inp['data_type']}]"
                if inp.get('range'):
                    inp_desc += f" [range: {inp['range']}]"
                if inp.get('default_value'):
                    inp_desc += f" [default: {inp['default_value']}]"
                if inp.get('unit'):
                    inp_desc += f" [{inp['unit']}]"
                if inp.get('required'):
                    inp_desc += " [REQUIRED]"

                sections.append(inp_desc)

                if inp.get('help_text'):
                    sections.append(f"    Help: {inp['help_text']}")
                if inp.get('location'):
                    sections.append(f"    Location: {inp['location']}")
            sections.append("")

        # Actions
        actions = pkg.get('actions', [])
        if actions:
            sections.append("ACTIONS:")
            for action in actions:
                sections.append(f"  - {action.get('button_text', 'N/A')}: {action.get('description', '')}")
            sections.append("")

        # Constraints
        constraints = pkg.get('constraints', [])
        if constraints:
            sections.append("CONSTRAINTS:")
            for constraint in constraints:
                sections.append(f"  - {constraint}")
            sections.append("")

        # Errors
        errors = pkg.get('errors', [])
        if errors:
            sections.append("ERROR CONDITIONS:")
            for error in errors:
                sections.append(f"  - {error.get('message', 'N/A')} (Trigger: {error.get('trigger', 'N/A')})")
            sections.append("")

        return "\n".join(sections)

    def get_status(self) -> Dict:
        """Get status of PKG loader"""
        return {
            'total_features': len(self.features),
            'cached_pkgs': len(self.pkg_cache),
            'pkg_directory': str(self.pkg_dir),
            'features_loaded': len(self.features) > 0
        }
