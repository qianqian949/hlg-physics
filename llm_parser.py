"""
LLM Parser Module
Formats text into structured prompts and calls LLM API
Supports Zhipu BigModel API (OpenAI-compatible)
"""

import os
import json
import re
import httpx
from typing import Dict, Optional
from difflib import SequenceMatcher
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import streamlit for session state access (optional)
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    st = None


class LLMParser:
    """
    Parser that uses LLM to extract hierarchical logic graphs from research papers.
    
    The prompt template is loaded from: prompts/paper_to_logicgraph.txt
    Modify that file to customize how the LLM analyzes papers.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "glm-5.2"):
        """
        Initialize the LLM parser.

        Args:
            api_key: Zhipu BigModel API key (if None, reads from environment)
            model: Model to use for parsing
        """
        self.api_key = api_key or os.getenv("ZHIPU_API_KEY")
        if not self.api_key:
            raise ValueError("ZHIPU_API_KEY not found in environment or provided")

        self.model = model

        # Create custom httpx client with better SSL/timeout handling
        # This helps with SSL connection issues
        try:
            http_client = httpx.Client(
                timeout=300.0,  # Increased timeout for slow connections / long analyses
                verify=True,    # Verify SSL certificates
                follow_redirects=True,
                # Use default SSL context but with longer timeout
            )

            self.client = OpenAI(
                base_url="https://open.bigmodel.cn/api/paas/v4",
                api_key=self.api_key,
                http_client=http_client,
            )
        except Exception as e:
            # Fallback to default client if custom client fails
            print(f"[WARNING] Could not create custom HTTP client: {e}")
            print("[INFO] Using default client configuration")
            self.client = OpenAI(
                base_url="https://open.bigmodel.cn/api/paas/v4",
                api_key=self.api_key,
            )
        
        # Load prompt templates
        self.prompt_template = self._load_prompt_template()
        self.relations_prompt_template = self._load_prompt_template("prompts/find_relations.txt")
        self.inference_prompt_template = self._load_prompt_template("prompts/infer_context.txt")
        self.cross_paper_prompt_template = self._load_prompt_template("prompts/cross_paper_relations.txt")
    
    def _find_closest_node(self, target_name: str, candidate_nodes: set, threshold: float = 0.6) -> Optional[str]:
        """
        Find the closest matching node name from a set of candidates.
        
        Args:
            target_name: The node name to match
            candidate_nodes: Set of candidate node names
            threshold: Minimum similarity score (0-1) to consider a match
            
        Returns:
            Closest matching node name, or None if no match above threshold
        """
        if not candidate_nodes:
            return None
        
        best_match = None
        best_score = 0.0
        
        target_lower = target_name.lower()
        
        for candidate in candidate_nodes:
            candidate_lower = candidate.lower()
            
            # Try exact case-insensitive match first
            if candidate_lower == target_lower:
                return candidate
            
            # Calculate similarity score
            score = SequenceMatcher(None, target_lower, candidate_lower).ratio()
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        # Return match if above threshold
        if best_score >= threshold:
            return best_match
        
        return None
    
    def _load_prompt_template(self, prompt_path: str = "prompts/paper_to_logicgraph.txt") -> str:
        """
        Load a prompt template from file or session state.
        
        Checks session state for custom prompts first, then falls back to file.
        
        Args:
            prompt_path: Path to the prompt template file
        
        Returns:
            Prompt template as string
            
        Raises:
            FileNotFoundError: If prompt file is not found
        """
        # Check for custom prompt in session state if streamlit is available
        if STREAMLIT_AVAILABLE and st is not None:
            # Map prompt paths to session state keys
            prompt_key_map = {
                "prompts/paper_to_logicgraph.txt": "custom_prompt_paper_to_logicgraph",
                "prompts/find_relations.txt": "custom_prompt_find_relations",
                "prompts/infer_context.txt": "custom_prompt_infer_context",
                "prompts/cross_paper_relations.txt": "custom_prompt_cross_paper_relations",
            }
            
            # Get the session state key for this prompt
            session_key = prompt_key_map.get(prompt_path)
            if session_key and session_key in st.session_state:
                custom_prompt = st.session_state[session_key]
                if custom_prompt and custom_prompt.strip():
                    return custom_prompt
        
        # Fall back to loading from file
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                template = f.read()
                if not template.strip():
                    raise ValueError(f"Prompt file {prompt_path} is empty")
                return template
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Prompt template not found at '{prompt_path}'. "
                f"Please ensure the file exists."
            )
    
    def parse_paper(self, paper_text: str, max_chars: Optional[int] = None, enable_inference: bool = False) -> Dict:
        """
        Parse a research paper and extract hierarchical logic graph with confidence scores.
        Uses a two-pass (or three-pass) approach:
        1. Extract all nodes (concepts at Level 1, 2, 3)
        2. Find all relations between the nodes with confidence scores
        3. (Optional) Infer additional context nodes and relations
        
        Args:
            paper_text: Raw text from the research paper (ideally from section-aware extraction)
            max_chars: Optional max characters to send to LLM (for safety, though pdf_extractor
                      should handle this). If None, no additional truncation is applied.
            enable_inference: If True, runs Pass 3 to infer additional contextual nodes and relations
            
        Returns:
            Dictionary containing:
                - Hierarchical logic graph with confidence scores
                - Token usage information under '_token_usage' key
                - Inferred nodes and relations (if enable_inference=True)
        """
        # Optional additional truncation (mainly for safety/backward compatibility)
        if max_chars and len(paper_text) > max_chars:
            paper_text = paper_text[:max_chars] + "\n\n[...truncated...]"
        
        # PASS 1: Extract nodes
        nodes_data = self._extract_nodes(paper_text)
        
        # PASS 2: Find all relations between nodes (grounded in paper text)
        relations_data = self._find_relations(nodes_data, paper_text)
        
        # Combine Pass 1 & 2 results
        hlg_data = {
            "Level3": nodes_data.get("Level3", []),
            "Level2": nodes_data.get("Level2", []),
            "Relations": relations_data.get("Relations", []),
            "Level1": nodes_data.get("Level1", []),
            "overall_confidence": relations_data.get("overall_confidence", 0),
            "overall_explanation": relations_data.get("overall_explanation", ""),
            "_token_usage": {
                "pass1_prompt_tokens": nodes_data["_token_usage"]["prompt_tokens"],
                "pass1_completion_tokens": nodes_data["_token_usage"]["completion_tokens"],
                "pass2_prompt_tokens": relations_data["_token_usage"]["prompt_tokens"],
                "pass2_completion_tokens": relations_data["_token_usage"]["completion_tokens"],
                "prompt_tokens": nodes_data["_token_usage"]["prompt_tokens"] + relations_data["_token_usage"]["prompt_tokens"],
                "completion_tokens": nodes_data["_token_usage"]["completion_tokens"] + relations_data["_token_usage"]["completion_tokens"],
                "total_tokens": nodes_data["_token_usage"]["total_tokens"] + relations_data["_token_usage"]["total_tokens"]
            }
        }
        
        # PASS 3 (Optional): Infer contextual nodes and relations
        if enable_inference:
            inference_data = self._infer_context(hlg_data)
            
            # Add inferred elements to the graph
            hlg_data["InferredNodes"] = inference_data.get("InferredNodes", [])
            hlg_data["InferredRelations"] = inference_data.get("InferredRelations", [])
            hlg_data["inference_confidence"] = inference_data.get("overall_confidence", 0)
            hlg_data["inference_explanation"] = inference_data.get("overall_explanation", "")
            
            # Update token usage
            hlg_data["_token_usage"]["pass3_prompt_tokens"] = inference_data["_token_usage"]["prompt_tokens"]
            hlg_data["_token_usage"]["pass3_completion_tokens"] = inference_data["_token_usage"]["completion_tokens"]
            hlg_data["_token_usage"]["prompt_tokens"] += inference_data["_token_usage"]["prompt_tokens"]
            hlg_data["_token_usage"]["completion_tokens"] += inference_data["_token_usage"]["completion_tokens"]
            hlg_data["_token_usage"]["total_tokens"] += inference_data["_token_usage"]["total_tokens"]
        
        return hlg_data
    
    def _call_api_with_retry(self, messages: list, max_tokens: int = 8000,
                            temperature: float = 0.0, max_retries: int = 5,
                            disable_thinking: bool = False):
        """
        Call the API with retry logic for handling transient failures.
        
        Args:
            messages: List of message dicts for the API
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            max_retries: Maximum number of retry attempts
            
        Returns:
            Response content string
            
        Raises:
            Exception: If all retries fail
        """
        import time
        
        for attempt in range(max_retries):
            try:
                print(f"[DEBUG] API call attempt {attempt + 1}/{max_retries}")
                
                request_options = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "extra_headers": {
                        "HTTP-Referer": "https://github.com/yourusername/yourrepo",
                        "X-Title": "Paper Analysis Tool"
                    }
                }

                # GLM-5.x enables extended thinking by default.  Relation passes
                # need long JSON responses, so thinking can consume most of the
                # output budget and make an otherwise valid request time out.
                if disable_thinking:
                    request_options["extra_body"] = {"thinking": {"type": "disabled"}}

                response = self.client.chat.completions.create(
                    **request_options
                )
                
                # Check if we got a valid response object
                if not response or not response.choices:
                    raise ValueError("Invalid API response: No choices returned")
                
                content = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason
                
                print(f"[DEBUG] API finish reason: {finish_reason}")
                print(f"[DEBUG] Response length: {len(content) if content else 0} characters")
                
                # Check if content is valid
                if not content or not content.strip():
                    raise ValueError(f"Empty response (finish_reason: {finish_reason})")
                
                # Check for corrupted/short responses
                if len(content) < 50 and not content.strip().startswith('{'):
                    raise ValueError(f"Corrupted/short response: {content[:200]}")
                
                # Return the response object for token usage tracking
                return response
                
            except Exception as e:
                error_str = str(e).lower()
                print(f"[WARNING] API call attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < max_retries - 1:
                    # Longer wait for SSL/connection errors
                    if 'ssl' in error_str or 'protocol' in error_str or 'eof' in error_str or 'connection' in error_str:
                        wait_time = (attempt + 1) * 3  # Longer backoff for SSL: 3s, 6s, 9s, 12s, 15s
                        print(f"[DEBUG] SSL/connection error detected. Retrying in {wait_time} seconds...")
                    else:
                        wait_time = (attempt + 1) * 2  # Normal backoff: 2s, 4s, 6s, 8s, 10s
                        print(f"[DEBUG] Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    # Provide more helpful error message for SSL issues
                    if 'ssl' in error_str or 'protocol' in error_str or 'eof' in error_str:
                        raise Exception(
                            f"API call failed after {max_retries} attempts due to SSL/connection error: {str(e)}\n\n"
                            f"Possible solutions:\n"
                            f"1. Check your network connection\n"
                            f"2. If behind a proxy, configure HTTP_PROXY and HTTPS_PROXY environment variables\n"
                            f"3. Try: python -m pip install --upgrade certifi\n"
                            f"4. Check firewall/antivirus settings\n"
                            f"5. Try from a different network"
                        )
                    else:
                        raise Exception(f"API call failed after {max_retries} attempts: {str(e)}")
    
    def _extract_nodes(self, paper_text: str) -> Dict:
        """
        PASS 1: Extract all nodes (concepts) from the paper.
        
        Args:
            paper_text: Raw text from the research paper
            
        Returns:
            Dictionary with Level1, Level2, Level3 nodes and token usage
        """
        # Load prompt template (check for custom prompt in session state)
        prompt_template = self._load_prompt_template()
        
        # Construct the full prompt
        full_prompt = f"{prompt_template}\n\n---\n\nPaper Text:\n\n{paper_text}"
        
        try:
            # Call the LLM API with retry logic
            print(f"[DEBUG] Calling LLM API (Pass 1 - Nodes) with model: {self.model}")
            print(f"[DEBUG] Prompt length: {len(full_prompt)} characters")
            print(f"[DEBUG] Paper text length: {len(paper_text)} characters")
            
            response = self._call_api_with_retry(
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=8000,
                temperature=0.0,
                max_retries=3
            )
            
            # Extract the response content
            content = response.choices[0].message.content
            
            # Parse JSON from the response
            parsed_json = self._extract_json(content)
            
            # Validate basic structure (without relations)
            required_keys = ["Level3", "Level2", "Level1"]
            for key in required_keys:
                if key not in parsed_json:
                    raise ValueError(f"Missing required key: {key}")

            # A model may occasionally return a nested Level2 object such as
            # {"Problem": [...], "Method": [...], "Relations": [...]}.  Do
            # not let that malformed-but-present value silently poison Pass 2.
            for key in required_keys:
                value = parsed_json[key]
                if isinstance(value, dict):
                    flattened = []
                    for nested_key, nested_value in value.items():
                        if nested_key.lower() == "relations":
                            continue
                        if isinstance(nested_value, list):
                            flattened.extend(nested_value)
                    value = flattened

                if not isinstance(value, list):
                    raise ValueError(f"{key} must be a list of node names")

                invalid_nodes = [node for node in value if not isinstance(node, str) or not node.strip()]
                if invalid_nodes:
                    raise ValueError(f"{key} must contain only non-empty strings")

                # Remove duplicates while preserving the model's order.
                parsed_json[key] = list(dict.fromkeys(node.strip() for node in value))
            
            # Add token usage information
            parsed_json["_token_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return parsed_json
        
        except Exception as e:
            raise Exception(f"Error extracting nodes with LLM: {str(e)}")
    
    def _find_relations(self, nodes_data: Dict, paper_text: str) -> Dict:
        """
        PASS 2: Find all relations between the extracted nodes, grounded in paper text.
        
        Args:
            nodes_data: Dictionary containing Level1, Level2, Level3 nodes
            paper_text: Original paper text for grounding relations
            
        Returns:
            Dictionary with Relations array (with confidence scores) and token usage
        """
        # Format the nodes for the prompt
        nodes_text = f"""
