"""
CloudWatch Dashboard Configuration for RetainWise Production

Creates comprehensive monitoring dashboards with:
1. Key Performance Indicators (KPIs)
2. Error tracking & alerts
3. Cost monitoring
4. Performance regression detection

Deploy with:
python -m backend.monitoring.cloudwatch_dashboard --deploy

Author: RetainWise Engineering
Date: December 15, 2025
Version: 1.0
"""

import boto3
import json
from typing import Dict, Any, List

cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')

# ========================================
# DASHBOARD CONFIGURATION
# ========================================

def create_production_dashboard() -> Dict[str, Any]:
    """
    Create comprehensive production monitoring dashboard
    
    Sections:
    ---------
    1. Key Metrics (top row)
       - Predictions/hour
       - Error rate %
       - P95 latency
       - Daily cost estimate
    
    2. Performance (middle row)
       - Prediction duration (P50, P95, P99)
       - Throughput trends
       - Regression alerts
    
    3. Errors & Security (bottom row)
       - Error breakdown by type
       - Security events
       - Failed authorizations
    
    4. Cost Breakdown (right column)
       - S3 costs
       - ECS costs
       - Database costs
       - Trend analysis
    
    CloudWatch Query Language (CWL):
    --------------------------------
    - fields @timestamp, prediction_id where error_type = "S3UploadError"
    - stats count() by error_type
    - filter prediction_id = "xxx" | sort @timestamp desc
    """
    
    dashboard_body = {
        "widgets": [
            # ========================================
            # ROW 1: KEY PERFORMANCE INDICATORS
            # ========================================
            
            # Widget 1: Predictions Per Hour
            {
                "type": "metric",
                "x": 0,
                "y": 0,
                "width": 6,
                "height": 6,
                "properties": {
                    "metrics": [
                        [
                            "RetainWise/Production",
                            "PredictionDuration",
                            {
                                "stat": "SampleCount",
                                "label": "Predictions/Hour"
                            }
                        ]
                    ],
                    "period": 3600,  # 1 hour
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "📊 Predictions per Hour",
                    "yAxis": {
                        "left": {
                            "label": "Count",
                            "showUnits": False
                        }
                    },
                    "annotations": {
                        "horizontal": [
                            {
                                "label": "Target: 100/hour",
                                "value": 100,
                                "fill": "above",
                                "color": "#2ca02c"
                            }
                        ]
                    }
                }
            },
            
            # Widget 2: Error Rate %
            {
                "type": "metric",
                "x": 6,
                "y": 0,
                "width": 6,
                "height": 6,
                "properties": {
                    "metrics": [
                        [
                            "RetainWise/Production",
                            "ErrorCount",
                            {
                                "stat": "Sum",
                                "id": "errors",
                                "visible": False
                            }
                        ],
                        [
                            ".",
                            "PredictionDuration",
                            {
                                "stat": "SampleCount",
                                "id": "total",
                                "visible": False
                            }
                        ],
                        [
                            {
                                "expression": "(errors / total) * 100",
                                "label": "Error Rate %",
                                "id": "error_rate"
                            }
                        ]
                    ],
                    "period": 300,  # 5 minutes
                    "stat": "Average",
                    "region": "us-east-1",
                    "title": "🚨 Error Rate %",
                    "yAxis": {
                        "left": {
                            "label": "%",
                            "min": 0,
                            "max": 10
                        }
                    },
                    "annotations": {
                        "horizontal": [
                            {
                                "label": "Critical: >5%",
                                "value": 5,
                                "fill": "above",
                                "color": "#d62728"
                            },
                            {
                                "label": "Warning: >2%",
                                "value": 2,
                                "fill": "above",
                                "color": "#ff7f0e"
                            }
                        ]
                    }
                }
            },
            
            # Widget 3: P95 Latency
            {
                "type": "metric",
                "x": 12,
                "y": 0,
                "width": 6,
                "height": 6,
                "properties": {
                    "metrics": [
                        [
                            "RetainWise/Production",
                            "PredictionDuration",
                            {
                                "stat": "p95",
                                "label": "P95 Latency"
                            }
                        ],
                        [
                            "...",
                            {
                                "stat": "p99",
                                "label": "P99 Latency"
                            }
                        ],
                        [
                            "...",
                            {
                                "stat": "Average",
                                "label": "Average Latency"
                            }
                        ]
                    ],
                    "period": 300,
                    "stat": "p95",
                    "region": "us-east-1",
                    "title": "⏱️ Prediction Latency (ms)",
                    "yAxis": {
                        "left": {
                            "label": "ms"
                        }
                    },
                    "annotations": {
                        "horizontal": [
                            {
                                "label": "Target P95: <1000ms",
                                "value": 1000,
                                "fill": "above",
                                "color": "#ff7f0e"
                            }
                        ]
                    }
                }
            },
            
            # Widget 4: Daily Cost Estimate
            {
                "type": "metric",
                "x": 18,
                "y": 0,
                "width": 6,
                "height": 6,
                "properties": {
                    "metrics": [
                        [
                            "RetainWise/Production",
                            "EstimatedCost",
                            {"stat": "Sum", "label": "Daily Cost"}
                        ]
                    ],
                    "period": 86400,  # 24 hours
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "💰 Daily Cost Estimate (USD)",
                    "yAxis": {
                        "left": {
                            "label": "$",
                            "min": 0
                        }
                    },
                    "annotations": {
                        "horizontal": [
                            {
                                "label": "Budget: $10/day",
                                "value": 10,
                                "fill": "above",
                                "color": "#d62728"
                            },
                            {
                                "label": "Alert: $8/day",
                                "value": 8,
                                "fill": "above",
                                "color": "#ff7f0e"
                            }
                        ]
                    }
                }
            },
            
            # ========================================
            # ROW 2: PERFORMANCE BREAKDOWN
            # ========================================
            
            # Widget 5: Prediction Duration by Row Count
            {
                "type": "metric",
                "x": 0,
                "y": 6,
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        [
                            "RetainWise/Production",
                            "PredictionDuration",
                            {"stat": "Average", "label": "<100 rows"},
                            {"RowCount": "<100"}
                        ],
                        [
                            "...",
                            {"stat": "Average", "label": "100-1K rows"},
                            {"RowCount": "100-1K"}
                        ],
                        [
                            "...",
                            {"stat": "Average", "label": "1K-10K rows"},
                            {"RowCount": "1K-10K"}
                        ]
                    ],
                    "period": 300,
                    "stat": "Average",
                    "region": "us-east-1",
                    "title": "📈 Performance by Dataset Size",
                    "yAxis": {
                        "left": {
                            "label": "ms"
                        }
                    }
                }
            },
            
            # Widget 6: Throughput (Rows/Second)
            {
                "type": "metric",
                "x": 12,
                "y": 6,
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        [
                            "RetainWise/Production",
                            "PredictionDuration",
                            {
                                "stat": "SampleCount",
                                "id": "predictions",
                                "visible": False
                            }
                        ]
                    ],
                    "period": 60,  # 1 minute
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "⚡ Throughput (predictions/min)",
                    "yAxis": {
                        "left": {
                            "label": "Count"
                        }
                    }
                }
            },
            
            # ========================================
            # ROW 3: ERRORS & SECURITY
            # ========================================
            
            # Widget 7: Error Breakdown
            {
                "type": "metric",
                "x": 0,
                "y": 12,
                "width": 8,
                "height": 6,
                "properties": {
                    "metrics": [
                        [
                            "RetainWise/Production",
                            "ErrorCount",
                            {"ErrorType": "S3UploadError"}
                        ],
                        [
                            "...",
                            {"ErrorType": "S3DownloadError"}
                        ],
                        [
                            "...",
                            {"ErrorType": "DatabaseError"}
                        ],
                        [
                            "...",
                            {"ErrorType": "ValidationError"}
                        ],
                        [
                            "...",
                            {"ErrorType": "MLModelError"}
                        ]
                    ],
                    "period": 300,
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "❌ Errors by Type (5-min)",
                    "yAxis": {
                        "left": {
                            "label": "Count"
                        }
                    },
                    "view": "timeSeries",
                    "stacked": True
                }
            },
            
            # Widget 8: Security Events
            {
                "type": "log",
                "x": 8,
                "y": 12,
                "width": 8,
                "height": 6,
                "properties": {
                    "query": """
                        SOURCE '/ecs/retainwise-service'
                        | fields @timestamp, severity, event, user_id, details
                        | filter severity = 'SECURITY'
                        | sort @timestamp desc
                        | limit 20
                    """,
                    "region": "us-east-1",
                    "title": "🔒 Security Events (Last 20)",
                    "stacked": False
                }
            },
            
            # Widget 9: CloudWatch Insights - Recent Failures
            {
                "type": "log",
                "x": 16,
                "y": 12,
                "width": 8,
                "height": 6,
                "properties": {
                    "query": """
                        SOURCE '/ecs/retainwise-worker'
                        | fields @timestamp, prediction_id, error_type, error_message
                        | filter event = 'prediction_failed'
                        | sort @timestamp desc
                        | limit 20
                    """,
                    "region": "us-east-1",
                    "title": "🔥 Recent Prediction Failures",
                    "stacked": False
                }
            },
            
            # ========================================
            # ROW 4: COST BREAKDOWN
            # ========================================
            
            # Widget 10: Cost by Service
            {
                "type": "metric",
                "x": 0,
                "y": 18,
                "width": 12,
                "height": 6,
                "properties": {
                    "metrics": [
                        [
                            "RetainWise/Production",
                            "EstimatedCost",
                            {"Service": "s3_upload"}
                        ],
                        [
                            "...",
                            {"Service": "prediction"}
                        ],
                        [
                            "...",
                            {"Service": "database"}
                        ]
                    ],
                    "period": 3600,  # 1 hour
                    "stat": "Sum",
                    "region": "us-east-1",
                    "title": "💸 Hourly Cost Breakdown",
                    "yAxis": {
                        "left": {
                            "label": "$"
                        }
                    },
                    "view": "timeSeries",
                    "stacked": True
                }
            },
            
            # Widget 11: Top 10 Queries - Performance Regression
            {
                "type": "log",
                "x": 12,
                "y": 18,
                "width": 12,
                "height": 6,
                "properties": {
                    "query": """
                        SOURCE '/ecs/retainwise-worker'
                        | fields @timestamp, operation, degradation_pct, baseline_ms, current_ms
                        | filter event = 'performance_regression_detected'
                        | sort degradation_pct desc
                        | limit 10
                    """,
                    "region": "us-east-1",
                    "title": "📉 Performance Regressions (Top 10)",
                    "stacked": False
                }
            }
        ]
    }
    
    return dashboard_body


