terraform {
  backend "s3" {
    bucket         = "retainwise-terraform-state-prod"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "retainwise-terraform-locks"
    
    # Prevent accidental deletion/modification
    skip_region_validation      = false
    skip_credentials_validation = false
    skip_metadata_api_check     = false
  }
  
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

