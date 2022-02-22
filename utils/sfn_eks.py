# Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# Author - Govindhi Venkatachalapathy <govindhi@amazon.com>
 
import argparse
import sys
import os
import yaml
import datetime
import time
from stepfunctions.steps.service import EksCreateClusterStep, EksCreateNodegroupStep, EksRunJobStep, EksDeleteNodegroupStep, EksDeleteClusterStep
from stepfunctions.workflow import Workflow
from stepfunctions.steps import Chain
from stepfunctions.steps.states import Choice
from stepfunctions.steps.states import Catch
from stepfunctions.steps.states import State
import boto3
import json

def createClusterConfig(cluster_name, cluster_role_arn, security_group, subnet_id, endpoint_access='both'):
    private_access = False
    public_access = False
    if endpoint_access == 'both':
        private_access = True
        public_access = True
    elif endpoint_access == 'private':
        private_access = True
    elif endpoint_access == 'public':
        public_access = True
    else:
        print("Invalid endpoint access method. Supported are both, private and public")

    create_cluster_info = {
    "Name": cluster_name,
    "Logging": { 
        "ClusterLogging": [ 
            { 
                "Enabled": True,
                "Types": [ "api" ]
            }
        ]
    },
    "ResourcesVpcConfig": { 
        "EndpointPrivateAccess": private_access,
        "EndpointPublicAccess": public_access,
        "SecurityGroupIds": security_group,
        "SubnetIds": subnet_id
    },
    "RoleArn": cluster_role_arn
    }
    create_cluster_info = json.dumps(create_cluster_info)
    #print(create_cluster_info)
    return create_cluster_info
    
def createNodeGroupConfig(cluster_name, node_role_arn, node_subnet, instance_type, scaling_config):
    nodegroup_name = '%s_ng' %cluster_name
    create_node_group = {
        "ClusterName": cluster_name,
        "NodegroupName": nodegroup_name,
        "NodeRole": node_role_arn,
        "Subnets": node_subnet,
        "ScalingConfig": { 
            "DesiredSize": scaling_config['DesiredSize'],
            "MaxSize": scaling_config['MaxSize'],
            "MinSize": scaling_config['MinSize']
        },
        "InstanceTypes": instance_type
    }
    create_node_group_info = json.dumps(create_node_group)
    return create_node_group_info

def deleteClusterConfig(cluster_name):
    delete_cluster_info = {"Name": cluster_name}
    delete_cluster_info = json.dumps(delete_cluster_info)
    return delete_cluster_info

def deleteNodeGroupConfig(cluster_name):
    nodegroup_name = '%s_ng' %cluster_name
    delete_node_group = {"ClusterName": cluster_name ,"NodegroupName": nodegroup_name}
    delete_node_group_info = json.dumps(delete_node_group)
    return delete_node_group_info

def runRobInfo(cluster_name, container_name):
    run_job_info = {
        "ClusterName": cluster_name,
        "CertificateAuthority.$": "$.eks.Cluster.CertificateAuthority.Data",
        "Endpoint.$": "$.eks.Cluster.Endpoint",
        "LogOptions": {
            "RetrieveLogs": True
        },
        "Job": {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
            "name": "etl-job"
            },
            "spec": {
                "backoffLimit": 0,
                "template": {
                    "metadata": {
                    "name": "etl-job"
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "etl-eks",
                                "image": container_name
                            }
                        ],
                        "restartPolicy": "Never"
                    }
                }
            }
        }
    }
    run_job_info = json.dumps(run_job_info)
    return run_job_info

def getFailedState(id):
    fail_state = State(state_id=id, state_type="Fail")
    return fail_state

