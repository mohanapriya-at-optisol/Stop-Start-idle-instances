import boto3
import json
from datetime import datetime, timedelta

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')
    cloudwatch = boto3.client('cloudwatch')
    
    # Modify the instnace types as needed
    gpu_instance_types = ['p3.2xlarge', 'p3.8xlarge', 'p3.16xlarge', 'p4d.24xlarge', 'g4dn.xlarge', 't2.micro']
    
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'instance-state-name', 'Values': ['running']},
            {'Name': 'instance-type', 'Values': gpu_instance_types}
        ]
    )
    
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=30) #Modify the time needed
    
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            
            # Check CPU utilization
            cpu_response = cloudwatch.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=1800,  # Modify the instance types as needed, now set as 30 minutes
                Statistics=['Average']
            )
            
            # Check Network In
            network_in_response = cloudwatch.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='NetworkIn',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=1800, # Modify the time as needed, now set as 30 minutes
                Statistics=['Sum']
            )
            
            # Check Network Out
            network_out_response = cloudwatch.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='NetworkOut',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=1800, # Modify the time as needed, now set as 30 minutes
                Statistics=['Sum']
            )
            
            # Stop if all conditions met: CPU < 10%, NetworkIn < 1MB, NetworkOut < 1MB
            should_stop = True
            avg_cpu = 0
            network_in = 0
            network_out = 0
            
            # Check CPU
            if cpu_response['Datapoints']:
                avg_cpu = cpu_response['Datapoints'][0]['Average']
                if avg_cpu > 10: #10% CPU threshold
                    should_stop = False
            else:
                should_stop = False  # No data = keep running
            
            # Check Network In
            if network_in_response['Datapoints'] and should_stop:
                network_in = network_in_response['Datapoints'][0]['Sum']
                if network_in > 1048576:  # 1MB in bytes
                    should_stop = False
            
            # Check Network Out
            if network_out_response['Datapoints'] and should_stop:
                network_out = network_out_response['Datapoints'][0]['Sum']
                if network_out > 1048576:  # 1MB in bytes
                    should_stop = False
            
            if should_stop:
                ec2.stop_instances(InstanceIds=[instance_id])
                print(f"Stopped idle instance: {instance_id} (CPU: {avg_cpu:.2f}%, NetworkIn: {network_in/1024:.2f}KB, NetworkOut: {network_out/1024:.2f}KB)")
            else:
                print(f"Instance {instance_id} is active (CPU: {avg_cpu:.2f}%, NetworkIn: {network_in/1024:.2f}KB, NetworkOut: {network_out/1024:.2f}KB)")
    
    return {'statusCode': 200, 'body': json.dumps('Idle check completed')}
