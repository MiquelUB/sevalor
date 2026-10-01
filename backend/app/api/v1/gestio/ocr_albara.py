from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from app.services.ocr_service import processar_albara_ocr

# Just a snippet to paste into magatzem.py
