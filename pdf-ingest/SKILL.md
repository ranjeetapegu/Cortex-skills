---
name: pdf-ingest
description: Ingest local PDF files into a Snowflake stage, parse text with AI_PARSE_DOCUMENT, summarize with CORTEX.SUMMARIZE, optionally extract and analyze images. All settings are user-configurable.
tools:
  - snowflake_sql_execute
  - bash
  - ask_user_question
---

# PDF Ingest Skill

Ingest PDF files from a local machine into Snowflake. Parses PDF content, generates summaries, and stores structured results in a table. Optionally extracts images from PDFs, classifies them, and generates descriptions.

## When to Use

- User wants to upload/ingest PDF files to Snowflake
- User wants to parse or extract text from PDFs stored in Snowflake
- User wants to extract and analyze images from PDFs
- User mentions "pdf ingest", "upload pdf", "parse pdf", "pdf to snowflake", "document ingestion", "extract images from pdf"

## Step 1: Gather User Inputs

Before doing anything, ask the user for the following using the `ask_user_question` tool. Use sensible defaults shown in brackets:

1. **Local PDF path** — file path or folder path containing PDFs (REQUIRED, no default)
2. **Database** — Snowflake database name [default: `RND_WORK`]
3. **Schema** — Snowflake schema name [default: `DATA`]
4. **Table name** — destination table for parsed text results [default: `PDF_DOCUMENTS`]
5. **Stage name** — internal stage for PDF uploads [default: `PDF_STAGE`]
6. **Extract images?** — Yes or No [default: `No`]

If the user says Yes to extract images, also ask:
7. **Images table name** — table for extracted image data [default: `PDF_IMAGES`]

Present these as a single question with defaults clearly shown so the user can accept defaults or override. Example prompt:

> I'll ingest your PDFs into Snowflake. Please confirm or adjust these settings:
> - **PDF path**: (you must provide this)
> - **Database**: `RND_WORK`
> - **Schema**: `DATA`
> - **Table**: `PDF_DOCUMENTS`
> - **Stage**: `PDF_STAGE`
> - **Extract images?**: No
>
> If you enable image extraction, images will be stored in a separate table (`PDF_IMAGES` by default) with AI-generated descriptions and classifications.

If the user only provides a PDF path, use all defaults for the rest.

## Step 2: Create Snowflake Objects

Run the following SQL statements using `snowflake_sql_execute`. Replace placeholders with the user's chosen values.

### Create database and schema (if not exists)

```sql
CREATE DATABASE IF NOT EXISTS <DATABASE>;
CREATE SCHEMA IF NOT EXISTS <DATABASE>.<SCHEMA>;
```

### Create internal stage

```sql
CREATE STAGE IF NOT EXISTS <DATABASE>.<SCHEMA>.<STAGE_NAME>
  DIRECTORY = (ENABLE = TRUE)
  COMMENT = 'Stage for PDF document ingestion';
```

### Create documents table

```sql
CREATE TABLE IF NOT EXISTS <DATABASE>.<SCHEMA>.<TABLE_NAME> (
    FILE_NAME        VARCHAR          COMMENT 'Original PDF file name',
    UPLOAD_TIMESTAMP TIMESTAMP_NTZ    DEFAULT CURRENT_TIMESTAMP() COMMENT 'When the file was ingested',
    PAGE_COUNT       INT              COMMENT 'Number of pages in the PDF',
    RAW_TEXT         VARCHAR(16777216) COMMENT 'Full extracted text (Markdown from LAYOUT mode)',
    SUMMARY          VARCHAR(16777216) COMMENT 'AI-generated summary of the document',
    PARSED_JSON      VARIANT          COMMENT 'Full AI_PARSE_DOCUMENT JSON output'
);
```

### Create images table (only if user enabled image extraction)

```sql
CREATE TABLE IF NOT EXISTS <DATABASE>.<SCHEMA>.<IMAGES_TABLE_NAME> (
    FILE_NAME         VARCHAR          COMMENT 'Source PDF file name',
    PAGE_INDEX        INT              COMMENT 'Page number where image was found (0-based)',
    IMAGE_ID          VARCHAR          COMMENT 'Unique image identifier from AI_PARSE_DOCUMENT',
    IMAGE_BASE64      VARCHAR(16777216) COMMENT 'Base64-encoded image data',
    BOUNDING_BOX      VARIANT          COMMENT 'Image position on page (top_left_x/y, bottom_right_x/y)',
    IMAGE_DESCRIPTION VARCHAR(16777216) COMMENT 'AI-generated description of the image',
    IMAGE_CLASSIFICATION VARCHAR       COMMENT 'Image type classification (chart, photo, diagram, table, signature, logo, other)',
    EXTRACT_TIMESTAMP TIMESTAMP_NTZ    DEFAULT CURRENT_TIMESTAMP() COMMENT 'When the image was extracted'
);
```

## Step 3: Upload PDF Files