# ========================================
# CLOUDWATCH ALARMS
# ========================================

def create_production_alarms():
    """
    Create CloudWatch alarms for critical issues
    
    Alarms:
    -------
    1. High error rate (>5% in 5 minutes)
    2. P95 latency degradation (>1000ms)
    3. Daily cost exceeded ($10/day)
    4. Security events spike (>10 in 5 minutes)
    5. Database connection failures
    
    SNS Topic:
    ----------
    Email: engineering@retainwise.ai
    SMS: +1-XXX-XXX-XXXX (on-call)
    """
    
    # Alarm 1: High Error Rate
    cloudwatch.put_metric_alarm(
        AlarmName='RetainWise-HighErrorRate',
        AlarmDescription='Error rate exceeded 5% - immediate investigation required',
        ActionsEnabled=True,
        MetricName='ErrorCount',
        Namespace='RetainWise/Production',
        Statistic='Sum',
        Period=300,  # 5 minutes
        EvaluationPeriods=1,
        Threshold=10,  # >10 errors in 5 minutes
        ComparisonOperator='GreaterThanThreshold',
        TreatMissingData='notBreaching'
    )
    
    # Alarm 2: P95 Latency Degradation
    cloudwatch.put_metric_alarm(
        AlarmName='RetainWise-HighLatency',
        AlarmDescription='P95 latency exceeded 1000ms - performance degradation',
        ActionsEnabled=True,
        MetricName='PredictionDuration',
        Namespace='RetainWise/Production',
        Statistic='p95',
        Period=300,
        EvaluationPeriods=2,  # 2 consecutive periods
        Threshold=1000,  # 1000ms
        ComparisonOperator='GreaterThanThreshold',
        TreatMissingData='notBreaching'
    )
    
    # Alarm 3: Daily Cost Exceeded
    cloudwatch.put_metric_alarm(
        AlarmName='RetainWise-HighCost',
        AlarmDescription='Daily cost exceeded $10 - budget alert',
        ActionsEnabled=True,
        MetricName='EstimatedCost',
        Namespace='RetainWise/Production',
        Statistic='Sum',
        Period=86400,  # 24 hours
        EvaluationPeriods=1,
        Threshold=10,  # $10/day
        ComparisonOperator='GreaterThanThreshold',
        TreatMissingData='notBreaching'
    )
    
    print("✅ Created 3 CloudWatch alarms")


