import React, { useState, useEffect } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { Download, FileSpreadsheet, AlertCircle, ChevronRight } from 'lucide-react';

interface PredictionSummary {
  id: string;
  filename: string;
  upload_time: string;
  churned_count: number;
  total_rows: number;
  at_risk_percentage: number;
  status: 'completed' | 'processing' | 'failed';
}

const Predictions: React.FC = () => {
  const { getToken } = useAuth();
  const [predictions, setPredictions] = useState<PredictionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    fetchPredictions();
  }, []);

  const fetchPredictions = async () => {
    try {
      setLoading(true);
      setError(null);
      const token = await getToken();
      const response = await fetch('http://localhost:8000/predictions', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch predictions');
      }

      const data = await response.json();
      setPredictions(data);
    } catch (err) {
      setError('Failed to load predictions. Please try again later.');
      console.error('Error fetching predictions:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (id: string) => {
    try {
      setDownloading(id);
      const token = await getToken();
      const response = await fetch(`http://localhost:8000/download_predictions/${id}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to download predictions');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `predictions_${id}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Error downloading predictions:', err);
    } finally {
      setDownloading(null);
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
          <p className="text-gray-600">No predictions available yet.</p>
          <p className="text-sm text-gray-500 mt-2">
            Upload a dataset to see predictions here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="sm:flex sm:items-center">
        <div className="sm:flex-auto">
          <h1 className="text-xl font-semibold text-gray-900">Customer Retention Predictions</h1>
          <p className="mt-2 text-sm text-gray-700">
            View and download retention predictions for your uploaded datasets
          </p>
        </div>
      </div>

      <div className="bg-white shadow-soft rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  File
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Upload Time
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  At Risk
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Risk %
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th scope="col" className="relative px-6 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {predictions.map((prediction) => (
                <tr key={prediction.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <FileSpreadsheet className="h-5 w-5 text-gray-400 mr-3" />
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {prediction.filename}
                        </div>
                        <div className="text-sm text-gray-500">
                          {prediction.total_rows.toLocaleString()} rows
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(prediction.upload_time).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">
                      {prediction.churned_count.toLocaleString()}
                    </div>
                    <div className="text-sm text-gray-500">
                      {((prediction.churned_count / prediction.total_rows) * 100).toFixed(1)}%
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">
                      {prediction.at_risk_percentage.toFixed(1)}%
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      prediction.status === 'completed'
                        ? 'bg-green-100 text-green-800'
                        : prediction.status === 'processing'
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {prediction.status.charAt(0).toUpperCase() + prediction.status.slice(1)}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    {prediction.status === 'completed' && (
                      <div className="flex items-center justify-end space-x-4">
                        <button
                          onClick={() => handleDownload(prediction.id)}
                          disabled={downloading === prediction.id}
                          className="text-primary-600 hover:text-primary-900 flex items-center"
                        >
                          {downloading === prediction.id ? (
                            <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-primary-600"></div>
                          ) : (
                            <>
                              <Download className="h-4 w-4 mr-1" />
                              Download
                            </>
                          )}
                        </button>
                        <button className="text-gray-400 hover:text-gray-500">
                          <ChevronRight className="h-5 w-5" />
                        </button>
                      </div>
                    )}
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