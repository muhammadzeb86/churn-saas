with open('.env', 'w', encoding='utf-8') as f:
    f.write('DATABASE_URL=postgresql+asyncpg://retainwiseuser:RetainWise2024@retainwise-db.co9icy24a1d9.us-east-1.rds.amazonaws.com:5432/retainwisedb\n')
    f.write('POWERBI_WORKSPACE_ID=cb604b66-17ab-4831-b8b9-2e718c5cf3f5\n')
    f.write('POWERBI_REPORT_ID=cda60607-7c02-47c5-a552-2b7c08a0d89c\n') 
