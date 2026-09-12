"""
Shared utilities for the Research Logic Graph Extractor application.
"""

import streamlit as st
import colorsys
from difflib import SequenceMatcher
import networkx as nx


def load_custom_css():
    """Load custom CSS for better styling."""
    st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #4A90E2;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #4A90E2;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        border: none;
    }
    .stButton>button:hover {
        background-color: #357ABD;
    }
    .info-box {
        padding: 1rem;
        border-radius: 8px;
        background-color: #f0f8ff;
        border-left: 4px solid #4A90E2;
        margin: 1rem 0;
    }
    .success-box {
        padding: 1rem;
        border-radius: 8px;
        background-color: #f0fff4;
        border-left: 4px solid #50C878;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        border-radius: 8px;
        background-color: #fff5f5;
        border-left: 4px solid #E85D75;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables for multi-paper mode."""
    # Multi-paper mode
    if 'multi_papers' not in st.session_state:
        st.session_state.multi_papers = []  # List of {id, name, text, hlg_data, color}
    if 'multi_graph_data' not in st.session_state:
        st.session_state.multi_graph_data = None
    if 'multi_graph_html' not in st.session_state:
        st.session_state.multi_graph_html = None
    if 'multi_processing_complete' not in st.session_state:
        st.session_state.multi_processing_complete = False


def render_confidence_badge(confidence):
    """Helper function to render confidence badge with color coding."""
    if isinstance(confidence, (int, float)):
        if confidence >= 8:
            confidence_color = "#50C878"  # Green
        elif confidence >= 6:
            confidence_color = "#FFD700"  # Yellow
        elif confidence >= 4:
            confidence_color = "#FFA500"  # Orange
        else:
            confidence_color = "#E85D75"  # Red
        return f'<span style="background-color: {confidence_color}; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold;">{confidence}/10</span>'
    else:
        return f'<span style="background-color: #999; color: white; padding: 2px 8px; border-radius: 4px;">N/A</span>'


def get_node_level_badge(node_name, hlg_data):
    """Helper function to get level badge for a node based on HLG data."""
    # Check Level 3
    if node_name in hlg_data.get("Level3", []):
        return '<span style="background-color: #4A90E2; color: white; padding: 1px 6px; border-radius: 3px; font-size: 0.85em; font-weight: bold;">L3</span>'
    
    # Check Level 2
    if node_name in hlg_data.get("Level2", []):
        return '<span style="background-color: #9B59B6; color: white; padding: 1px 6px; border-radius: 3px; font-size: 0.85em; font-weight: bold;">L2</span>'
    
    # Check Level 1
    if node_name in hlg_data.get("Level1", []):
        return '<span style="background-color: #9B9B9B; color: white; padding: 1px 6px; border-radius: 3px; font-size: 0.85em; font-weight: bold;">L1</span>'
    
    # Check Inferred Nodes
    for inferred_node in hlg_data.get("InferredNodes", []):
        if inferred_node.get("node") == node_name:
            level = inferred_node.get("level", "")
            if level == "Level3":
                return '<span style="background-color: #4A90E2; color: white; padding: 1px 6px; border-radius: 3px; font-size: 0.85em; font-weight: bold; border: 1px dashed white;">L3*</span>'
            elif level == "Level2":
                return '<span style="background-color: #9B59B6; color: white; padding: 1px 6px; border-radius: 3px; font-size: 0.85em; font-weight: bold; border: 1px dashed white;">L2*</span>'
            elif level == "Level1":
                return '<span style="background-color: #9B9B9B; color: white; padding: 1px 6px; border-radius: 3px; font-size: 0.85em; font-weight: bold; border: 1px dashed white;">L1*</span>'
    
    # Unknown level
    return '<span style="background-color: #666; color: white; padding: 1px 6px; border-radius: 3px; font-size: 0.85em;">?</span>'


def hsl_to_hex(h, s, l):
    """Convert HSL color to hex format.
    
    Args:
        h: Hue (0-360)
        s: Saturation (0-100)
        l: Lightness (0-100)
    
    Returns:
        Hex color string (e.g., "#FF0000")
    """
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"


def semantic_search_nodes(search_text, graph_data, threshold=0.4):
    """
    Perform semantic search to find nodes matching the search text.
    
    Args:
        search_text: Text to search for
        graph_data: Multi-paper graph data dictionary with 'papers' list
        threshold: Minimum similarity score (0-1) to consider a match
        
    Returns:
        List of tuples: (node_id, node_name, paper_id, similarity_score)
    """
    if not search_text or not search_text.strip():
        return []
    
    matches = []
    search_lower = search_text.lower().strip()
    search_words = set(search_lower.split())
    
    # Collect all nodes from all papers
    for paper in graph_data.get('papers', []):
        paper_id = paper.get('id', '')
        hlg_data = paper.get('hlg_data', {})
        
        # Skip papers without hlg_data
        if not hlg_data:
            continue
        
        # Search in Level 3, Level 2, Level 1 nodes
        for level_key in ['Level3', 'Level2', 'Level1']:
            for node_name in hlg_data.get(level_key, []):
                node_id = f"{paper_id}::{node_name}"
                node_lower = node_name.lower()
                
                # Calculate multiple similarity metrics
                # 1. Exact substring match
                if search_lower in node_lower or node_lower in search_lower:
                    matches.append((node_id, node_name, paper_id, 1.0))
                    continue
                
                # 2. Word overlap score
                node_words = set(node_lower.split())
                word_overlap = len(search_words & node_words) / max(len(search_words), 1)
                
                # 3. Sequence similarity (fuzzy matching)
                seq_similarity = SequenceMatcher(None, search_lower, node_lower).ratio()
                
                # 4. Combined score (weighted average)
                combined_score = (word_overlap * 0.4 + seq_similarity * 0.6)
                
                if combined_score >= threshold:
                    matches.append((node_id, node_name, paper_id, combined_score))
        
        # Also search in inferred nodes
        for inferred_node in hlg_data.get('InferredNodes', []):
            node_name = inferred_node.get('node', '')
            if node_name:
                node_id = f"{paper_id}::{node_name}"
                node_lower = node_name.lower()
                
                if search_lower in node_lower or node_lower in search_lower:
                    matches.append((node_id, node_name, paper_id, 1.0))
                    continue
                
                node_words = set(node_lower.split())
                word_overlap = len(search_words & node_words) / max(len(search_words), 1)
                seq_similarity = SequenceMatcher(None, search_lower, node_lower).ratio()
                combined_score = (word_overlap * 0.4 + seq_similarity * 0.6)
                
                if combined_score >= threshold:
                    matches.append((node_id, node_name, paper_id, combined_score))
    
    # Sort by similarity score (descending) and remove duplicates
    matches = sorted(set(matches), key=lambda x: x[3], reverse=True)
    return matches


def extract_subgraph_with_connected_components(graph, matching_node_ids):
    """
    Extract subgraph containing all nodes reachable from matching nodes.
    
    Args:
        graph: NetworkX DiGraph
        matching_node_ids: List of node IDs that match the search
        
    Returns:
        NetworkX DiGraph containing the subgraph
    """
    if not matching_node_ids or graph.number_of_nodes() == 0:
        return nx.DiGraph()
    
    # Find all nodes reachable from matching nodes (forward and backward)
    reachable_nodes = set(matching_node_ids)
    
    for node_id in matching_node_ids:
        if node_id in graph:
            # Forward reachable (nodes reachable from this node)
            forward_reachable = nx.descendants(graph, node_id)
            reachable_nodes.update(forward_reachable)
            
            # Backward reachable (nodes that can reach this node)
            backward_reachable = nx.ancestors(graph, node_id)
            reachable_nodes.update(backward_reachable)
    
    # Create subgraph with all reachable nodes
    subgraph = graph.subgraph(reachable_nodes).copy()
    
    return subgraph


def generate_paper_color(index, base_colors):
    """Generate a distinct color for a paper.
    
    Args:
        index: Paper index (0-based)
        base_colors: List of base color dictionaries
        
    Returns:
        Color dictionary with name, hex, and level colors
    """
    # Use predefined colors for first 5 papers
    if index < len(base_colors):
        return base_colors[index]
    
    # Generate distinct colors for papers beyond 5 using HSL color space
    # Distribute colors evenly around the color wheel
    num_extra = index - len(base_colors)
    total_extra = num_extra + 1  # How many extra colors we need
    
    # Use golden angle for even distribution (137.5 degrees)
    hue_step = 137.5
    hue = (len(base_colors) * hue_step + num_extra * hue_step) % 360
    
    # Use medium saturation and lightness for good visibility
    saturation = 70
    lightness = 50
    
    # Generate main color
    hex_color = hsl_to_hex(hue, saturation, lightness)
    
    # Generate level-specific colors (slightly adjusted)
    l3_color = hsl_to_hex(hue, saturation, lightness)
    l2p_color = hsl_to_hex((hue + 30) % 360, saturation - 10, lightness + 10)
    l2m_color = hsl_to_hex((hue + 60) % 360, saturation - 5, lightness + 15)
    l1_color = hsl_to_hex(hue, saturation - 40, lightness + 30)
    
    # Generate color name based on hue
    color_names = {
        (0, 30): "Red", (30, 60): "Orange", (60, 90): "Yellow",
        (90, 150): "Green", (150, 210): "Cyan", (210, 270): "Blue",
        (270, 300): "Indigo", (300, 330): "Violet", (330, 360): "Magenta"
    }
    color_name = "Custom"
    for (start, end), name in color_names.items():
        if start <= hue < end:
            color_name = name
            break
    
    return {
        "name": f"{color_name} {index + 1}",
        "hex": hex_color,
        "l3": l3_color,
        "l2p": l2p_color,
        "l2m": l2m_color,
        "l1": l1_color
    }


def render_prompt_customization_ui(prompts_config):
    """
    Render a UI for customizing prompts.
    
    Args:
        prompts_config: List of dicts with keys:
            - 'name': Display name for the prompt
            - 'key': Session state key for storing custom prompt
            - 'file_path': Path to the default prompt file
            - 'description': Description of what the prompt does
    """
    st.markdown("### ✏️ Customize Prompts")
    st.caption("Edit prompts to customize how the LLM analyzes papers. Changes take effect immediately for new analyses.")
    
    # Load default prompts
    def load_default_prompt(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""
    
    # Create tabs for each prompt
    prompt_tabs = st.tabs([prompt['name'] for prompt in prompts_config])
    
    for tab_idx, prompt_info in enumerate(prompts_config):
        with prompt_tabs[tab_idx]:
            st.markdown(f"#### {prompt_info['name']}")
            st.caption(prompt_info.get('description', ''))
            
            # Initialize session state if not exists
            session_key = prompt_info['key']
            if session_key not in st.session_state:
                st.session_state[session_key] = ""
            
            # Load default prompt
            default_prompt = load_default_prompt(prompt_info['file_path'])
            
            # Show current status
            col1, col2 = st.columns([3, 1])
            with col1:
                if st.session_state[session_key] and st.session_state[session_key].strip():
                    st.info("✅ Using custom prompt")
                else:
                    st.info("ℹ️ Using default prompt from file")
            
            with col2:
                if st.button("🔄 Reset to Default", key=f"reset_{session_key}"):
                    st.session_state[session_key] = ""
                    st.experimental_rerun()
            
            # Text area for editing prompt
            current_prompt = st.session_state[session_key] if st.session_state[session_key] else default_prompt
            
            edited_prompt = st.text_area(
                "Edit Prompt:",
                value=current_prompt,
                height=400,
                key=f"editor_{session_key}",
                help="Modify the prompt template. Use {paper_text}, {nodes}, {graph_summary}, {papers_data}, {researcher_1_data}, {researcher_2_data}, {hlg_summary} as placeholders where applicable."
            )
            
            # Save button
            col_save1, col_save2, col_save3 = st.columns([1, 1, 2])
            with col_save1:
                if st.button("💾 Save Custom Prompt", key=f"save_{session_key}"):
                    if edited_prompt.strip():
                        st.session_state[session_key] = edited_prompt.strip()
                        st.success("✅ Custom prompt saved!")
                    else:
                        st.warning("⚠️ Prompt cannot be empty")
            
            with col_save2:
                if st.button("🗑️ Clear Custom Prompt", key=f"clear_{session_key}"):
                    st.session_state[session_key] = ""
                    st.experimental_rerun()
            
            # Show character count
            st.caption(f"📊 Character count: {len(edited_prompt)}")
            
            # Show preview of default prompt in expander
            with st.expander("👁️ View Default Prompt"):
                st.text_area(
                    "Default Prompt:",
                    value=default_prompt,
                    height=300,
                    key=f"default_{session_key}",
                    disabled=True
                )




