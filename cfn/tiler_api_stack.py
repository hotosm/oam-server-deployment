import json

from troposphere import (
    Base64,
    GetAtt,
    Join,
    Output,
    Parameter,
    Ref,
    Tags,
    Template
)

from utils.cfn import read_file, validate_cloudformation_template
from utils.constants import (
    ALLOW_ALL_CIDR,
    EC2_AVAILABILITY_ZONES,
    EMR_EC2_INSTANCE_TYPES,
    VPC_CIDR,
)

import troposphere.ec2 as ec2
import troposphere.iam as iam
import troposphere.policies as policies

t = Template()

t.add_version('2010-09-09')
t.add_description('OpenAerialMap tiler API stack')

ref_stack_id = Ref('AWS::StackId')
ref_region = Ref('AWS::Region')
ref_stack_name = Ref('AWS::StackName')

#
# Parameters
#
keyname_param = t.add_parameter(Parameter(
    'KeyName', Type='AWS::EC2::KeyPair::KeyName', Default='hotosm',
    Description='Name of an existing EC2 key pair'
))

role_param = t.add_parameter(Parameter(
    'Role', Type='String', Default='OAMServer',
    Description='IAM Instance Role'
))

tiler_ami_param = t.add_parameter(Parameter(
    'CoreOSAMI', Type='String', Default='ami-05783d60',
    Description='CoreOS AMI'
))

server_api_version_param = t.add_parameter(Parameter(
    'ServerAPIVersion', Type='String',
    Description='Server API Docker image version'
))

publisher_version_param = t.add_parameter(Parameter(
    'PublisherVersion', Type='String',
    Description='Publisher Docker image version'
))

small_cluster_size_param = t.add_parameter(Parameter(
    'SmallClusterSize', Type='Number',
    Description='"Small" task node count'
))

medium_cluster_size_param = t.add_parameter(Parameter(
    'MediumClusterSize', Type='Number',
    Description='"Medium" task node count'
))

large_cluster_size_param = t.add_parameter(Parameter(
    'LargeClusterSize', Type='Number',
    Description='"Large" task node count'
))

small_threshold_param = t.add_parameter(Parameter(
    'SmallThreshold', Type='Number',
    Description='Maximum number of images to count as a "small" job'
))

medium_threshold_param = t.add_parameter(Parameter(
    'MediumThreshold', Type='Number',
    Description='Maximum number of images to count as a "medium" job'
))

emr_master_instance_type_param = t.add_parameter(Parameter(
    'EMRMasterInstanceType', Type='String', Default='m3.xlarge',
    AllowedValues=EMR_EC2_INSTANCE_TYPES,
    ConstraintDescription='must be an EMR-supported EC2 instance type.',
    Description='EMR master instance type'
))

emr_core_instance_type_param = t.add_parameter(Parameter(
    'EMRCoreInstanceType', Type='String', Default='m3.xlarge',
    AllowedValues=EMR_EC2_INSTANCE_TYPES,
    ConstraintDescription='must be an EMR-supported EC2 instance type.',
    Description='EMR core instance type'
))

emr_task_instance_type_param = t.add_parameter(Parameter(
    'EMRTaskInstanceType', Type='String', Default='m3.xlarge',
    AllowedValues=EMR_EC2_INSTANCE_TYPES,
    ConstraintDescription='must be an EMR-supported EC2 instance type.',
    Description='EMR task instance type'
))

emr_core_cluster_size_param = t.add_parameter(Parameter(
    'EMRCoreClusterSize', Type='Number',
    Description='Reserved instance count, less master node'
))

emr_task_bid_price_param = t.add_parameter(Parameter(
    'EMRTaskBidPrice', Type='Number',
    Description='EMR task instance bid price'
))

auth_token_bucket_param = t.add_parameter(Parameter(
    'AuthTokenBucket', Type='String',
    Description='S3 bucket containing auth tokens'
))

auth_token_key_param = t.add_parameter(Parameter(
    'AuthTokenKey', Type='String',
    Description='S3 key containing auth tokens'
))

status_bucket_param = t.add_parameter(Parameter(
    'StatusBucket', Type='String',
    Description='S3 bucket containing task statuses'
))

status_prefix_param = t.add_parameter(Parameter(
    'StatusKeyPrefix', Type='String',
    Description='S3 key prefix for task statuses'
))

