import json
import boto3
from datetime import datetime

cloudformation = boto3.client('cloudformation')
dynamodb_resource = boto3.resource('dynamodb')
bedrock_ag = boto3.client('bedrock-agent')
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')


def create_base_infrastructure(solution_id):
    # Read the YAML template file
    with open('src/base-infra.yaml', 'r') as f:
        template_body = f.read()

    # Define the stack parameters
    stack_parameters = [
        {
            'ParameterKey': 'SolutionId',
            'ParameterValue': solution_id
        }
    ]

    # Create the CloudFormation stack
    stack_name = solution_id
    response = cloudformation.create_stack(
        StackName=stack_name,
        TemplateBody=template_body,
        Parameters=stack_parameters,
        Capabilities=['CAPABILITY_NAMED_IAM']  # Required if your template creates IAM resources
    )

    stack_id = response['StackId']
    print(f'Creating stack {stack_name} ({stack_id})')

    # Wait for the stack to be created
    waiter = cloudformation.get_waiter('stack_create_complete')
    waiter.wait(StackName=stack_id)

    # Get the stack outputs
    stack_outputs = cloudformation.describe_stacks(StackName=stack_id)['Stacks'][0]['Outputs']

    # Extract the output values into variables
    dynamo_table = next((output['OutputValue'] for output in stack_outputs if output['OutputKey'] == 'DynamoDBTableName'), None)
    sns_topic = next((output['OutputValue'] for output in stack_outputs if output['OutputKey'] == 'SNSTopicArn'), None)

    print('Stack outputs:')
    print(f'DynamoDB Table: {dynamo_table}')
    print(f'SNS Topic Arn: {sns_topic}')
   
    return dynamo_table, sns_topic


def create_dynamodb_item(table, prompt_id, prompt_name, prompt_version, prompt_text):
    """
    Create a new item in a DynamoDB table for a prompt.

    Args:
        table (boto3.resources.factory.dynamodb.Table): The DynamoDB table resource.
        prompt_id (str): The ID of the prompt.
        prompt_name (str): The name of the prompt.
        prompt_version (str): The version of the prompt.
        prompt_text (str): The text of the prompt.

    Returns:
        bool: True if the item was successfully inserted, False otherwise.
    """
    try:
        item = {
            'promptId': prompt_id,
            'version': str(prompt_version),
            'promptText': prompt_text,
            'status': 'Pending',
            'createdAt': str(datetime.now()),
            'updatedAt': str(datetime.now())
        }
        dynamodb_table = dynamodb_resource.Table(table)
        dynamodb_table.put_item(Item=item)
        return(f"Prompt '{prompt_name}' (version {prompt_version}) inserted successfully with status 'Pending'.")
    
    except Exception as e:
        return(f"Error inserting prompt: {e}")


def create_bedrock_flow_role(role_name='MyBedrockFlowsRole'):
    """
    Create a new AWS IAM role for Bedrock Flows or use an existing role.

    Args:
        role_name (str): The name of the IAM role to create. Default is 'MyBedrockFlowsRole'.

    Returns:
        str: The Amazon Resource Name (ARN) of the IAM role.
    """
    iam = boto3.client('iam')

    try:
        # Create a new IAM role
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "bedrock.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            })
        )
        flow_role_arn = response['Role']['Arn']

        # Attach the AmazonBedrockFullAccess policy to the role
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/AmazonBedrockFullAccess'
        )

        print(f'Created new IAM role: {flow_role_arn}')

    except iam.exceptions.EntityAlreadyExistsException:
        # Use an existing IAM role
        flow_role_arn = f'arn:aws:iam::{iam.get_user()["User"]["Arn"].split(":")[4]}:role/{role_name}'
        print(f'Using existing IAM role: {flow_role_arn}')

    return flow_role_arn