Use the `snow` CLI via bash to upload local PDFs to the stage:

### Single file
```bash
snow stage copy <LOCAL_PDF_PATH> @<DATABASE>.<SCHEMA>.<STAGE_NAME> --connection <active_connection> --overwrite
```

### Folder of PDFs (glob pattern)
If the user provides a folder path, upload all PDFs in it:
```bash
snow stage copy "<FOLDER_PATH>/*.pdf" @<DATABASE>.<SCHEMA>.<STAGE_NAME> --connection <active_connection> --overwrite
```

After upload, verify files are on stage:
```bash
snow sql -q "LIST @<DATABASE>.<SCHEMA>.<STAGE_NAME>" --connection <active_connection>
```

## Step 4: Parse and Store Each PDF (Text)

For EACH uploaded PDF file, run the following SQL. Process files one at a time to handle large documents gracefully.

### Insert parsed results with summary

The `AI_PARSE_DOCUMENT` options depend on whether image extraction is enabled:
- **Without images**: `{'mode': 'LAYOUT', 'page_split': true}`
- **With images**: `{'mode': 'LAYOUT', 'page_split': true, 'extract_images': true}`

For each file, run an INSERT that parses, summarizes, and stores in one statement:

```sql
INSERT INTO <DATABASE>.<SCHEMA>.<TABLE_NAME>
    (FILE_NAME, UPLOAD_TIMESTAMP, PAGE_COUNT, RAW_TEXT, SUMMARY, PARSED_JSON)
WITH parsed AS (
    SELECT
        PARSE_JSON(
            AI_PARSE_DOCUMENT(
                TO_FILE('@<DATABASE>.<SCHEMA>.<STAGE_NAME>', '<FILE_NAME>'),
                {'mode': 'LAYOUT', 'page_split': true}
            )
        ) AS doc
),
extracted AS (
    SELECT
        doc:metadata:pageCount::INT AS page_count,
        ARRAY_TO_STRING(
            TRANSFORM(doc:pages, p -> p:content::VARCHAR),
            '\n\n---\n\n'
        ) AS full_text,
        doc
    FROM parsed
)
SELECT
    '<FILE_NAME>',
    CURRENT_TIMESTAMP(),
    page_count,
    full_text,
    SNOWFLAKE.CORTEX.SUMMARIZE(full_text),
    doc
FROM extracted;
```

**IMPORTANT**: If a document is very large and `SNOWFLAKE.CORTEX.SUMMARIZE` fails due to token limits, catch the error and insert with SUMMARY set to `'Summary unavailable - document too large'`. You can also try summarizing just the first few pages in that case.

**IMPORTANT**: Use a longer timeout (e.g. `timeout_seconds: 300`) for the INSERT SQL since AI_PARSE_DOCUMENT and SUMMARIZE can take time on large PDFs.

## Step 5: Extract and Analyze Images (Only if user enabled image extraction)

**Skip this entire step if the user said No to image extraction.**

For each PDF file, extract images, classify them, and generate descriptions. This step requires `extract_images: true` in the AI_PARSE_DOCUMENT call.

### 5a: Parse with image extraction and flatten images

```sql
INSERT INTO <DATABASE>.<SCHEMA>.<IMAGES_TABLE_NAME>
    (FILE_NAME, PAGE_INDEX, IMAGE_ID, IMAGE_BASE64, BOUNDING_BOX, IMAGE_DESCRIPTION, IMAGE_CLASSIFICATION, EXTRACT_TIMESTAMP)
WITH parsed AS (
    SELECT
        PARSE_JSON(
            AI_PARSE_DOCUMENT(
                TO_FILE('@<DATABASE>.<SCHEMA>.<STAGE_NAME>', '<FILE_NAME>'),
                {'mode': 'LAYOUT', 'page_split': true, 'extract_images': true}
            )
        ) AS doc
),
images_flat AS (
    SELECT
        p.value:index::INT AS page_index,
        img.value:id::VARCHAR AS image_id,
        img.value:image_base64::VARCHAR AS image_b64,
        OBJECT_CONSTRUCT(
            'top_left_x', img.value:top_left_x,
            'top_left_y', img.value:top_left_y,
            'bottom_right_x', img.value:bottom_right_x,
            'bottom_right_y', img.value:bottom_right_y
        ) AS bbox
    FROM parsed,
        LATERAL FLATTEN(input => doc:pages) p,
        LATERAL FLATTEN(input => p.value:images, OUTER => TRUE) img
    WHERE img.value:image_base64 IS NOT NULL
)
SELECT
    '<FILE_NAME>',
    page_index,
    image_id,
    image_b64,
    bbox,
    AI_COMPLETE(
        'claude-3-5-sonnet',
        CONCAT(
            'Describe this image in detail. What does it show? ',
            'If it is a chart or graph, describe the data trends. ',
            'If it is a diagram, explain the structure. ',
            'If it is a photo, describe what is depicted. ',
            'Keep the description under 500 words.'
        ),
        TO_FILE_FROM_BASE64(image_b64, 'image/png')
    ) AS image_description,
    AI_CLASSIFY(
        AI_COMPLETE(
            'claude-3-5-sonnet',
            CONCAT(
                'What type of image is this? Answer with exactly one word from: ',
                'chart, photo, diagram, table, signature, logo, screenshot, equation, map, other'
            ),
            TO_FILE_FROM_BASE64(image_b64, 'image/png')
        ),
        ['chart', 'photo', 'diagram', 'table', 'signature', 'logo', 'screenshot', 'equation', 'map', 'other']
    )::VARCHAR AS image_classification,
    CURRENT_TIMESTAMP()
FROM images_flat;
```

