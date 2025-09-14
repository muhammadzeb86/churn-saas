import React, { useState, useEffect, useRef } from 'react';
import { useUser } from '@clerk/clerk-react';
import { useNavigate, Link } from 'react-router-dom';
import { Download, FileSpreadsheet, AlertCircle, ChevronRight, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { predictionsAPI } from '../services/api';
import { useToast } from '../components/ui/use-toast';

interface PredictionListItem {
  id: string;
  upload_id: number;
  status: string;
  rows_processed: number;
  created_at: string;
  has_output: boolean;
}

interface PredictionListResponse {
  success: boolean;
  predictions: PredictionListItem[];
  count: number;
}

const Predictions: React.FC = () => {
  const { user } = useUser();
  const { toast } = useToast();
  const [predictions, setPredictions] = useState<PredictionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (user?.id) {
      fetchPredictions();
    }
  }, [user?.id]);

  // Start polling when component mounts if we have recent predictions
  useEffect(() => {
    if (predictions.length > 0) {
      const hasActiveJobs = predictions.some(p => 
        p.status === 'QUEUED' || p.status === 'RUNNING'
      );
      
      if (hasActiveJobs && !polling) {
        startPolling();
      }
    }
    
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [predictions, polling]);

  const fetchPredictions = async () => {
    if (!user?.id) return;
    
    try {
      setError(null);
      const response = await predictionsAPI.getPredictions(user.id);
      const data: PredictionListResponse = response.data;
      
      if (data.success) {
        setPredictions(data.predictions);
      } else {
        setError('Failed to load predictions');
      }
    } catch (err) {
      setError('Failed to load predictions. Please try again later.');
      console.error('Error fetching predictions:', err);
    } finally {
      setLoading(false);
    }
  };

  const startPolling = () => {
    if (polling || !user?.id) return;
    
    setPolling(true);
    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await predictionsAPI.getPredictions(user.id);
        const data: PredictionListResponse = response.data;
        
        if (data.success) {
          const oldPredictions = predictions;
          const newPredictions = data.predictions;
          
          // Check for status changes
          newPredictions.forEach(newPred => {
            const oldPred = oldPredictions.find(p => p.id === newPred.id);
            if (oldPred && oldPred.status !== newPred.status) {
              if (newPred.status === 'COMPLETED') {
                toast({
                  title: 'Prediction Complete!',
                  description: `Prediction for upload ${newPred.upload_id} has finished successfully.`,
                });
              } else if (newPred.status === 'FAILED') {
                toast({
                  variant: 'destructive',
                  title: 'Prediction Failed',
                  description: `Prediction for upload ${newPred.upload_id} has failed.`,
                });
              }
            }
          });
          
          setPredictions(newPredictions);
          
          // Stop polling if no active jobs
          const hasActiveJobs = newPredictions.some(p => 
            p.status === 'QUEUED' || p.status === 'RUNNING'
          );
          
          if (!hasActiveJobs) {
            stopPolling();
          }
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 3000); // Poll every 3 seconds
  };

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    setPolling(false);
  };

  const handleDownload = async (predictionId: string) => {
    if (!user?.id) return;
    
    try {
      setDownloading(predictionId);
      const response = await predictionsAPI.downloadPrediction(predictionId, user.id);
      
      // Handle redirect URL response
      if (response.data.success && response.data.download_url) {
        // Create a temporary link to trigger download
        const link = document.createElement('a');
        link.href = response.data.download_url;
        link.download = `prediction_results_${predictionId}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        toast({
          title: 'Download Started',
          description: 'Your prediction results are being downloaded.',
        });
      }
    } catch (err: any) {
      console.error('Error downloading predictions:', err);
      toast({
        variant: 'destructive',
        title: 'Download Failed',
        description: err.response?.data?.detail || 'Failed to download prediction results.',
      });
    } finally {
      setDownloading(null);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'FAILED':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'RUNNING':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'QUEUED':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusChip = (status: string) => {
    const baseClasses = "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium";
    
    switch (status) {
      case 'COMPLETED':
        return `${baseClasses} bg-green-100 text-green-800`;
      case 'FAILED':
        return `${baseClasses} bg-red-100 text-red-800`;
      case 'RUNNING':
        return `${baseClasses} bg-blue-100 text-blue-800`;
      case 'QUEUED':
        return `${baseClasses} bg-yellow-100 text-yellow-800`;
      default:
        return `${baseClasses} bg-gray-100 text-gray-800`;
    }
  };

  if (loading) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-8 w-8 text-red-500 mx-auto mb-4" />
          <p className="text-gray-600">{error}</p>
          <button
            onClick={fetchPredictions}
            className="mt-4 text-primary-600 hover:text-primary-700 font-medium"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (predictions.length === 0) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <div className="text-center">
          <FileSpreadsheet className="h-8 w-8 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">No predictions yet.</p>
          <p className="text-sm text-gray-500 mt-2">
            Upload a dataset to see predictions here.
          </p>
          <Link 
            to="/upload"
            className="mt-4 inline-flex items-center text-primary-600 hover:text-primary-700 font-medium"
          >
            Go to Upload
            <ChevronRight className="h-4 w-4 ml-1" />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-xl font-semibold text-gray-900">ML Predictions</h1>
          <p className="mt-2 text-sm text-gray-700">
            View and download machine learning prediction results
          </p>
        </div>
        {polling && (
          <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
            <div className="inline-flex items-center text-sm text-blue-600">
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Checking for updates...
            </div>
          </div>
        )}
      </div>

      <div className="bg-white shadow-soft rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Rows Processed
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Upload ID
                </th>
                <th scope="col" className="relative px-6 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {predictions.map((prediction) => (
                <tr key={prediction.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(prediction.created_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center space-x-2">
                      {getStatusIcon(prediction.status)}
                      <span className={getStatusChip(prediction.status)}>
                        {prediction.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {prediction.rows_processed.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    #{prediction.upload_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex items-center justify-end space-x-4">
                      {prediction.status === 'COMPLETED' && prediction.has_output && (
                        <button
                          onClick={() => handleDownload(prediction.id)}
                          disabled={downloading === prediction.id}
                          className="text-primary-600 hover:text-primary-900 flex items-center"
                        >
                          {downloading === prediction.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <>
                              <Download className="h-4 w-4 mr-1" />
                              Download CSV
                            </>
                          )}
                        </button>
                      )}
                      {prediction.status === 'FAILED' && (
                        <button className="text-red-600 hover:text-red-900 text-sm">
                          View Error
                        </button>
                      )}
                      {(prediction.status === 'QUEUED' || prediction.status === 'RUNNING') && (
                        <div className="flex items-center text-gray-500">
                          <Loader2 className="h-4 w-4 animate-spin mr-1" />
                          <span className="text-sm">Processing...</span>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Predictions; 