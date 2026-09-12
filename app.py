"""
Research Logic Graph Extractor - Streamlit Application
Multi-Paper Comparison Mode: Compare multiple research papers and find cross-paper relations
"""

import streamlit as st
from utils import load_custom_css, initialize_session_state
from modes import render_multi_paper_mode


# Page configuration
st.set_page_config(
    page_title="Research Logic Graph Extractor",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)




def main():
    """Main application function."""
    load_custom_css()
    initialize_session_state()
    
    # Header
    st.markdown('<div class="main-header">🧠 Multi-Paper Comparison Tool</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Compare multiple research papers and find cross-paper relations</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("📊 About")
        st.markdown("""
        This tool uses LLMs with a **multi-pass approach** to extract and compare the logical structure of multiple research papers.
        
        **Multi-Pass Analysis:**
        - 📝 **Pass 1**: Extract all concepts (nodes) from each paper
        - 🔗 **Pass 2**: Find ALL relations **grounded in paper text**
        - 🔮 **Pass 3 (Optional)**: Infer contextual nodes & relations
          - Adds concepts not in paper but relevant to research context
          - Infers logical connections and broader research context
          - Visually distinguished with dashed borders/lines
        - ✅ Every element has confidence scores and explanations
        
        **Cross-Paper Analysis:**
        - 🔍 Automatically identifies relations between concepts from different papers
        - 🎯 Finds connections like: extends, improves, validates, conflicts
        - 📊 Color-coded visualization with paper filters
        
        **Three Levels (Problem → Formulation → Solution):**
        - 🔵 **Level 3**: Research field problems & challenges
        - 🟣 **Level 2**: Mathematical/conceptual formulations
        - ⚫ **Level 1**: Technical solutions & algorithms
        """)
        
        st.markdown("---")
        
        # Model selection
        st.header("⚙️ Settings")
        model = st.selectbox(
            "LLM Model",
            [
                "glm-5.2",
                "glm-5.2-air",
                "glm-5.2-flash"
            ],
            index=0
        )
        
        max_chars = st.slider(
            "Max Characters to Process",
            min_value=5000,
            max_value=30000,
            value=15000,
            step=1000,
            help="Longer texts may take more time and tokens"
        )
        
        enable_inference = st.checkbox(
            "🔮 Enable Pass 3: Contextual Inference",
            value=False,
            help="Infer additional context nodes and relations beyond what's in the paper. Uses extra tokens."
        )
        
        st.session_state.model = model
        st.session_state.max_chars = max_chars
        st.session_state.enable_inference = enable_inference
        
        # Status indicator
        st.markdown("---")
        st.header("📊 Current Status")
        
        if st.session_state.multi_graph_data:
            st.success(f"✅ Multi-Paper Analysis Complete ({len(st.session_state.multi_papers)} papers)")
            st.caption("Your analysis data is available in all tabs")
        elif st.session_state.multi_papers:
            st.info(f"📝 {len(st.session_state.multi_papers)} Paper(s) Ready to Analyze")
        else:
            st.info("📝 Upload 2-5 papers to start analysis")
    
    # Render multi-paper mode
    render_multi_paper_mode()


if __name__ == "__main__":
    main()