Level 3 (Abstract Theoretical Concepts):
{chr(10).join(f"  - {node}" for node in nodes_data.get("Level3", []))}

Level 2 (Mathematical/Conceptual Frameworks):
{chr(10).join(f"  - {node}" for node in nodes_data.get("Level2", []))}

Level 1 (Concrete Techniques):
{chr(10).join(f"  - {node}" for node in nodes_data.get("Level1", []))}
"""
        
        # Load prompt template (check for custom prompt in session state)
        relations_prompt_template = self._load_prompt_template("prompts/find_relations.txt")
        
        # Construct the prompt with both nodes and paper text
        full_prompt = relations_prompt_template.replace("{nodes}", nodes_text)
        full_prompt = full_prompt.replace("{paper_text}", paper_text)
        
        try:
            # Call the LLM API with retry logic
            print(f"[DEBUG] Calling LLM API (Pass 2 - Relations) with model: {self.model}")
            
            response = self._call_api_with_retry(
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=8000,
                temperature=0.0,
                max_retries=3,
                disable_thinking=True
            )
            
            # Extract the response
            content = response.choices[0].message.content
            
            # Parse JSON from the response
            parsed_json = self._extract_json(content)
            
            # Validate relations structure
            # Accept a harmless casing variation from the model.
            if "Relations" not in parsed_json and "relations" in parsed_json:
                parsed_json["Relations"] = parsed_json.pop("relations")

            if "Relations" not in parsed_json:
                raise ValueError("Missing required key: Relations")
            
            if not isinstance(parsed_json["Relations"], list):
                raise ValueError("Relations must be a list")
            
            # Keep valid relations even if one model-generated item is bad.
            valid_relations = []
            for i, relation in enumerate(parsed_json["Relations"]):
                if not isinstance(relation, dict):
                    print(f"[WARNING] Relation {i}: expected an object, skipping")
                    continue

                required_fields = ["source", "target", "relation", "confidence", "explanation"]
                if not all(k in relation for k in required_fields):
                    print(f"[WARNING] Relation {i}: missing required fields, skipping")
                    continue
                
                # Validate confidence is within range
                confidence = relation.get("confidence")
                if isinstance(confidence, str):
                    try:
                        confidence = float(confidence)
                        relation["confidence"] = confidence
                    except ValueError:
                        pass
                if not isinstance(confidence, (int, float)) or not (1 <= confidence <= 10):
                    print(f"[WARNING] Relation {i}: invalid confidence, skipping")
                    continue

                valid_relations.append(relation)

            parsed_json["Relations"] = valid_relations
            
            # Add token usage information
            parsed_json["_token_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return parsed_json
        
        except Exception as e:
            raise Exception(f"Error finding relations with LLM: {str(e)}")
    
    def _infer_context(self, hlg_data: Dict) -> Dict:
        """
        PASS 3: Infer additional contextual nodes and relations based on the existing graph.
        
        Args:
            hlg_data: Dictionary containing the complete graph from Pass 1 & 2
            
        Returns:
            Dictionary with InferredNodes and InferredRelations arrays (with confidence scores) and token usage
        """
        # Create a summary of the existing graph for the prompt
        graph_summary = f"""
