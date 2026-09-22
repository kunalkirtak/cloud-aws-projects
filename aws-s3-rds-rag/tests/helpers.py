def upload_and_ingest(client, name: str, text: str) -> dict:
    response = client.post("/documents/upload", files={"file": (name, text.encode(), "text/plain")})
    assert response.status_code == 201, response.text
    document = response.json()
    ingest = client.post("/documents/ingest", json={"document_id": document["id"]})
    assert ingest.status_code == 200, ingest.text
    return document
