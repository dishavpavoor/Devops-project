provider "aws" {
  region  = var.region
  profile = var.aws_profile
  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "Terraform"
    }
  }
}

# Existing networking and an existing EC2 key pair are supplied by the team.
data "aws_vpc" "selected" {
  id = var.vpc_id
}

data "aws_subnet" "selected" {
  id = var.subnet_id
}

data "aws_key_pair" "selected" {
  key_name = var.key_name
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "sentinel" {
  name_prefix = "${var.project_name}-"
  description = "Sentinel administration through SSH; dashboard access through a tunnel"
  vpc_id      = data.aws_vpc.selected.id

  ingress {
    description = "SSH from the team administrative network"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }
  egress {
    description = "Download OS packages and container images"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "sentinel" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = data.aws_subnet.selected.id
  associate_public_ip_address = true
  key_name                    = data.aws_key_pair.selected.key_name
  vpc_security_group_ids      = [aws_security_group.sentinel.id]

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }
  root_block_device {
    volume_size           = var.root_volume_gb
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }
  tags = { Name = "${var.project_name}-monitor" }

  lifecycle {
    precondition {
      condition     = data.aws_subnet.selected.vpc_id == var.vpc_id
      error_message = "subnet_id must belong to the supplied vpc_id."
    }
  }
}