NODES FROM PAPER:

Level 3 (Abstract Theoretical Concepts):
{chr(10).join(f"  - {node}" for node in hlg_data.get("Level3", []))}

Level 2 (Mathematical/Conceptual Frameworks):
{chr(10).join(f"  - {node}" for node in hlg_data.get("Level2", []))}

Level 1 (Concrete Techniques):
{chr(10).join(f"  - {node}" for node in hlg_data.get("Level1", []))}

RELATIONS FROM PAPER:

{chr(10).join(f"  - {rel.get('source')} --[{rel.get('relation')}]--> {rel.get('target')}" for rel in hlg_data.get("Relations", []))}
"""
        
        # Load prompt template (check for custom prompt in session state)
        inference_prompt_template = self._load_prompt_template("prompts/infer_context.txt")
        
        # Construct the prompt
        full_prompt = inference_prompt_template.replace("{graph_summary}", graph_summary)
        
        try:
            # Call the LLM API with retry logic
            print(f"[DEBUG] Calling LLM API (Pass 3 - Inference) with model: {self.model}")
            
            response = self._call_api_with_retry(
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=8000,
                temperature=0.2,
                max_retries=3
            )
            
            # Extract the response
            content = response.choices[0].message.content
            
            # Parse JSON from the response
            parsed_json = self._extract_json(content)
            
            # Validate structure
            if "InferredNodes" not in parsed_json:
                raise ValueError("Missing required key: InferredNodes")
            
            if "InferredRelations" not in parsed_json:
                raise ValueError("Missing required key: InferredRelations")
            
            # Validate inferred nodes
            for i, node in enumerate(parsed_json["InferredNodes"]):
                required_fields = ["node", "level", "confidence", "explanation"]
                if not all(k in node for k in required_fields):
                    raise ValueError(
                        f"InferredNode {i}: must have node, level, confidence, and explanation fields"
                    )
                
                # Validate confidence
                confidence = node.get("confidence")
                if not isinstance(confidence, (int, float)) or not (1 <= confidence <= 10):
                    raise ValueError(f"InferredNode {i}: confidence must be a number between 1 and 10")
            
            # Validate inferred relations
            for i, relation in enumerate(parsed_json["InferredRelations"]):
                required_fields = ["source", "target", "relation", "confidence", "explanation"]
                if not all(k in relation for k in required_fields):
                    raise ValueError(
                        f"InferredRelation {i}: must have source, target, relation, confidence, and explanation fields"
                    )
                
                # Validate confidence
                confidence = relation.get("confidence")
                if not isinstance(confidence, (int, float)) or not (1 <= confidence <= 10):
                    raise ValueError(f"InferredRelation {i}: confidence must be a number between 1 and 10")
            
            # Add token usage information
            parsed_json["_token_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return parsed_json
        
        except Exception as e:
            raise Exception(f"Error inferring context with LLM: {str(e)}")
    
    def find_cross_paper_relations(self, papers: list) -> Dict:
        """
        PASS 4 (Multi-Paper Mode): Find relations between concepts from different papers.
        
        Args:
            papers: List of paper dictionaries, each containing:
                - id: paper identifier
                - name: paper filename
                - text: extracted paper text (for context)
                - hlg_data: HLG data from individual analysis
                
        Returns:
            Dictionary with cross-paper relations array (with confidence scores) and token usage
        """
        # Format papers data for the prompt
        papers_text = ""
        for paper in papers:
            hlg = paper['hlg_data']
            
            # Get paper abstract/intro (first 2000 chars for context)
            paper_excerpt = paper['text'][:2000] if len(paper['text']) > 2000 else paper['text']
            
            papers_text += f"""
========================================
PAPER ID: {paper['id']}
PAPER NAME: {paper['name']}
========================================

PAPER EXCERPT (for context):
{paper_excerpt}

EXTRACTED CONCEPTS:

Level 3 (Problems & Challenges):
{chr(10).join(f"  - {node}" for node in hlg.get("Level3", []))}

Level 2 (Mathematical/Conceptual Frameworks):
{chr(10).join(f"  - {node}" for node in hlg.get("Level2", []))}

Level 1 (Techniques & Implementations):
{chr(10).join(f"  - {node}" for node in hlg.get("Level1", []))}

