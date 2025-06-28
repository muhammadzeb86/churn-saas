import React, { useEffect, useState } from 'react';
import { PowerBIEmbed } from 'powerbi-client-react';
import * as models from 'powerbi-client';
import { Report } from 'powerbi-client';
import axios from 'axios';
import { useUserContext } from '../contexts/UserContext';
import { useAuth } from '@clerk/clerk-react';
import { useToast } from '../components/ui/use-toast';
import { Loader2 } from 'lucide-react';

interface PowerBIConfig {
  embedUrl: string;
  embedToken: string;
  reportId: string;
}

declare global {
  interface Window {
    report: Report;
  }
}

const Dashboard: React.FC = () => {
  const { dbUser } = useUserContext();
  const { getToken } = useAuth();
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [powerBIConfig, setPowerBIConfig] = useState<PowerBIConfig | null>(null);

  useEffect(() => {
    const fetchEmbedToken = async () => {
      try {
        setLoading(true);
        const token = await getToken();
        const response = await axios.get('http://localhost:8000/powerbi/embed-token', {
          headers: {
            Authorization: `Bearer ${token}`
          }
        });
        setPowerBIConfig(response.data);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load Power BI report';
        setError(errorMessage);
        toast({
          variant: "destructive",
          title: "Error",
          description: errorMessage
        });
      } finally {
        setLoading(false);
      }
    };

    if (dbUser) {
      fetchEmbedToken();
    }
  }, [dbUser, getToken]);

  if (loading) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
        <span className="ml-2 text-gray-600">Loading dashboard...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <div className="text-center">
          <h3 className="text-lg font-medium text-gray-900">Failed to load dashboard</h3>
          <p className="mt-2 text-sm text-gray-500">{error}</p>
        </div>
      </div>
    );
  }

  if (!powerBIConfig) {
    return null;
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">RetainWise Analytics Dashboard</h1>
        <p className="mt-2 text-sm text-gray-600">
          View your customer retention metrics and insights
        </p>
      </div>

      <div className="bg-white rounded-xl shadow-soft p-4">
        <PowerBIEmbed
          embedConfig={{
            type: 'report',
            id: powerBIConfig.reportId,
            embedUrl: powerBIConfig.embedUrl,
            accessToken: powerBIConfig.embedToken,
            tokenType: models.TokenType.Embed,
            settings: {
              filterPaneEnabled: false,
              navContentPaneEnabled: true,
              background: models.BackgroundType.Transparent,
            },
          }}
          cssClassName="w-full h-[80vh] rounded-lg"
          getEmbeddedComponent={(embeddedReport: Report) => {
            window.report = embeddedReport;
          }}
        />
      </div>
    </div>
  );
};

export default Dashboard; 