import requests
import json

# Test the upload endpoint
def test_upload_endpoint():
    url = "http://localhost:8002/upload/csv"
    
    # Create a simple CSV file content
    csv_content = "customerID,gender,SeniorCitizen,Partner,Dependents,tenure,PhoneService,MultipleLines,InternetService,OnlineSecurity,OnlineBackup,DeviceProtection,TechSupport,StreamingTV,StreamingMovies,Contract,PaperlessBilling,PaymentMethod,MonthlyCharges,TotalCharges\n123456,Male,0,Yes,No,12,Yes,No,DSL,No,Yes,No,No,No,No,Month-to-month,Yes,Electronic check,29.85,29.85"
    
    # Create form data
    files = {
        'file': ('test.csv', csv_content, 'text/csv')
    }
    data = {
        'user_id': '1'  # Test user ID
    }
    
    try:
        print("Testing upload endpoint...")
        print(f"URL: {url}")
        print(f"Files: {files}")
        print(f"Data: {data}")
        
        response = requests.post(url, files=files, data=data)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Upload endpoint is working!")
        else:
            print("❌ Upload endpoint failed")
            
    except Exception as e:
        print(f"❌ Error testing upload endpoint: {e}")

if __name__ == "__main__":
    test_upload_endpoint() 