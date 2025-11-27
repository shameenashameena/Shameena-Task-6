import logging
import os
import json
from datetime import datetime, timezone, timedelta
import tempfile

import azure.functions as func
from azure.storage.blob import BlobServiceClient

# Config
SQL_CONN = os.getenv("SQL_CONN")  
BLOB_CONN = os.getenv("BLOB_CONN")  
ARCHIVE_CONTAINER = os.getenv("ARCHIVE_CONTAINER", "source")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
DAYS_OLD = int(os.getenv("DAYS_OLD", "30"))

# SQL templates
SELECT_BATCH_SQL = """
SELECT TOP (? ) orderId, customerId, orderDate, amount
FROM Orders
WHERE orderDate < DATEADD(day, -?, GETUTCDATE())
ORDER BY orderDate ASC;
"""

def fetch_batch(cursor, limit, days_old):
    cursor.execute(SELECT_BATCH_SQL, (limit, days_old))
    cols = [c[0] for c in cursor.description]
    rows = cursor.fetchall()
    return [dict(zip(cols, r)) for r in rows]

def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]

def main(mytimer: func.TimerRequest, context: func.Context) -> None:
    utc_now = datetime.now(timezone.utc)
    run_id = utc_now.strftime("%Y%m%dT%H%M%SZ")
    logging.info(f"TimerCleanupFunction run_id={run_id} started at {utc_now.isoformat()}")

    if not BLOB_CONN:
        logging.error("BLOB_CONN not configured")
        return

    # Initialize blob client
    blob_service = BlobServiceClient.from_connection_string(BLOB_CONN)
    container_client = blob_service.get_container_client(ARCHIVE_CONTAINER)
    try:
        container_client.create_container()
    except Exception:
        pass  # container already exists

    SQL_DISABLED = os.getenv("DISABLE_SQL") == "true"
    if SQL_DISABLED:
        logging.warning("SQL cleanup disabled — skipping SQL archiving/deletion.")
        return

    try:
        import pyodbc
    except Exception:
        logging.error("pyodbc import failed.")
        return

    if not SQL_CONN:
        logging.error("SQL_CONN not configured")
        return

    # Connect to SQL
    cnxn = pyodbc.connect(SQL_CONN)
    cnxn.autocommit = False
    cursor = cnxn.cursor()

    total_archived = 0
    start_time = datetime.now(timezone.utc)

    try:
        while True:
            rows = fetch_batch(cursor, BATCH_SIZE, DAYS_OLD)
            if not rows:
                break

            ndjson_lines = []
            ids = []
            for r in rows:
                if isinstance(r.get("orderDate"), datetime):
                    r["orderDate"] = r["orderDate"].isoformat()
                ndjson_lines.append(json.dumps(r, default=str))
                ids.append(r["orderId"])

            # NDJSON to temp file
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            blob_path = f"orders/{utc_now.year}/{utc_now.month:02d}/{utc_now.day:02d}/orders-{timestamp}.ndjson"

            with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmpf:
                for line in ndjson_lines:
                    tmpf.write(line + "\n")
                tmpf.flush()
                tmp_name = tmpf.name

            # Upload to blob
            blob_client = container_client.get_blob_client(blob_path)
            with open(tmp_name, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            logging.info(f"Uploaded archive blob: {blob_client.url} ({len(ndjson_lines)} rows)")

            # Delete archived in db
            try:
                for ids_chunk in chunked(ids, 1000):
                    placeholders = ",".join("?" for _ in ids_chunk)
                    delete_sql = f"DELETE FROM Orders WHERE orderId IN ({placeholders})"
                    cursor.execute(delete_sql, ids_chunk)
                cnxn.commit()
                logging.info(f"Deleted {len(ids)} rows from Orders")
                total_archived += len(ids)
            except Exception as e:
                cnxn.rollback()
                logging.error(f"Failed deleting rows: {e}")
                raise

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        logging.info(f"Finished. Total archived: {total_archived} rows in {duration:.1f}s run_id={run_id}")

    except Exception as err:
        logging.exception(f"TimerCleanupFunction failed: {err}")
    finally:
        try:
            cursor.close()
            cnxn.close()
        except:
            pass