def create_bedrock_flow(flow_name, description, prompt_arn, flow_role_arn):
    response = bedrock_ag.create_flow(
        name=flow_name,
        description=description,
        executionRoleArn=flow_role_arn,
        definition={
            "connections": [
                {
                    "configuration": {
                        "data": {
                            "sourceOutput": "modelCompletion",
                            "targetInput": "document"
                        }
                    },
                    "name": "Prompt_1PromptsNode0ToFlowOutputNodeFlowOutputNode0",
                    "source": "Prompt_1",
                    "target": "FlowOutputNode",
                    "type": "Data"
                },
                {
                    "configuration": {
                        "data": {
                            "sourceOutput": "document",
                            "targetInput": "input_text"
                        }
                    },
                    "name": "FlowInputNodeFlowInputNode0ToPrompt_1PromptsNode0",
                    "source": "FlowInputNode",
                    "target": "Prompt_1",
                    "type": "Data"
                }
            ],
            "nodes": [
                {
                    "configuration": {
                        "input": {}
                    },
                    "name": "FlowInputNode",
                    "outputs": [
                        {
                            "name": "document",
                            "type": "String"
                        }
                    ],
                    "type": "Input"
                },
                {
                    "configuration": {
                        "output": {}
                    },
                    "inputs": [
                        {
                            "expression": "$.data",
                            "name": "document",
                            "type": "String"
                        }
                    ],
                    "name": "FlowOutputNode",
                    "type": "Output"
                },
                {
                    "configuration": {
                        "prompt": {
                            "sourceConfiguration": {
                                "resource": {
                                    "promptArn": prompt_arn
                                }
                            }
                        }
                    },
                    "inputs": [
                        {
                            "expression": "$.data",
                            "name": "input_text",
                            "type": "String"
                        }
                    ],
                    "name": "Prompt_1",
                    "outputs": [
                        {
                            "name": "modelCompletion",
                            "type": "String"
                        }
                    ],
                    "type": "Prompt"
                }
            ]
        }
    )

    return response

def prepare_and_create_flow_alias(flow_name, flow_description, flow_role_arn, prompt_arn, flow_alias_description):

    # Create the flow
    print("Creating the flow...")
    create_flow_response = create_bedrock_flow(flow_name, flow_description, prompt_arn, flow_role_arn)
    flow_id = create_flow_response['id']
    print(f"Flow created with ID: {flow_id}")

    # Prepare the flow
    print("Preparing the flow...")
    prepare_flow_response = bedrock_ag.prepare_flow(flowIdentifier=flow_id)
    print(json.dumps(prepare_flow_response, indent=2, default=str))

    # Get the flow status
    print("Getting the flow status...")
    get_flow_response = bedrock_ag.get_flow(flowIdentifier=flow_id)
    print("Status:", get_flow_response["status"])

    # Create a flow version
    print("Creating a flow version...")
    create_flow_version_response = bedrock_ag.create_flow_version(flowIdentifier=flow_id)
    print(json.dumps(create_flow_version_response, indent=2, default=str))
    flow_version = create_flow_version_response["version"]
    
    # Create a flow alias
    print("Creating a flow alias...")
    create_flow_alias_response = bedrock_ag.create_flow_alias(
        flowIdentifier=flow_id,
        name=flow_name,
        description=flow_description,
        routingConfiguration=[
            {
                "flowVersion": flow_version
            }
        ]
    )
    print(json.dumps(create_flow_alias_response, indent=2, default=str))
    flow_alias_id = create_flow_alias_response['id']
    print("Flow creation complete. The alias id is: {}".format(flow_alias_id))

    return flow_id, flow_alias_id


def get_prompt_status(table, prompt_id, version):
    """
    Retrieve the status of a prompt from a DynamoDB table.

    Args:
        table (boto3.resources.factory.dynamodb.Table): The DynamoDB table resource.
        prompt_id (str): The ID of the prompt.
        version (str): The version of the prompt.

    Returns:
        str: The status of the prompt, or None if the prompt is not found.
    """
    try:
        dynamodb_table = dynamodb_resource.Table(table)
        response = dynamodb_table.get_item(
            Key={
                'promptId': prompt_id,
                'version': str(version)
            }
        )
        item = response.get('Item')
        if item:
            return item.get('status')
        else:
            return None
    except Exception as e:
        print(f"Error retrieving prompt status: {e}")
        return None