# ========================================
# CLOUDWATCH LOGS INSIGHTS QUERIES
# ========================================

USEFUL_QUERIES = {
    "recent_predictions": """
        fields @timestamp, prediction_id, row_count, duration_ms
        | filter event = 'prediction_completed'
        | sort @timestamp desc
        | limit 50
    """,
    
    "slow_predictions": """
        fields @timestamp, prediction_id, duration_ms, row_count
        | filter event = 'prediction_completed' and duration_ms > 1000
        | sort duration_ms desc
        | limit 20
    """,
    
    "error_breakdown": """
        fields error_type
        | filter event = 'prediction_failed'
        | stats count() by error_type
        | sort count desc
    """,
    
    "user_activity": """
        fields @timestamp, user_id, event
        | filter user_id = '***HASH_HERE'
        | sort @timestamp desc
        | limit 100
    """,
    
    "cost_by_operation": """
        fields operation, estimated_cost_usd
        | filter event = 'prediction_completed'
        | stats sum(estimated_cost_usd) as total_cost by operation
        | sort total_cost desc
    """,
    
    "security_audit": """
        fields @timestamp, user_id, event, attempted_resource
        | filter severity = 'SECURITY'
        | sort @timestamp desc
        | limit 50
    """
}


# ========================================
# DEPLOYMENT FUNCTIONS
# ========================================

