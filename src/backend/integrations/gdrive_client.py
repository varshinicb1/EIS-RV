"""
Google Drive Service Account Client
=====================================
Authenticates using GOOGLE_SERVICE_ACCOUNT_JSON env var and provides
helpers to list, download, and watch files in a Drive folder.
"""

import io
import json
import logging
import os
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]

DRIVE_FOLDER_ID = "1wcWa-pTMFUinnVBIvhUFLbL6LrMawrQV"

# MIME types we can process
PROCESSABLE_MIME = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "application/vnd.google-apps.document": "gdoc",
}


def _build_service():
    """Build a Google Drive API service from the service account JSON."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not sa_json:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON env var not set")

        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return service
    except Exception as e:
        logger.error("Failed to build Drive service: %s", e)
        raise


def list_files_in_folder(folder_id: str = DRIVE_FOLDER_ID, recursive: bool = True) -> List[Dict]:
    """
    List all processable files in a Drive folder (optionally recursive).
    Returns list of dicts with id, name, mimeType, modifiedTime, parents, size, webViewLink.
    """
    service = _build_service()
    all_files = []
    _collect_files(service, folder_id, all_files, recursive)
    logger.info("Found %d processable files in Drive folder %s", len(all_files), folder_id)
    return all_files


def _collect_files(service, folder_id: str, result: list, recursive: bool):
    """Recursively collect files from a folder."""
    page_token = None
    while True:
        query = f"'{folder_id}' in parents and trashed=false"
        resp = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, webViewLink, parents)",
            pageSize=100,
            pageToken=page_token,
        ).execute()

        for f in resp.get("files", []):
            if f["mimeType"] == "application/vnd.google-apps.folder":
                if recursive:
                    _collect_files(service, f["id"], result, recursive)
            elif f["mimeType"] in PROCESSABLE_MIME:
                result.append(f)

        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def download_file_bytes(file_id: str, mime_type: str) -> bytes:
    """Download a file's content as bytes. Exports Google Docs to PDF."""
    from googleapiclient.http import MediaIoBaseDownload

    service = _build_service()

    if mime_type == "application/vnd.google-apps.document":
        request = service.files().export_media(fileId=file_id, mimeType="application/pdf")
    else:
        request = service.files().get_media(fileId=file_id)

    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def get_folder_info(folder_id: str = DRIVE_FOLDER_ID) -> Dict:
    """Get metadata about the target folder."""
    try:
        service = _build_service()
        f = service.files().get(
            fileId=folder_id,
            fields="id, name, modifiedTime, owners"
        ).execute()
        return f
    except Exception as e:
        logger.error("get_folder_info failed: %s", e)
        return {"id": folder_id, "name": "Unknown", "error": str(e)}


def get_service_account_email() -> str:
    """Return the service account email for sharing instructions."""
    try:
        sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
        info = json.loads(sa_json)
        return info.get("client_email", "")
    except Exception:
        return ""
