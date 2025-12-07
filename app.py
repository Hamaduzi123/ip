"""
Patent Pipeline - Streamlit Web UI
A tool to update your Qatar patent database with new patents from EPO and Lens.org

Run with: python -m streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import time
import io

# Local imports
from config import MASTER_FILE, DATA_DIR, LOGS_DIR
from extractors import EPOExtractor, LensExtractor
from transformers import PatentCleaner
from loaders import ExcelLoader
from utils import PipelineLogger, PipelineState


# Page config
st.set_page_config(
    page_title="QRDI Patent Updater",
    page_icon="🇶🇦",
    layout="wide"
)

# Custom CSS for better styling + hide Streamlit branding
st.markdown("""
<style>
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}

    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: #8B1538;
    }
    .org-badge {
        font-size: 0.9rem;
        color: #8B1538;
        font-weight: 600;
        margin-bottom: 0.3rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #8B1538 0%, #5c0f26 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'pipeline_running' not in st.session_state:
    st.session_state.pipeline_running = False


def main():
    # Header with QRDI/Innolight branding
    st.markdown('<p class="org-badge">QRDI - Innolight</p>', unsafe_allow_html=True)
    st.markdown('<p class="main-header">Qatar Patent Database Updater</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Upload your existing patent list and automatically find new patents from EPO and Lens.org</p>', unsafe_allow_html=True)

    # Main content - Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Update Patents", "View Database", "Compare Changes", "Export"
    ])

    # Tab 1: Update Patents (Main workflow)
    with tab1:
        st.markdown("### Step 1: Upload Your Current Patent List")
        st.markdown("Upload your existing CurrentIPs Excel file (includes patents from WIPO, Lens, EPO, etc.)")

        uploaded_file = st.file_uploader(
            "Drop your Excel file here",
            type=['xlsx'],
            key="main_uploader",
            help="This should be your master patent list that you want to update"
        )

        existing_df = None
        if uploaded_file:
            try:
                existing_df = pd.read_excel(uploaded_file)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Patents in File", f"{len(existing_df):,}")
                with col2:
                    if 'PatentYear' in existing_df.columns:
                        years = existing_df['PatentYear'].dropna()
                        if len(years) > 0:
                            st.metric("Year Range", f"{int(years.min())}-{int(years.max())}")
                with col3:
                    if 'Title' in existing_df.columns:
                        with_title = (existing_df['Title'].notna() & (existing_df['Title'] != '')).sum()
                        st.metric("With Titles", f"{with_title:,}")

                st.success(f"Loaded **{len(existing_df):,}** patents from your file")

                # Save to temp for pipeline use
                temp_path = DATA_DIR / "temp_upload.xlsx"
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                existing_df.to_excel(temp_path, index=False)

            except Exception as e:
                st.error(f"Error reading file: {e}")

        st.markdown("---")
        st.markdown("### Step 2: Select Sources to Search")

        col1, col2 = st.columns(2)
        with col1:
            use_epo = st.checkbox("EPO (European Patent Office)", value=True,
                                  help="Search European Patent Office database")
        with col2:
            use_lens = st.checkbox("Lens.org", value=True,
                                   help="Search Lens.org (includes US, GB, CN, and more)")

        st.markdown("---")
        st.markdown("### Step 3: Run Update")

        can_run = uploaded_file is not None and (use_epo or use_lens)

        if not uploaded_file:
            st.warning("Please upload your existing patent file first")
        elif not use_epo and not use_lens:
            st.warning("Please select at least one data source")

        if st.button("🚀 Find New Patents", type="primary", disabled=not can_run or st.session_state.pipeline_running):
            st.session_state.pipeline_running = True

            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                logger = PipelineLogger()
                cleaner = PatentCleaner(logger=logger)
                loader = ExcelLoader(logger=logger)

                all_patents = []
                stats = {'epo': 0, 'lens': 0, 'new_added': 0, 'total_after': 0}

                steps_total = (1 if use_epo else 0) + (1 if use_lens else 0) + 2
                step = 0

                # Extract from EPO
                if use_epo:
                    status_text.text("🔍 Searching EPO database...")
                    progress_bar.progress(int((step / steps_total) * 100))

                    epo = EPOExtractor(logger=logger)
                    if epo.authenticate():
                        doc_ids = epo.search_patents()
                        if doc_ids:
                            status_text.text(f"📥 Extracting {len(doc_ids)} patents from EPO...")
                            epo_patents = []
                            for i, doc_id in enumerate(doc_ids):
                                if i % 50 == 0:
                                    status_text.text(f"📥 EPO: {i+1}/{len(doc_ids)} patents...")
                                details = epo.get_patent_details(doc_id)
                                if details:
                                    epo_patents.append(details)
                                if i % 10 == 0:
                                    time.sleep(1)
                            all_patents.extend(epo_patents)
                            stats['epo'] = len(epo_patents)
                    step += 1

                # Extract from Lens
                if use_lens:
                    progress_bar.progress(int((step / steps_total) * 100))
                    status_text.text("🔍 Searching Lens.org database...")

                    lens = LensExtractor(logger=logger)
                    lens_patents = lens.extract_all()
                    if lens_patents:
                        all_patents.extend(lens_patents)
                        stats['lens'] = len(lens_patents)
                    step += 1

                if not all_patents:
                    st.error("No patents found from selected sources")
                    st.session_state.pipeline_running = False
                    st.stop()

                # Clean and merge
                progress_bar.progress(int((step / steps_total) * 100))
                status_text.text(f"🧹 Processing {len(all_patents)} patents...")

                cleaned_df = cleaner.clean(all_patents)

                # Load existing and merge
                existing_df = loader.load_existing(DATA_DIR / "temp_upload.xlsx")
                initial_count = len(existing_df) if existing_df is not None else 0

                if existing_df is not None:
                    merged_df = cleaner.merge_with_existing(cleaned_df, existing_df)
                    stats['new_added'] = len(merged_df) - initial_count
                    stats['total_after'] = len(merged_df)
                else:
                    merged_df = cleaned_df
                    stats['new_added'] = len(cleaned_df)
                    stats['total_after'] = len(cleaned_df)

                step += 1

                # Save
                progress_bar.progress(int((step / steps_total) * 100))
                status_text.text("💾 Saving results...")

                success = loader.save(merged_df)

                if success:
                    progress_bar.progress(100)
                    status_text.empty()

                    # Show results
                    st.balloons()

                    st.markdown("### ✅ Update Complete!")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("New Patents Found", f"+{stats['new_added']}", delta=stats['new_added'])
                    with col2:
                        st.metric("Total in Database", f"{stats['total_after']:,}")
                    with col3:
                        st.metric("Patents Searched", f"{stats['epo'] + stats['lens']:,}")

                    if stats['new_added'] > 0:
                        st.info(f"Found **{stats['new_added']}** new patents! Go to **Export** tab to download the updated file.")
                    else:
                        st.success("Your database is already up to date!")

                    # Record run
                    PipelineState().record_run({
                        'source': 'EPO+LENS',
                        'searched': stats['epo'] + stats['lens'],
                        'extracted': len(all_patents),
                        'new_added': stats['new_added'],
                        'total_after': stats['total_after'],
                    })
                else:
                    st.error("Failed to save results")

            except Exception as e:
                st.error(f"Error: {e}")
                import traceback
                st.code(traceback.format_exc())
            finally:
                st.session_state.pipeline_running = False

    # Tab 2: View Database
    with tab2:
        st.markdown("### Current Patent Database")

        loader = ExcelLoader()
        df = loader.load_existing()

        if df is not None:
            # Summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Patents", f"{len(df):,}")
            with col2:
                with_title = (df['Title'].notna() & (df['Title'] != '')).sum()
                st.metric("With Titles", f"{with_title:,}")
            with col3:
                if 'PatentYear' in df.columns:
                    years = df['PatentYear'].dropna()
                    if len(years) > 0:
                        st.metric("Year Range", f"{int(years.min())}-{int(years.max())}")

            st.markdown("---")

            # Filters
            col1, col2 = st.columns(2)
            with col1:
                search = st.text_input("🔍 Search by title or applicant", placeholder="Enter search term...")
            with col2:
                if 'PatentYear' in df.columns:
                    years_list = sorted([str(int(y)) for y in df['PatentYear'].dropna().unique() if y], reverse=True)
                    year_filter = st.selectbox("Filter by year", ["All Years"] + years_list)
                else:
                    year_filter = "All Years"

            # Apply filters
            display_df = df.copy()

            if search:
                mask = (
                    df['Title'].str.contains(search, case=False, na=False) |
                    df['Applicants'].str.contains(search, case=False, na=False)
                )
                display_df = display_df[mask]

            if year_filter != "All Years":
                display_df = display_df[display_df['PatentYear'].astype(str).str.startswith(year_filter)]

            st.markdown(f"**Showing {len(display_df):,} patents**")

            # Data table
            display_cols = ['ApplicationNumber', 'Title', 'Applicants', 'PatentYear']
            st.dataframe(
                display_df[display_cols],
                use_container_width=True,
                height=500
            )
        else:
            st.info("No database found. Run an update first to create one.")

    # Tab 3: Compare Changes
    with tab3:
        st.markdown("### Compare Your File with Database")
        st.markdown("See what new patents have been added since your last export")

        compare_file = st.file_uploader(
            "Upload your file to compare",
            type=['xlsx'],
            key="compare_uploader"
        )

        if compare_file:
            try:
                your_df = pd.read_excel(compare_file)

                loader = ExcelLoader()
                current_df = loader.load_existing()

                if current_df is not None:
                    # Compare by ApplicationNumber
                    your_apps = set(your_df['ApplicationNumber'].dropna().astype(str).tolist())
                    current_apps = set(current_df['ApplicationNumber'].dropna().astype(str).tolist())

                    new_apps = current_apps - your_apps

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("In Your File", f"{len(your_df):,}")
                    with col2:
                        st.metric("In Database", f"{len(current_df):,}")
                    with col3:
                        st.metric("New Patents", f"+{len(new_apps)}", delta=len(new_apps))

                    if new_apps:
                        st.markdown("---")
                        st.markdown(f"### New Patents ({len(new_apps)})")

                        new_df = current_df[current_df['ApplicationNumber'].astype(str).isin(new_apps)]

                        st.dataframe(
                            new_df[['ApplicationNumber', 'Title', 'Applicants', 'PatentYear']],
                            use_container_width=True,
                            height=400
                        )

                        # Export button
                        buffer = io.BytesIO()
                        new_df.to_excel(buffer, index=False)
                        buffer.seek(0)

                        st.download_button(
                            "📥 Download New Patents Only",
                            data=buffer,
                            file_name="New_Patents.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.success("✅ Your file is up to date! No new patents found.")
                else:
                    st.warning("No database found. Run an update first.")

            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.info("Upload a file to compare with the current database")

    # Tab 4: Export
    with tab4:
        st.markdown("### Export Patent Data")

        loader = ExcelLoader()
        df = loader.load_existing()

        if df is not None:
            st.markdown(f"**{len(df):,}** patents ready to export")

            export_df = df.drop(columns=['Source', 'ExtractedDate'], errors='ignore')

            buffer = io.BytesIO()
            export_df.to_excel(buffer, index=False)
            buffer.seek(0)

            st.download_button(
                "📥 Download IPs_QRDI.xlsx",
                data=buffer,
                file_name="IPs_QRDI.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.info("No data to export. Run an update first.")

    # Footer
    st.markdown("---")
    st.markdown(
        '<p style="text-align: center; color: #888; font-size: 0.85rem;">'
        'Made by <strong>Hamad Aldous</strong> | QRDI - Innolight'
        '</p>',
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
