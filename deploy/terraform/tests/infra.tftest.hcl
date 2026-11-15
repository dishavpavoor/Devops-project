# Mock-provider plans require no AWS account and create no cloud resources.
mock_provider "aws" {
  mock_data "aws_vpc" {
    defaults = { id = "vpc-0123456789abcdef0" }
  }
  mock_data "aws_subnet" {
    defaults = {
      id     = "subnet-0123456789abcdef0"
      vpc_id = "vpc-0123456789abcdef0"
    }
  }
  mock_data "aws_key_pair" {
    defaults = { key_name = "student-project-key" }
  }
  mock_data "aws_ami" {
    defaults = { id = "ami-0123456789abcdef0" }
  }
}

variables {
  vpc_id     = "vpc-0123456789abcdef0"
  subnet_id  = "subnet-0123456789abcdef0"
  key_name   = "student-project-key"
  admin_cidr = "203.0.113.10/32"
}

run "restricted_host_plan" {
  command = plan
  assert {
    condition     = length(aws_security_group.sentinel.ingress) == 1 && one(aws_security_group.sentinel.ingress).from_port == 22 && one(aws_security_group.sentinel.ingress).to_port == 22 && toset(one(aws_security_group.sentinel.ingress).cidr_blocks) == toset([var.admin_cidr])
    error_message = "Only SSH from the configured administrative network should be exposed."
  }
  assert {
    condition     = one(aws_instance.sentinel.root_block_device).encrypted && one(aws_instance.sentinel.root_block_device).volume_size == 20
    error_message = "The root volume must be encrypted and match the configured size."
  }
  assert {
    condition     = one(aws_instance.sentinel.metadata_options).http_tokens == "required"
    error_message = "IMDSv2 must be required."
  }
}

run "reject_public_ssh" {
  command = plan
  variables {
    admin_cidr = "0.0.0.0/0"
  }
  expect_failures = [var.admin_cidr]
}

run "reject_mismatched_network" {
  command = plan
  variables {
    vpc_id = "vpc-11111111111111111"
  }
  expect_failures = [aws_instance.sentinel]
}