status_sqs_queue_url_param = t.add_parameter(Parameter(
    'StatusSQSQueueURL', Type='String',
    Description='SQS queue URL for status updates'
))

oam_api_token_param = t.add_parameter(Parameter(
    'OAMAPIToken', Type='String',
    Description='OAM API Token'
))

#
# VPC
#

VPC = t.add_resource(
    ec2.VPC(
        'VPC',
        CidrBlock='10.0.0.0/16',
        Tags=Tags(
            Application=ref_stack_id)))

subnet = t.add_resource(
    ec2.Subnet(
        'Subnet',
        CidrBlock='10.0.0.0/24',
        VpcId=Ref(VPC),
        Tags=Tags(
            Application=ref_stack_id)))

internetGateway = t.add_resource(
    ec2.InternetGateway(
        'InternetGateway',
        Tags=Tags(
            Application=ref_stack_id)))

gatewayAttachment = t.add_resource(
    ec2.VPCGatewayAttachment(
        'AttachGateway',
        VpcId=Ref(VPC),
        InternetGatewayId=Ref(internetGateway)))

routeTable = t.add_resource(
    ec2.RouteTable(
        'RouteTable',
        VpcId=Ref(VPC),
        Tags=Tags(
            Application=ref_stack_id)))

route = t.add_resource(
    ec2.Route(
        'Route',
        DependsOn='AttachGateway',
        GatewayId=Ref('InternetGateway'),
        DestinationCidrBlock='0.0.0.0/0',
        RouteTableId=Ref(routeTable),
    ))

subnetRouteTableAssociation = t.add_resource(
    ec2.SubnetRouteTableAssociation(
        'SubnetRouteTableAssociation',
        SubnetId=Ref(subnet),
        RouteTableId=Ref(routeTable),
    ))

networkAcl = t.add_resource(
    ec2.NetworkAcl(
        'NetworkAcl',
        VpcId=Ref(VPC),
        Tags=Tags(
            Application=ref_stack_id),
    ))

inBoundPrivateNetworkAclEntry = t.add_resource(
    ec2.NetworkAclEntry(
        'InboundHTTPNetworkAclEntry',
        NetworkAclId=Ref(networkAcl),
        RuleNumber='100',
        Protocol='6',
        PortRange=ec2.PortRange(To='80', From='80'),
        Egress='false',
        RuleAction='allow',
        CidrBlock='0.0.0.0/0',
    ))

inboundSSHNetworkAclEntry = t.add_resource(
    ec2.NetworkAclEntry(
        'InboundSSHNetworkAclEntry',
        NetworkAclId=Ref(networkAcl),
        RuleNumber='101',
        Protocol='6',
        PortRange=ec2.PortRange(To='22', From='22'),
        Egress='false',
        RuleAction='allow',
        CidrBlock='0.0.0.0/0',
    ))

inboundResponsePortsNetworkAclEntry = t.add_resource(
    ec2.NetworkAclEntry(
        'InboundResponsePortsNetworkAclEntry',
        NetworkAclId=Ref(networkAcl),
        RuleNumber='102',
        Protocol='6',
        PortRange=ec2.PortRange(To='65535', From='1024'),
        Egress='false',
        RuleAction='allow',
        CidrBlock='0.0.0.0/0',
    ))

outBoundHTTPNetworkAclEntry = t.add_resource(
    ec2.NetworkAclEntry(
        'OutBoundHTTPNetworkAclEntry',
        NetworkAclId=Ref(networkAcl),
        RuleNumber='100',
        Protocol='6',
        PortRange=ec2.PortRange(To='80', From='80'),
        Egress='true',
        RuleAction='allow',
        CidrBlock='0.0.0.0/0',
    ))

outBoundHTTPSNetworkAclEntry = t.add_resource(
    ec2.NetworkAclEntry(
        'OutBoundHTTPSNetworkAclEntry',
        NetworkAclId=Ref(networkAcl),
        RuleNumber='101',
        Protocol='6',
        PortRange=ec2.PortRange(To='443', From='443'),
        Egress='true',
        RuleAction='allow',
        CidrBlock='0.0.0.0/0',
    ))

