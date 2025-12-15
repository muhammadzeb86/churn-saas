# ElastiCache Redis Cluster for Prediction Caching
# Cost: ~$15/month (cache.t3.micro)
# Expected ROI: $30-50/month savings from caching

resource "aws_elasticache_subnet_group" "redis" {
  name       = "retainwise-redis-subnet-group"
  subnet_ids = [data.aws_subnet.public_1.id, data.aws_subnet.public_2.id]

  tags = {
    Name        = "retainwise-redis-subnet-group"
    Project     = "RetainWise"
    Environment = "Production"
  }
}

resource "aws_security_group" "redis" {
  name        = "retainwise-redis-sg"
  description = "Security group for RetainWise Redis cache"
  vpc_id      = data.aws_vpc.existing.id

  # Allow Redis access from ECS tasks
  ingress {
    description     = "Redis from ECS"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "retainwise-redis-sg"
    Project     = "RetainWise"
    Environment = "Production"
  }
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "retainwise-cache"
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [aws_security_group.redis.id]

  # Maintenance window
  maintenance_window = "tue:07:30-tue:08:30"
  
  # Snapshot window (daily backups)
  snapshot_window          = "10:00-11:00"
  snapshot_retention_limit = 1  # Keep 1 day of snapshots

  tags = {
    Name        = "retainwise-cache"
    Project     = "RetainWise"
    Environment = "Production"
    Purpose     = "Prediction result caching"
  }
}

# Output the Redis endpoint for use in other resources
output "redis_endpoint" {
  description = "Redis cluster endpoint"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "redis_port" {
  description = "Redis cluster port"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].port
}

output "redis_url" {
  description = "Full Redis connection URL"
  value       = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.cache_nodes[0].port}"
  sensitive   = false
}

