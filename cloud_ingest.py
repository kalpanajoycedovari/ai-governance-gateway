import os
from qdrant_client import QdrantClient
from app.kb import ingest as ing
from pathlib import Path

URL = "https://qdrant.victoriousdesert-a185ae98.swedencentral.azurecontainerapps.io"

client = QdrantClient(url=URL, port=443, https=True, prefer_grpc=False, timeout=60)
client.set_model(ing.DENSE_MODEL)
client.set_sparse_model(ing.SPARSE_MODEL)

col = "governance_kb"
if client.collection_exists(col):
    client.delete_collection(col)
client.create_collection(
    collection_name=col,
    vectors_config=client.get_fastembed_vector_params(),
    sparse_vectors_config=client.get_fastembed_sparse_vector_params(),
)

docs, ids, meta, idx = [], [], [], 0
sources = list(Path("docs").glob("*.md")) + list(Path("data/policy").glob("*.md"))
for p in sources:
    tag, body = ing._read_tagged(p)
    for chunk in ing._chunk(body):
        docs.append(chunk); ids.append(idx); meta.append({"source": tag}); idx += 1

client.add(collection_name=col, documents=docs, ids=ids, metadata=meta)
print(f"Ingested {len(docs)} chunks into CLOUD '{col}'")
print("Sources:", sorted({m['source'] for m in meta}))