def update_flow_prompt(flow_id, prompt_arn, prompt_id, prompt_version, flow_name, flow_description, flow_role_arn, dynamodb_table_name, flow_alias_id, flow_alias_description):
    prompt_status = get_prompt_status(dynamodb_table_name, prompt_id, prompt_version)

    if prompt_status == "Approved":
        prompt_v = "{}:{}".format(prompt_arn, prompt_version)
        response = bedrock_ag.update_flow(
            definition={
                "connections": [
                    {
                        "configuration": {
                            "data": {
                                "sourceOutput": "modelCompletion",
                                "targetInput": "document"
                            }
                        },
                        "name": "Prompt_1PromptsNode0ToFlowOutputNodeFlowOutputNode0",
                        "source": "Prompt_1",
                        "target": "FlowOutputNode",
                        "type": "Data"
                    },
                    {
                        "configuration": {
                            "data": {
                                "sourceOutput": "document",
                                "targetInput": "input_text"
                            }
                        },
                        "name": "FlowInputNodeFlowInputNode0ToPrompt_1PromptsNode0",
                        "source": "FlowInputNode",
                        "target": "Prompt_1",
                        "type": "Data"
                    }
                ],
                "nodes": [
                    {
                        "configuration": {
                            "input": {}
                        },
                        "name": "FlowInputNode",
                        "outputs": [
                            {
                                "name": "document",
                                "type": "String"
                            }
                        ],
                        "type": "Input"
                    },
                    {
                        "configuration": {
                            "output": {}
                        },
                        "inputs": [
                            {
                                "expression": "$.data",
                                "name": "document",
                                "type": "String"
                            }
                        ],
                        "name": "FlowOutputNode",
                        "type": "Output"
                    },
                    {
                        "configuration": {
                            "prompt": {
                                "sourceConfiguration": {
                                    "resource": {
                                        "promptArn": prompt_v
                                    }
                                }
                            }
                        },
                        "inputs": [
                            {
                                "expression": "$.data",
                                "name": "input_text",
                                "type": "String"
                            }
                        ],
                        "name": "Prompt_1",
                        "outputs": [
                            {
                                "name": "modelCompletion",
                                "type": "String"
                            }
                        ],
                        "type": "Prompt"
                    }
                ]
            },
            description=flow_description,
            executionRoleArn=flow_role_arn,
            flowIdentifier=flow_id,
            name=flow_name
        )
        print(response)

        # Prepare the flow
        print("Preparing the flow...")
        prepare_flow_response = bedrock_ag.prepare_flow(flowIdentifier=flow_id)
        print(json.dumps(prepare_flow_response, indent=2, default=str))
    
        # Get the flow status
        print("Getting the flow status...")
        get_flow_response = bedrock_ag.get_flow(flowIdentifier=flow_id)
        print("Status:", get_flow_response["status"])
    
        # Create a flow version
        print("Creating a flow version...")
        create_flow_version_response = bedrock_ag.create_flow_version(flowIdentifier=flow_id)
        print(json.dumps(create_flow_version_response, indent=2, default=str))

        # Update alias
        update_alias_response = bedrock_ag.update_flow_alias(
            aliasIdentifier=flow_alias_id,
            description=flow_alias_description,
            flowIdentifier=flow_id,
            name=flow_name,
            routingConfiguration=[
                {
                    'flowVersion': create_flow_version_response["version"]
                },
            ]
        )
        
    else:
        print(f"Prompt status is '{prompt_status}'. Flow not updated.")

def executePromptFlow(prompt, flow_id, flow_alias_id):
    response = bedrock_agent_runtime.invoke_flow(
        flowIdentifier = flow_id,
        flowAliasIdentifier = flow_alias_id,
        inputs = [
            { 
                "content": { 
                    "document": prompt
                },
                "nodeName": "FlowInputNode",
                "nodeOutputName": "document"
            }
        ]
    )
    event_stream = response["responseStream"]
    for event in event_stream:
        if "flowOutputEvent" in event:
            flow_response = event["flowOutputEvent"]["content"]["document"]
            print(flow_response)