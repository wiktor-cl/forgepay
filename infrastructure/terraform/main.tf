terraform {
  required_version = ">= 1.8.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Architecture example only. Do not run without reviewing cost and security settings.
provider "aws" {
  region = var.aws_region
}

module "network" {
  source = "./modules/network"
  count  = 0
}

resource "aws_secretsmanager_secret" "forgepay" {
  name = "${var.project_name}/application"
}
