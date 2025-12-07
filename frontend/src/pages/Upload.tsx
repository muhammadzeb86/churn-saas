import React, { useState, useRef, useEffect } from 'react';
import { useUser } from '@clerk/clerk-react';
import { useNavigate } from 'react-router-dom';
import { Upload as UploadIcon, FileSpreadsheet, AlertCircle, CheckCircle2, Download } from 'lucide-react';
import { uploadAPI } from '../services/api';
import { useToast } from '../components/ui/use-toast';

interface UploadResponse {
  success: boolean;
  message: string;
  upload_id?: number;
  object_key?: string;
  filename?: string;
  file_size?: number;
  prediction_id?: string;
  prediction_status?: string;
  publish_warning?: boolean;
}

const Upload: React.FC = () => {
  const { user } = useUser();
  const navigate = useNavigate();
  const { toast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [uploadResponse, setUploadResponse] = useState<UploadResponse | null>(null);
  const [previousUploads, setPreviousUploads] = useState<any[]>([]);

  useEffect(() => {
    fetchPreviousUploads();
  }, []);

  const fetchPreviousUploads = async () => {
    try {
      if (!user?.id) return;
      const response = await uploadAPI.getUploads(user.id);
      setPreviousUploads(response.data);
    } catch (err) {
      console.error('Error fetching previous uploads:', err);
    }
  };

  const validateFile = (file: File): string | null => {
    if (!file.name.endsWith('.csv')) {
      return 'Please upload a CSV file';
    }
    if (file.size > 10 * 1024 * 1024) { // 10MB limit to match backend
      return 'File size must be less than 10MB';
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
    setUploadProgress(0);
    setError(null);
    setSuccess(false);
    setUploadResponse(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', user.id);

    try {
      const response = await uploadAPI.uploadCSV(formData, (progress) => {
        setUploadProgress(progress);
        console.log(`Upload progress: ${progress}%`);
      });
      console.log('Upload successful:', response.data);
      
      setSuccess(true);
      setUploadResponse(response.data);
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      await fetchPreviousUploads();
      
      // Navigate to predictions page and show toast
      setTimeout(() => {
        navigate('/predictions');
        if (response.data.prediction_id) {
          toast({
            title: 'Upload Successful!',
            description: `File uploaded and prediction started. Prediction ID: ${response.data.prediction_id}`,
          });
        }
      }, 1500); // Small delay to show success state
    } catch (err: any) {
      console.error('Upload error details:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Upload failed. Please try again.';
      setError(errorMessage);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const downloadSampleCSV = async (industry: 'telecom' | 'saas') => {
    try {
      const apiUrl = process.env.REACT_APP_API_URL || '';
      const url = `${apiUrl}/api/csv/sample-csv/${industry}`;
      
      // Fetch the file with proper headers
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Accept': 'text/csv',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to download: ${response.statusText}`);
      }

      // Get the blob from response
      const blob = await response.blob();
      
      // Create a blob URL and trigger download
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = `retainwise_sample_${industry}.csv`;
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
      
      toast({
        title: 'Download Started',
        description: `Sample ${industry} CSV is downloading...`,
      });
    } catch (err: any) {
      console.error('Download error:', err);
      toast({
        title: 'Download Failed',
        description: err.message || 'Failed to download sample CSV. Please try again.',
        variant: 'destructive',
      });
    }
  };

  const clerkId = user?.id;
  const isDisabled = !file || uploading || !clerkId;

  return (
    <div className="space-y-8">
      <div className="bg-white rounded-xl shadow-soft p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Upload Dataset</h2>
        
        {!clerkId && (
          <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <div className="flex items-center space-x-2 text-yellow-700">
              <AlertCircle size={16} />
              <span className="text-sm">Please sign in to upload files.</span>
            </div>
          </div>
        )}
        
        <div className="space-y-4">
          <div className="border-2 border-dashed border-gray-200 rounded-lg p-6">
            <div className="flex flex-col items-center justify-center space-y-4">
              <UploadIcon className="h-12 w-12 text-gray-400" />
              <div className="text-center">
                <p className="text-sm text-gray-600">
                  Upload your customer dataset for retention analysis (CSV only, max 10MB)
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  The file should contain customer data with relevant retention indicators
                </p>
                {clerkId && (
                  <p className="text-xs text-blue-600 mt-1">
                    User ID: {clerkId}
                  </p>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                disabled={!clerkId}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-600 hover:file:bg-primary-100 disabled:opacity-50"
              />
            </div>
          </div>

          {uploading && uploadProgress > 0 && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm text-gray-600">
                <span>Uploading...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div 
                  className="bg-primary-600 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center space-x-2 text-red-600 bg-red-50 p-3 rounded-lg">
              <AlertCircle size={16} />
              <span className="text-sm">{error}</span>
            </div>
          )}

          {success && uploadResponse && (
            <div className="flex items-center space-x-2 text-green-600 bg-green-50 p-3 rounded-lg">
              <CheckCircle2 size={16} />
              <div className="text-sm">
                <p>Upload successful!</p>
                <p className="text-xs text-green-700 mt-1">
                  Upload ID: {uploadResponse.upload_id} | File: {uploadResponse.filename} | Size: {uploadResponse.file_size} bytes
                </p>
              </div>
            </div>
          )}

          <button
            onClick={handleUpload}
            disabled={isDisabled}
            className="w-full py-2 px-4 rounded-lg font-medium bg-primary-600 text-white hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {!clerkId 
              ? 'Please sign in' 
              : uploading 
                ? 'Uploading...' 
                : 'Upload Dataset'
            }
          </button>
        </div>
      </div>

      {/* NEW: Sample CSV Download Section */}
      <div className="bg-white rounded-xl shadow-soft p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">New to RetainWise?</h3>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start space-x-3">
            <FileSpreadsheet className="text-blue-600 flex-shrink-0 mt-0.5" size={20} />
            <div className="flex-1">
              <h4 className="text-sm font-medium text-blue-900 mb-2">
                Start with a sample CSV
              </h4>
              <p className="text-xs text-blue-700 mb-3">
                Download a sample dataset to understand the format and test predictions instantly.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => downloadSampleCSV('telecom')}
                  className="inline-flex items-center space-x-2 px-4 py-2 text-sm font-medium text-blue-700 bg-white border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors"
                >
                  <Download size={16} />
                  <span>Telecom Sample</span>
                </button>
                <button
                  onClick={() => downloadSampleCSV('saas')}
                  className="inline-flex items-center space-x-2 px-4 py-2 text-sm font-medium text-blue-700 bg-white border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors"
                >
                  <Download size={16} />
                  <span>SaaS Sample</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* NEW: Column Name Flexibility Info */}
      <div className="bg-white rounded-xl shadow-soft p-6">
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-start space-x-3">
            <CheckCircle2 className="text-green-600 flex-shrink-0 mt-0.5" size={20} />
            <div className="flex-1">
              <h4 className="text-sm font-medium text-green-900 mb-2">
                No need to match exact column names!
              </h4>
              <p className="text-xs text-green-700 mb-2">
                Our intelligent mapper recognizes 200+ column name variations. Just upload your CSV as-is.
              </p>
              <div className="text-xs text-green-600 space-y-1">
                <p><strong>We recognize:</strong></p>
                <p>• <code className="bg-green-100 px-1 rounded">customer_id</code>, <code className="bg-green-100 px-1 rounded">user_id</code>, <code className="bg-green-100 px-1 rounded">Customer ID</code> → customerID</p>
                <p>• <code className="bg-green-100 px-1 rounded">mrr</code>, <code className="bg-green-100 px-1 rounded">monthly_fee</code>, <code className="bg-green-100 px-1 rounded">Monthly Charges</code> → MonthlyCharges</p>
                <p>• <code className="bg-green-100 px-1 rounded">ltv</code>, <code className="bg-green-100 px-1 rounded">lifetime_value</code>, <code className="bg-green-100 px-1 rounded">Total Charges</code> → TotalCharges</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {previousUploads.length > 0 && (
        <div className="bg-white rounded-xl shadow-soft p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Previous Uploads</h3>
          <div className="space-y-4">
            {previousUploads.map((upload, index) => (
              <div
                key={upload.id || index}
                className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center space-x-3">
                  <FileSpreadsheet className="text-gray-400" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{upload.filename}</p>
                    <p className="text-xs text-gray-500">
                      {upload.created_at ? new Date(upload.created_at).toLocaleDateString() : 'Unknown date'}
                    </p>
                  </div>
                </div>
                <span
                  className="text-xs px-2 py-1 rounded-full bg-green-100 text-green-800"
                >
                  {upload.status || 'uploaded'}
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
