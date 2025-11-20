"""
Centralized prompt definitions for LLM extraction logic.
"""
PDF_CLASSIFICATION_PROMPT = """
You classify construction-related PDFs using strict rule-based logic. 
Your output must be deterministic and follow the priority hierarchy listed below.

========================
A. FUNCTIONAL CATEGORY (Pick EXACTLY one)
========================

Allowed values:
- construction_costing
- project_schedule
- construction_approval
- ura_circular
- other

========================
A1. COSTING OVERRIDE (Highest Priority)
========================

If ANY of the following indicators appear anywhere in the document, you MUST classify as **construction_costing**, 
even if scheduling or narrative text appears:

Cost keywords:
- rate, unit rate, cost, quantity, qty, item no, item number, amount, total, estimate, estimation, boq, bill of quantities

Currency markers:
- Rs., INR, ₹, $, €, AED, SGD

Patterns:
- multiple numeric values per line across several lines
- structured numeric rows or columns resembling tables
- material units: sqm, sq.m, m2, cum, m3, kg, mt, nos, ltr, litre
- phrases like “rate per”, “unit rate”, “labour”, “materials”, “machinery”, “manpower”

If any of these appear → ALWAYS choose **construction_costing**.

========================
A2. PROJECT SCHEDULING LOGIC (Second Priority)
========================

Choose **project_schedule** ONLY IF:
- there are NO costing indicators, AND
- the majority of the content is about durations, timelines, start/finish dates, dependencies, milestones,
  task sequences, phases of work, critical path, bar charts, or gantt-like structures.

Keywords that support scheduling:
- duration, weeks, days, sequencing, activity, timeline, start date, finish date, milestone, dependency, 
  construction stages, phasing

Scheduling is NEVER selected if any costing signal exists.

========================
A3. APPROVAL / CIRCULAR LOGIC (Third Priority)
========================

construction_approval:
- approval stages, authority workflows, submission requirements, permit processes, NOC steps,
  forms, checklists, compliance procedures

ura_circular:
- regulatory circulars, official notices, policies, statutory rules, definitions, guidelines,
  sections/clauses, legal formatting

If neither applies, select “other”.

========================
B. LAYOUT TYPE (Pick EXACTLY one)
========================

Choose the layout that dominates MOST pages:

- text_pdf       → mostly paragraphs or sentences
- table_pdf      → tables, numeric grids, BOQ formats
- flowchart_pdf  → diagrams with boxes/arrows/decision paths
- gantt_chart_pdf → schedule bars, timeline charts
- image_pdf      → mostly images or scanned pages
- mixed_pdf      → mix of tables + text + images with no clear majority

========================
C. STRUCTURAL FLAGS (true/false)
========================
Each flag indicates whether that element appears meaningfully anywhere:

- contains_text
- contains_images
- contains_flowchart
- contains_tables
- contains_gantt
- contains_other_charts
- requires_ocr   → true if scanned, faint, low-text-density, or mostly image-based

========================
D. STRICT JSON OUTPUT FORMAT
========================

Return ONLY this JSON object (no markdown, no comments):

{
  "pdf_type": "<one category>",
  "layout_type": "<one layout>",
  "flags": {
    "contains_text": true/false,
    "contains_images": true/false,
    "contains_flowchart": true/false,
    "contains_tables": true/false,
    "contains_gantt": true/false,
    "contains_other_charts": true/false,
    "requires_ocr": true/false
  },
  "reason": "Short, clear explanation of why pdf_type and layout_type were chosen."
}

========================
CONTENT TO ANALYZE:
{{CONTENT}}
========================
"""


# 1. Extract construction approval workflow (flowchart-like PDFs)
CONSTRUCTION_PROCESS_PROMPT = """
You are an expert in interpreting construction approval workflows, including flowcharts,
multi-column layouts, stepped diagrams, and OCR-converted process text.

Your task:
- Identify each approval step
- Normalize text (remove OCR artifacts)
- Preserve original order
- Merge wrapped/broken lines into full descriptions
- Remove page numbers and non-step text

Response Format (STRICT JSON):
[
  {"step_number": 1, "description": "Clean step description"},
  {"step_number": 2, "description": "Next step..."},
  ...
]

Rules:
- Infer correct order even if text is scattered or broken.
- Ignore arrows, symbols, unicode artifacts, or OCR noise.
- Do NOT add any explanation or commentary.
- Only output valid JSON.

Content:
{{CONTENT}}
"""


