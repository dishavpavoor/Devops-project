output "public_ip" {
  description = "EC2 public IPv4 address; can change after a stop/start."
  value       = aws_instance.sentinel.public_ip
}

output "instance_id" {
  value = aws_instance.sentinel.id
}

output "security_group_id" {
  value = aws_security_group.sentinel.id
}

output "ssh_tunnel" {
  description = "Add -i /path/to/your-key.pem if your key is not already available to SSH."
  value       = "ssh -L 3000:localhost:3000 -L 9090:localhost:9090 -L 9093:localhost:9093 -L 8001:localhost:8001 ubuntu@${aws_instance.sentinel.public_ip}"
}

output "ansible_inventory" {
  description = "Inventory text; add ansible_ssh_private_key_file locally if required."
  value       = "[sentinel]\n${aws_instance.sentinel.public_ip} ansible_user=ubuntu\n"
}
