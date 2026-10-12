# DataPilot Studio

A premium-styled, local-first data cleaning and merge dashboard built with Streamlit.

## Features
- Upload multiple CSV, Excel (`.xlsx`, `.xls`) and table-based PDF files
- Inspect data previews, data types, missing cells, unique values and duplicate rows
- Quick numeric distribution chart and automated quality observations
- Filter rows by equality, contains, numeric comparisons, missing values, or selected values
- Clean text whitespace, blank strings, duplicates, missing values and recognizable date columns
- Merge multiple datasets by appending rows, aligning by column name or using common columns
- Export the current cleaned/merged result as CSV, Excel, or PDF

## Run on Windows in VS Code
1. Install Python 3.10 or newer and the VS Code Python extension.
2. Extract this ZIP to a folder and open that folder in VS Code.
3. Double-click `run.bat`, or open the VS Code terminal and run:
   ```bat
   run.bat
   ```
4. The script creates `.venv`, installs dependencies, and starts Streamlit. Open the local URL printed in the terminal (normally `http://localhost:8501`).

## Run on macOS/Linux
```bash
chmod +x run.sh
./run.sh
```

## Important notes
- No separate frontend server is needed: Streamlit serves the UI and backend logic together.
- Data processing runs locally in the app process. Uploaded data is held in Streamlit session state, not sent to an AI API.
- "AI-assisted" in this starter means automated profiling and explainable data-cleaning heuristics, not a connected generative AI model. You can integrate an LLM later if required.
- PDF support extracts tables from text-based PDFs. Scanned/image-only PDFs need OCR, which is not included.
- PDF export includes at most the first 500 rows as a compact report preview; CSV and Excel export all rows.
- Review cleaning settings before applying them, especially before dropping rows or filling missing values.
