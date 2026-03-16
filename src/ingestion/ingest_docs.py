# Databricks notebook source
"""Document ingestion pipeline using Databricks Auto Loader.

Reads raw documentation files (Markdown, plain text, reStructuredText) from a
Unity Catalog Volume and writes them to the raw_documents Delta table.  Designed
to run as a Streaming Table inside a Databricks Streaming Delta Pipeline (SDP).
"""

import dlt
from pyspark.sql import functions as F


VOLUME_PATH = "/Volumes/${var.catalog}/${var.schema}/source_docs"


@dlt.table(
    name="raw_documents",
    comment="Raw ingested documentation files before chunking",
    table_properties={"quality": "bronze"},
)
def raw_documents():
    """Incrementally ingest documentation files via Auto Loader.

    Auto Loader watches the configured Volume path and picks up new or
    modified files.  Each row contains the full text content of a single
    document together with its path and format.
    """
    return (
        spark.readStream.format("cloudFiles")  # noqa: F821 — spark provided at runtime
        .option("cloudFiles.format", "text")
        .option("cloudFiles.inferColumnTypes", "false")
        .option("wholeText", "true")
        .load(VOLUME_PATH)
        .select(
            F.col("_metadata.file_path").alias("doc_path"),
            F.col("value").alias("doc_content"),
            F.regexp_extract(F.col("_metadata.file_name"), r"\.([^.]+)$", 1).alias(
                "doc_format"
            ),
            F.current_timestamp().alias("ingested_at"),
        )
    )
