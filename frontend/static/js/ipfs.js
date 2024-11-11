// ipfs.js
const IPFSHandler = {
    // Function to upload file to IPFS Desktop
    async uploadFile(file) {
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/ipfs/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Upload failed');
            }

            const data = await response.json();
            return data.hash; // Returns IPFS hash
        } catch (error) {
            console.error('IPFS upload error:', error);
            throw error;
        }
    },

    // Function to get file from IPFS
    async getFile(hash) {
        try {
            const response = await fetch(`/api/ipfs/get/${hash}`);
            if (!response.ok) {
                throw new Error('Failed to fetch file');
            }
            return response;
        } catch (error) {
            console.error('IPFS fetch error:', error);
            throw error;
        }
    }
};

// File upload handling
document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const fileInput = document.querySelector('input[type="file"]');
            const file = fileInput.files[0];
            
            try {
                const hash = await IPFSHandler.uploadFile(file);
                alert(`File uploaded successfully! IPFS Hash: ${hash}`);
            } catch (error) {
                alert('Upload failed: ' + error.message);
            }
        });
    }
});