outBoundResponsePortsNetworkAclEntry = t.add_resource(
    ec2.NetworkAclEntry(
        'OutBoundResponsePortsNetworkAclEntry',
        NetworkAclId=Ref(networkAcl),
        RuleNumber='102',
        Protocol='6',
        PortRange=ec2.PortRange(To='65535', From='1024'),
        Egress='true',
        RuleAction='allow',
        CidrBlock='0.0.0.0/0',
    ))

subnetNetworkAclAssociation = t.add_resource(
    ec2.SubnetNetworkAclAssociation(
        'SubnetNetworkAclAssociation',
        SubnetId=Ref(subnet),
        NetworkAclId=Ref(networkAcl),
    ))

instanceSecurityGroup = t.add_resource(
    ec2.SecurityGroup(
        'InstanceSecurityGroup',
        GroupDescription='Enable SSH access via port 22',
        SecurityGroupIngress=[
            ec2.SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='22',
                ToPort='22',
                CidrIp='0.0.0.0/0'),
            ec2.SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='80',
                ToPort='80',
                CidrIp='0.0.0.0/0')],
        VpcId=Ref(VPC),
    ))

#
# Instance
#

refs = dict(
    aws_stack_name=Ref('AWS::StackName'),
    aws_region=Ref('AWS::Region'),
    keyname=Ref(keyname_param),
    server_api_version=Ref(server_api_version_param),
    publisher_version=Ref(publisher_version_param),
    small_cluster_size=Ref(small_cluster_size_param),
    medium_cluster_size=Ref(medium_cluster_size_param),
    large_cluster_size=Ref(large_cluster_size_param),
    small_image_count=Ref(small_threshold_param),
    medium_image_count=Ref(medium_threshold_param),
    emr_master_instance_type=Ref(emr_master_instance_type_param),
    emr_core_cluster_size=Ref(emr_core_cluster_size_param),
    emr_core_instance_type=Ref(emr_core_instance_type_param),
    emr_task_instance_type=Ref(emr_task_instance_type_param),
    emr_task_bid_price=Ref(emr_task_bid_price_param),
    auth_token_bucket=Ref(auth_token_bucket_param),
    auth_token_key=Ref(auth_token_key_param),
    status_bucket=Ref(status_bucket_param),
    status_prefix=Ref(status_prefix_param),
    status_sqs_queue_url=Ref(status_sqs_queue_url_param),
    oam_api_token=Ref(oam_api_token_param),
)

# convert to JSON representations
refs = dict([(k, '|||' + json.dumps(v.JSONrepr()) + '|||') for (k, v) in refs.items()])

# interpolate and split into an array
user_data = read_file('cloud-config/oam-server-api.yml').format(**refs).split('|||')

# replace stringified refs with objects
user_data = map(lambda x: json.loads(x) if x.startswith('{"Ref": "') else x, user_data)

instance_profile = t.add_resource(iam.InstanceProfile(
    'InstanceProfile',
    Path='/',
    Roles=[Ref(role_param)]
))

instance = t.add_resource(
    ec2.Instance(
        'WebServerInstance',
        IamInstanceProfile=Ref(instance_profile),
        ImageId=Ref(tiler_ami_param),
        InstanceType='t2.medium',
        KeyName=Ref(keyname_param),
        NetworkInterfaces=[
            ec2.NetworkInterfaceProperty(
                GroupSet=[
                    Ref(instanceSecurityGroup)],
                AssociatePublicIpAddress='true',
                DeviceIndex='0',
                DeleteOnTermination='true',
                SubnetId=Ref(subnet))],
        UserData=Base64(Join('', user_data)),
        CreationPolicy=policies.CreationPolicy(
            ResourceSignal=policies.ResourceSignal(
                Timeout='PT15M')),
        Tags=Tags(
            Application=ref_stack_id),
    ))

#
# Elastic IP
#

ipAddress = t.add_resource(
    ec2.EIP('IPAddress',
        DependsOn='AttachGateway',
        Domain='vpc',
        InstanceId=Ref(instance)
        ))

#
# Outputs
#
t.add_output([
    Output('IPAddress',
           Description='OAM Server API IP',
           Value=GetAtt('WebServerInstance', 'PublicIp'))
])

if __name__ == '__main__':
    template_json = t.to_json()
    file_name = __file__.replace('.py', '.json')

    validate_cloudformation_template(template_json)

    with open(file_name, 'w') as f:
        f.write(template_json)

    print('Template validated and written to %s' % file_name)
