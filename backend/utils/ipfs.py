import ipfshttpclient
from typing import Optional, Tuple, Union
import logging
import tempfile
from pathlib import Path
import aiohttp
import asyncio
from datetime import datetime

class IPFSError(Exception):
    """Base exception for IPFS-related errors"""
    pass

class IPFSHandler:
    def __init__(
        self, 
        ipfs_host: str = '/ip4/127.0.0.1/tcp/5001',
        ipfs_gateway: str = 'https://ipfs.io/ipfs'
    ):
        self.ipfs_host = ipfs_host
        self.ipfs_gateway = ipfs_gateway
        self.client = None
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure logging for IPFS operations"""
        self.logger = logging.getLogger('IPFSHandler')
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    async def connect(self) -> bool:
        """
        Establish connection to IPFS daemon
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if not self.client:
                self.client = ipfshttpclient.connect(self.ipfs_host)
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to IPFS: {e}")
            return False

    async def upload_file(
        self, 
        file_path: Union[str, Path], 
        keep_filename: bool = True
    ) -> Tuple[str, Optional[str]]:
        """
        Upload a file to IPFS
        
        Args:
            file_path: Path to the file
            keep_filename: Whether to preserve original filename in IPFS
            
        Returns:
            Tuple[str, Optional[str]]: (IPFS hash, filename if kept)
        """
        try:
            if not await self.connect():
                raise IPFSError("Failed to connect to IPFS")

            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            result = self.client.add(
                str(file_path),
                pin=True,
                wrap_with_directory=keep_filename
            )

            if keep_filename:
                # Get the hash of the directory
                ipfs_hash = result[-1]['Hash']
                filename = file_path.name
            else:
                ipfs_hash = result['Hash']
                filename = None

            self.logger.info(f"File uploaded to IPFS: {ipfs_hash}")
            return ipfs_hash, filename

        except Exception as e:
            self.logger.error(f"Error uploading to IPFS: {e}")
            raise IPFSError(f"Upload failed: {str(e)}")

    async def upload_bytes(
        self, 
        content: bytes, 
        filename: Optional[str] = None
    ) -> str:
        """
        Upload bytes data to IPFS
        
        Args:
            content: Bytes to upload
            filename: Optional filename to preserve
            
        Returns:
            str: IPFS hash
        """
        try:
            if not await self.connect():
                raise IPFSError("Failed to connect to IPFS")

            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                if filename:
                    ipfs_hash, _ = await self.upload_file(tmp_path, keep_filename=True)
                else:
                    ipfs_hash, _ = await self.upload_file(tmp_path, keep_filename=False)
                
                return ipfs_hash

            finally:
                Path(tmp_path).unlink()

        except Exception as e:
            self.logger.error(f"Error uploading bytes to IPFS: {e}")
            raise IPFSError(f"Upload failed: {str(e)}")

    async def get_file(
        self, 
        ipfs_hash: str,
        timeout: int = 30
    ) -> bytes:
        """
        Retrieve a file from IPFS
        
        Args:
            ipfs_hash: IPFS hash of the file
            timeout: Timeout in seconds
            
        Returns:
            bytes: File content
        """
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.ipfs_gateway}/{ipfs_hash}"
                async with session.get(url, timeout=timeout) as response:
                    if response.status != 200:
                        raise IPFSError(f"Failed to fetch file: HTTP {response.status}")
                    return await response.read()

            except asyncio.TimeoutError:
                raise IPFSError("Timeout while fetching file from IPFS")
            except Exception as e:
                raise IPFSError(f"Error fetching file: {str(e)}")

    async def is_available(self, ipfs_hash: str) -> bool:
        """
        Check if a file is available on IPFS
        
        Args:
            ipfs_hash: IPFS hash to check
            
        Returns:
            bool: True if available, False otherwise
        """
        try:
            await self.get_file(ipfs_hash, timeout=5)
            return True
        except:
            return False

    def close(self) -> None:
        """Close IPFS connection"""
        if self.client:
            try:
                self.client.close()
                self.client = None
            except Exception as e:
                self.logger.error(f"Error closing IPFS connection: {e}")