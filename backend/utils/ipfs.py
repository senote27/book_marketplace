# backend/utils/ipfs.py
import ipfshttpclient
import aiofiles
import os
from fastapi import UploadFile, HTTPException
from typing import Optional
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class IPFSManager:
    def __init__(self):
        self.client = None
        self.connect()
        self.allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
        self.max_file_size = 50 * 1024 * 1024  # 50MB

    def connect(self):
        """Establish connection to local IPFS daemon"""
        try:
            self.client = ipfshttpclient.connect('/ip4/127.0.0.1/tcp/5001')
        except Exception as e:
            logger.error(f"Failed to connect to IPFS: {str(e)}")
            raise HTTPException(status_code=500, detail="IPFS connection failed")

    def validate_file(self, file: UploadFile) -> None:
        """Validate file extension and size"""
        # Check extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in self.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {self.allowed_extensions}"
            )

    async def add_file(self, file: UploadFile) -> str:
        """Add file to IPFS and return hash"""
        try:
            self.validate_file(file)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                
                # Write uploaded file to temporary file
                async with aiofiles.open(temp_path, 'wb') as out_file:
                    content = await file.read()
                    if len(content) > self.max_file_size:
                        raise HTTPException(
                            status_code=400,
                            detail=f"File size exceeds maximum limit of {self.max_file_size/1024/1024}MB"
                        )
                    await out_file.write(content)

                # Add to IPFS
                ipfs_response = self.client.add(temp_path)
                ipfs_hash = ipfs_response['Hash']

                # Clean up
                os.unlink(temp_path)
                
                return ipfs_hash

        except Exception as e:
            logger.error(f"IPFS upload failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to upload to IPFS: {str(e)}")

    async def get_file(self, ipfs_hash: str) -> Optional[bytes]:
        """Retrieve file from IPFS by hash"""
        try:
            return self.client.cat(ipfs_hash)
        except Exception as e:
            logger.error(f"IPFS retrieval failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to retrieve from IPFS: {str(e)}")

    def get_ipfs_url(self, ipfs_hash: str) -> str:
        """Generate IPFS gateway URL for hash"""
        return f"http://localhost:8080/ipfs/{ipfs_hash}"

    async def pin_file(self, ipfs_hash: str) -> None:
        """Pin file to ensure persistence"""
        try:
            self.client.pin.add(ipfs_hash)
        except Exception as e:
            logger.error(f"IPFS pinning failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to pin file: {str(e)}")

    def __del__(self):
        """Cleanup IPFS client connection"""
        if self.client:
            try:
                self.client.close()
            except:
                pass