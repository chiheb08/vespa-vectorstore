### 2026-01-08 — `POST /ingest/file` error: “Expected UploadFile, received: <class 'str'>”

#### Symptom
Calling the ingest endpoint with a file path like this:

```bash
curl -s http://localhost:8000/ingest/file \
  -F "doc_id=myfile-1" \
  -F "file=/Users/chihebmhamdi/Downloads/resumeprojet.pdf" \
  | python3 -m json.tool
```

returned:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "file"],
      "msg": "Value error, Expected UploadFile, received: <class 'str'>",
      "input": "/Users/chihebmhamdi/Downloads/resumeprojet.pdf"
    }
  ]
}
```

#### Root cause
In `curl -F`, sending `file=/path/to/file.pdf` sends a **string field** containing the path.
FastAPI’s `UploadFile` expects a **real file upload** (multipart file part), not a string.

#### Fix
Use `@` to tell curl to upload the file contents:

```bash
curl -s http://localhost:8000/ingest/file \
  -F "doc_id=myfile-1" \
  -F "file=@/Users/chihebmhamdi/Downloads/resumeprojet.pdf" \
  | python3 -m json.tool
```

#### Where this fails in the architecture
The request never reaches PDF parsing or Vespa. It fails at the API boundary:

```mermaid
flowchart LR
  U["You (curl)"] --> API["rag-api /ingest/file"]
  API --> FAIL["Validation error\nExpected UploadFile\nreceived string"]
```



