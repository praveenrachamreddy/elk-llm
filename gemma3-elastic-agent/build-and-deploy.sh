#!/bin/bash

# Build and Deploy Script for OpenShift
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
IMAGE_NAME="gemma3-elastic-agent"
TAG=${TAG:-"latest"}
NAMESPACE=${NAMESPACE:-"praveen-datascience"}
REGISTRY=${REGISTRY:-"image-registry.openshift-image-registry.svc:5000"}

echo -e "${BLUE}🚀 Building and Deploying Gemma3 Elasticsearch MCP Agent to OpenShift${NC}"
echo -e "${BLUE}============================================================${NC}"

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if oc is installed
if ! command -v oc &> /dev/null; then
    print_error "OpenShift CLI (oc) is not installed or not in PATH"
    exit 1
fi

# Check if logged into OpenShift
if ! oc whoami &> /dev/null; then
    print_error "Not logged into OpenShift. Please run 'oc login' first"
    exit 1
fi

print_status "Logged into OpenShift as $(oc whoami)"

# Create namespace if it doesn't exist
if ! oc get namespace "$NAMESPACE" &> /dev/null; then
    print_warning "Namespace $NAMESPACE doesn't exist. Creating it..."
    oc create namespace "$NAMESPACE"
    print_status "Created namespace: $NAMESPACE"
else
    print_status "Using existing namespace: $NAMESPACE"
fi

# Switch to the namespace
oc project "$NAMESPACE"

# Build the image using OpenShift BuildConfig
echo -e "\n${BLUE}🔨 Building Docker image...${NC}"

# Create BuildConfig if it doesn't exist
if ! oc get bc "$IMAGE_NAME" &> /dev/null; then
    cat <<EOF | oc apply -f -
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: $IMAGE_NAME
  namespace: $NAMESPACE
spec:
  output:
    to:
      kind: ImageStreamTag
      name: $IMAGE_NAME:$TAG
  source:
    type: Binary
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: Dockerfile
EOF
    print_status "Created BuildConfig: $IMAGE_NAME"
fi

# Create ImageStream if it doesn't exist
if ! oc get is "$IMAGE_NAME" &> /dev/null; then
    oc create imagestream "$IMAGE_NAME"
    print_status "Created ImageStream: $IMAGE_NAME"
fi

# Start the build
print_status "Starting binary build..."
oc start-build "$IMAGE_NAME" --from-dir=. --follow

print_status "Image built successfully: $REGISTRY/$NAMESPACE/$IMAGE_NAME:$TAG"

# Deploy the application
echo -e "\n${BLUE}🚀 Deploying to OpenShift...${NC}"

# Update the deployment YAML with the correct image
sed -i.bak "s|your-registry/gemma3-elastic-agent:latest|$REGISTRY/$NAMESPACE/$IMAGE_NAME:$TAG|g" openshift-deployment.yaml

# Apply the deployment
if oc apply -f openshift-deployment.yaml; then
    print_status "Deployment applied successfully"
else
    print_error "Failed to apply deployment"
    exit 1
fi

# Wait for deployment to be ready
echo -e "\n${BLUE}⏳ Waiting for deployment to be ready...${NC}"
oc rollout status deployment/gemma3-elastic-agent --timeout=300s

# Get deployment status
echo -e "\n${BLUE}📊 Deployment Status:${NC}"
oc get pods -l app=gemma3-elastic-agent
oc get svc gemma3-elastic-agent-service
oc get route gemma3-elastic-agent-route

# Get the route URL
ROUTE_URL=$(oc get route gemma3-elastic-agent-route -o jsonpath='{.spec.host}' 2>/dev/null || echo "No route found")

echo -e "\n${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "📝 Application Details:"
echo -e "   • Namespace: $NAMESPACE"
echo -e "   • Image: $REGISTRY/$NAMESPACE/$IMAGE_NAME:$TAG"
echo -e "   • Route URL: https://$ROUTE_URL"
echo -e "\n📋 Useful Commands:"
echo -e "   • View logs: ${YELLOW}oc logs -f deployment/gemma3-elastic-agent${NC}"
echo -e "   • Get pods: ${YELLOW}oc get pods -l app=gemma3-elastic-agent${NC}"
echo -e "   • Describe pod: ${YELLOW}oc describe pod <pod-name>${NC}"
echo -e "   • Delete deployment: ${YELLOW}oc delete -f openshift-deployment.yaml${NC}"

# Optional: Show recent logs
echo -e "\n${BLUE}📋 Recent logs:${NC}"
oc logs deployment/gemma3-elastic-agent --tail=20 || true