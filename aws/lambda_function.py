import json
import os
import time
import boto3

# Initialize the Boto3 Athena Client
athena_client = boto3.client('athena')

# Load configuration from environment variables
DATABASE_NAME = os.environ.get('ATHENA_DATABASE')
S3_OUTPUT_LOCATION = os.environ.get('ATHENA_OUTPUT_BUCKET')
# e.g., s3://athena-query-results-bucket/

# Define the structure for the execution configuration
RESULT_CONFIGURATION = {
    'OutputLocation': S3_OUTPUT_LOCATION
}


def execute_athena_query(sql_query):
    """
    Executes an SQL query on AWS Athena.
    Returns the Query Execution ID.
    """
    try:
        response = athena_client.start_query_execution(
            QueryString=sql_query,
            QueryExecutionContext={
                'Database': DATABASE_NAME
            },
            ResultConfiguration=RESULT_CONFIGURATION
        )

        return {
            'query_execution_id': response['QueryExecutionId']
        }

    except Exception as e:
        print(f"Error starting Athena query: {e}")
        # The Lambda function returns an error message for the Self-Correction Loop
        raise RuntimeError(f"Athena Execution Error: {str(e)}")


def get_query_results(query_execution_id):
    """
    Waits for the query to finish and retrieves the first page of results.
    For simplicity, this example only fetches status.
    In a real system, you would check status and then fetch results from S3.
    """
    # 1. Wait for query completion (Simplified polling)
    while True:
        status_response = athena_client.get_query_execution(
            QueryExecutionId=query_execution_id
        )
        state = status_response['QueryExecution']['Status']['State']

        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break

        # Poll every 0.5 seconds to check status
        time.sleep(0.5)

        # 2. Check final state
    if state == 'SUCCEEDED':
        # In the real world, you would then parse the CSV/JSON file from the
        # S3_OUTPUT_LOCATION using the QueryExecutionId as part of the path.
        # For this architecture, we return a success status.
        return {
            'status': 'SUCCESS',
            'state': state,
            'result_s3_path': f"{S3_OUTPUT_LOCATION}{query_execution_id}.csv"
            # This is the path the Data Results will be fetched from by a different service
        }
    else:
        # Extract the error message for the Self-Correction Loop
        error_reason = status_response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown Error')
        raise ValueError(f"Athena Query Failed: {error_reason}")


def lambda_handler(event, context):
    """
    Main handler for the Lambda function, invoked by API Gateway.
    """
    try:
        # Extract SQL query from the API Gateway event body (as mapped in the template)
        # Assuming the API Gateway passed a dict like {'sqlQuery': 'SELECT * FROM ...'}
        sql_query = event['sql_query']

        # 1. Execute the query
        execution_info = execute_athena_query(sql_query)
        query_id = execution_info['query_execution_id']

        # 2. Poll for results (This is synchronous polling, recommended to use SNS/SQS for async in production)
        results = get_query_results(query_id)

        # Return success (This is the "Data Results" path in the diagram)
        return {
            'statusCode': 200,
            'body': json.dumps(results)
        }

    except (RuntimeError, ValueError) as e:
        # Return error (This is the "Error Message" path in the diagram)
        # Note: API Gateway should be configured to map this Lambda error to an HTTP 4xx/5xx error.
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'ERROR',
                'message': str(e)
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'FATAL_ERROR',
                'message': f"An unexpected error occurred: {str(e)}"
            })
        }
