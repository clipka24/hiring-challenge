variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
  default     = "eu-central-1"
}

variable "project_name" {
  description = "Short name used as a prefix for all resource names"
  type        = string
  default     = "ab-test-analyzer"
}

variable "vpc_id" {
  description = "ID of the VPC in which Lambda and RDS will be placed"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs (min 2 for Multi-AZ RDS)"
  type        = list(string)
}

variable "db_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "abtests"
}

variable "db_master_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "abtestadmin"
}

variable "rds_instance_class" {
  description = "RDS instance class. Note: db.t3.micro does not support Multi-AZ — use at least db.t3.small when rds_multi_az is true."
  type        = string
  default     = "db.t3.micro"
}

variable "rds_multi_az" {
  description = "Enable Multi-AZ deployment for RDS"
  type        = bool
  default     = false
}

variable "psycopg2_layer_zip_path" {
  description = "Local path to the psycopg2 Lambda layer ZIP file"
  type        = string
  default     = "../layers/psycopg2-layer.zip"
}

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
