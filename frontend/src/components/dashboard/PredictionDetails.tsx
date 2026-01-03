import React from 'react';
import { AlertCircle, TrendingUp, Calendar, FileText } from 'lucide-react';
import { parseStringArray } from '../../utils/validationUtils';
import type { Prediction } from '../../types';

interface PredictionDetailsProps {
  prediction: Prediction;
}

export const PredictionDetails: React.FC<PredictionDetailsProps> = ({ prediction }) => {
  // ✅ SECURE: Validate and parse factors safely
  const riskFactors = parseStringArray(prediction.risk_factors);
  const protectiveFactors = parseStringArray(prediction.protective_factors);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left Column - Metadata */}
      <div className="space-y-4">
        {/* Prediction ID */}
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-start gap-3">
            <FileText className="w-5 h-5 text-gray-600 dark:text-gray-400 mt-0.5 flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">
                Prediction ID
              </p>
              <p className="text-sm font-mono text-gray-900 dark:text-white mt-1 break-all">
                {prediction.id}
              </p>
            </div>
          </div>
        </div>

        {/* Probabilities with visual bars */}
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-start gap-3">
            <TrendingUp className="w-5 h-5 text-gray-600 dark:text-gray-400 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase mb-3">
                Probabilities
              </p>

              <div className="space-y-3">
                {/* Churn Risk Bar */}
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700 dark:text-gray-300">Churn Risk</span>
                    <span className="font-semibold text-red-600 dark:text-red-400 tabular-nums">
                      {(prediction.churn_probability * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-red-500 to-red-600 transition-all duration-300"
                      style={{ width: `${prediction.churn_probability * 100}%` }}
                    />
                  </div>
                </div>

                {/* Retention Bar */}
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700 dark:text-gray-300">Retention</span>
                    <span className="font-semibold text-green-600 dark:text-green-400 tabular-nums">
                      {(prediction.retention_probability * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-green-500 to-green-600 transition-all duration-300"
                      style={{ width: `${prediction.retention_probability * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Created Date */}
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-start gap-3">
            <Calendar className="w-5 h-5 text-gray-600 dark:text-gray-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-xs font-medium text-gray-600 dark:text-gray-400 uppercase">Created</p>
              <p className="text-sm text-gray-900 dark:text-white mt-1">
                {new Date(prediction.created_at).toLocaleString('en-US', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Right Column - Factors & Explanation */}
      <div className="space-y-4">
        {/* Risk Factors */}
        {riskFactors.length > 0 && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-red-800 dark:text-red-300 mb-2">
                  Risk Factors
                </p>
                <ul className="space-y-1">
                  {riskFactors.map((factor, index) => (
                    <li key={index} className="text-sm text-red-700 dark:text-red-400 flex items-start">
                      <span className="mr-2 flex-shrink-0">•</span>
                      <span className="break-words">{factor}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Protective Factors */}
        {protectiveFactors.length > 0 && (
          <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <TrendingUp className="w-5 h-5 text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-green-800 dark:text-green-300 mb-2">
                  Protective Factors
                </p>
                <ul className="space-y-1">
                  {protectiveFactors.map((factor, index) => (
                    <li
                      key={index}
                      className="text-sm text-green-700 dark:text-green-400 flex items-start"
                    >
                      <span className="mr-2 flex-shrink-0">✓</span>
                      <span className="break-words">{factor}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Explanation/Recommendation */}
        {prediction.explanation && (
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <p className="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-2">
              Recommendation
            </p>
            <p className="text-sm text-blue-700 dark:text-blue-400 leading-relaxed break-words">
              {prediction.explanation}
            </p>
          </div>
        )}

        {/* Empty state */}
        {riskFactors.length === 0 &&
          protectiveFactors.length === 0 &&
          !prediction.explanation && (
            <div className="bg-gray-50 dark:bg-gray-900/50 rounded-lg p-8 text-center border border-gray-200 dark:border-gray-700">
              <p className="text-gray-500 dark:text-gray-400 text-sm">
                No additional details available for this prediction.
              </p>
            </div>
          )}
      </div>
    </div>
  );
};