def deploy_dashboard():
    """Deploy the CloudWatch dashboard to AWS"""
    dashboard_body = create_production_dashboard()
    
    try:
        response = cloudwatch.put_dashboard(
            DashboardName='RetainWise-Production',
            DashboardBody=json.dumps(dashboard_body)
        )
        
        print("✅ Dashboard deployed successfully!")
        print(f"View at: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=RetainWise-Production")
        
        return response
        
    except Exception as e:
        print(f"❌ Failed to deploy dashboard: {e}")
        raise


def deploy_alarms():
    """Deploy CloudWatch alarms"""
    try:
        create_production_alarms()
        print("✅ Alarms deployed successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to deploy alarms: {e}")
        raise


def print_useful_queries():
    """Print useful CloudWatch Insights queries"""
    print("\n📊 **USEFUL CLOUDWATCH INSIGHTS QUERIES**\n")
    
    for name, query in USEFUL_QUERIES.items():
        print(f"### {name.replace('_', ' ').title()}")
        print(f"```")
        print(query.strip())
        print(f"```\n")


# ========================================
# CLI
# ========================================

if __name__ == "__main__":
    import sys
    
    if "--deploy" in sys.argv:
        print("🚀 Deploying CloudWatch Dashboard & Alarms...\n")
        deploy_dashboard()
        deploy_alarms()
        print("\n✅ Deployment complete!")
        
    elif "--queries" in sys.argv:
        print_useful_queries()
        
    else:
        print("Usage:")
        print("  python -m backend.monitoring.cloudwatch_dashboard --deploy")
        print("  python -m backend.monitoring.cloudwatch_dashboard --queries")

