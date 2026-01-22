import boto3
import json
import urllib.request
import urllib.parse
import urllib.error
import time
import os

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')
    
    # Route based on path
    path = event.get('path', '/')
    print(f"Request path: {path}")
    print(f"Available env vars: INSTANCE_ID={os.environ.get('INSTANCE_ID')}, INSTANCE_ID_1={os.environ.get('INSTANCE_ID_1')}")
    
    instance_config = get_instance_config(path)
    
    if not instance_config:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Service not found', 'path': path, 'debug': 'No matching instance config'})
        }
    
    instance_id, docker_port, health_path = instance_config
    
    # Get current instance IP dynamically
    docker_endpoint = get_instance_endpoint(ec2, instance_id, docker_port)
    if not docker_endpoint:
        return {
            'statusCode': 503,
            'body': json.dumps({'error': 'Instance not found or no IP available'})
        }
    
    # Check if instance is running and Docker is healthy
    try:
        req = urllib.request.Request(f"{docker_endpoint}{health_path}")
        with urllib.request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                # Forward request to Docker app
                return forward_request(event, docker_endpoint)
    except:
        pass
    
    # Start instance if not responding
    try:
        ec2.start_instances(InstanceIds=[instance_id])
        
        # Wait for instance to be running
        waiter = ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 15, 'MaxAttempts': 20})
        
        # Get new IP after instance starts
        docker_endpoint = get_instance_endpoint(ec2, instance_id, docker_port)
        if not docker_endpoint:
            return {
                'statusCode': 503,
                'body': json.dumps({'error': 'Instance started but no IP available'})
            }
        
        # Wait for Docker to be ready (up to 5 minutes)
        for i in range(30):
            try:
                req = urllib.request.Request(f"{docker_endpoint}{health_path}")
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        break
            except:
                pass
            time.sleep(10)
        
        # Forward request to Docker app
        return forward_request(event, docker_endpoint)
        
    except Exception as e:
        return {
            'statusCode': 503,
            'body': json.dumps({'error': 'Service temporarily unavailable'})
        }

def get_instance_config(path):
    """Route requests to different instances based on path"""
    configs = {
        '/app1': (os.environ.get('INSTANCE_ID_1'), os.environ.get('DOCKER_PORT_1', '5000'), '/')
    }
    
    for prefix, config in configs.items():
        if path.startswith(prefix):
            instance_id, port, health = config
            if instance_id:  # Only return if instance_id is set
                return instance_id, port, health
    
    # Dynamic fallback - find any available instance
    for i in range(1, 100):  # Check INSTANCE_ID_1 through INSTANCE_ID_99
        instance_id = os.environ.get(f'INSTANCE_ID_{i}')
        if instance_id:
            port = os.environ.get(f'DOCKER_PORT_{i}', '5000')
            return instance_id, port, '/'
    
    # Final fallback to single instance mode
    instance_id = os.environ.get('INSTANCE_ID')
    if instance_id:
        return instance_id, os.environ.get('DOCKER_PORT', '5000'), '/'
    
    return None

def get_instance_endpoint(ec2, instance_id, port):
    """Get current instance IP and build endpoint URL"""
    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        
        # Try public IP first, then private IP
        public_ip = instance.get('PublicIpAddress')
        private_ip = instance.get('PrivateIpAddress')
        
        ip = public_ip if public_ip else private_ip
        if ip:
            return f"http://{ip}:{port}"
        return None
    except:
        return None

def forward_request(event, docker_endpoint):
    """Forward the request to Docker app"""
    try:
        # Handle different event types (Function URL vs manual test)
        method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        url = f"{docker_endpoint}{path}"
        
        # Prepare request
        data = body.encode('utf-8') if body else None
        req = urllib.request.Request(url, data=data, method=method)
        
        # Add headers
        for key, value in headers.items():
            if key.lower() not in ['host', 'content-length']:
                req.add_header(key, value)
        
        # Make request
        with urllib.request.urlopen(req, timeout=30) as response:
            response_body = response.read()
            response_headers = dict(response.headers)
            content_type = response_headers.get('Content-Type', 'text/html')
            
            # Handle binary vs text content
            is_binary = not content_type.startswith(('text/', 'application/json', 'application/xml'))
            
            if is_binary:
                import base64
                body = base64.b64encode(response_body).decode('utf-8')
                is_base64_encoded = True
            else:
                body = response_body.decode('utf-8')
                is_base64_encoded = False
            
            return {
                'statusCode': response.status,
                'headers': {
                    'Content-Type': content_type,
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
                },
                'body': body,
                'isBase64Encoded': is_base64_encoded
            }
            
    except Exception as e:
        print(f"Error in forward_request: {str(e)}")
        return {
            'statusCode': 502,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Bad Gateway', 'details': str(e)})
        }