def createSFNEKSWorkflow():
    input_config = {}
    sfn_steps = []
    result = ''

    ecr_repo = "%s.dkr.ecr.%s.amazonaws.com" %(accountid, args.region)
    #print(ecr_repo)
    with open(args.cfgfile) as filerd:
        input_config = yaml.load(filerd, Loader=yaml.FullLoader)

    # Create Cluster
    create_cluster_info_json = createClusterConfig(input_config['ClusterName'], 
                                                   eks_cluster_role_arn,
                                                   input_config['SecurityGroup'],
                                                   input_config['SubnetIds'],
                                                   input_config['EndpointAccess'])
    cluster_create = EksCreateClusterStep(
        state_id="CreateCluster",
        comment="CreateEKSCluster",
        parameters=json.loads(create_cluster_info_json),
        result_path="$.eks"
    )
    
    sfn_steps.append(cluster_create)
    # Create Node Group
    create_node_group_info_json = createNodeGroupConfig(input_config['ClusterName'],
                                                        eks_node_role_arn,
                                                        input_config['NodeGroupSubnetIds'], 
                                                        input_config['InstanceType'],
                                                        input_config['ScalingConfig'])
    create_ng = EksCreateNodegroupStep(
        state_id="CreateNodeGroup",
        parameters=json.loads(create_node_group_info_json),
        result_path="$.nodegroup"
    )
    sfn_steps.append(create_ng)
    # Run Job
    container_name = '%s/%s' %(ecr_repo, args.cntrimage)
    run_job_info = runRobInfo(input_config['ClusterName'], container_name)
    run_job = EksRunJobStep(
        state_id="RunJob",
        parameters=json.loads(run_job_info),
        result_path="$.RunJobResult"
    )
    sfn_steps.append(run_job)
    # Delete Node Group
    delete_node_group = deleteNodeGroupConfig(input_config['ClusterName'])
    delete_ng = EksDeleteNodegroupStep(
        state_id="DeleteNodeGroup",
        parameters=json.loads(delete_node_group)
    )
    sfn_steps.append(delete_ng)
    
    # Delete EKS Cluster
    delete_cluster_info = deleteClusterConfig(input_config['ClusterName'])
    cluster_delete = EksDeleteClusterStep(
        state_id="DeleteCluster",
        comment="DeleteEKSCluster",
        parameters=json.loads(delete_cluster_info)
    )
    sfn_steps.append(cluster_delete)

    # Create Chain of steps
    workflow_graph = Chain(sfn_steps)
    #print(workflow_graph)
    # Create Workflow object
    currentDT = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    workflow_name = "Workflow-%s" %currentDT
    workflow = Workflow(name=workflow_name,
                        definition=workflow_graph,
                        role=sfn_eks_execution_role_arn,
                        client=None)
    #print(workflow)
    #print(workflow.definition.to_json(pretty=True))
    state_machine_arn = workflow.create()
    result = 'Workflow %s created' %state_machine_arn
    print(result)
    if args.execute:
        # Execute workflow        
        execution = workflow.execute()
        print('Workflow %s execution started...' %state_machine_arn)
        time.sleep(60)
        execution_output = execution.get_output(wait=True)
        if execution_output:
            result = execution_output.get("ProcessingJobStatus")
        else:
            result = "Error in workflow execution"
    return result
 
def file_exist_valid(cfile):
    if not os.path.exists(cfile):
        raise argparse.ArgumentTypeError("{0} does not exist".format(cfile))
    return cfile
 
if __name__ == '__main__':
    parser = parser = argparse.ArgumentParser(description='Step functions for Orchestrating the ETL Workloads in EKS')
    parser.add_argument('-c', '--cfgfile', required=True, metavar="FILE", type=file_exist_valid, help='Use this option to create sfn workflow to execute a EKS Job in a cluster') 
    parser.add_argument('-k', '--accesskey', required=False, help='AWS Access Key Id. If not provided, will use the env variable')
    parser.add_argument('-s', '--secretaccess', required=False, help='AWS Secret Access Key.If not provided, will use the env variable')
    parser.add_argument('-r', '--region', required=False, help='AWS Region.If not provided, will use the env variable')
    parser.add_argument('-e', '--execute', action="store_true", help="Use this option to execute the step functions workflow after creation.\
        Do not specify this option if workflow has to be just created.")
    parser.add_argument('-i', '--cntrimage', required=True, help='Container image to be used in ETL Job')
    args = parser.parse_args()
 
    # Set the env variables for AWS Config
    if not args.accesskey:
        args.accesskey = os.environ["AWS_ACCESS_KEY_ID"]
    if not args.secretaccess:
        args.secretaccess = os.environ["AWS_SECRET_ACCESS_KEY"]
    if not args.region:
        args.region = os.environ["AWS_DEFAULT_REGION"]
 
    client = boto3.client('sts')
    accountid = client.get_caller_identity()["Account"]

    eks_cluster_role_arn = 'arn:aws:iam::%s:role/eks-cluster-role' %accountid
    eks_node_role_arn = 'arn:aws:iam::%s:role/eks-node-role' %accountid
    sfn_eks_execution_role_arn = 'arn:aws:iam::%s:role/sfn-eks-execution-role' %accountid

    try:
        response = createSFNEKSWorkflow()
        print(response)
    except Exception as e:
        print ("Unexcepted Exception seen while creating stepfunction workflow:%s" %e)

    
