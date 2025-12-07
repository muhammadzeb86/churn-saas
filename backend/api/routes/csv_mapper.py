"""
CSV Column Mapping API

Provides endpoints for:
- Previewing column mappings
- Downloading sample CSVs
- Getting mapping suggestions

Author: AI Assistant
Created: December 7, 2025
Version: 2.0 (Enhanced with security fixes)
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse, StreamingResponse
from typing import Dict, Any
import pandas as pd
import io
import logging
from pathlib import Path

from backend.ml.column_mapper import IntelligentColumnMapper

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/csv", tags=["csv-mapping"])


@router.post("/preview-mapping")
async def preview_column_mapping(
    file: UploadFile = File(...),
    industry: str = Query('telecom', description="Industry type (telecom, saas)")
):
    """
    Preview how columns will be mapped without actually processing the file.
    
    This endpoint helps users understand:
    - Which columns we detected
    - How confident we are about each mapping
    - What columns are missing
    - Suggestions for fixing issues
    
    Args:
        file: CSV file to analyze
        industry: Industry type for appropriate column mapping
    
    Returns:
        JSON with mapping preview and suggestions
    
    Example Response:
        {
            "success": true,
            "confidence": 92.5,
            "total_columns": 20,
            "mapped_columns": 18,
            "missing_required": [],
            "mappings": [
                {
                    "from": "customer id",
                    "to": "customerID",
                    "confidence": 100.0,
                    "strategy": "normalized"
                }
            ],
            "unmapped": ["extra_column_1"],
            "suggestions": ["✅ All required columns detected!"]
        }
    """
    try:
        # Read CSV
        content = await file.read()
        
        # Remove UTF-8 BOM if present (Excel export bug)
        if content.startswith(b'\xef\xbb\xbf'):
            content = content[3:]
            logger.debug("Removed UTF-8 BOM from CSV")
        
        df = pd.read_csv(io.BytesIO(content))
        
        # Validate CSV
        if len(df) == 0:
            raise HTTPException(
                status_code=400,
                detail="CSV file is empty"
            )
        
        if len(df.columns) == 0:
            raise HTTPException(
                status_code=400,
                detail="CSV file has no columns"
            )
        
        # Preview mapping
        mapper = IntelligentColumnMapper(industry=industry)
        preview = mapper.preview_mapping(df)
        
        logger.info(
            f"Mapping preview: industry={industry}, "
            f"success={preview['success']}, confidence={preview['confidence']}%"
        )
        
        return preview
    
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="CSV file is empty or invalid")
    except pd.errors.ParserError as e:
        raise HTTPException(status_code=400, detail=f"CSV parsing error: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error previewing mapping: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to preview column mapping")


@router.get("/sample-csv/{industry}")
async def download_sample_csv(industry: str):
    """
    Download sample CSV file for testing.
    
    Args:
        industry: 'telecom' or 'saas'
    
    Returns:
        CSV file download
    
    Example:
        GET /api/csv/sample-csv/telecom
        GET /api/csv/sample-csv/saas
    """
    if industry not in ['telecom', 'saas']:
        raise HTTPException(
            status_code=404,
            detail=f"Sample CSV not found for industry: {industry}. Available: telecom, saas"
        )
    
    # Path to sample CSV
    sample_file = Path(__file__).parent.parent.parent / "static" / "sample_data" / f"sample_{industry}.csv"
    
    if not sample_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Sample CSV file not found: {sample_file}"
        )
    
    logger.info(f"Sample CSV download: industry={industry}")
    
    # Read file content synchronously (small files, <10KB)
    # This ensures the entire file is sent with proper headers
    with open(sample_file, 'rb') as f:
        content = f.read()
    
    # Use Response with explicit headers for maximum compatibility
    # This approach works reliably for both direct links and JavaScript fetch
    from fastapi.responses import Response
    
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",  # Single Content-Type (no duplicate)
        headers={
            "Content-Disposition": f'attachment; filename="retainwise_sample_{industry}.csv"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@router.get("/column-aliases/{standard_column}")
async def get_column_aliases(standard_column: str):
    """
    Get list of recognized aliases for a standard column.
    
    Helps users understand what column name variations we support.
    
    Args:
        standard_column: Standard column name (e.g., 'customerID', 'tenure')
    
    Returns:
        List of recognized aliases
    
    Example:
        GET /api/csv/column-aliases/customerID
        
        Response:
        {
            "standard_column": "customerID",
            "aliases": [
                "customer_id",
                "user_id",
                "account_id",
                "cust_id",
                ...
            ]
        }
    """
    from backend.ml.column_mapper import ColumnAliases
    
    aliases_dict = ColumnAliases.get_all_aliases()
    
    if standard_column not in aliases_dict:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown standard column: {standard_column}. Available: {', '.join(aliases_dict.keys())}"
        )
    
    return {
        'standard_column': standard_column,
        'aliases': aliases_dict[standard_column],
        'count': len(aliases_dict[standard_column])
    }


@router.get("/supported-columns/{industry}")
async def get_supported_columns(industry: str):
    """
    Get list of supported columns for an industry.
    
    Args:
        industry: 'telecom' or 'saas'
    
    Returns:
        Required and optional columns for the industry
    
    Example:
        GET /api/csv/supported-columns/telecom
        
        Response:
        {
            "industry": "telecom",
            "required": ["customerID", "tenure", "MonthlyCharges", ...],
            "optional": ["gender", "SeniorCitizen", ...]
        }
    """
    try:
        mapper = IntelligentColumnMapper(industry=industry)
        
        return {
            'industry': industry,
            'required': mapper.required_columns,
            'optional': mapper.optional_columns,
            'total': len(mapper.required_columns) + len(mapper.optional_columns)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

