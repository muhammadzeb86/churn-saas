declare module 'powerbi-client' {
  export enum TokenType {
    Aad = 0,
    Embed = 1
  }

  export enum BackgroundType {
    Default = 0,
    Transparent = 1
  }

  export interface Report {
    reload(): Promise<void>;
    getPages(): Promise<Page[]>;
    setPage(pageName: string): Promise<void>;
    getCurrentPage(): Promise<Page>;
  }

  export interface Page {
    name: string;
    displayName: string;
    isActive: boolean;
  }

  export interface IEmbedConfiguration {
    type: string;
    id?: string;
    embedUrl: string;
    accessToken: string;
    tokenType: TokenType;
    settings?: {
      filterPaneEnabled?: boolean;
      navContentPaneEnabled?: boolean;
      background?: BackgroundType;
    };
  }
}

declare module 'powerbi-client-react' {
  import { IEmbedConfiguration, Report } from 'powerbi-client';
  import { Component } from 'react';

  export interface PowerBIEmbedProps {
    embedConfig: IEmbedConfiguration;
    cssClassName?: string;
    getEmbeddedComponent?: (embeddedReport: Report) => void;
  }

  export class PowerBIEmbed extends Component<PowerBIEmbedProps> {}
} 