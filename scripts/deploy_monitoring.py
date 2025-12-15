#!/usr/bin/env python3
"""
Deploy CloudWatch Dashboard and Alarms for RetainWise Production

This script:
1. Deploys CloudWatch dashboard with 11 monitoring widgets
2. Creates CloudWatch alarms for critical metrics
3. Configures SNS topic for alerts

Usage:
    python scripts/deploy_monitoring.py --deploy
    python scripts/deploy_monitoring.py --verify
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.monitoring.cloudwatch_dashboard import (
    deploy_dashboard,
    deploy_alarms,
    print_useful_queries
)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy CloudWatch monitoring')
    parser.add_argument(
        '--deploy',
        action='store_true',
        help='Deploy dashboard and alarms to AWS'
    )
    parser.add_argument(
        '--queries',
        action='store_true',
        help='Print useful CloudWatch Insights queries'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify deployment'
    )
    
    args = parser.parse_args()
    
    if args.deploy:
        print("🚀 Deploying CloudWatch Monitoring...\n")
        
        try:
            # Deploy dashboard
            print("📊 Deploying CloudWatch Dashboard...")
            deploy_dashboard()
            print("✅ Dashboard deployed!\n")
            
            # Deploy alarms
            print("🚨 Deploying CloudWatch Alarms...")
            deploy_alarms()
            print("✅ Alarms deployed!\n")
            
            print("=" * 60)
            print("✅ MONITORING DEPLOYMENT COMPLETE!")
            print("=" * 60)
            print("\n📊 View Dashboard:")
            print("https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=RetainWise-Production")
            print("\n🚨 View Alarms:")
            print("https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#alarmsV2:")
            print("\n💡 Next Steps:")
            print("1. Subscribe to SNS topic 'retainwise-production-alerts' for email/SMS")
            print("2. Test alarms by triggering test conditions")
            print("3. Review dashboard metrics after first predictions")
            
        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            sys.exit(1)
    
    elif args.queries:
        print_useful_queries()
    
    elif args.verify:
        print("🔍 Verifying monitoring deployment...")
        
        import boto3
        
        try:
            cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
            
            # Check dashboard exists
            dashboards = cloudwatch.list_dashboards(
                DashboardNamePrefix='RetainWise-Production'
            )
            
            if dashboards['DashboardEntries']:
                print("✅ Dashboard exists")
            else:
                print("⚠️ Dashboard not found")
            
            # Check alarms exist
            alarms = cloudwatch.describe_alarms(
                AlarmNamePrefix='RetainWise-'
            )
            
            alarm_count = len(alarms['MetricAlarms'])
            print(f"✅ Found {alarm_count} alarms")
            
            if alarm_count >= 3:
                print("✅ Monitoring fully deployed!")
            else:
                print(f"⚠️ Expected 3+ alarms, found {alarm_count}")
                
        except Exception as e:
            print(f"❌ Verification failed: {e}")
            sys.exit(1)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

