import requests
import os

# Test the upload endpoint
def test_upload():
    url = "http://localhost:8003/upload/csv"
    
    # Create a test file
    with open("test.csv", "w") as f:
        f.write("id,name,email\n1,Test User,test@example.com\n")
    
    # Test upload
    with open("test.csv", "rb") as f:
        files = {"file": ("test.csv", f, "text/csv")}
        data = {"user_id": 1}
        
        try:
            response = requests.post(url, files=files, data=data)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
    
    # Clean up
    os.remove("test.csv")

if __name__ == "__main__":
    test_upload() 