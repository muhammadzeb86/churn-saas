aws ecs run-task ^
  --cluster retainwise-cluster ^
  --task-definition retainwise-backend ^
  --launch-type FARGATE ^
  --network-configuration "awsvpcConfiguration={subnets=[subnet-0d539fd1a67a870ec,subnet-03dcb4c3648af8f4d],securityGroups=[sg-09e3fefba95c18c75],assignPublicIp=ENABLED}" ^
  --overrides "{\"containerOverrides\":[{\"name\":\"retainwise-backend\",\"command\":[\"python\",\"backend/scripts/run_migrations.py\"]}]}" ^
  --region us-east-1 