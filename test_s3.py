import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("Testing S3 environment variables...")
print(f"AWS_REGION: {os.getenv('AWS_REGION', 'NOT_SET')}")
print(f"AWS_ACCESS_KEY_ID: {os.getenv('AWS_ACCESS_KEY_ID', 'NOT_SET')[:10] + '...' if os.getenv('AWS_ACCESS_KEY_ID') else 'NOT_SET'}")
print(f"S3_BUCKET: {os.getenv('S3_BUCKET', 'NOT_SET')}")

# Test S3 service import
try:
    from backend.services.s3_service import s3_service
    print("✅ S3 service imported successfully")
    
    # Test S3 service initialization
    print(f"S3 Bucket: {s3_service.bucket_name}")
    print(f"S3 Region: {s3_service.region}")
    
except Exception as e:
    print(f"❌ Error importing S3 service: {e}") 