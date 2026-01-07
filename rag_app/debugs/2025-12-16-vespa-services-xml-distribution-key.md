### 2025-12-16 — Vespa deploy failed: `distribution-key` missing in `services.xml`

---

### Symptom

`vespa-deployer` failed with HTTP 400:

> Invalid application: Invalid XML according to XML schema, error in services.xml:  
> element "node" missing required attribute "distribution-key"

---

### Main cause

In newer Vespa versions, `<content><nodes><node .../></nodes></content>` requires a `distribution-key` attribute.

Our `rag_app/vespa/app/services.xml` had:

```xml
<node hostalias="node1"/>
```

---

### Fix

Add the attribute:

```xml
<node hostalias="node1" distribution-key="0"/>
```

Then rerun:

```bash
cd rag_app
docker compose up -d --build
```



