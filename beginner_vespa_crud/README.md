### Beginner Vespa Tutorial (Docker + CRUD + Debug + Simple UI)

This is a **very beginner-friendly** Vespa mini-project.

You will learn how to:

- start Vespa with Docker
- deploy a simple schema (an `item` document type)
- do CRUD with `curl`:
  - **Create / Update** (PUT)
  - **Read/Search** (query)
  - **Delete** (DELETE)
- debug common problems (health, logs, trace)
- use a small UI to visualize/add/delete/search items

---

## 0) Prerequisites

- Docker Desktop running

---

## 1) Start Vespa (and deploy the schema)

From repo root:

```bash
cd beginner_vespa_crud
docker compose up -d --build
```

Wait until Vespa becomes healthy:

```bash
curl -fsS http://localhost:19072/state/v1/health
```

You should get a healthy response (HTTP 200).

---

## 2) CRUD (copy/paste)

This tutorial uses:

- **namespace**: `demo`
- **document type**: `item`

### 2.1 Create (PUT a document)

```bash
curl -X PUT "http://localhost:8081/document/v1/demo/item/docid/1" \
  -H "Content-Type: application/json" \
  -d '{
    "fields": {
      "title": "Hello Vespa",
      "body": "This is my first document stored in Vespa.",
      "tags": ["tutorial", "beginner"]
    }
  }'
```

### 2.2 Update (PUT again with same id)

```bash
curl -X PUT "http://localhost:8081/document/v1/demo/item/docid/1" \
  -H "Content-Type: application/json" \
  -d '{
    "fields": {
      "title": "Hello Vespa (updated)",
      "body": "I updated the body text.",
      "tags": ["tutorial", "update"]
    }
  }'
```

### 2.3 Read/Search (keyword search)

Search in `body` / `title`:

```bash
curl -s "http://localhost:8081/search/?" \
  --data-urlencode 'yql=select * from sources item where userInput(@q);' \
  --data-urlencode 'q=updated' \
  --data-urlencode 'hits=5' | python3 -m json.tool
```

### 2.4 List all documents

```bash
curl -s "http://localhost:8081/search/?" \
  --data-urlencode 'yql=select * from sources item where true;' \
  --data-urlencode 'hits=20' | python3 -m json.tool
```

### 2.5 Delete

```bash
curl -X DELETE "http://localhost:8081/document/v1/demo/item/docid/1"
```

Confirm it’s gone by searching again.

---

## 3) Debugging (very practical)

### 3.1 Check container logs

```bash
docker logs --tail 200 beginner_vespa
```

If deploy failed:

```bash
docker logs --tail 200 beginner_vespa_deployer
```

### 3.2 Check Vespa health + status

```bash
curl -fsS http://localhost:19072/state/v1/health
```

### 3.3 Debug a slow/strange query (trace)

Add `tracelevel=3`:

```bash
curl -s "http://localhost:8081/search/?" \
  --data-urlencode 'yql=select * from sources item where userInput(@q);' \
  --data-urlencode 'q=vespa' \
  --data-urlencode 'hits=5' \
  --data-urlencode 'tracelevel=3' | python3 -m json.tool
```

### 3.4 Metrics (optional)

```bash
curl -s http://localhost:19072/metrics/v2/values | head -n 40
```

---

## 4) UI (simple visualization)

This project includes a small Streamlit UI:

- URL: `http://localhost:8501`

It can:

- add/update an item
- delete by id
- search by keyword
- list recent items

---

## 5) Stop everything

```bash
docker compose down
```


