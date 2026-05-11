terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

variable "aws_region" {
  type        = string
  description = "AWS region for the provider and regional resources (e.g. Lambda)."
  default     = "ap-south-1"
}

variable "aws_bucket" {
  type        = string
  description = "S3 bucket name passed to Lambda functions as AWS_BUCKET."
  default     = "rearc-quest-bucket-aws"
}

variable "s3_notification_object_key_prefix" {
  type        = string
  description = <<-EOT
    S3 object key prefix for SQS notifications. S3 has no exact-key filter; use the full key
    (e.g. path/to/file.csv) so only that object (and keys that start with the same string) match.
    Optionally set s3_notification_object_key_suffix to narrow further.
  EOT
  default     = "api/data.json"
}

variable "s3_notification_object_key_suffix" {
  type        = string
  description = "S3 object key suffix filter; leave empty to match on prefix only."
  default     = ""
}

provider "aws" {
  region = var.aws_region
}

# 1. Archive the source code
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda"
  output_path = "${path.module}/../infra/lambda_function.zip"
}

# Archive the source code for the lambda report
data "archive_file" "lambda_report_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambdaReport"
  output_path = "${path.module}/../infra/lambda_report_function.zip"
}

# 2. Create the Execution Role
resource "aws_iam_role" "iam_for_lambda" {
  name = "questLambdaRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# 3. Attach S3 and CloudWatch Logs permissions
resource "aws_iam_role_policy_attachment" "lambda_s3_full" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "lambda_cloudwatch_logs_full" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

# 4. Define the Lambda Function
resource "aws_lambda_function" "questLambdaTF" {
  filename      = data.archive_file.lambda_zip.output_path
  function_name = "questLambda"
  role          = aws_iam_role.iam_for_lambda.arn
  handler       = "main.handler" # filename.method (main.py → main)

  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  runtime = "python3.11"

  environment {
    variables = {
      AWS_REGION = var.aws_region
      AWS_BUCKET = var.aws_bucket
    }
  }

  tags = {
    project = "rearc"
    type    = "quest"
  }
}

# Define the Lambda Function for the report
resource "aws_lambda_function" "questLambdaReportTF" {
  filename      = data.archive_file.lambda_report_zip.output_path
  function_name = "questLambdaReport"
  role          = aws_iam_role.iam_for_lambda.arn
  handler       = "analyse.handle" # filename.method (analyse.py → handle)

  source_code_hash = data.archive_file.lambda_report_zip.output_base64sha256

  runtime = "python3.11"

  environment {
    variables = {
      AWS_REGION = var.aws_region
      AWS_BUCKET = var.aws_bucket
    }
  }

  tags = {
    project = "rearc"
    type    = "quest"
  }
}

resource "aws_s3_bucket" "lambda_bucket" {
  bucket = "rearc-quest-bucket-aws"
  force_destroy = true

  tags = {
    project = "rearc"
    type = "quest"
  }
}

resource "aws_s3_bucket_notification" "object_created_to_sqs" {
  bucket = aws_s3_bucket.lambda_bucket.id

  queue {
    queue_arn     = aws_sqs_queue.questQueue.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = var.s3_notification_object_key_prefix
    filter_suffix = var.s3_notification_object_key_suffix != "" ? var.s3_notification_object_key_suffix : null
  }

  depends_on = [aws_sqs_queue_policy.questQueue_policy]
}

resource "aws_sqs_queue" "questQueue" {
  name                      = "questQueue"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 10

  tags = {
    project = "rearc"
    type = "quest"
  }
}

resource "aws_sqs_queue_policy" "questQueue_policy" {
  queue_url = aws_sqs_queue.questQueue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Allow-S3-ObjectCreated-Notifications"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.questQueue.arn
        Condition = {
          ArnLike = {
            "aws:SourceArn" = aws_s3_bucket.lambda_bucket.arn
          }
        }
      },
      {
        Sid    = "Allow-questLambdaReport-Consume"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.questQueue.arn
        Condition = {
          ArnLike = {
            "aws:SourceArn" = aws_lambda_function.questLambdaReportTF.arn
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_quest_queue_consume" {
  name = "questQueueConsume"
  role = aws_iam_role.iam_for_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.questQueue.arn
      }
    ]
  })
}