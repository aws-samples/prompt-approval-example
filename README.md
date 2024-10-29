# Prompt Approval Example

## Overview

This project demonstrates how to implement a manual approval workflow for prompt management in Amazon Bedrock. It aims to enhance the quality and reliability of prompts deployed to production environments by introducing a structured approval process.

## Background

Amazon Bedrock's Prompt Management system allows users to create, save, and iterate on prompts that can be integrated with larger applications. While this system offers great flexibility, it's crucial to maintain quality control, especially in production environments.

## Sample Goal

The main objective of this sample is to create a manual approval process for new versions of prompts before they are deployed to production. This ensures that only thoroughly vetted and approved prompts are used in live systems.

## Features

- Implementation of a manual approval workflow for prompt management
- Integration with Amazon Bedrock's Prompt Management system

## Getting Started

### Prerequisites

- Amazon Web Services (AWS) account
- Access to Amazon Bedrock 
- Basic understanding of prompt engineering and management

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/aws-samples/prompt-approval-example
   ```
2. Navigate to the project directory:
   ```
   cd prompt-approval-example
   ```
3. Follow the instructions in the provided notebook to set up and run the workflow.

## Notebook Contents

The Jupyter notebook in this project guides you through the following steps:

1. **Setup and Infrastructure Creation**
    - Import necessary libraries and set up AWS clients
    - Create base infrastructure using CloudFormation (SNS topic, API Gateway, DynamoDB table, Lambda functions)

2. **Email Subscription for Approvers**
    - Subscribe an approver's email to the SNS topic for notifications

3. **Prompt Creation and Management**
    - Create a new prompt in Amazon Bedrock Prompt Management
    - Store prompt information in DynamoDB

4. **Approval Process Demonstration**
    - Explain the approval/denial process via email notifications

5. **Prompt Flow Creation**
    - Create an Amazon Bedrock Prompt Flow to execute the prompt
    - Demonstrate the execution of the prompt flow

6. **Prompt Version Update**
    - Create a new version of the prompt
    - Trigger the approval process for the new version

7. **Prompt Flow Update**
    - Update the Prompt Flow with the new approved prompt version

8. **Resource Cleanup**
    - Delete all created resources to avoid unnecessary costs

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.