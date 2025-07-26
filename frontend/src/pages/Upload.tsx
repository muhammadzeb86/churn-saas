import React, { useState, useRef, useEffect } from 'react';
import { useUser } from '@clerk/clerk-react';
import { Upload as UploadIcon, FileSpreadsheet, AlertCircle, CheckCircle2 } from 'lucide-react';
import { uploadAPI } from '../services/api';

interface UploadResponse {
  id: string;
  filename: string;
  created_at: string;
  status: string;
}

const Upload: React.FC = () => {
  const { user } = useUser();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [previousUploads, setPreviousUploads] = useState<UploadResponse[]>([]);

  useEffect(() => {
    fetchPreviousUploads();
  }, []);

  const fetchPreviousUploads = async () => {
    try {
      const response = await uploadAPI.getUploads();
      setPreviousUploads(response.data);
    } catch (err) {
      console.error('Error fetching previous uploads:', err);
    }
  };

  const validateFile = (file: File): string | null => {
    if (!file.name.endsWith('.csv')) {
      return 'Please upload a CSV file';
    }
    if (file.size > 5 * 1024 * 1024) {
      return 'File size must be less than 5MB';
    }
    return null;
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      const validationError = validateFile(selectedFile);
      if (validationError) {
        setError(validationError);
        setFile(null);
      } else {
        setFile(selectedFile);
        setError(null);
      }
    }
  };

  const handleUpload = async () => {
    if (!file || !user) return;

    setUploading(true);
    setError(null);
    setSuccess(false);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', parseInt(user.id).toString());

    try {
      const response = await uploadAPI.uploadCSV(formData);
      console.log('Upload successful:', response.data);
      
      setSuccess(true);
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      await fetchPreviousUploads();
    } catch (err) {
      console.error('Upload error details:', err);
      setError(err instanceof Error ? err.message : 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="bg-white rounded-xl shadow-soft p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Upload Dataset</h2>
        
        <div className="space-y-4">
          <div className="border-2 border-dashed border-gray-200 rounded-lg p-6">
            <div className="flex flex-col items-center justify-center space-y-4">
              <UploadIcon className="h-12 w-12 text-gray-400" />
              <div className="text-center">
                <p className="text-sm text-gray-600">
                  Upload your customer dataset for retention analysis (CSV only, max 5MB)
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  The file should contain customer data with relevant retention indicators
                </p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-600 hover:file:bg-primary-100"
              />
            </div>
          </div>

          {error && (
            <div className="flex items-center space-x-2 text-red-600 bg-red-50 p-3 rounded-lg">
              <AlertCircle size={16} />
              <span className="text-sm">{error}</span>
            </div>
          )}

          {success && (
            <div className="flex items-center space-x-2 text-green-600 bg-green-50 p-3 rounded-lg">
              <CheckCircle2 size={16} />
              <span className="text-sm">Upload successful! View predictions when ready.</span>
            </div>
          )}

          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className={`w-full py-2 px-4 rounded-lg font-medium ${
              !file || uploading
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                : 'bg-primary-600 text-white hover:bg-primary-700'
            }`}
          >
            {uploading ? 'Uploading...' : 'Upload Dataset'}
          </button>
        </div>
      </div>

      {previousUploads.length > 0 && (
        <div className="bg-white rounded-xl shadow-soft p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Previous Uploads</h3>
          <div className="space-y-4">
            {previousUploads.map((upload) => (
              <div
                key={upload.id}
                className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center space-x-3">
                  <FileSpreadsheet className="text-gray-400" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{upload.filename}</p>
                    <p className="text-xs text-gray-500">
                      {new Date(upload.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <span
                  className={`text-xs px-2 py-1 rounded-full ${
                    upload.status === 'completed'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-yellow-100 text-yellow-700'
                  }`}
                >
                  {upload.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Upload; 