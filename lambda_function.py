import boto3
from datetime import datetime, timedelta

# Initialize AWS clients
cloudwatch = boto3.client('cloudwatch', region_name='eu-north-1')
sns = boto3.client('sns', region_name='eu-north-1')

def lambda_handler(event, context):
    # Define time window for metric collection
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)

    # List of AWS namespaces to monitor
    namespaces = [
        'AWS/EC2', 'AWS/Lambda', 'AWS/RDS', 'AWS/S3', 'AWS/DynamoDB',
        'AWS/ElasticBeanstalk', 'AWS/ElastiCache', 'AWS/ElasticLoadBalancing',
        'AWS/SNS', 'AWS/SQS', 'AWS/CloudFront', 'AWS/CloudWatch',
        'AWS/ApiGateway', 'AWS/Route53', 'AWS/Kinesis', 'AWS/Redshift'
    ]

    high_utilization_service = None
    high_utilization_value = 0
    service_details = []

    # Loop through each namespace and fetch metrics
    for namespace in namespaces:
        try:
            # List all available metrics for a namespace
            metrics = cloudwatch.list_metrics(Namespace=namespace)

            for metric in metrics['Metrics']:
                metric_name = metric['MetricName']
                dimensions = metric['Dimensions']

                # Get the metric statistics for the last hour
                response = cloudwatch.get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric_name,
                    Dimensions=dimensions,
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,
                    Statistics=['Average']
                )

                # Only process if there are datapoints
                if response['Datapoints']:
                    avg_value = response['Datapoints'][0]['Average']
                    service_details.append((namespace, metric_name, avg_value))

                    # Track the highest utilization
                    if avg_value > high_utilization_value:
                        high_utilization_value = avg_value
                        high_utilization_service = (namespace, metric_name, avg_value)

        except Exception as e:
            print(f"Error fetching metrics for {namespace}: {e}")

    # Prepare table with the highest utilization service on top
    table = ""

    # Highlight the highest utilized service
    if high_utilization_service:
        table += f"{'Service':<50} | {'Metric':<30} | {'Utilization':<15}\n"
        table += "-" * 100 + "\n"
        table += f"{high_utilization_service[0]:<50} | {high_utilization_service[1]:<30} | {high_utilization_service[2]:<15.2f} <== HIGHEST\n"
        table += "-" * 100 + "\n"

    # Add the remaining services
    for service, metric, utilization in service_details:
        # Skip the highest utilized service (already displayed)
        if (service, metric, utilization) == high_utilization_service:
            continue
        table += f"{service:<50} | {metric:<30} | {utilization:<15.2f}\n"

    # Format the email content
    email_body = f"""
    AWS Service Utilization Report
    ==============================

    Service utilization in the last hour:

    {table}
    """

    # Send the email via SNS (Simple Notification Service)
    try:
        sns.publish(
            TopicArn='arn:aws:sns:eu-north-1:863518417872:AllServiceUtilization',
            Subject='AWS Service Utilization Report',
            Message=email_body
        )
        print("Notification sent successfully.")
    except Exception as e:
        print(f"Error sending notification: {e}")

    return {
        'statusCode': 200,
        'body': 'Notification processed successfully'
    }