"""
        
        # Load prompt template (check for custom prompt in session state)
        cross_paper_prompt_template = self._load_prompt_template("prompts/cross_paper_relations.txt")
        
        # Construct the prompt
        full_prompt = cross_paper_prompt_template.replace("{papers_data}", papers_text.strip())
        
        try:
            # Call the LLM API with retry logic
            num_papers = len(papers)
            num_pairs = num_papers * (num_papers - 1) // 2
            print(f"[DEBUG] Calling LLM API (Pass 4 - Cross-Paper) with model: {self.model}")
            print(f"[DEBUG] Analyzing {num_papers} papers ({num_pairs} possible paper pairs)")
            
            response = self._call_api_with_retry(
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=8000,  # Increased to allow more comprehensive cross-paper analysis
                temperature=0.0,  # Deterministic generation for consistent results
                max_retries=3,
                disable_thinking=True
            )
            
            # Extract the response
            content = response.choices[0].message.content
            
            # Parse JSON from the response
            parsed_json = self._extract_json(content)
            
            # Validate structure
            if "relations" not in parsed_json:
                raise ValueError("Missing required key: relations")
            
            if not isinstance(parsed_json["relations"], list):
                raise ValueError("relations must be a list")
            
            # Build a map of paper_id -> all extracted nodes for validation
            paper_nodes_map = {}
            for paper in papers:
                paper_id = paper['id']
                hlg = paper.get('hlg_data', {})
                # Collect all nodes from all levels
                all_nodes = set()
                all_nodes.update(hlg.get("Level3", []))
                all_nodes.update(hlg.get("Level2", []))
                all_nodes.update(hlg.get("Level1", []))
                # Also include inferred nodes if present
                for inferred_node in hlg.get("InferredNodes", []):
                    all_nodes.add(inferred_node.get("node"))
                paper_nodes_map[paper_id] = all_nodes
            
            # Validate and auto-correct cross-paper relations
            valid_relations = []
            corrected_count = 0
            skipped_count = 0
            
            for i, relation in enumerate(parsed_json["relations"]):
                # Check required fields
                required_fields = ["source", "source_paper", "target", "target_paper", "relation", "confidence", "explanation"]
                if not all(k in relation for k in required_fields):
                    skipped_count += 1
                    print(f"[WARNING] Cross-paper relation {i}: missing required fields, skipping")
                    continue
                
                # Validate confidence
                confidence = relation.get("confidence")
                if not isinstance(confidence, (int, float)) or not (1 <= confidence <= 10):
                    skipped_count += 1
                    print(f"[WARNING] Cross-paper relation {i}: invalid confidence ({confidence}), skipping")
                    continue
                
                # Validate that source_paper != target_paper
                if relation.get("source_paper") == relation.get("target_paper"):
                    skipped_count += 1
                    print(f"[WARNING] Cross-paper relation {i}: source and target papers are the same, skipping")
                    continue
                
                # Check and correct source node
                source = relation.get("source")
                source_paper = relation.get("source_paper")
                if source_paper not in paper_nodes_map:
                    skipped_count += 1
                    print(f"[WARNING] Cross-paper relation {i}: source paper '{source_paper}' not found, skipping")
                    continue
                
                if source not in paper_nodes_map[source_paper]:
                    # Try to find closest matching node
                    closest_source = self._find_closest_node(source, paper_nodes_map[source_paper])
                    if closest_source:
                        print(f"[INFO] Cross-paper relation {i}: source node '{source}' not found, using closest match '{closest_source}'")
                        relation["source"] = closest_source
                        corrected_count += 1
                    else:
                        skipped_count += 1
                        print(f"[WARNING] Cross-paper relation {i}: source node '{source}' not found in {source_paper} and no close match found. Skipping relation.")
                        continue
                
                # Check and correct target node
                target = relation.get("target")
                target_paper = relation.get("target_paper")
                if target_paper not in paper_nodes_map:
                    skipped_count += 1
                    print(f"[WARNING] Cross-paper relation {i}: target paper '{target_paper}' not found, skipping")
                    continue
                
                if target not in paper_nodes_map[target_paper]:
                    # Try to find closest matching node
                    closest_target = self._find_closest_node(target, paper_nodes_map[target_paper])
                    if closest_target:
                        print(f"[INFO] Cross-paper relation {i}: target node '{target}' not found, using closest match '{closest_target}'")
                        relation["target"] = closest_target
                        corrected_count += 1
                    else:
                        skipped_count += 1
                        print(f"[WARNING] Cross-paper relation {i}: target node '{target}' not found in {target_paper} and no close match found. Skipping relation.")
                        continue
                
                # Relation is valid (possibly corrected), add it
                valid_relations.append(relation)
            
            # Replace relations list with corrected/valid relations
            parsed_json["relations"] = valid_relations
            
            if corrected_count > 0 or skipped_count > 0:
                print(f"[INFO] Processed cross-paper relations: {corrected_count} corrected, {skipped_count} skipped, {len(valid_relations)} valid relation(s) remaining.")
            
            # Add token usage information
            parsed_json["_token_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            # Debug: Show coverage of paper pairs
            paper_ids = [p['id'] for p in papers]
            found_pairs = set()
            for rel in parsed_json.get("relations", []):
                src = rel.get("source_paper")
                tgt = rel.get("target_paper")
                # Normalize pair order for checking
                pair = tuple(sorted([src, tgt]))
                found_pairs.add(pair)
            
            all_pairs = set()
            for i in range(len(paper_ids)):
                for j in range(i + 1, len(paper_ids)):
                    all_pairs.add(tuple(sorted([paper_ids[i], paper_ids[j]])))
            
            missing_pairs = all_pairs - found_pairs
            print(f"[DEBUG] Cross-paper relations found between {len(found_pairs)} of {len(all_pairs)} possible paper pairs")
            if missing_pairs:
                print(f"[DEBUG] No relations found between: {', '.join([f'{p[0]}↔{p[1]}' for p in missing_pairs])}")
            
            return parsed_json
        
        except Exception as e:
            raise Exception(f"Error finding cross-paper relations with LLM: {str(e)}")
    
    def _extract_json(self, text: str) -> Dict:
        """
        Find relations between concepts from two researchers' HLGs.
        
        Args:
            researcher_1_hlg: HLG data from researcher 1
            researcher_2_hlg: HLG data from researcher 2
            researcher_1_id: ID/label for researcher 1 (default: "R1")
            researcher_2_id: ID/label for researcher 2 (default: "R2")
            
        Returns:
            Dictionary with cross-researcher relations array (with confidence scores) and token usage
        """
        # Format HLG data for the prompt
        def format_hlg_data(hlg_data: Dict, researcher_label: str) -> str:
            """Format HLG data into a readable string for the prompt."""
            level3_nodes = hlg_data.get("Level3", [])
            level2_nodes = hlg_data.get("Level2", [])
            level1_nodes = hlg_data.get("Level1", [])
            relations = hlg_data.get("Relations", [])
            
            formatted = f"""
{researcher_label} CONCEPTS:

Level 3 (Problems & Challenges):
{chr(10).join(f"  - {node}" for node in level3_nodes) if level3_nodes else "  (none)"}

Level 2 (Mathematical/Conceptual Frameworks):
{chr(10).join(f"  - {node}" for node in level2_nodes) if level2_nodes else "  (none)"}

Level 1 (Techniques & Implementations):
{chr(10).join(f"  - {node}" for node in level1_nodes) if level1_nodes else "  (none)"}

