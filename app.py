from pathlib import Path
import io, re
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="DataPilot Studio", page_icon="✦", layout="wide", initial_sidebar_state="expanded")

# Premium dark dashboard styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root { --bg:#080b12; --panel:#101522; --line:#222a3a; --muted:#8e9bb1; --text:#edf2ff; --accent:#9b8cff; --mint:#60e3bd; }
.stApp { background: radial-gradient(ellipse at 75% -15%, #24204b 0%, #0b1020 32%, #080b12 70%); color:var(--text); font-family:'DM Sans',sans-serif; }
header[data-testid="stHeader"] { background:transparent; }
.block-container { padding-top:1.5rem; max-width:1500px; }
section[data-testid="stSidebar"] { background:#0b0f19; border-right:1px solid var(--line); }
h1,h2,h3 { font-family:'Manrope',sans-serif !important; letter-spacing:-.035em; }
.hero { padding:28px 30px; border:1px solid #292d48; border-radius:24px; background:linear-gradient(120deg,rgba(155,140,255,.16),rgba(96,227,189,.055) 55%,rgba(18,24,40,.85)); margin-bottom:22px; }
.eyebrow { color:var(--mint); text-transform:uppercase; letter-spacing:.18em; font-size:.72rem; font-weight:800; }
.hero h1 { font-size:2.35rem; margin:.3rem 0 .5rem; }
.hero p { color:#aab5c9; max-width:780px; margin:0; }
.metric { background:linear-gradient(145deg,#141a2a,#0e1320); border:1px solid var(--line); border-radius:17px; padding:18px 20px; min-height:105px; }
.metric-label { color:var(--muted); font-size:.78rem; margin-bottom:9px; }
.metric-value { color:#f5f7ff; font:800 1.8rem 'Manrope',sans-serif; }
.metric-note { color:var(--mint); font-size:.75rem; margin-top:4px; }
.section-head { margin:20px 0 8px; }
div[data-testid="stFileUploader"] { background:#101522; border:1px dashed #3a4560; border-radius:18px; padding:12px; }
.stButton>button, .stDownloadButton>button { border-radius:10px; border:1px solid #6658b9; background:linear-gradient(100deg,#8e7bff,#6c5ce7); color:white; font-weight:700; min-height:2.7rem; }
.stButton>button:hover, .stDownloadButton>button:hover { border-color:#b4aaff; color:white; }
div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:14px; overflow:hidden; }
div[data-testid="stTabs"] button { font-weight:700; }
.small-muted { color:var(--muted); font-size:.85rem; }
div[data-testid="stExpander"] { border:1px solid var(--line); border-radius:12px; }
hr { border-color:var(--line); }
</style>
""", unsafe_allow_html=True)

def read_file(upload):
    name = upload.name.lower()
    raw = upload.getvalue()
    if name.endswith(".csv"):
        try:
            return pd.read_csv(io.BytesIO(raw)), None
        except UnicodeDecodeError:
            return pd.read_csv(io.BytesIO(raw), encoding="latin-1"), None
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(raw)), None
    if name.endswith(".pdf"):
        try:
            import pdfplumber
            tables = []
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                for page in pdf.pages:
                    for table in (page.extract_tables() or []):
                        if table and len(table) > 1:
                            tables.append(pd.DataFrame(table[1:], columns=table[0]))
            if tables:
                return pd.concat(tables, ignore_index=True), None
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
            lines = [re.split(r"\s{2,}|\t", x.strip()) for x in text.splitlines() if x.strip()]
            if len(lines) > 1 and len({len(x) for x in lines}) == 1:
                return pd.DataFrame(lines[1:], columns=lines[0]), None
            return None, "No extractable table found. This PDF may be scanned or layout-based; use OCR/table extraction first."
        except Exception as e:
            return None, f"Could not read PDF: {e}"
    return None, "Unsupported file type."

def profile(df):
    rows=[]
    for c in df.columns:
        s=df[c]
        examples=", ".join(map(str, s.dropna().astype(str).head(3).tolist()))
        rows.append({"Column":str(c),"Data type":str(s.dtype),"Non-null":int(s.notna().sum()),
                     "Missing":int(s.isna().sum()),"Unique":int(s.nunique(dropna=True)),
                     "Example values":examples[:120]})
    return pd.DataFrame(rows)

def clean_data(df, options):
    out=df.copy()
    actions=[]
    if options.get("trim", True):
        obj=out.select_dtypes(include=["object","string"]).columns
        for c in obj:
            old=out[c].copy()
            out[c]=out[c].map(lambda x: x.strip() if isinstance(x,str) else x)
            changed=int((old.fillna("\\0") != out[c].fillna("\\0")).sum())
            if changed: actions.append(f"Trimmed whitespace in **{c}** ({changed} cells).")
    if options.get("normalize_empty", True):
        for c in out.select_dtypes(include=["object","string"]).columns:
            out[c]=out[c].replace(r"^\s*$", pd.NA, regex=True)
    if options.get("dedupe", True):
        before=len(out); out=out.drop_duplicates()
        n=before-len(out)
        if n: actions.append(f"Removed **{n:,}** duplicate rows.")
    if options.get("missing") == "Drop rows":
        before=len(out); out=out.dropna()
        n=before-len(out)
        if n: actions.append(f"Dropped **{n:,}** rows containing missing values.")
    elif options.get("missing") == "Fill numeric median":
        for c in out.select_dtypes(include="number").columns:
            n=int(out[c].isna().sum())
            if n:
                med=out[c].median()
                if pd.notna(med): out[c]=out[c].fillna(med); actions.append(f"Filled **{n:,}** missing values in **{c}** with median.")
    elif options.get("missing") == "Fill text with Unknown":
        for c in out.columns:
            if out[c].isna().any() and (pd.api.types.is_object_dtype(out[c]) or pd.api.types.is_string_dtype(out[c])):
                n=int(out[c].isna().sum()); out[c]=out[c].fillna("Unknown")
                actions.append(f"Filled **{n:,}** missing values in **{c}** with `Unknown`.")
    if options.get("convert_dates", True):
        for c in out.select_dtypes(include=["object","string"]).columns:
            if any(token in str(c).lower() for token in ["date","time","created","updated"]):
                parsed=pd.to_datetime(out[c], errors="coerce")
                if parsed.notna().sum() >= max(1, int(out[c].notna().sum()*.7)):
                    out[c]=parsed; actions.append(f"Converted **{c}** to datetime.")
    return out, actions

st.sidebar.markdown("## ✦ DataPilot")
st.sidebar.caption("STUDIO · DATA WORKSPACE")
page=st.sidebar.radio("Workspace", ["Overview", "Explore & filter", "Clean & merge", "Export"], label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.markdown("**Workflow**")
for i, label in enumerate(["01  Import files","02  Profile data","03  Filter records","04  Clean & merge","05  Export results"],1):
    st.sidebar.markdown(f"<div style='padding:7px 0;color:{'#60e3bd' if i=={'Overview':1,'Explore & filter':3,'Clean & merge':4,'Export':5}.get(page,2) else '#8e9bb1'}'>{label}</div>", unsafe_allow_html=True)
st.sidebar.divider()
st.sidebar.caption("Local-first processing · Files stay in this app session")

st.markdown("""<div class="hero"><div class="eyebrow">INTELLIGENT DATA WORKSPACE</div>
<h1>Turn raw data into <span style="color:#a99cff">clear decisions.</span></h1>
<p>Import multiple datasets, understand every column, shape the records with flexible filters, clean inconsistencies, and export one polished deliverable.</p></div>""", unsafe_allow_html=True)

if "datasets" not in st.session_state: st.session_state.datasets={}
if "filtered" not in st.session_state: st.session_state.filtered=None
if "cleaned" not in st.session_state: st.session_state.cleaned=None
if "clean_log" not in st.session_state: st.session_state.clean_log=[]
if "active_df" not in st.session_state: st.session_state.active_df=None

st.markdown("### 01 · Import your files")
uploads=st.file_uploader("Drop CSV, Excel, or table-based PDF files here", type=["csv","xlsx","xls","pdf"], accept_multiple_files=True, help="Upload multiple files. Tables in PDFs can be extracted; scanned PDFs need OCR.")
c1,c2,c3=st.columns([1,1,2])
with c1:
    if st.button("＋  Load files", use_container_width=True):
        if not uploads: st.warning("Choose at least one file first.")
        else:
            loaded, errors={},[]
            for f in uploads:
                df,err=read_file(f)
                if err: errors.append(f"{f.name}: {err}")
                elif df is not None:
                    df.columns=[str(x).strip() or f"column_{i+1}" for i,x in enumerate(df.columns)]
                    loaded[f.name]=df
            st.session_state.datasets.update(loaded)
            st.session_state.filtered=None; st.session_state.cleaned=None
            if loaded: st.success(f"Loaded {len(loaded)} file(s).")
            for e in errors: st.error(e)
with c2:
    if st.button("Reset workspace", use_container_width=True):
        st.session_state.datasets={}; st.session_state.filtered=None; st.session_state.cleaned=None; st.session_state.clean_log=[]; st.rerun()
with c3:
    st.markdown("<div class='small-muted' style='padding-top:10px'>CSV · XLSX · XLS · PDF tables &nbsp; / &nbsp; Multiple files supported</div>", unsafe_allow_html=True)

if st.session_state.datasets:
    names=list(st.session_state.datasets)
    chosen=st.selectbox("Active dataset", names, index=0)
    source=st.session_state.datasets[chosen]
    st.session_state.active_df=source
    st.markdown("### 02 · Dataset intelligence")
    total_rows=sum(len(x) for x in st.session_state.datasets.values())
    total_cols=sum(len(x.columns) for x in st.session_state.datasets.values())
    missing=sum(int(x.isna().sum().sum()) for x in st.session_state.datasets.values())
    duplicates=sum(int(x.duplicated().sum()) for x in st.session_state.datasets.values())
    metrics=st.columns(4)
    for col,label,val,note in [
        (metrics[0],"Imported files",len(st.session_state.datasets),"datasets in workspace"),
        (metrics[1],"Rows in active file",f"{len(source):,}",f"{len(source.columns)} columns detected"),
        (metrics[2],"Missing cells",f"{int(source.isna().sum().sum()):,}","active dataset"),
        (metrics[3],"Duplicate rows",f"{int(source.duplicated().sum()):,}","active dataset")]:
        with col: st.markdown(f"<div class='metric'><div class='metric-label'>{label}</div><div class='metric-value'>{val}</div><div class='metric-note'>{note}</div></div>",unsafe_allow_html=True)
    tab1,tab2,tab3=st.tabs(["Data preview","Column profile","Quick insights"])
    with tab1:
        st.dataframe(source.head(100), use_container_width=True, height=360)
        st.caption(f"Showing first {min(100,len(source)):,} of {len(source):,} rows.")
    with tab2:
        st.dataframe(profile(source), use_container_width=True, hide_index=True)
        st.download_button("Download column profile (CSV)", profile(source).to_csv(index=False).encode(), file_name="column_profile.csv", mime="text/csv")
    with tab3:
        left,right=st.columns(2)
        with left:
            numeric=source.select_dtypes(include="number").columns.tolist()
            if numeric:
                col=st.selectbox("Numeric distribution",numeric)
                fig=px.histogram(source,x=col,template="plotly_dark",color_discrete_sequence=["#9b8cff"],title=f"Distribution · {col}")
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig,use_container_width=True)
            else: st.info("No numeric columns found in this dataset.")
        with right:
            st.markdown("**Automated observations**")
            st.write(f"- **{len(source):,}** rows and **{len(source.columns)}** columns.")
            st.write(f"- **{source.isna().sum().sum():,}** missing cells ({(source.isna().sum().sum()/max(1,source.size)*100):.1f}% of all cells).")
            st.write(f"- **{source.duplicated().sum():,}** fully duplicated rows.")
            high_missing=[f"{c} ({source[c].isna().mean():.0%})" for c in source if source[c].isna().mean()>=.3]
            st.write("- Columns with ≥30% missing: " + (", ".join(high_missing) if high_missing else "none detected") + ".")
            high_card=[c for c in source if source[c].nunique(dropna=True)>max(50,len(source)*.8)]
            st.write("- High-cardinality columns: " + (", ".join(map(str,high_card)) if high_card else "none detected") + ".")

    st.markdown("---")
    if page in ["Explore & filter","Overview"]:
        st.markdown("### 03 · Smart filter studio")
        st.caption("Combine multiple conditions. All selected conditions are applied together (AND logic).")
        filter_df=st.session_state.filtered if st.session_state.filtered is not None else source.copy()
        with st.expander("Build your filter rules", expanded=(page=="Explore & filter")):
            selected_cols=st.multiselect("Columns to include (leave empty to keep all)", list(source.columns), default=list(source.columns))
            filter_col=st.selectbox("Filter column", list(source.columns), key="filter_col")
            s=source[filter_col]
            operator=st.selectbox("Condition", ["equals","contains","greater than","less than","is missing","is not missing","one of selected values"], key="filter_op")
            if operator=="one of selected values":
                vals=source[filter_col].dropna().astype(str).unique().tolist()
                filter_value=st.multiselect("Matching values", vals, key="filter_vals")
            elif operator not in ["is missing","is not missing"]:
                if pd.api.types.is_numeric_dtype(s):
                    filter_value=st.number_input("Value", value=float(s.median()) if s.notna().any() else 0.0, key="filter_num")
                else: filter_value=st.text_input("Value", key="filter_text")
            else: filter_value=None
            if st.button("Apply filter", type="primary"):
                mask=pd.Series(True,index=source.index)
                if operator=="equals": mask=source[filter_col].astype(str)==str(filter_value)
                elif operator=="contains": mask=source[filter_col].astype(str).str.contains(str(filter_value),case=False,na=False,regex=False)
                elif operator=="greater than": mask=pd.to_numeric(source[filter_col],errors="coerce")>float(filter_value)
                elif operator=="less than": mask=pd.to_numeric(source[filter_col],errors="coerce")<float(filter_value)
                elif operator=="is missing": mask=source[filter_col].isna()
                elif operator=="is not missing": mask=source[filter_col].notna()
                elif operator=="one of selected values": mask=source[filter_col].astype(str).isin(filter_value)
                st.session_state.filtered=source.loc[mask, selected_cols].copy()
                st.success(f"Filter applied · {len(st.session_state.filtered):,} rows remain.")
        current=st.session_state.filtered if st.session_state.filtered is not None else source
        st.dataframe(current.head(100),use_container_width=True,height=300)
        st.caption(f"Current view: {len(current):,} rows × {len(current.columns)} columns")
        if st.button("Clear filter"): st.session_state.filtered=None; st.rerun()

    if page in ["Clean & merge","Overview"]:
        st.markdown("### 04 · AI-assisted cleaning & merge")
        st.caption("Transparent rule-based cleaning with data profiling. Review the choices before applying them; no external AI service is required.")
        a,b,c=st.columns(3)
        with a: trim=st.checkbox("Trim text whitespace",True)
        with b: dedupe=st.checkbox("Remove duplicate rows",True)
        with c: dates=st.checkbox("Detect date columns",True)
        missing=st.selectbox("Missing-value strategy",["Keep missing values","Fill numeric median","Fill text with Unknown","Drop rows"])
        normalize=st.checkbox("Convert blank strings to missing values",True)
        if st.button("✨ Clean active dataset",type="primary"):
            start=st.session_state.filtered if st.session_state.filtered is not None else source
            cleaned,log=clean_data(start,{"trim":trim,"dedupe":dedupe,"convert_dates":dates,"missing":missing,"normalize_empty":normalize})
            st.session_state.cleaned=cleaned; st.session_state.clean_log=log
            st.success(f"Cleaning complete · {len(start):,} → {len(cleaned):,} rows.")
        if st.session_state.cleaned is not None:
            st.markdown("**Cleaning report**")
            if st.session_state.clean_log:
                for item in st.session_state.clean_log: st.markdown(f"- {item}")
            else: st.info("No changes were required by the selected cleaning rules.")
            st.dataframe(st.session_state.cleaned.head(100),use_container_width=True,height=260)
        st.markdown("#### Merge datasets")
        st.caption("Append rows from multiple files. Columns are aligned by column name; missing columns are filled with empty values.")
        merge_names=st.multiselect("Files to merge",names,default=names)
        merge_mode=st.radio("Merge strategy",["Append rows (union columns)","Append rows (common columns only)"],horizontal=True)
        if st.button("Merge selected files"):
            if len(merge_names)<2: st.warning("Select at least two files to merge.")
            else:
                frames=[st.session_state.datasets[n].copy() for n in merge_names]
                if merge_mode=="Append rows (common columns only)":
                    common=set(frames[0].columns)
                    for f in frames[1:]: common &= set(f.columns)
                    common=[c for c in frames[0].columns if c in common]
                    merged=pd.concat([f[common] for f in frames],ignore_index=True)
                else: merged=pd.concat(frames,ignore_index=True,sort=False)
                st.session_state.cleaned=merged
                st.session_state.clean_log=[f"Merged {len(merge_names)} files: "+", ".join(merge_names)]
                st.success(f"Merge complete · {len(merged):,} rows × {len(merged.columns)} columns.")
                st.dataframe(merged.head(100),use_container_width=True,height=260)

    if page in ["Export","Overview"]:
        st.markdown("### 05 · Export your deliverable")
        final_df=st.session_state.cleaned if st.session_state.cleaned is not None else (st.session_state.filtered if st.session_state.filtered is not None else source)
        st.caption(f"Export source: {'cleaned / merged result' if st.session_state.cleaned is not None else 'current active dataset or filtered view'} · {len(final_df):,} rows × {len(final_df.columns)} columns")
        x1,x2,x3=st.columns(3)
        with x1: st.download_button("↓  Download CSV",final_df.to_csv(index=False).encode("utf-8-sig"),file_name="datapilot_cleaned.csv",mime="text/csv",use_container_width=True)
        with x2:
            buf=io.BytesIO()
            with pd.ExcelWriter(buf,engine="openpyxl") as writer: final_df.to_excel(writer,index=False,sheet_name="Cleaned Data")
            st.download_button("↓  Download Excel",buf.getvalue(),file_name="datapilot_cleaned.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
        with x3:
            try:
                from reportlab.lib import colors
                from reportlab.lib.pagesizes import landscape, A4
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet
                pdfbuf=io.BytesIO(); doc=SimpleDocTemplate(pdfbuf,pagesize=landscape(A4),rightMargin=24,leftMargin=24,topMargin=24,bottomMargin=24)
                styles=getSampleStyleSheet()
                data=[list(map(str,final_df.columns))]+final_df.head(500).fillna("").astype(str).values.tolist()
                data=[[str(v)[:60] for v in row] for row in data]
                table=Table(data,repeatRows=1)
                table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#28234b")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.25,colors.HexColor("#cbd5e1")),("FONTSIZE",(0,0),(-1,-1),7),("VALIGN",(0,0),(-1,-1),"TOP"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f1f5f9")])]))
                doc.build([Paragraph("DataPilot Studio — Data Export",styles["Title"]),Paragraph(f"{len(final_df):,} total rows · PDF preview includes at most 500 rows",styles["Normal"]),Spacer(1,12),table])
                st.download_button("↓  Download PDF",pdfbuf.getvalue(),file_name="datapilot_report.pdf",mime="application/pdf",use_container_width=True)
            except Exception as e: st.error(f"PDF export unavailable: {e}")
else:
    st.markdown("""
    <div style="border:1px solid #252d40;background:rgba(16,21,34,.7);padding:25px;border-radius:18px;margin-top:20px">
    <div class="eyebrow">YOUR WORKFLOW</div><h3>One workspace. From raw files to ready-to-use data.</h3>
    <p style="color:#9aa8be">Upload several files to begin. DataPilot will profile columns, reveal missing values and duplicates, help you filter records, clean the data with transparent rules, merge datasets, and export CSV, Excel, or PDF.</p>
    </div>""",unsafe_allow_html=True)
    st.info("Tip: PDF import works best with selectable text and tables. Scanned PDFs require OCR and are not automatically recognized in this starter.")