# 2. Costing / Bill of Quantities extraction (tables, semi-structured text)
COSTING_EXTRACTION_PAGE_PROMPT = """
You are a construction cost extraction engine.

You will receive ONE PDF page (text + tables) from a civil engineering
planning/costing document.

Extract every cost line where ALL of these appear ON THIS PAGE:
1. quantity (number)
2. unit of measure (m, m2, m3, t, days, months, sheets, piles, no, etc.)
3. unit price (any currency: yen, Rp, $, etc.)
4. total cost (same currency as unit price)

Also detect whether the line is marked as local or foreign cost, if possible.

Return ONLY valid JSON (no comments, no markdown), with this schema:

[
  {
    "page_number": <int>,
    "page_text_snippet": "<short snippet from source>",
    "items": [
      {
        "item_name": "<string>",
        "quantity": <float>,
        "unit_of_measure": "<string>",
        "currency": "<string>",          # e.g. "yen", "Rp"
        "unit_price": <float>,
        "total_cost": <float>,
        "cost_type": "local cost" | "foreign cost" | "unspecified"
      }
    ]
  }
]

If you find no valid items on this page, return an empty list: [].

PAGE NUMBER: {{PAGE_NUMBER}}

PAGE TEXT:
{{PAGE_TEXT}}

PAGE TABLES:
{{PAGE_TABLES}}
"""


# 3. Project schedule extraction (tasks, durations, dates)
PROJECT_SCHEDULE_PROMPT = """
You are a senior project scheduler.

You will receive a chunk of text from a construction schedule document
(Gantt-style text, milestones, timelines, or irregular formatting).

Your task:
- Identify all tasks / activities mentioned in the text.
- For each task, extract:
  - task_name
  - duration_days
  - start_date
  - finish_date

Output:
Return ONLY a JSON array (no explanation, no markdown):

[
  {
    "task_name": "string",
    "duration_days": 0,
    "start_date": "YYYY-MM-DD or null",
    "finish_date": "YYYY-MM-DD or null"
  }
]

Rules:
- Merge multi-line task names into a single clean string.
- If duration is clearly derivable (e.g. "10 days", "3 months"), convert to
  an integer number of days. If not clear, use null.
- If a date is missing or ambiguous, set it to null (do NOT invent dates).
- Use ISO format YYYY-MM-DD for all explicit dates.
- Ignore purely decorative timelines, ASCII art, or non-task text.
- Do NOT output anything except valid JSON.
"""



# 4. Regulatory rules extraction (URA, GFA definitions, government circulars)
REGULATORY_RULES_PROMPT = """
You are a regulatory compliance analyst for building regulations
(e.g. URA, GFA, building codes, statutory circulars).

You will receive a chunk of text from such a document.

Your task:
- Extract each distinct rule or regulation mentioned.
- For each rule, return:
  - rule_summary
  - measurement_basis

Output:
Return ONLY a JSON array (no explanation, no markdown):

[
  {
    "rule_summary": "string",
    "measurement_basis": "string or null"
  }
]

Where:
- "rule_summary" is a short, precise description of the rule.
- "measurement_basis" is a short description **only if** the rule clearly
  explains how something is measured, such as:
    - area computation
    - gross floor area (GFA)
    - what is included / excluded
    - thresholds or limits
    - qualifying criteria / conditions
  If no measurement basis is described, set this field to null.

Rules:
- One JSON object per rule or regulatory point.
- Summaries must be concise but accurate (do not copy long paragraphs).
- Ignore headers, footers, page numbers, and IDs unless they contain a rule.
- Do NOT output anything except valid JSON.
"""
