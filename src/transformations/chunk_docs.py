"""DLT table definition for document chunking.

Reads from the raw_documents streaming table, applies the chunking logic from
chunking.py, and writes the result to the doc_chunks Delta table.

The pure-Python chunking helpers live in chunking.py so they can be tested
without Spark/DLT dependencies.
"""

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType, StructField, StructType

from transformations.chunking import chunk_document

# ---------------------------------------------------------------------------
# Spark UDF registration
# ---------------------------------------------------------------------------

_chunk_schema = ArrayType(
    StructType(
        [
            StructField("chunk_id", StringType()),
            StructField("doc_source", StringType()),
            StructField("chunk_text", StringType()),
            StructField("chunk_index", StringType()),  # cast to INT below
            StructField("metadata", StringType()),
        ]
    )
)

chunk_document_udf = F.udf(chunk_document, _chunk_schema)


# ---------------------------------------------------------------------------
# DLT table definition
# ---------------------------------------------------------------------------


@dlt.table(
    name="doc_chunks",
    comment="Chunked and cleaned documentation segments ready for embedding",
    table_properties={"quality": "silver"},
)
def doc_chunks():
    """Transform raw documents into fixed-size, overlapping chunks.

    Each chunk carries its source path, positional index, and JSON-encoded
    metadata (title, section headings).
    """
    raw = dlt.read_stream("raw_documents")

    return (
        raw.withColumn(
            "chunks",
            F.explode(chunk_document_udf(F.col("doc_path"), F.col("doc_content"))),
        )
        .select(
            F.col("chunks.chunk_id").alias("chunk_id"),
            F.col("chunks.doc_source").alias("doc_source"),
            F.col("chunks.chunk_text").alias("chunk_text"),
            F.col("chunks.chunk_index").cast("int").alias("chunk_index"),
            F.col("chunks.metadata").alias("metadata"),
        )
    )