{researcher_label} RELATIONS ({len(relations)} total):
{chr(10).join(f"  - {rel.get('source')} --[{rel.get('relation')}]--> {rel.get('target')}" for rel in relations[:20]) if relations else "  (none)"}
{"..." if len(relations) > 20 else ""}
"""
            return formatted
        
        researcher_1_text = format_hlg_data(researcher_1_hlg, f"RESEARCHER 1 ({researcher_1_id})")
        researcher_2_text = format_hlg_data(researcher_2_hlg, f"RESEARCHER 2 ({researcher_2_id})")
        
        # Load prompt template (check for custom prompt in session state)
        cross_researcher_prompt_template = self._load_prompt_template("prompts/cross_researcher_relations.txt")
        
        # Construct the prompt
        full_prompt = cross_researcher_prompt_template.replace("{researcher_1_data}", researcher_1_text.strip())
        full_prompt = full_prompt.replace("{researcher_2_data}", researcher_2_text.strip())
        
        try:
            # Call the LLM API with retry logic
            print(f"[DEBUG] Calling LLM API (Cross-Researcher Relations) with model: {self.model}")
            
            response = self._call_api_with_retry(
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=8000,
                temperature=0.0,  # Deterministic generation
                max_retries=3
            )
            
            # Extract the response
            content = response.choices[0].message.content
            
            # Parse JSON from the response
            parsed_json = self._extract_json(content)
            
            # Validate structure
            if "relations" not in parsed_json:
                raise ValueError("Missing required key: relations")
            
            if not isinstance(parsed_json["relations"], list):
                raise ValueError("relations must be a list")
            
            # Build node maps for validation
            r1_nodes = set()
            r1_nodes.update(researcher_1_hlg.get("Level3", []))
            r1_nodes.update(researcher_1_hlg.get("Level2", []))
            r1_nodes.update(researcher_1_hlg.get("Level1", []))
            for inferred_node in researcher_1_hlg.get("InferredNodes", []):
                r1_nodes.add(inferred_node.get("node"))
            
            r2_nodes = set()
            r2_nodes.update(researcher_2_hlg.get("Level3", []))
            r2_nodes.update(researcher_2_hlg.get("Level2", []))
            r2_nodes.update(researcher_2_hlg.get("Level1", []))
            for inferred_node in researcher_2_hlg.get("InferredNodes", []):
                r2_nodes.add(inferred_node.get("node"))
            
            # Validate and auto-correct cross-researcher relations
            valid_relations = []
            corrected_count = 0
            skipped_count = 0
            
            for i, relation in enumerate(parsed_json["relations"]):
                # Check required fields
                required_fields = ["source", "source_researcher", "target", "target_researcher", "relation", "confidence", "explanation"]
                if not all(k in relation for k in required_fields):
                    skipped_count += 1
                    print(f"[WARNING] Cross-researcher relation {i}: missing required fields, skipping")
                    continue
                
                # Validate confidence
                confidence = relation.get("confidence")
                if not isinstance(confidence, (int, float)) or not (1 <= confidence <= 10):
                    skipped_count += 1
                    print(f"[WARNING] Cross-researcher relation {i}: invalid confidence ({confidence}), skipping")
                    continue
                
                # Validate that source_researcher != target_researcher
                if relation.get("source_researcher") == relation.get("target_researcher"):
                    skipped_count += 1
                    print(f"[WARNING] Cross-researcher relation {i}: source and target researchers are the same, skipping")
                    continue
                
                # Check and correct source node
                source = relation.get("source")
                source_researcher = relation.get("source_researcher")
                # Map researcher IDs to node sets
                source_nodes = r1_nodes if source_researcher == researcher_1_id else r2_nodes if source_researcher == researcher_2_id else None
                
                if source_nodes is None:
                    skipped_count += 1
                    print(f"[WARNING] Cross-researcher relation {i}: invalid source researcher '{source_researcher}' (expected {researcher_1_id} or {researcher_2_id}), skipping")
                    continue
                
                if source not in source_nodes:
                    # Try to find closest matching node
                    closest_source = self._find_closest_node(source, source_nodes)
                    if closest_source:
                        print(f"[INFO] Cross-researcher relation {i}: source node '{source}' not found, using closest match '{closest_source}'")
                        relation["source"] = closest_source
                        corrected_count += 1
                    else:
                        skipped_count += 1
                        print(f"[WARNING] Cross-researcher relation {i}: source node '{source}' not found in {source_researcher} and no close match found. Skipping relation.")
                        continue
                
                # Check and correct target node
                target = relation.get("target")
                target_researcher = relation.get("target_researcher")
                # Map researcher IDs to node sets
                target_nodes = r1_nodes if target_researcher == researcher_1_id else r2_nodes if target_researcher == researcher_2_id else None
                
                if target_nodes is None:
                    skipped_count += 1
                    print(f"[WARNING] Cross-researcher relation {i}: invalid target researcher '{target_researcher}' (expected {researcher_1_id} or {researcher_2_id}), skipping")
                    continue
                
                if target not in target_nodes:
                    # Try to find closest matching node
                    closest_target = self._find_closest_node(target, target_nodes)
                    if closest_target:
                        print(f"[INFO] Cross-researcher relation {i}: target node '{target}' not found, using closest match '{closest_target}'")
                        relation["target"] = closest_target
                        corrected_count += 1
                    else:
                        skipped_count += 1
                        print(f"[WARNING] Cross-researcher relation {i}: target node '{target}' not found in {target_researcher} and no close match found. Skipping relation.")
                        continue
                
                # Relation is valid (possibly corrected), add it
                valid_relations.append(relation)
            
            # Replace relations list with corrected/valid relations
            parsed_json["relations"] = valid_relations
            
            # Add token usage information
            parsed_json["_token_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            if corrected_count > 0 or skipped_count > 0:
                print(f"[INFO] Processed cross-researcher relations: {corrected_count} corrected, {skipped_count} skipped, {len(valid_relations)} valid relation(s) remaining.")
            
            return parsed_json
        
        except Exception as e:
            raise Exception(f"Error finding cross-researcher relations with LLM: {str(e)}")
    
    def _extract_json(self, text: str) -> Dict:
        """
        Extract JSON from LLM response.
        
        Args:
            text: Response text that may contain JSON
            
        Returns:
            Parsed JSON dictionary
        """
        # Print debug info (first 500 chars of response)
        print(f"\n[DEBUG] LLM Response (first 500 chars):\n{text[:500]}\n")
        
        # Try to find JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON directly
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = text
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Provide more detailed error message
            error_msg = (
                f"Failed to parse JSON from LLM response.\n"
                f"JSONDecodeError: {str(e)}\n"
                f"Model: {self.model}\n"
                f"Response length: {len(text)} characters\n"
                f"First 500 chars of response:\n{text[:500]}\n"
            )
            if len(text) > 500:
                error_msg += f"Last 200 chars of response:\n{text[-200:]}\n"
            
            raise ValueError(error_msg)
    
    def test_api_connection(self) -> bool:
        """
        Test the API connection with a simple request.
        
        Args:
            hlg_data: Hierarchical logic graph dictionary
            paper_text: Original paper text for context
            
        Returns:
            Dictionary with evaluation scores and issues
        """
        issues = {
            "correctness": [],
            "conciseness": [],
            "insightfulness": []
        }
        
        # Extract node counts
        level3_count = len(hlg_data.get("Level3", []))
        level2_count = len(hlg_data.get("Level2", []))
        level1_count = len(hlg_data.get("Level1", []))
        total_nodes = level3_count + level2_count + level1_count
        relations_count = len(hlg_data.get("Relations", []))
        
        # Paper metrics
        paper_length = len(paper_text)
        words_count = len(paper_text.split())
        
        # === CORRECTNESS HEURISTICS ===
        correctness_score = 10
        
        # Check for isolated nodes
        nodes_in_relations = set()
        for rel in hlg_data.get("Relations", []):
            nodes_in_relations.add(rel.get("source"))
            nodes_in_relations.add(rel.get("target"))
        
        all_nodes = set(hlg_data.get("Level3", [])) | set(hlg_data.get("Level2", [])) | set(hlg_data.get("Level1", []))
        isolated_nodes = all_nodes - nodes_in_relations
        
        if len(isolated_nodes) > 0:
            issues["correctness"].append({
                "type": "isolated_nodes",
                "description": f"{len(isolated_nodes)} node(s) have no connections: {', '.join(list(isolated_nodes)[:3])}"
            })
            correctness_score -= min(2, len(isolated_nodes) * 0.5)
        
        # Check for very low confidence relations
        low_conf_count = sum(1 for rel in hlg_data.get("Relations", []) if rel.get("confidence", 10) < 5)
        if low_conf_count > relations_count * 0.3:  # More than 30% low confidence
            issues["correctness"].append({
                "type": "low_confidence",
                "description": f"{low_conf_count} relations have confidence < 5/10"
            })
            correctness_score -= 1
        
        # === CONCISENESS HEURISTICS ===
        conciseness_score = 10
        
        # Check node density (nodes per 1000 words)
        nodes_per_1k_words = (total_nodes / words_count) * 1000 if words_count > 0 else 0
        
        if nodes_per_1k_words > 15:  # Too dense
            issues["conciseness"].append({
                "type": "too_dense",
                "description": f"High node density ({nodes_per_1k_words:.1f} nodes/1000 words). Consider consolidating similar concepts."
            })
            conciseness_score -= 2
        elif nodes_per_1k_words < 2:  # Too sparse
            issues["conciseness"].append({
                "type": "too_sparse",
                "description": f"Low node density ({nodes_per_1k_words:.1f} nodes/1000 words). May be missing important concepts."
            })
            conciseness_score -= 2
        
        # Check for very long labels (>4 words)
        long_labels = [node for node in all_nodes if len(node.split()) > 4]
        if len(long_labels) > 0:
            issues["conciseness"].append({
                "type": "verbose_labels",
                "description": f"{len(long_labels)} node(s) have labels >4 words. Examples: {', '.join(long_labels[:2])}"
            })
            conciseness_score -= 1
        
        # Check relation density
        max_possible_relations = total_nodes * (total_nodes - 1)
        relation_density = relations_count / max_possible_relations if max_possible_relations > 0 else 0
        
        if relation_density > 0.3:  # Too connected
            issues["conciseness"].append({
                "type": "over_connected",
                "description": f"Very high connectivity ({relation_density:.1%}). Consider keeping only essential relations."
            })
            conciseness_score -= 1
        
        # === INSIGHTFULNESS HEURISTICS ===
        insightfulness_score = 10
        
        # Check level balance
        if level3_count == 0:
            issues["insightfulness"].append({
                "type": "missing_level",
                "description": "No Level 3 concepts (high-level problems). Missing big picture context."
            })
            insightfulness_score -= 3
        
        if level2_count == 0:
            issues["insightfulness"].append({
                "type": "missing_level",
                "description": "No Level 2 concepts (frameworks). Missing theoretical foundation."
            })
            insightfulness_score -= 3
        
        if level1_count == 0:
            issues["insightfulness"].append({
                "type": "missing_level",
                "description": "No Level 1 concepts (techniques). Missing concrete implementations."
            })
            insightfulness_score -= 3
        
        # Check for cross-level connections
        cross_level_relations = 0
        for rel in hlg_data.get("Relations", []):
            src = rel.get("source")
            tgt = rel.get("target")
            src_level = None
            tgt_level = None
            
            if src in hlg_data.get("Level3", []): src_level = 3
            elif src in hlg_data.get("Level2", []): src_level = 2
            elif src in hlg_data.get("Level1", []): src_level = 1
            
            if tgt in hlg_data.get("Level3", []): tgt_level = 3
            elif tgt in hlg_data.get("Level2", []): tgt_level = 2
            elif tgt in hlg_data.get("Level1", []): tgt_level = 1
            
            if src_level and tgt_level and src_level != tgt_level:
                cross_level_relations += 1
        
        if cross_level_relations == 0 and total_nodes > 3:
            issues["insightfulness"].append({
                "type": "no_cross_level",
                "description": "No cross-level connections. Missing problem→solution narrative."
            })
            insightfulness_score -= 2
        
        # Check minimum connectivity
        avg_connections_per_node = (relations_count * 2) / total_nodes if total_nodes > 0 else 0
        if avg_connections_per_node < 1.5:
            issues["insightfulness"].append({
                "type": "low_connectivity",
                "description": f"Low average connectivity ({avg_connections_per_node:.1f} connections/node). Graph may be fragmented."
            })
            insightfulness_score -= 1
        
        # Ensure scores are in valid range
        correctness_score = max(1, min(10, correctness_score))
        conciseness_score = max(1, min(10, conciseness_score))
        insightfulness_score = max(1, min(10, insightfulness_score))
        overall_score = (correctness_score + conciseness_score + insightfulness_score) / 3
        
        # Generate strengths
        strengths = []
        if len(isolated_nodes) == 0:
            strengths.append("All nodes are connected")
        if 5 <= nodes_per_1k_words <= 10:
            strengths.append("Good node density")
        if cross_level_relations > 0:
            strengths.append(f"{cross_level_relations} cross-level connections")
        if low_conf_count == 0:
            strengths.append("All relations have high confidence")
        
        return {
            "correctness": {
                "score": round(correctness_score, 1),
                "explanation": f"Heuristic analysis based on {total_nodes} nodes and {relations_count} relations. {len(isolated_nodes)} isolated nodes found.",
                "issues": issues["correctness"],
                "strengths": strengths[:2] if strengths else ["Structure is present"]
            },
            "conciseness": {
                "score": round(conciseness_score, 1),
                "explanation": f"Node density: {nodes_per_1k_words:.1f} nodes per 1000 words. Relation density: {relation_density:.1%}.",
                "issues": issues["conciseness"],
                "suggestions": ["Check for redundant concepts", "Ensure all labels are concise"] if issues["conciseness"] else []
            },
            "insightfulness": {
                "score": round(insightfulness_score, 1),
                "explanation": f"Level distribution: L3={level3_count}, L2={level2_count}, L1={level1_count}. {cross_level_relations} cross-level relations.",
                "strengths": strengths[2:] if len(strengths) > 2 else ["Basic structure present"],
                "missing_insights": ["Consider adding more cross-level connections"] if cross_level_relations < 2 else []
            },
            "overall_score": round(overall_score, 1),
            "overall_assessment": f"Quick heuristic evaluation based on structural metrics. Overall score: {overall_score:.1f}/10. Use Deep Evaluation for semantic analysis.",
            "improvement_suggestions": self._generate_quick_suggestions(issues, level3_count, level2_count, level1_count, cross_level_relations),
            "evaluation_type": "quick_heuristic"
        }
    
    def _generate_quick_suggestions(self, issues: Dict, l3: int, l2: int, l1: int, cross_level: int) -> list:
        """Generate improvement suggestions from heuristic issues."""
        suggestions = []
        
        for correctness_issue in issues["correctness"]:
            if correctness_issue["type"] == "isolated_nodes":
                suggestions.append("Connect isolated nodes or remove them if not relevant")
            elif correctness_issue["type"] == "low_confidence":
                suggestions.append("Review low-confidence relations for accuracy")
        
        for conciseness_issue in issues["conciseness"]:
            if conciseness_issue["type"] == "too_dense":
                suggestions.append("Consolidate similar or overlapping concepts")
            elif conciseness_issue["type"] == "too_sparse":
                suggestions.append("Add more key concepts from the paper")
            elif conciseness_issue["type"] == "verbose_labels":
                suggestions.append("Shorten node labels to ≤4 words")
        
        for insight_issue in issues["insightfulness"]:
            if insight_issue["type"] == "missing_level":
                suggestions.append(insight_issue["description"])
            elif insight_issue["type"] == "no_cross_level":
                suggestions.append("Add relations between L3→L2→L1 to show problem-solution flow")
        
        if not suggestions:
            suggestions.append("Structure looks good! Use Deep Evaluation for semantic quality check.")
        
        return suggestions[:5]  # Return top 5
    
    def deep_evaluate_hlg(self, hlg_data: Dict, paper_text: str) -> Dict:
        """
        Deep LLM-based semantic evaluation of HLG quality.
        
        Args:
            hlg_data: Hierarchical logic graph dictionary
            paper_text: Original paper text for comparison
            
        Returns:
            Dictionary with detailed evaluation scores and suggestions
        """
        # Format HLG for the prompt
        hlg_summary = f"""
