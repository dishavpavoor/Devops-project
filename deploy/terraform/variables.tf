variable "region" {
  description = "AWS region containing the supplied VPC, subnet and EC2 key pair."
  type        = string
  default     = "ap-south-1"
}

variable "aws_profile" {
  description = "Optional locally configured AWS profile; null uses the default credential chain."
  type        = string
  default     = null
}

variable "project_name" {
  description = "Project tag and resource-name prefix."
  type        = string
  default     = "sentinel"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,24}$", var.project_name))
    error_message = "Use 2–25 lowercase letters, numbers or hyphens, starting with a letter."
  }
}

variable "vpc_id" {
  description = "Existing VPC ID. No VPC is created or deleted by this configuration."
  type        = string
  validation {
    condition     = can(regex("^vpc-([0-9a-f]{8}|[0-9a-f]{17})$", var.vpc_id))
    error_message = "Supply a valid VPC ID such as vpc-0123456789abcdef0."
  }
}

variable "subnet_id" {
  description = "Existing public subnet with a route to an internet gateway. Must be in vpc_id."
  type        = string
  validation {
    condition     = can(regex("^subnet-([0-9a-f]{8}|[0-9a-f]{17})$", var.subnet_id))
    error_message = "Supply a valid subnet ID."
  }
}

variable "key_name" {
  description = "Name of an existing EC2 key pair in this region, not the private key or its contents."
  type        = string
  validation {
    condition     = length(trimspace(var.key_name)) > 0
    error_message = "Supply the name of an existing EC2 key pair."
  }
}

variable "admin_cidr" {
  description = "Your public IPv4 /32, or a trusted administrative network /24 or narrower."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.admin_cidr)) && try(tonumber(split("/", var.admin_cidr)[1]) >= 24, false)
    error_message = "Supply an IPv4 CIDR /24 or narrower, preferably your public IP /32."
  }
}

variable "instance_type" {
  description = "Supported x86 T3 instance size. Pricing/free-tier eligibility depends on your account."
  type        = string
  default     = "t3.small"
  validation {
    condition     = contains(["t3.micro", "t3.small", "t3.medium", "t3.large"], var.instance_type)
    error_message = "Choose t3.micro, t3.small, t3.medium or t3.large for this x86 configuration."
  }
}

variable "root_volume_gb" {
  description = "Encrypted gp3 root volume size in GiB."
  type        = number
  default     = 20
  validation {
    condition     = var.root_volume_gb >= 20 && var.root_volume_gb <= 100 && floor(var.root_volume_gb) == var.root_volume_gb
    error_message = "Choose a whole-number root disk size from 20 to 100 GiB."
  }
}
