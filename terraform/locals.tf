locals {
  common_tags = merge(
    {
      Project     = var.project_name
      ManagedBy   = "terraform"
      Environment = var.environment
    },
    var.tags,
  )
}