LEVEL 3 (Problems & Challenges):
{chr(10).join(f"  - {node}" for node in hlg_data.get("Level3", []))}

LEVEL 2 (Mathematical/Conceptual Frameworks):
{chr(10).join(f"  - {node}" for node in hlg_data.get("Level2", []))}

LEVEL 1 (Techniques & Implementations):
{chr(10).join(f"  - {node}" for node in hlg_data.get("Level1", []))}

RELATIONS ({len(hlg_data.get("Relations", []))} total):
{chr(10).join(f"  - {rel.get('source')} --[{rel.get('relation')}]--> {rel.get('target')} (confidence: {rel.get('confidence')}/10)" for rel in hlg_data.get("Relations", [])[:20])}
{"..." if len(hlg_data.get("Relations", [])) > 20 else ""}

OVERALL CONFIDENCE: {hlg_data.get('overall_confidence', 'N/A')}/10
"""
        
        # Load prompt template (check for custom prompt in session state)
        evaluation_prompt_template = self._load_prompt_template("prompts/evaluate_hlg.txt")
        
        # Construct the prompt
        full_prompt = evaluation_prompt_template.replace("{hlg_summary}", hlg_summary)
        full_prompt = full_prompt.replace("{paper_text}", paper_text[:10000])  # Limit paper text to first 10k chars
        
        try:
            # Call the LLM API
            print(f"[DEBUG] Calling LLM API (HLG Evaluation) with model: {self.model}")
            
            response = self._call_api_with_retry(
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=8000,
                temperature=0.1,  # Low temperature for consistent evaluation
                max_retries=3
            )
            
            # Extract the response
            content = response.choices[0].message.content
            
            # Parse JSON from the response
            parsed_json = self._extract_json(content)
            
            # Validate structure
            required_keys = ["correctness", "conciseness", "insightfulness", "overall_score", "overall_assessment"]
            for key in required_keys:
                if key not in parsed_json:
                    raise ValueError(f"Missing required key: {key}")
            
            # Add token usage information
            parsed_json["_token_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            parsed_json["evaluation_type"] = "deep_llm"
            
            return parsed_json
        
        except Exception as e:
            raise Exception(f"Error evaluating HLG with LLM: {str(e)}")
    
    def test_api_connection(self) -> bool:
        """
        Test the API connection with a simple request.
        
        Returns:
            True if the API is working, False otherwise
        """
        try:
            print(f"[API TEST] Testing connection to Zhipu BigModel with model: {self.model}")
            print(f"[API TEST] API Key (first 10 chars): {self.api_key[:10]}...")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": "Reply with exactly this JSON: {\"status\": \"ok\"}"}
                ],
                temperature=0.0,
                max_tokens=2048,  # Reasoning models spend tokens on chain-of-thought first
            )
            
            content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            
            print(f"[API TEST] Response received:")
            print(f"[API TEST] - Length: {len(content)} characters")
            print(f"[API TEST] - Finish reason: {finish_reason}")
            print(f"[API TEST] - Content: {content[:200]}")
            
            if content and len(content) > 0:
                print("[API TEST] [OK] API connection successful!")
                return True
            else:
                print("[API TEST] [FAIL] API returned empty response")
                return False
                
        except Exception as e:
            print(f"[API TEST] [ERROR] API connection failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def generate_embeddings(self, texts: list, model: str = "scibert") -> list:
        """
        Generate embeddings for a list of texts using SciBERT model.
        
        Args:
            texts: List of text strings to embed
            model: Embedding model to use (default: scibert, uses allenai/scibert_scivocab_uncased)
            
        Returns:
            List of embedding vectors (each is a list of floats)
        """
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            import numpy as np
            import os
            import time
            
            print(f"[EMBEDDING] Generating embeddings for {len(texts)} texts using SciBERT")
            
            # Load SciBERT model and tokenizer (cache in class if not already loaded)
            if not hasattr(self, '_scibert_tokenizer') or not hasattr(self, '_scibert_model'):
                print("[EMBEDDING] Loading SciBERT model (this may take a moment on first run)...")
                model_name = "allenai/scibert_scivocab_uncased"
                
                # Configure proxy settings if available
                proxy_config = {}
                if os.environ.get('HTTP_PROXY'):
                    proxy_config['proxies'] = {'http': os.environ['HTTP_PROXY'], 'https': os.environ['HTTP_PROXY']}
                if os.environ.get('HTTPS_PROXY'):
                    proxy_config['proxies'] = {'http': os.environ['HTTPS_PROXY'], 'https': os.environ['HTTPS_PROXY']}
                
                # Try loading with retry logic for network issues
                max_retries = 3
                retry_delay = 2
                
                for attempt in range(1, max_retries + 1):
                    try:
                        # Try to load from cache first (local_files_only=True)
                        # If that fails, try downloading
                        try:
                            print(f"[EMBEDDING] Attempt {attempt}: Trying to load from cache...")
                            self._scibert_tokenizer = AutoTokenizer.from_pretrained(
                                model_name, 
                                local_files_only=True
                            )
                            self._scibert_model = AutoModel.from_pretrained(
                                model_name,
                                local_files_only=True
                            )
                            print("[EMBEDDING] Model loaded from cache successfully")
                            break
                        except (OSError, ValueError) as cache_error:
                            # Model not in cache, try downloading
                            if attempt < max_retries:
                                print(f"[EMBEDDING] Model not in cache. Attempting to download (attempt {attempt}/{max_retries})...")
                            else:
                                print(f"[EMBEDDING] Model not in cache. Attempting final download...")
                            
                            # Set environment variables for proxy if needed
                            if proxy_config.get('proxies'):
                                import requests
                                # Configure requests to use proxy
                                os.environ.setdefault('HTTP_PROXY', proxy_config['proxies']['http'])
                                os.environ.setdefault('HTTPS_PROXY', proxy_config['proxies']['https'])
                            
                            self._scibert_tokenizer = AutoTokenizer.from_pretrained(model_name)
                            self._scibert_model = AutoModel.from_pretrained(model_name)
                            print("[EMBEDDING] Model downloaded and loaded successfully")
                            break
                            
                    except Exception as download_error:
                        error_str = str(download_error)
                        
                        # Check for proxy/SSL errors
                        if 'proxy' in error_str.lower() or 'ssl' in error_str.lower() or 'SSLEOFError' in error_str:
                            if attempt < max_retries:
                                print(f"[EMBEDDING] Network/proxy error (attempt {attempt}/{max_retries}): {error_str[:200]}")
                                print(f"[EMBEDDING] Retrying in {retry_delay} seconds...")
                                time.sleep(retry_delay)
                                retry_delay *= 2  # Exponential backoff
                            else:
                                # Final attempt failed
                                error_msg = (
                                    f"Failed to download SciBERT model after {max_retries} attempts.\n\n"
                                    f"Error: {error_str}\n\n"
                                    f"Possible solutions:\n"
                                    f"1. Check your internet connection\n"
                                    f"2. Configure proxy settings:\n"
                                    f"   - Set HTTP_PROXY and HTTPS_PROXY environment variables\n"
                                    f"   - Or configure proxy in your system settings\n"
                                    f"3. If behind a firewall, ensure huggingface.co is accessible\n"
                                    f"4. Try downloading the model manually and placing it in the cache:\n"
                                    f"   - Cache location: ~/.cache/huggingface/hub/models--allenai--scibert_scivocab_uncased\n"
                                    f"5. Use a VPN if your network blocks Hugging Face\n"
                                )
                                raise Exception(error_msg)
                        else:
                            # Other errors, raise immediately
                            raise
                
                self._scibert_model.eval()  # Set to evaluation mode
                print("[EMBEDDING] SciBERT model ready for inference")
            
            embeddings = []
            
            # Process in batches to manage memory
            batch_size = 32  # Smaller batches for local model processing
            
            with torch.no_grad():  # Disable gradient computation for inference
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i + batch_size]
                    print(f"[EMBEDDING] Processing batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size} ({len(batch)} texts)")
                    
                    # Tokenize batch
                    encoded = self._scibert_tokenizer(
                        batch,
                        padding=True,
                        truncation=True,
                        max_length=512,
                        return_tensors='pt'
                    )
                    
                    # Generate embeddings
                    outputs = self._scibert_model(**encoded)
                    
                    # Use mean pooling: average the token embeddings (excluding padding)
                    # Shape: (batch_size, seq_len, hidden_size)
                    attention_mask = encoded['attention_mask']
                    token_embeddings = outputs.last_hidden_state
                    
                    # Expand attention mask to match embedding dimensions
                    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
                    
                    # Sum embeddings and divide by sum of attention mask (mean pooling)
                    sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, dim=1)
                    sum_mask = torch.clamp(input_mask_expanded.sum(dim=1), min=1e-9)
                    batch_embeddings = (sum_embeddings / sum_mask).cpu().numpy()
                    
                    # Convert to list of lists
                    embeddings.extend([emb.tolist() for emb in batch_embeddings])
            
            print(f"[EMBEDDING] Successfully generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            error_msg = str(e)
            # Provide more helpful error message
            if 'proxy' in error_msg.lower() or 'ssl' in error_msg.lower():
                raise Exception(
                    f"Error generating embeddings (Network/Proxy Issue): {error_msg}\n\n"
                    f"To fix this:\n"
                    f"1. Set proxy environment variables: HTTP_PROXY and HTTPS_PROXY\n"
                    f"2. Check your network connection and firewall settings\n"
                    f"3. Ensure huggingface.co is accessible from your network\n"
                    f"4. Try using a VPN if your network blocks Hugging Face"
                )
            else:
                raise Exception(f"Error generating embeddings: {error_msg}")


if __name__ == "__main__":
    # Test the two-pass parser
    parser = LLMParser()
    
    test_text = """
    This paper introduces BETag, a novel approach for item tagging using behavior-enhanced 
    finetuning of large language models. We address the problem of sparse tag distribution 
    and unbalanced user behavior by employing low-rank parameter adaptation (LoRA) and 
    behavior-conditioned finetuning. Our method demonstrates significant improvements in 
    tag generation quality and diversity.
    """
    
    try:
        print("=" * 70)
        print("TWO-PASS LLM PARSER TEST")
        print("=" * 70)
        print("\nStarting analysis...\n")
        
        result = parser.parse_paper(test_text)
        
        # Display token usage (two-pass breakdown)
        if "_token_usage" in result:
            usage = result["_token_usage"]
            print("=" * 70)
            print("TOKEN USAGE (TWO-PASS)")
            print("=" * 70)
            print(f"\nPass 1 (Node Extraction):")
            print(f"  Prompt tokens:     {usage.get('pass1_prompt_tokens', 0):,}")
            print(f"  Completion tokens: {usage.get('pass1_completion_tokens', 0):,}")
            print(f"  Subtotal:          {usage.get('pass1_prompt_tokens', 0) + usage.get('pass1_completion_tokens', 0):,}")
            
            print(f"\nPass 2 (Relation Finding):")
            print(f"  Prompt tokens:     {usage.get('pass2_prompt_tokens', 0):,}")
            print(f"  Completion tokens: {usage.get('pass2_completion_tokens', 0):,}")
            print(f"  Subtotal:          {usage.get('pass2_prompt_tokens', 0) + usage.get('pass2_completion_tokens', 0):,}")
            
            print(f"\nTotal:")
            print(f"  Prompt tokens:     {usage['prompt_tokens']:,}")
            print(f"  Completion tokens: {usage['completion_tokens']:,}")
            print(f"  Total tokens:      {usage['total_tokens']:,}")
            print("=" * 70)
            print()
        
        # Display confidence scores summary
        print("=" * 70)
        print("CONFIDENCE SCORES")
        print("=" * 70)
        
        # Overall confidence
        if "overall_confidence" in result:
            print(f"\nOverall Analysis Confidence: {result['overall_confidence']}/10")
            print(f"Explanation: {result.get('overall_explanation', 'N/A')}")
        
        # Per-relation confidence
        if "Relations" in result:
            relations = result["Relations"]
            print(f"\n{len(relations)} Relations Found (ALL from LLM reasoning):\n")
            
            for i, rel in enumerate(relations, 1):
                confidence = rel.get('confidence', 'N/A')
                source = rel.get('source', 'N/A')
                target = rel.get('target', 'N/A')
                relation_type = rel.get('relation', 'N/A')
                explanation = rel.get('explanation', 'N/A')
                
                print(f"[{i}] {source} --[{relation_type}]--> {target}")
                print(f"    Confidence: {confidence}/10")
                print(f"    Explanation: {explanation}")
                print()
        
        print("=" * 70)
        print()
        
        # Display the full hierarchical logic graph JSON
        print("FULL JSON OUTPUT:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
