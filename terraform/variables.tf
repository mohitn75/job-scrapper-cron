variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "project" {
  type    = string
  default = "jobwatch"
}

variable "ssm_prefix" {
  type    = string
  default = "/jobwatch"
}

variable "schedule" {
  type    = string
  default = "rate(1 hour)"
}
