# Basic EC2 Monitoring Setup (CPU, Network)

This guide shows how to set up basic monitoring for EC2 instances using AWS built-in metrics.

## Prerequisites
- Run the Docker Applications as Systemd Services to start when the instance boots
- Copy the Lambda proxy function URL and paste it in the nginx configuration file to route incoming requests

## Cost

- **$0** - Uses free AWS built-in metrics
- **Lambda execution**: Minimal cost (covered by free tier)

## What This Monitors

- **CPU Utilization**: Average CPU usage over 30 minutes
- **Network In**: Total incoming network traffic over 30 minutes  
- **Network Out**: Total outgoing network traffic over 30 minutes

## Step 1: Create Lambda Function for Stopping Idle EC2 Instances

Copy the code from `lambda_stop_idle.py`

## Step 2: Modify the Lambda IAM Role
- Attach **EC2FullAccess** permission to this role

## Step 3: Set Up EventBridge Rule

Create an EventBridge Scheduler to invoke the Lambda function at custom intervals

## Step 4: Customize Thresholds

Modify these values in the Lambda code as needed:

```python
# CPU threshold (percentage)
if avg_cpu > 10:  # Change 10 to your desired percentage

# Network thresholds (bytes)
if network_in > 1048576:  # 1MB - change as needed
if network_out > 1048576:  # 1MB - change as needed

# Time window (minutes)
start_time = end_time - timedelta(minutes=30)  # Change 30 to desired minutes
```

## Step 5: Test the Function

### Instance will be STOPPED if ALL conditions are met:
- CPU utilization < 10% (average over 30 minutes)
- Network In < 1MB (total over 30 minutes)
- Network Out < 1MB (total over 30 minutes)

### Instance will KEEP RUNNING if ANY condition is met:
- CPU utilization ≥ 10%
- Network In ≥ 1MB
- Network Out ≥ 1MB
- No CloudWatch data available

## Step 6: Create Lambda Function for Starting EC2 Instances
- Copy the code from `lambda_proxy.py` and attach EC2 Full access permission
- Create a Function URL
- **Create Environment variables as needed:**
  ```
  INSTANCE_ID_1 = i-1234567890abcdef0
  DOCKER_PORT_1 = 5000
  INSTANCE_ID_2 = i-0987654321fedcba0
  DOCKER_PORT_2 = 8080
  ```

**Update the variables in get_instance_config function:**
```python
'/app1': (os.environ.get('INSTANCE_ID_1'), os.environ.get('DOCKER_PORT_1', '5000'), '/'),
'/app2': (os.environ.get('INSTANCE_ID_2'), os.environ.get('DOCKER_PORT_2', '8080'), '/'),
```
## Step 7: Enable CORS:
- Enable CORS on the Lambda Function URL to allow cross-origin requests 

## Step 8: Update Nginx Config File
- Update the nginx configuration file with the Function URL from Step 6
- Route incoming requests to the Lambda function

**Example:**
```nginx
location /app1/ {
    proxy_pass https://your-lambda-function-url/app1/;
}
location /app2/ {
    proxy_pass https://your-lambda-function-url/app2/;
}
```

## Complete Setup Summary

1. **Stop Function**: Monitors CPU/Network → Stops idle instances
2. **Start Function**: Receives requests → Starts instances on-demand
3. **Nginx**: Routes traffic → Lambda proxy → EC2 instances
4. **Result**: Automatic start/stop based on usage


