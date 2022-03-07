#!/bin/bash
set -e

# get current AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)

# get current AWS REGION to use from Environment variable
if [[ ! -v AWS_DEFAULT_REGION ]]; then
    echo "AWS_DEFAULT_REGION is not set"
elif [[ -z "$AWS_DEFAULT_REGION" ]]; then
    echo "AWS_DEFAULT_REGION is set to the empty string"
else
    REGION=$AWS_DEFAULT_REGION
fi

sam validate --template-file template.yml 

sam package --template-file template.yml --output-template-file packaged.yaml --force-upload --region ${REGION} --s3-bucket dev

sam deploy --template-file packaged.yaml --stack-name sfn-eks-stack --region ${REGION} --no-fail-on-empty-changeset --force-upload --capabilities CAPABILITY_NAMED_IAM

docker build -t etl-eks  .

docker tag etl-eks ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/etl-eks
aws ecr get-login-password --region ${REGION}| docker login -u AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/etl-eks
docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/etl-eks

python3 ./utils/sfn_eks.py -c ./config.yml -e -i etl-eks