**IMPORTANT**: Use `timeout_seconds: 600` for this query since image analysis with AI_COMPLETE is slower.

**FALLBACK**: If `AI_COMPLETE` with vision fails or `TO_FILE_FROM_BASE64` is not available, use a simpler approach:
- Set IMAGE_DESCRIPTION to `'Description not available - vision model error'`
- Set IMAGE_CLASSIFICATION to `'unknown'`
- Still store the base64 data so images can be analyzed later

**ALTERNATIVE simpler classification** if AI_CLASSIFY on AI_COMPLETE output causes issues:

```sql
AI_COMPLETE(
    'claude-3-5-sonnet',
    CONCAT(
        'Classify this image into exactly one category: ',
        'chart, photo, diagram, table, signature, logo, screenshot, equation, map, other. ',
        'Respond with only the category name, nothing else.'
    ),
    TO_FILE_FROM_BASE64(image_b64, 'image/png')
) AS image_classification
```

## Step 6: Report Results

After processing all files, query both tables and show a summary to the user.

### Documents summary
```sql
SELECT
    FILE_NAME,
    UPLOAD_TIMESTAMP,
    PAGE_COUNT,
    LEFT(SUMMARY, 200) AS SUMMARY_PREVIEW
FROM <DATABASE>.<SCHEMA>.<TABLE_NAME>
ORDER BY UPLOAD_TIMESTAMP DESC
LIMIT 20;
```

### Images summary (only if image extraction was enabled)
```sql
SELECT
    FILE_NAME,
    COUNT(*) AS TOTAL_IMAGES,
    LISTAGG(DISTINCT IMAGE_CLASSIFICATION, ', ') AS IMAGE_TYPES
FROM <DATABASE>.<SCHEMA>.<IMAGES_TABLE_NAME>
GROUP BY FILE_NAME
ORDER BY FILE_NAME;
```

And show a detailed breakdown:
```sql
SELECT
    FILE_NAME,
    PAGE_INDEX,
    IMAGE_ID,
    IMAGE_CLASSIFICATION,
    LEFT(IMAGE_DESCRIPTION, 150) AS DESCRIPTION_PREVIEW
FROM <DATABASE>.<SCHEMA>.<IMAGES_TABLE_NAME>
ORDER BY FILE_NAME, PAGE_INDEX
LIMIT 50;
```

Present results in a clean format:
- Total files processed
- For each file: name, page count, and first ~200 chars of summary
- If images extracted: total images found, breakdown by type, and description previews

## Error Handling

- If `snow stage copy` fails, check the file path exists and suggest corrections
- If `AI_PARSE_DOCUMENT` fails, it may be a file format issue — inform the user and skip that file
- If `SNOWFLAKE.CORTEX.SUMMARIZE` fails on large docs, fall back to summarizing the first 3 pages only
- If image extraction fails for a file, log the error and continue with the next file
- If `AI_COMPLETE` vision calls fail, store images with placeholder descriptions and inform the user
- Always report which files succeeded and which failed

## Examples

### Example 1: Single PDF with defaults, no images
```
User: $pdf-ingest /Users/me/reports/quarterly.pdf
```
Uses defaults: RND_WORK.DATA.PDF_DOCUMENTS, stage PDF_STAGE, no image extraction.

### Example 2: With image extraction
```
User: $pdf-ingest
```
Agent asks for inputs. User provides:
- Path: /Users/me/research/paper.pdf
- Extract images: Yes
- (accepts all other defaults)

Creates PDF_DOCUMENTS and PDF_IMAGES tables. Extracts text, summary, images, image descriptions, and classifications.

### Example 3: Custom everything with images
```
User: $pdf-ingest
```
Agent asks for inputs. User provides:
- Path: /Users/me/invoices/
- Database: FINANCE
- Schema: DOCS
- Table: INVOICE_TEXT
- Stage: INVOICE_STAGE
- Extract images: Yes
- Images table: INVOICE_IMAGES

### Example 4: Folder batch upload
```
User: $pdf-ingest /Users/me/contracts/
```
Uploads all PDFs in the folder, parses each, stores results. Asks about image extraction.
