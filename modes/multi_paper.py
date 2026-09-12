"""
Render Multi Paper Mode
"""

import streamlit as st
import json
import tempfile
import os
import streamlit.components.v1 as components
from pdf_extractor import extract_text_from_pdf_bytes, get_pdf_metadata
from llm_parser import LLMParser
from graph_builder import GraphBuilder
from utils import generate_paper_color, get_node_level_badge, render_confidence_badge, render_prompt_customization_ui

def render_multi_paper_mode():
    """Render the multi-paper analysis mode."""
    # Define paper colors for visualization
    PAPER_COLORS = [
        {"name": "Blue", "hex": "#4A90E2", "l3": "#4A90E2", "l2p": "#9B59B6", "l2m": "#50C878", "l1": "#9B9B9B"},
        {"name": "Red", "hex": "#E74C3C", "l3": "#E74C3C", "l2p": "#E67E22", "l2m": "#F39C12", "l1": "#BDC3C7"},
        {"name": "Green", "hex": "#27AE60", "l3": "#27AE60", "l2p": "#16A085", "l2m": "#1ABC9C", "l1": "#95A5A6"},
        {"name": "Purple", "hex": "#8E44AD", "l3": "#8E44AD", "l2p": "#9B59B6", "l2m": "#BB79C6", "l1": "#A9AEAF"},
        {"name": "Orange", "hex": "#D35400", "l3": "#D35400", "l2p": "#E67E22", "l2m": "#F39C12", "l1": "#BDC3C7"}
    ]
    
    st.header("📚 Multi-Paper Comparison Mode")
    st.markdown("Upload and compare multiple research papers to find cross-paper relations and insights.")
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📁 Load JSON", "📄 Upload Papers", "🔍 Analysis", "🎨 Visualization", "💾 Export", "✏️ Customize Prompts"])
    
    # Tab 1: Load JSON
    with tab1:
        st.header("📁 Load Multi-Paper Analysis from JSON")
        
        st.markdown("""
        **Quick Start: Upload Previously Exported Multi-Paper Analysis**
        
        Skip the PDF extraction and LLM analysis steps by uploading a JSON file that was exported from a previous multi-paper analysis.
        
        **Benefits:**
        - ✅ Instant visualization without LLM API costs
        - 📊 Share analysis results with collaborators
        - 💾 Review past comparative analyses offline
        - ⚡ No waiting for expensive multi-paper API calls
        - 🎨 Includes all papers and cross-paper relations
        
        **Compatible Files:**
        - Files exported from 'Export' tab → 'Download Multi-Paper Analysis JSON'
        - Any valid multi-paper analysis JSON with 'papers' array structure
        """)
        
        st.markdown("---")
        
        uploaded_json = st.file_uploader(
            "Choose a multi-paper JSON file",
            type=['json'],
            key="multi_json_upload_tab",
            help="Upload a multi-paper analysis JSON file exported from a previous analysis"
        )
        
        if uploaded_json is not None:
            try:
                json_content = json.loads(uploaded_json.read().decode('utf-8'))
                
                # Validate multi-paper structure
                if "papers" in json_content and isinstance(json_content.get("papers"), list):
                    # Ensure papers have color info
                    for idx, paper in enumerate(json_content["papers"]):
                        if "color" not in paper or not paper["color"]:
                            paper["color"] = generate_paper_color(idx, PAPER_COLORS)
                    
                    st.session_state.multi_graph_data = json_content
                    st.session_state.multi_papers = json_content["papers"]
                    st.session_state.multi_processing_complete = True
                    
                    st.success(f"✅ Successfully loaded: {uploaded_json.name}")
                    
                    # Show preview of loaded data
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Papers Loaded", len(json_content["papers"]))
                    with col2:
                        total_relations = sum(
                            len(p.get('hlg_data', {}).get('Relations', []))
                            for p in json_content["papers"]
                        )
                        st.metric("Intra-Paper Relations", total_relations)
                    with col3:
                        cross_relations = len(json_content.get('cross_paper_relations', []))
                        st.metric("Cross-Paper Relations", cross_relations)
                    
                    st.info("💡 Go to the 'Visualization' tab to see the interactive multi-paper graph!")
                    
                    # Show papers list
                    st.markdown("### 📚 Loaded Papers:")
                    for idx, paper in enumerate(json_content["papers"]):
                        color = paper.get('color', PAPER_COLORS[0])
                        st.markdown(f"**{idx+1}.** {paper.get('name', 'Unknown')} - <span style='background-color: {color['hex']}; color: white; padding: 2px 8px; border-radius: 4px;'>{color['name']}</span>", unsafe_allow_html=True)
                    
                    # Show quick preview
                    with st.expander("👁️ Preview Loaded Data"):
                        # Don't show full text to keep it manageable
                        preview_data = json_content.copy()
                        for paper in preview_data.get("papers", []):
                            if "text" in paper:
                                paper["text"] = f"{paper['text'][:200]}... (truncated)"
                        st.json(preview_data)
                else:
                    st.error("❌ Invalid multi-paper JSON format. Missing 'papers' array")
                    st.info("💡 Make sure you're uploading a file exported from this application's 'Export' tab in Multi-Paper mode.")
                    
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON file: {str(e)}")
            except Exception as e:
                st.error(f"❌ Error loading JSON: {str(e)}")
        else:
            st.info("👆 Upload a multi-paper JSON file to get started, or go to 'Upload Papers' tab to analyze new papers")
    
    # Tab 2: Upload Papers
    with tab2:
        st.header("📄 Upload Research Papers")
        st.markdown("Upload 2-5 papers for comparative analysis")
        st.caption("Start from scratch by uploading PDFs and running multi-paper LLM analysis")
        
        # File uploader for multiple files
        uploaded_files = st.file_uploader(
            "Choose PDF files",
            type=['pdf'],
            accept_multiple_files=True,
            help="Upload 2-5 research papers in PDF format"
        )
        
        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} file(s) uploaded")
            
            # Display uploaded papers
            st.subheader("📋 Uploaded Papers")
            
            for idx, uploaded_file in enumerate(uploaded_files):
                color = generate_paper_color(idx, PAPER_COLORS)
                
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.markdown(f"**Paper {idx+1}:** {uploaded_file.name}")
                    st.markdown(f"<span style='background-color: {color['hex']}; color: white; padding: 2px 8px; border-radius: 4px;'>{color['name']}</span>", unsafe_allow_html=True)
                
                with col2:
                    # Check if already extracted
                    existing_paper = next((p for p in st.session_state.multi_papers if p['name'] == uploaded_file.name), None)
                    if existing_paper and existing_paper.get('text'):
                        st.success(f"✓ Extracted ({len(existing_paper['text'])} chars)")
                    else:
                        st.info("⏳ Not extracted")
                
                with col3:
                    if st.button(f"🗑️", key=f"remove_{idx}"):
                        st.session_state.multi_papers = [p for p in st.session_state.multi_papers if p['name'] != uploaded_file.name]
                        st.experimental_rerun()
            
            st.markdown("---")
            
            # Extract all papers button
            if st.button("🔍 Extract Text from All Papers"):
                with st.spinner("Extracting text from all papers..."):
                    try:
                        st.session_state.multi_papers = []
                        
                        for idx, uploaded_file in enumerate(uploaded_files):
                            color = generate_paper_color(idx, PAPER_COLORS)
                            
                            # Extract text
                            pdf_bytes = uploaded_file.read()
                            text, full_length = extract_text_from_pdf_bytes(
                                pdf_bytes,
                                section_aware=True,
                                max_chars=st.session_state.max_chars
                            )
                            
                            # Store paper data
                            paper_data = {
                                'id': f"paper_{idx+1}",
                                'name': uploaded_file.name,
                                'text': text,
                                'full_text_length': full_length,
                                'color': color,
                                'hlg_data': None
                            }
                            st.session_state.multi_papers.append(paper_data)
                            
                            # Reset to beginning for next iteration
                            uploaded_file.seek(0)
                        
                        st.success(f"✅ Extracted text from {len(st.session_state.multi_papers)} papers!")
                        
                        # Show preview
                        with st.expander("📖 Preview Extracted Texts"):
                            for paper in st.session_state.multi_papers:
                                extracted_len = len(paper['text'])
                                full_len = paper.get('full_text_length', extracted_len)
                                if full_len > extracted_len:
                                    st.markdown(f"**{paper['name']}** - Extracted: {extracted_len:,} chars (from {full_len:,} total)")
                                else:
                                    st.markdown(f"**{paper['name']}** - {extracted_len:,} chars (full paper)")
                                st.text(paper['text'][:500] + "..." if len(paper['text']) > 500 else paper['text'])
                                st.markdown("---")
                    
                    except Exception as e:
                        st.error(f"❌ Error extracting text: {str(e)}")
        
        else:
            st.info("👆 Please upload 2 or more PDF files to begin")
        
        # Display current papers in session
        if st.session_state.multi_papers:
            st.markdown("---")
            st.subheader("✅ Papers Ready for Analysis")
            for paper in st.session_state.multi_papers:
                st.markdown(f"- **{paper['name']}** ({len(paper['text'])} chars) - {paper['color']['name']}")
    
    # Tab 3: Analysis
    with tab3:
        st.header("🔍 Multi-Paper Analysis")
        
        if not st.session_state.multi_papers or len(st.session_state.multi_papers) < 2:
            st.warning("⚠️ Please upload and extract text from at least 2 papers (Tab: Upload Papers)")
        else:
            st.markdown(f"""
            <div class="info-box">
            <strong>Ready for Analysis</strong><br>
            Papers: {len(st.session_state.multi_papers)}<br>
            Model: {st.session_state.model}<br>
            Pass 3 (Inference): {"✅ Enabled" if st.session_state.get('enable_inference', False) else "❌ Disabled"}
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🚀 Analyze All Papers & Find Cross-Paper Relations"):
                with st.spinner("🧠 Analyzing papers... This may take a few minutes..."):
                    try:
                        parser = LLMParser(model=st.session_state.model)
                        
                        # Phase 1: Analyze each paper individually
                        st.markdown("### Phase 1: Analyzing Individual Papers")
                        progress_bar = st.progress(0)
                        
                        for idx, paper in enumerate(st.session_state.multi_papers):
                            st.write(f"📄 Analyzing {paper['name']}...")
                            
                            hlg_data = parser.parse_paper(
                                paper['text'],
                                max_chars=st.session_state.max_chars,
                                enable_inference=st.session_state.get('enable_inference', False)
                            )
                            
                            paper['hlg_data'] = hlg_data
                            progress_bar.progress((idx + 1) / len(st.session_state.multi_papers))
                        
                        st.success("✅ Phase 1 Complete: All papers analyzed individually")
                        
                        # Phase 2: Find cross-paper relations
                        st.markdown("### Phase 2: Finding Cross-Paper Relations")
                        
                        cross_paper_data = parser.find_cross_paper_relations(
                            st.session_state.multi_papers
                        )
                        
                        st.session_state.multi_graph_data = {
                            'papers': st.session_state.multi_papers,
                            'cross_paper_relations': cross_paper_data.get('relations', []),
                            'cross_paper_confidence': cross_paper_data.get('overall_confidence', 'N/A'),
                            'cross_paper_explanation': cross_paper_data.get('overall_explanation', ''),
                            '_cross_paper_token_usage': cross_paper_data.get('_token_usage', {})
                        }
                        
                        st.session_state.multi_processing_complete = True
                        st.success("✅ Phase 2 Complete: Cross-paper relations identified!")
                        
                        # Display results
                        st.markdown("---")
                        st.subheader("📊 Analysis Results")
                        
                        # Display per-paper relations in separate blocks
                        for paper in st.session_state.multi_papers:
                            hlg = paper['hlg_data']
                            paper_color = paper['color']['hex']
                            
                            st.markdown("---")
                            
                            # Paper header with color
                            st.markdown(f"""
                            <div style="background-color: {paper_color}; color: white; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                                <h3 style="margin: 0;">📄 {paper['name']}</h3>
                                <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 0.9em;">Intra-Paper Relations</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Statistics
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Level 3 Nodes", len(hlg.get('Level3', [])))
                            with col2:
                                st.metric("Level 2 Nodes", len(hlg.get('Level2', [])))
                            with col3:
                                st.metric("Level 1 Nodes", len(hlg.get('Level1', [])))
                            with col4:
                                st.metric("Relations", len(hlg.get('Relations', [])))
                            
                            # Display relations with confidence scores and explanations
                            relations = hlg.get('Relations', [])
                            if relations:
                                st.markdown(f"#### 🔗 {len(relations)} Relations Found")
                                
                                for i, rel in enumerate(relations, 1):
                                    confidence = rel.get('confidence', 'N/A')
                                    explanation = rel.get('explanation', '')
                                    source = rel.get('source', '')
                                    target = rel.get('target', '')
                                    
                                    # Get level badges for source and target
                                    source_badge = get_node_level_badge(source, hlg)
                                    target_badge = get_node_level_badge(target, hlg)
                                    confidence_badge = render_confidence_badge(confidence)
                                    
                                    st.markdown(f"""
                                    **[{i}]** {source_badge} **{source}** → *{rel.get('relation')}* → {target_badge} **{target}** {confidence_badge}
                                    """, unsafe_allow_html=True)
                                    
                                    if explanation:
                                        st.caption(f"💡 {explanation}")
                                    
                                    st.markdown("")  # Spacing
                            else:
                                st.info("No intra-paper relations found.")
                            
                            # Show token usage in expander
                            if "_token_usage" in hlg:
                                with st.expander(f"🔢 Token Usage for {paper['name'][:30]}..."):
                                    usage = hlg["_token_usage"]
                                    col1, col2, col3 = st.columns(3)
                                    col1.metric("Prompt", f"{usage.get('prompt_tokens', 0):,}")
                                    col2.metric("Completion", f"{usage.get('completion_tokens', 0):,}")
                                    col3.metric("Total", f"{usage.get('total_tokens', 0):,}")
                        
                        # Cross-paper relations (separate block)
                        st.markdown("---")
                        
                        st.markdown("""
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                            <h3 style="margin: 0;">🔗 Cross-Paper Relations</h3>
                            <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 0.9em;">Relations between concepts from different papers</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        cross_paper_relations = st.session_state.multi_graph_data.get('cross_paper_relations', [])
                        
                        if cross_paper_relations:
                            # Overall confidence
                            st.markdown(f"""
                            <div class="info-box">
                            <strong>🎯 Cross-Paper Analysis Confidence: {st.session_state.multi_graph_data['cross_paper_confidence']}/10</strong><br>
                            {st.session_state.multi_graph_data['cross_paper_explanation']}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.markdown(f"#### 🔗 {len(cross_paper_relations)} Cross-Paper Relations Found")
                            
                            for i, rel in enumerate(cross_paper_relations, 1):
                                confidence = rel.get('confidence', 'N/A')
                                explanation = rel.get('explanation', '')
                                source_paper_id = rel.get('source_paper', 'Unknown')
                                target_paper_id = rel.get('target_paper', 'Unknown')
                                source = rel.get('source', '')
                                target = rel.get('target', '')
                                
                                # Find paper colors and names
                                source_paper_data = next((p for p in st.session_state.multi_papers if p['id'] == source_paper_id), None)
                                target_paper_data = next((p for p in st.session_state.multi_papers if p['id'] == target_paper_id), None)
                                
                                source_color = source_paper_data['color']['hex'] if source_paper_data else '#666'
                                target_color = target_paper_data['color']['hex'] if target_paper_data else '#666'
                                source_name = source_paper_data['name'][:25] if source_paper_data else source_paper_id
                                target_name = target_paper_data['name'][:25] if target_paper_data else target_paper_id
                                
                                # Get level badges from respective papers
                                source_level_badge = get_node_level_badge(source, source_paper_data['hlg_data']) if source_paper_data else ''
                                target_level_badge = get_node_level_badge(target, target_paper_data['hlg_data']) if target_paper_data else ''
                                
                                confidence_badge = render_confidence_badge(confidence)
                                
                                st.markdown(f"""
                                **[{i}]** <span style="background-color: {source_color}; color: white; padding: 2px 6px; border-radius: 3px;" title="{source_paper_data['name'] if source_paper_data else source_paper_id}">{source_name}</span> 
                                {source_level_badge} **{source}** → *{rel.get('relation')}* → 
                                <span style="background-color: {target_color}; color: white; padding: 2px 6px; border-radius: 3px;" title="{target_paper_data['name'] if target_paper_data else target_paper_id}">{target_name}</span> 
                                {target_level_badge} **{target}** {confidence_badge}
                                """, unsafe_allow_html=True)
                                
                                if explanation:
                                    st.caption(f"💡 {explanation}")
                                
                                st.markdown("")  # Spacing
                        else:
                            st.info("ℹ️ No cross-paper relations found. This may indicate that the papers cover different topics or use different terminology.")
                        
                        # Overall Token usage summary
                        st.markdown("---")
                        with st.expander("🔢 Overall Token Usage Summary"):
                            st.markdown("#### Per-Paper Analysis (Phase 1)")
                            for paper in st.session_state.multi_papers:
                                if "_token_usage" in paper['hlg_data']:
                                    usage = paper['hlg_data']['_token_usage']
                                    st.markdown(f"**{paper['name'][:40]}...**: {usage.get('total_tokens', 0):,} tokens")
                            
                            st.markdown("#### Cross-Paper Analysis (Phase 2)")
                            if '_cross_paper_token_usage' in st.session_state.multi_graph_data:
                                usage = st.session_state.multi_graph_data['_cross_paper_token_usage']
                                st.markdown(f"**Cross-Paper Relations**: {usage.get('total_tokens', 0):,} tokens")
                            
                            st.markdown("#### Grand Total")
                            total_tokens = sum(
                                p['hlg_data'].get('_token_usage', {}).get('total_tokens', 0) 
                                for p in st.session_state.multi_papers
                            )
                            if '_cross_paper_token_usage' in st.session_state.multi_graph_data:
                                total_tokens += st.session_state.multi_graph_data['_cross_paper_token_usage'].get('total_tokens', 0)
                            st.markdown(f"**🎯 Total Tokens Used**: {total_tokens:,}")
                        
                    except Exception as e:
                        st.error(f"❌ Error during analysis: {str(e)}")
                        import traceback
                        with st.expander("🐛 Error Details"):
                            st.code(traceback.format_exc())
    
    # Tab 4: Visualization
    with tab4:
        st.header("🎨 Multi-Paper Graph Visualization")
        
        # Show status and clear button
        col_status, col_clear = st.columns([3, 1])
        with col_status:
            if st.session_state.multi_graph_data:
                st.success(f"✅ Multi-paper analysis data loaded - Visualization ready! ({len(st.session_state.multi_papers)} papers)")
        with col_clear:
            if st.session_state.multi_graph_data:
                if st.button("🗑️ Clear Data", key="clear_multi_viz_data", help="Clear current multi-paper analysis data"):
                    st.session_state.multi_graph_data = None
                    st.session_state.multi_graph_html = None
                    st.session_state.multi_papers = []
                    st.session_state.multi_processing_complete = False
                    st.experimental_rerun()
        
        if not st.session_state.multi_graph_data:
            st.warning("⚠️ No multi-paper analysis data available")
            
            # Show helpful status
            if st.session_state.multi_papers:
                st.info(f"💡 {len(st.session_state.multi_papers)} paper(s) ready but not analyzed yet. Go to 'Analysis' tab and click 'Analyze All Papers'")
            else:
                st.info("💡 No data yet. Go to 'Load JSON' tab to upload a previous analysis, or 'Upload Papers' tab to start a new analysis")
        else:
            try:
                # Layout selection
                layout_option = st.radio(
                    "📐 Layout Style:",
                    ["Linear (Horizontal Lines)", "Circular (Concentric Circles)"],
                    horizontal=True,
                    help="Choose how nodes are arranged: Linear = horizontal lines by level, Circular = concentric circles"
                )
                layout = "circular" if layout_option == "Circular (Concentric Circles)" else "linear"
                
                st.markdown("---")
                
                # Paper Filter Toggles
                st.markdown("### 🔘 Paper Filters")
                st.caption("Toggle papers on/off to focus on specific papers or see the complete graph")
                
                active_papers = []
                
                for idx, paper in enumerate(st.session_state.multi_papers):
                    # Create a row with checkbox and colored block containing paper name
                    row_cols = st.columns([1, 11])
                    
                    with row_cols[0]:
                        # Use paper name as part of key to make it unique
                        is_active = st.checkbox(
                            "",
                            value=True,  # All papers active by default
                            key=f"filter_{paper['id']}",
                            help=f"Show/hide {paper['name']}"
                        )
                    
                    with row_cols[1]:
                        # Display paper name inside colored block
                        st.markdown(f"""
                        <div style="background-color: {paper['color']['hex']}; color: white; padding: 8px; border-radius: 5px; text-align: left;">
                        <strong>📄 {paper['name']}</strong>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    if is_active:
                        active_papers.append(paper['id'])
                
                st.markdown("---")
                
                # Validate at least one paper is active
                if not active_papers:
                    st.warning("⚠️ Please select at least one paper to visualize")
                else:
                    # Filter graph data based on active papers
                    filtered_graph_data = {
                        'papers': [p for p in st.session_state.multi_graph_data['papers'] if p['id'] in active_papers],
                        'cross_paper_relations': [
                            rel for rel in st.session_state.multi_graph_data.get('cross_paper_relations', [])
                            if rel.get('source_paper') in active_papers and rel.get('target_paper') in active_papers
                        ]
                    }
                    
                    # Build filtered multi-paper graph
                    builder = GraphBuilder(layout=layout)
                    G = builder.build_multi_paper_graph(filtered_graph_data)
                    
                    # Display statistics
                    stats = builder.get_statistics()
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Nodes", stats['total_nodes'])
                    col2.metric("Total Edges", stats['total_edges'])
                    col3.metric("Active Papers", len(active_papers))
                    col4.metric("Cross-Paper Relations", len(filtered_graph_data.get('cross_paper_relations', [])))
                    
                    st.markdown("---")
                    
                    # Generate visualization with filtered data
                    with st.spinner("Generating interactive graph..."):
                        net = builder.to_pyvis(height="700px", width="100%")
                        
                        # Save to temporary file
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8') as f:
                            net.save_graph(f.name)
                            st.session_state.multi_graph_html = f.name
                            
                            # Read and display
                            with open(f.name, 'r', encoding='utf-8') as html_file:
                                html_content = html_file.read()
                                components.html(html_content, height=750, scrolling=True)
                    
                    # Dynamic tip based on number of active papers
                    if len(active_papers) == 1:
                        st.info("💡 **Tip**: Viewing single paper mode. Toggle other papers on to see cross-paper relations!")
                    else:
                        st.info("💡 **Tip**: Papers are color-coded! Cross-paper relations shown with thick magenta dashed lines. Toggle papers on/off to focus. You can drag nodes and zoom in/out!")
                
            except Exception as e:
                st.error(f"❌ Error creating visualization: {str(e)}")
                import traceback
                with st.expander("🐛 Error Details"):
                    st.code(traceback.format_exc())
    
    # Tab 5: Export
    with tab5:
        st.header("💾 Export Multi-Paper Results")
        
        # Show status at top of tab
        if st.session_state.multi_graph_data:
            st.success(f"✅ Multi-paper analysis data loaded - Export options ready! ({len(st.session_state.multi_papers)} papers)")
        
        if not st.session_state.multi_graph_data:
            st.warning("⚠️ No multi-paper analysis data available to export")
            
            # Show helpful status
            if st.session_state.multi_papers:
                st.info(f"💡 {len(st.session_state.multi_papers)} paper(s) ready but not analyzed yet. Go to 'Analysis' tab and click 'Analyze All Papers'")
            else:
                st.info("💡 No data yet. Go to 'Load JSON' tab to upload a previous analysis, or 'Upload Papers' tab to start a new analysis")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📄 Download JSON")
                json_str = json.dumps(st.session_state.multi_graph_data, indent=2, ensure_ascii=False)
                st.download_button(
                    label="⬇️ Download Multi-Paper Analysis JSON",
                    data=json_str,
                    file_name="multi_paper_analysis.json",
                    mime="application/json"
                )
                
                with st.expander("👁️ Preview JSON"):
                    st.json(st.session_state.multi_graph_data)
            
            with col2:
                st.subheader("🌐 Download Graph HTML")
                
                # Layout selection for HTML export
                export_layout_option = st.radio(
                    "📐 Layout for Export:",
                    ["Linear (Horizontal Lines)", "Circular (Concentric Circles)"],
                    horizontal=True,
                    help="Choose layout style for the exported HTML graph"
                )
                export_layout = "circular" if export_layout_option == "Circular (Concentric Circles)" else "linear"
                
                # Generate HTML with selected layout
                try:
                    # Filter graph data based on active papers (use all papers for export)
                    filtered_graph_data = {
                        'papers': st.session_state.multi_graph_data['papers'],
                        'cross_paper_relations': st.session_state.multi_graph_data.get('cross_paper_relations', [])
                    }
                    
                    builder = GraphBuilder(layout=export_layout)
                    builder.build_multi_paper_graph(filtered_graph_data)
                    
                    # Generate HTML
                    net = builder.to_pyvis(height="700px", width="100%")
                    
                    # Save to temporary file to get HTML content
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8')
                    temp_path = temp_file.name
                    temp_file.close()  # Close immediately after getting path
                    
                    net.save_graph(temp_path)
                    
                    # Read the HTML content
                    with open(temp_path, 'r', encoding='utf-8') as html_file:
                        html_content = html_file.read()
                    
                    # Clean up temp file (close file first, then delete)
                    try:
                        os.unlink(temp_path)
                    except:
                        pass  # Ignore errors if file is still locked
                    
                    layout_suffix = "circular" if export_layout == "circular" else "linear"
                    st.download_button(
                        label=f"⬇️ Download Interactive Graph ({export_layout_option})",
                        data=html_content,
                        file_name=f"multi_paper_graph_{layout_suffix}.html",
                        mime="text/html"
                    )
                except Exception as e:
                    st.error(f"❌ Error generating HTML: {str(e)}")
                    st.info("📊 Make sure analysis data is available")
    
    # Tab 6: Customize Prompts
    with tab6:
        
        prompts_config = [
            {
                'name': 'Pass 1: Node Extraction',
                'key': 'custom_prompt_paper_to_logicgraph',
                'file_path': 'prompts/paper_to_logicgraph.txt',
                'description': 'Controls how the LLM extracts nodes (Level 3, Level 2, Level 1) from each paper. Use {paper_text} as placeholder.'
            },
            {
                'name': 'Pass 2: Relation Finding',
                'key': 'custom_prompt_find_relations',
                'file_path': 'prompts/find_relations.txt',
                'description': 'Controls how the LLM finds relations between nodes within each paper. Use {nodes} and {paper_text} as placeholders.'
            },
            {
                'name': 'Pass 3: Contextual Inference',
                'key': 'custom_prompt_infer_context',
                'file_path': 'prompts/infer_context.txt',
                'description': 'Controls how the LLM infers additional contextual nodes and relations. Use {graph_summary} as placeholder. Only used when Pass 3 is enabled.'
            },
            {
                'name': 'Cross-Paper Relations',
                'key': 'custom_prompt_cross_paper_relations',
                'file_path': 'prompts/cross_paper_relations.txt',
                'description': 'Controls how the LLM finds relations between nodes from different papers. Use {papers_data} as placeholder.'
            }
        ]
        
        render_prompt_customization_ui(prompts_config)


if __name__ == "__main__":
    main()



